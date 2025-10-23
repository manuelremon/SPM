import secrets
from flask import request, jsonify

CSRF_COOKIE = 'spm_csrf_token'
CSRF_HEADER = 'X-CSRF-Token'

def issue_csrf(resp):
    from flask import make_response
    token = secrets.token_urlsafe(32)
    # Si resp no es Response, lo convierte
    if not hasattr(resp, 'set_cookie'):
        resp = make_response(resp)
    resp.set_cookie(
        CSRF_COOKIE, token,
        httponly=False, samesite='Lax', secure=False, path='/'
    )
    return resp

def verify_csrf():
    if request.method in ('GET','HEAD','OPTIONS'):
        return None
    h = request.headers.get(CSRF_HEADER)
    c = request.cookies.get(CSRF_COOKIE)
    if not h or not c or h != c:
        return jsonify({'error':'csrf_failed'}), 403
    return None

def csrf_required(f):
    from functools import wraps
    @wraps(f)
    def wrapper(*args, **kwargs):
        error = verify_csrf()
        if error:
            return error
        return f(*args, **kwargs)
    return wrapper
