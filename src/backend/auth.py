from __future__ import annotations

import time
from typing import Any, Dict, Optional, Tuple

import jwt
from flask import Response, current_app, g, jsonify, request, Blueprint, make_response
import secrets, json
from datetime import timedelta, datetime, timezone
from .csrf import issue_csrf
from .ratelimit import limit
import hmac, hashlib, base64, json

from .auth_helpers import TOKEN_COOKIE_NAME, extract_bearer_token
from .config import Settings
from .decorators import require_auth
from .db import get_connection, get_user_by_username, get_db
from .jwt_utils import create_access_token, verify_access_token, create_token, verify_token
from .security import hash_password, verify_password

auth_bp = Blueprint("auth", __name__)

auth_required = require_auth


def now() -> int:
    return int(time.time())


def _token_ttl() -> int:
    return int(current_app.config.get("TOKEN_TTL", current_app.config.get("ACCESS_TOKEN_TTL", 86_400)))


def _cookie_args(ttl: Optional[int] = None, *, clearing: bool = False) -> Dict[str, Any]:
    configured = dict(current_app.config.get("COOKIE_ARGS", {}))
    if not configured:
        configured = dict(Settings.COOKIE_ARGS)
    args: Dict[str, Any] = {
        "httponly": configured.get("httponly", True),
        "samesite": configured.get("samesite", "Strict"),
        "secure": bool(configured.get("secure", False)),
        "path": configured.get("path", "/"),
    }
    if clearing:
        args["expires"] = 0
        args["max_age"] = 0
    elif ttl is not None:
        args["max_age"] = int(ttl)
    return args


def issue_token(user_id: str, *, extra: Optional[Dict[str, Any]] = None, ttl: Optional[int] = None) -> str:
    claims: Dict[str, Any] = {"uid": user_id, "id_spm": user_id}
    if extra:
        claims.update(extra)
        if "rol" in extra and "roles" not in claims and extra.get("rol"):
            claims["roles"] = [extra["rol"]]
    ttl = ttl or _token_ttl()
    return create_access_token(subject=user_id, ttl=int(ttl), claims=claims)


def decode_token(token: str) -> Dict[str, Any]:
    return verify_access_token(token)


def set_auth_cookie(response: Response, token: str, *, ttl: Optional[int] = None) -> Response:
    ttl = ttl or _token_ttl()
    response.set_cookie(TOKEN_COOKIE_NAME, token, **_cookie_args(ttl))
    return response


def clear_auth_cookie(response: Response) -> Response:
    response.set_cookie(TOKEN_COOKIE_NAME, "", **_cookie_args(clearing=True))
    return response


def _normalize_centros(raw: Any) -> list[str]:
    if isinstance(raw, str) and raw.strip():
        return [part.strip() for part in raw.replace(";", ",").split(",") if part.strip()]
    if isinstance(raw, (list, tuple)):
        return [str(part).strip() for part in raw if str(part).strip()]
    return []


def _serialize_user_row(row: Dict[str, Any]) -> Dict[str, Any]:
    user_id = row.get("id_spm")
    payload: Dict[str, Any] = {
        "id": user_id,
        "id_spm": user_id,
        "username": user_id,
        "nombre": row.get("nombre"),
        "apellido": row.get("apellido"),
        "rol": row.get("rol"),
        "posicion": row.get("posicion"),
        "sector": row.get("sector"),
        "mail": row.get("mail"),
        "telefono": row.get("telefono"),
        "id_red": row.get("id_ypf"),
        "id_ypf": row.get("id_ypf"),
        "jefe": row.get("jefe"),
        "gerente1": row.get("gerente1"),
        "gerente2": row.get("gerente2"),
        "centros": _normalize_centros(row.get("centros")),
    }
    return payload


