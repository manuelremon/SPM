from src.backend.app import app as flask_app
from src.backend.db import get_db
from src.backend.security import hash_password

def _seed_user(db, u='alice', pw='secret123'):
    db.execute("INSERT OR REPLACE INTO users(username,password_hash,email,display_name) VALUES(?,?,?,?)",
               (u, hash_password(pw), 'a@x.com', 'Alice'))
    db.commit()

def test_update_profile_and_change_password():
    app = flask_app
    client = app.test_client()
    with app.app_context():
        db = get_db()
        _seed_user(db)
    # login
    rv = client.post('/api/auth/login', json={'username':'alice','password':'secret123'})
    assert rv.status_code == 200
    cookie = rv.headers['Set-Cookie']
    # update profile
    rv = client.put('/api/users/me', headers={'Cookie': cookie}, json={'email':'new@x.com','display_name':'A'})
    assert rv.status_code == 200
    # wrong current
    rv = client.put('/api/auth/password', headers={'Cookie': cookie}, json={'current':'bad','new':'longnewpw'})
    assert rv.status_code == 400
    # ok change
    rv = client.put('/api/auth/password', headers={'Cookie': cookie}, json={'current':'secret123','new':'longnewpw'})
    assert rv.status_code == 200
