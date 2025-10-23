from io import BytesIO
from src.backend.app import app as flask_app
from src.backend.db import get_db
from src.backend.security import hash_password

def _login(client):
    rv = client.post('/api/login', json={'username':'u','password':'p@ssw0rd!'})
    assert rv.status_code == 200
    return rv.headers['Set-Cookie']

def _seed_user():
    with flask_app.app_context():
        db = get_db()
        db.execute("""
            INSERT OR REPLACE INTO usuarios (
                id_spm, nombre, apellido, rol, contrasena, sector, centros, posicion,
                mail, telefono, id_ypf, jefe, gerente1, gerente2
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            'u', 'Test', 'User', 'user', hash_password('p@ssw0rd!'), '', '', '',
            'test@example.com', '', '', '', '', ''
        ))
        db.commit()

def test_paging_and_search(tmp_path):
    _seed_user()
    c = flask_app.test_client()
    cookie = _login(c)
    # crear 25 archivos
    for i in range(25):
        data = {'file': (BytesIO(f'file-{i}'.encode()), f'note_{i:02}.txt')}
        rv = c.post('/api/files', headers={'Cookie': cookie}, data=data,
                    content_type='multipart/form-data')
        assert rv.status_code in (200,201)
    # page 1, 10 por página
    rv = c.get('/api/files?per_page=10&page=1', headers={'Cookie': cookie})
    j = rv.get_json()
    assert rv.status_code == 200
    assert j['meta']['total'] >= 25
    assert len(j['items']) == 10
    # búsqueda por nombre
    rv = c.get('/api/files?q=note_05', headers={'Cookie': cookie})
    j = rv.get_json()
    assert any('note_05' in it['original_name'] for it in j['items'])
    # orden ascendente por nombre
    rv = c.get('/api/files?sort=original_name&order=asc&per_page=5', headers={'Cookie': cookie})
    j = rv.get_json()
    names = [it['original_name'] for it in j['items']]
    assert names == sorted(names)
