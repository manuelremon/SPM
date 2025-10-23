from src.backend.app import app as flask_app

def _login(client, username='admin'):
    rv = client.post('/api/auth/login', json={'username': username, 'password':'x'})
    assert rv.status_code == 200
    return rv.headers['Set-Cookie']

def test_forbidden_when_missing_role():
    client = flask_app.test_client()
    cookie = _login(client, username='user')  # solo 'user'
    rv = client.get('/api/export/solicitudes', headers={'Cookie': cookie})
    assert rv.status_code == 403

def test_allowed_for_admin():
    client = flask_app.test_client()
    cookie = _login(client, username='admin')  # 'admin'
    rv = client.get('/api/export/solicitudes', headers={'Cookie': cookie})
    assert rv.status_code == 200
