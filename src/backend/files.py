from flask import Blueprint, request, jsonify, send_from_directory, current_app
from .ratelimit import limit
import os, uuid
from .jwt_utils import verify_token
from .db import get_db
from .config import Config
UPLOAD_DIR = Config.UPLOAD_DIR
MAX_CONTENT_LENGTH = Config.MAX_CONTENT_LENGTH
ALLOWED_EXTS = Config.ALLOWED_EXTS
ALLOWED_MIMES = Config.ALLOWED_MIMES
from .file_utils import sha256_file, sniff_mime

files_bp = Blueprint('files', __name__, url_prefix='/api/files')

@files_bp.before_app_request
def _limit():
    current_app.config['MAX_CONTENT_LENGTH'] = MAX_CONTENT_LENGTH

def _auth_user():
    token = request.cookies.get('spm_token') or request.cookies.get('access_token')
    payload = verify_token(token) if token else None
    return payload['sub'] if payload else None

@files_bp.post('')
@limit(key='files_post', limit=30, window=60)
def upload():
    from .csrf import verify_csrf
    csrf_result = verify_csrf()
    if csrf_result is not None:
        return csrf_result
    user = _auth_user()
    if not user: return jsonify({'error':'unauthorized'}), 401
    if 'file' not in request.files: return jsonify({'error':'no_file'}), 400
    f = request.files['file']
    if not f.filename: return jsonify({'error':'empty_name'}), 400
    _, ext = os.path.splitext(f.filename.lower())
    if ext not in ALLOWED_EXTS: return jsonify({'error':'ext_not_allowed'}), 400
    tmp_name = f'~{uuid.uuid4().hex}{ext}'
    tmp_path = os.path.join(UPLOAD_DIR, tmp_name)
    f.save(tmp_path)
    mime = sniff_mime(tmp_path, f.filename)
    if mime not in ALLOWED_MIMES:
        os.remove(tmp_path)
        return jsonify({'error':'mime_not_allowed', 'mime': mime}), 400
    size = os.path.getsize(tmp_path)
    if size > MAX_CONTENT_LENGTH:
        os.remove(tmp_path)
        return jsonify({'error':'too_large'}), 413
    with open(tmp_path, 'rb') as fp:
        digest = sha256_file(fp)
    stored = f'{uuid.uuid4().hex}{ext}'
    final_path = os.path.join(UPLOAD_DIR, stored)
    os.replace(tmp_path, final_path)
    db = get_db()
    # evita duplicados por usuario
    row = db.execute('SELECT id FROM uploads WHERE sha256=? AND owner=?', (digest, user)).fetchone()
    if row:
        os.remove(final_path)
        return jsonify({'duplicate_of': row['id']}), 200
    cur = db.execute(
        'INSERT INTO uploads(owner, original_name, stored_name, size, mime, sha256) VALUES(?,?,?,?,?,?)',
        (user, f.filename, stored, size, mime, digest)
    )
    db.commit()
    return jsonify({'id': cur.lastrowid, 'name': f.filename, 'size': size, 'mime': mime}), 201

from .paging import parse_paging_args

@files_bp.get('')
def list_my_files():
    user = _auth_user()
    if not user: return jsonify({'error':'unauthorized'}), 401
    page, per_page, q, sort, order = parse_paging_args(
        request.args, allowed_sort={'created_at','original_name','size','mime'}
    )
    db = get_db()
    params = [user]
    where = 'WHERE owner=?'
    if q:
        where += ' AND (original_name LIKE ? OR mime LIKE ?)'
        like = f'%{q}%'
        params += [like, like]
    total = db.execute(f'SELECT count(*) AS c FROM uploads {where}', params).fetchone()['c']
    sort_sql = f' ORDER BY {sort} {order}'
    limit_sql = ' LIMIT ? OFFSET ?'
    params_page = params + [per_page, (page-1)*per_page]
    rows = db.execute(
        f'SELECT id, original_name, size, mime, created_at FROM uploads {where}{sort_sql}{limit_sql}',
        params_page
    ).fetchall()
    return jsonify({
        'items':[dict(r) for r in rows],
        'meta':{
            'page':page,'per_page':per_page,'total':total,
            'pages': (total + per_page - 1)//per_page,
            'sort':sort,'order':order,'q':q
        }
    })

@files_bp.get('/<int:file_id>')
def download(file_id: int):
    user = _auth_user()
    if not user: return jsonify({'error':'unauthorized'}), 401
    db = get_db()
    r = db.execute('SELECT original_name, stored_name, owner FROM uploads WHERE id=?', (file_id,)).fetchone()
    if not r: return jsonify({'error':'not_found'}), 404
    if r['owner'] != user: return jsonify({'error':'forbidden'}), 403
    return send_from_directory(UPLOAD_DIR, r['stored_name'], as_attachment=True, download_name=r['original_name'])

@files_bp.delete('/<int:file_id>')
@limit(key='files_del', limit=30, window=60)
def delete(file_id: int):
    user = _auth_user()
    if not user: return jsonify({'error':'unauthorized'}), 401
    db = get_db()
    r = db.execute('SELECT stored_name, owner FROM uploads WHERE id=?', (file_id,)).fetchone()
    if not r: return jsonify({'error':'not_found'}), 404
    if r['owner'] != user: return jsonify({'error':'forbidden'}), 403
    try:
        os.remove(os.path.join(UPLOAD_DIR, r['stored_name']))
    except FileNotFoundError:
        pass
    db.execute('DELETE FROM uploads WHERE id=?', (file_id,))
    db.commit()
    return jsonify({'ok': True})