def load_user_by_id(user_id: Optional[str]) -> Optional[Dict[str, Any]]:
    if not user_id:
        return None
    with get_connection() as con:
        row = con.execute(
            """
            SELECT id_spm, nombre, apellido, rol, sector, centros, posicion,
                   mail, telefono, id_ypf, jefe, gerente1, gerente2
              FROM usuarios
             WHERE id_spm = ?
             LIMIT 1
            """,
            (user_id,),
        ).fetchone()
    if not row:
        return None
    return _serialize_user_row(dict(row))


def authenticate_user(username: str, password: str) -> Optional[Dict[str, Any]]:
    if not username or not password:
        return None
    with get_connection() as con:
        row = con.execute(
            """
            SELECT id_spm, nombre, apellido, rol, contrasena, sector, centros, posicion,
                   mail, telefono, id_ypf, jefe, gerente1, gerente2
              FROM usuarios
             WHERE id_spm = ? COLLATE NOCASE
                OR mail = ? COLLATE NOCASE
                OR nombre = ? COLLATE NOCASE
             LIMIT 1
            """,
            (username, username, username),
        ).fetchone()
        if not row:
            return None
        valid, needs_rehash = verify_password(row["contrasena"], password)
        if not valid:
            return None
        if needs_rehash:
            new_hash = hash_password(password)
            con.execute("UPDATE usuarios SET contrasena = ? WHERE id_spm = ?", (new_hash, row["id_spm"]))
            con.commit()
    return _serialize_user_row(dict(row))


def _token_from_request() -> Optional[str]:
    return extract_bearer_token(request)


def _clear_auth_context() -> None:
    setattr(g, "user", None)  # type: ignore[attr-defined]
    setattr(g, "user_id", None)  # type: ignore[attr-defined]
    setattr(g, "user_claims", None)  # type: ignore[attr-defined]


def _set_auth_context(user: Dict[str, Any], claims: Dict[str, Any]) -> None:
    setattr(g, "user", user)  # type: ignore[attr-defined]
    setattr(g, "user_id", user.get("id") or user.get("id_spm") or claims.get("sub"))  # type: ignore[attr-defined]
    setattr(g, "user_claims", claims)  # type: ignore[attr-defined]


def authenticate_request() -> bool:
    if getattr(g, "_auth_evaluated", False):
        return bool(getattr(g, "user", None))

    token = _token_from_request()
    if not token:
        _clear_auth_context()
        setattr(g, "_auth_evaluated", True)  # type: ignore[attr-defined]
        return False

    try:
        claims = verify_access_token(token)
    except jwt.InvalidTokenError as exc:
        current_app.logger.warning("Invalid access token: %s", exc)
        _clear_auth_context()
        setattr(g, "_auth_evaluated", True)  # type: ignore[attr-defined]
        return False
    except Exception as exc:  # pragma: no cover - defensive
        current_app.logger.exception("Unexpected auth error: %s", exc)
        _clear_auth_context()
        setattr(g, "_auth_evaluated", True)  # type: ignore[attr-defined]
        return False

    user = load_user_by_id(claims.get("sub"))
    if not user:
        current_app.logger.warning("Authenticated token subject not found: %s", claims.get("sub"))
        _clear_auth_context()
        setattr(g, "_auth_evaluated", True)  # type: ignore[attr-defined]
        return False

    _set_auth_context(user, claims)
    setattr(g, "_auth_evaluated", True)  # type: ignore[attr-defined]
    return True


def get_current_user() -> Optional[Dict[str, Any]]:
    user = getattr(g, "user", None)
    if user is not None:
        return user
    if authenticate_request():
        return getattr(g, "user", None)
    return None


def get_current_user_id() -> Optional[str]:
    user = get_current_user()
    if not user:
        return None
    return user.get("id") or user.get("id_spm")


