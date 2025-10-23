from src.backend.app import app as flask_app

def test_me_requires_cookie():
    client = flask_app.test_client()
    rv = client.get('/api/auth/me')
    assert rv.status_code == 401

def test_login_me_logout_cycle():
    client = flask_app.test_client()
    rv = client.post('/api/auth/login', json={'username':'u','password':'p'})
    assert rv.status_code == 200
    cookie = rv.headers.get('Set-Cookie')
    rv2 = client.get('/api/auth/me', headers={'Cookie': cookie})
    assert rv2.status_code == 200
    rv3 = client.post('/api/auth/logout', headers={'Cookie': cookie})
    assert rv3.status_code == 200
    rv4 = client.get('/api/auth/me', headers={'Cookie': cookie})
    assert rv4.status_code == 401
