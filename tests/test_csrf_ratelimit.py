from http.cookies import SimpleCookie
from src.backend.app import app as flask_app

def _login_and_get_csrf(client):
    r = client.post('/api/login', json={'username':'u','password':'p@ssw0rd!'})
    assert r.status_code == 200, f"Login failed: {r.status_code}"
    # Use dummy csrf for test
    return 'dummy'

def test_csrf_required_on_post(tmp_path):
    # Crea usuario válido antes del test
    from src.backend.db import get_db
    from src.backend.security import hash_password
    pw_hash = hash_password('p@ssw0rd!')
    with flask_app.app_context():
        db = get_db()
        db.execute("INSERT OR IGNORE INTO users (username, password_hash) VALUES (?, ?)", ('u', pw_hash))
        db.commit()
    from werkzeug.datastructures import FileStorage
    import io
    c = flask_app.test_client()
    csrf = _login_and_get_csrf(c)
    # sin header -> 403
    file_data1 = {'file': (io.BytesIO(b'data'), 'x.txt')}
    rv = c.post('/api/files', data=file_data1, content_type='multipart/form-data')
    assert rv.status_code == 403
    # con header y cookie -> 200/201
    file_data2 = {'file': (io.BytesIO(b'data'), 'x.txt')}
    c.set_cookie('spm_csrf_token', csrf)
    rv = c.post('/api/files', data=file_data2,
                headers={'X-CSRF-Token': csrf},
                content_type='multipart/form-data')
    assert rv.status_code in (200,201)

def test_login_rate_limit():
    # Limpia el bucket de rate limit antes del test
    from src.backend import ratelimit
    ratelimit._buckets.clear()
    c = flask_app.test_client()
    # Crea usuario válido antes del test
    from src.backend.db import get_db
    from src.backend.security import hash_password
    pw_hash = hash_password('p@ssw0rd!')
    with flask_app.app_context():
        db = get_db()
        db.execute("INSERT OR IGNORE INTO users (username, password_hash) VALUES (?, ?)", ('u', pw_hash))
        db.commit()
    valid = {'username':'u','password':'p@ssw0rd!'}
    # Prueba hasta 20 intentos para asegurar el límite
    last_status = None
    for i in range(1, 25):
        r = c.post('/api/login', json=valid)
        last_status = r.status_code
        if last_status == 429:
            break
    assert last_status == 429
