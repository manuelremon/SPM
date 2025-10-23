from __future__ import annotations

import time
from typing import Any, Dict, Optional

import jwt

from .config import Settings

_ALGORITHM = "HS256"


def _prepare_claims(claims: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    base: Dict[str, Any] = {}
    if claims:
        base.update({key: value for key, value in claims.items() if value is not None})
    return base


def _encode(payload: Dict[str, Any]) -> str:
    if not Settings.SECRET_KEY:
        raise RuntimeError("SECRET_KEY must be configured before issuing tokens")
    return jwt.encode(payload, Settings.SECRET_KEY, algorithm=_ALGORITHM)


def create_access_token(
    *,
    subject: str,
    ttl: Optional[int] = None,
    claims: Optional[Dict[str, Any]] = None,
) -> str:
    if not subject or not isinstance(subject, str):
        raise ValueError("subject must be a non-empty string")

    now = int(time.time())
    ttl = int(ttl or Settings.ACCESS_TOKEN_TTL)

    payload: Dict[str, Any] = {
        "sub": subject,
        "iat": now,
        "exp": now + ttl,
        "iss": "spm",
        "typ": "access",
    }
    payload.update(_prepare_claims(claims))

    payload.setdefault("uid", subject)
    payload.setdefault("id_spm", subject)

    return _encode(payload)


def create_refresh_token(
    *,
    subject: str,
    ttl: Optional[int] = None,
    claims: Optional[Dict[str, Any]] = None,
) -> str:
    if not subject or not isinstance(subject, str):
        raise ValueError("subject must be a non-empty string")

    now = int(time.time())
    ttl = int(ttl or getattr(Settings, "REFRESH_TOKEN_TTL", Settings.ACCESS_TOKEN_TTL * 24))

    payload: Dict[str, Any] = {
        "sub": subject,
        "iat": now,
        "exp": now + ttl,
        "iss": "spm",
        "typ": "refresh",
    }
    payload.update(_prepare_claims(claims))
    payload.setdefault("uid", subject)
    payload.setdefault("id_spm", subject)

    return _encode(payload)


def create_token(payload: dict) -> str:
    return create_access_token(subject=payload.get('sub'), claims=payload)


def _decode_and_validate(token: str) -> Dict[str, Any]:
    if not isinstance(token, str) or not token.strip():
        raise jwt.InvalidTokenError("Token must be a non-empty string")
    return jwt.decode(token, Settings.SECRET_KEY, algorithms=[_ALGORITHM])


def verify_access_token(token: str) -> Dict[str, Any]:
    data = _decode_and_validate(token)
    token_type = data.get("typ")
    if token_type != "access":
        raise jwt.InvalidTokenError("Invalid token type")
    subject = data.get("sub")
    if not subject or not isinstance(subject, str):
        raise jwt.InvalidTokenError("Token missing subject")
    return data


def verify_refresh_token(token: str) -> Dict[str, Any]:
    data = _decode_and_validate(token)
    token_type = data.get("typ")
    if token_type != "refresh":
        raise jwt.InvalidTokenError("Invalid token type")
    subject = data.get("sub")
    if not subject or not isinstance(subject, str):
        raise jwt.InvalidTokenError("Token missing subject")
    return data


def verify_token(token: str) -> dict:
    return verify_access_token(token)
