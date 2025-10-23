from io import BytesIO
from src.backend.app import app as flask_app
from src.backend.db import get_db
from src.backend.security import hash_password

def _login(client):
    rv = client.post('/api/auth/login', json={'username':'u','password':'p@ssw0rd!'})
    assert rv.status_code == 200
    return rv.headers['Set-Cookie']

def _seed_user():
    with flask_app.app_context():
        db = get_db()
        db.execute("INSERT OR REPLACE INTO users(username,password_hash) VALUES(?,?)",
                   ('u', hash_password('p@ssw0rd!')))
        db.commit()

def test_upload_list_download_delete(tmp_path, monkeypatch):
    _seed_user()
    client = flask_app.test_client()
    cookie = _login(client)
    data = {
        'file': (BytesIO(b'hello world'), 'note.txt')
    }
    rv = client.post('/api/files', headers={'Cookie': cookie}, data=data,
                     content_type='multipart/form-data')
    assert rv.status_code in (200,201)
    file_id = (rv.get_json().get('id')
               or rv.get_json().get('duplicate_of'))
    # list
    rv = client.get('/api/files', headers={'Cookie': cookie})
    assert rv.status_code == 200
    # download
    rv = client.get(f'/api/files/{file_id}', headers={'Cookie': cookie})
    assert rv.status_code == 200
    # delete
    rv = client.delete(f'/api/files/{file_id}', headers={'Cookie': cookie})
    assert rv.status_code == 200