def _sign(payload: dict) -> str:
    """JWT-like HS256 minimalista para sesión de desarrollo."""
    key = current_app.config["SECRET_KEY"].encode()
    header = base64.urlsafe_b64encode(json.dumps({"alg":"HS256","typ":"JWT"}).encode()).rstrip(b"=")
    body = base64.urlsafe_b64encode(json.dumps(payload).encode()).rstrip(b"=")
    sig = hmac.new(key, header+b"."+body, hashlib.sha256).digest()
    sigb64 = base64.urlsafe_b64encode(sig).rstrip(b"=")
    return b".".join([header, body, sigb64]).decode()


def _verify(token: str) -> dict | None:
    try:
        key = current_app.config["SECRET_KEY"].encode()
        h,b,s = token.split(".")
        sig = hmac.new(key, f"{h}.{b}".encode(), hashlib.sha256).digest()
        if base64.urlsafe_b64encode(sig).rstrip(b"=") != s.encode(): return None
        body = json.loads(base64.urlsafe_b64decode(b + "=="))
        if body.get("exp") and datetime.now(timezone.utc).timestamp() > body["exp"]:
            return None
        return body
    except Exception:
        return None


def _set_cookie(resp, token: str):
    cfg = current_app.config
    resp.set_cookie(
        cfg["COOKIE_NAME"], token,
        httponly=True,
        secure=cfg["COOKIE_SECURE"],
        samesite=cfg["COOKIE_SAMESITE"],
        max_age=3600,  # 1h
        path="/"
    )


@auth_bp.post("/login")
@limit(key='auth_login', limit=1, window=60)
def login():
    data = request.get_json(silent=True) or {}
    username = (data.get("username") or "").strip()
    password = data.get("password") or ""
    if not username or not password:
        return jsonify({"error":"missing_credentials"}), 400
    user = get_user_by_username(username)
    if not user or not user.check_password(password):
        return jsonify({"error":"invalid_credentials"}), 401
    token = create_access_token(subject=str(user.id), claims={"u": user.username})
    csrf_token = secrets.token_urlsafe(32)
    resp = make_response(jsonify({"ok": True}), 200)
    # access_token cookie
    from werkzeug.http import dump_cookie
    access_header = dump_cookie(
        key=current_app.config.get("COOKIE_NAME", "access_token"),
        value=token,
        httponly=True,
        secure=False,
        samesite="Lax",
        path="/",
        max_age=3600
    )
    csrf_header = f"spm_csrf_token={csrf_token}; Path=/; SameSite=Lax"
    resp.headers.add("Set-Cookie", access_header)
    resp.headers.add("Set-Cookie", csrf_header)
    return resp


@auth_bp.get("/me")
def me():
    token = request.cookies.get(current_app.config["COOKIE_NAME"])
    payload = verify_token(token) if token else None
    if not payload:
        return jsonify({"authenticated": False}), 401
    return jsonify({"authenticated": True, "user": {"id": payload["sub"], "username": payload["u"], "roles": payload.get("roles", [])}})


@auth_bp.post("/logout")
def logout():
    resp = make_response(jsonify({"ok": True}))
    # Invalida cookie
    resp.set_cookie(current_app.config["COOKIE_NAME"], "", max_age=0, path="/")
    return resp, 200


@auth_bp.put('/password')
def change_password():
    token = request.cookies.get('spm_token')
    payload = verify_token(token) if token else None
    if not payload:
        return jsonify({'error':'unauthorized'}), 401
    data = request.get_json() or {}
    current = data.get('current','')
    new = data.get('new','')
    if len(new) < 8:
        return jsonify({'error':'weak_password', 'min_len':8}), 400
    db = get_db()
    row = db.execute('SELECT password_hash FROM users WHERE username=?', (payload['sub'],)).fetchone()
    if not row or not verify_password(current, row['password_hash']):
        return jsonify({'error':'invalid_current_password'}), 400
    db.execute('UPDATE users SET password_hash=? WHERE username=?', (hash_password(new), payload['sub']))
    db.commit()
    return jsonify({'ok': True}), 200

