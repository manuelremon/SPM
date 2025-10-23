from __future__ import annotations
import base64
import binascii
import os
import hmac
from hashlib import pbkdf2_hmac
from typing import Any, Dict, Tuple

from .jwt_utils import (
    create_access_token as _create_access_token,
    create_refresh_token as _create_refresh_token,
    verify_access_token as _verify_access_token,
    verify_refresh_token as _verify_refresh_token,
)

_ITER = 390_000
_SALT = 16

def hash_password(pw: str) -> str:
    pw = (pw or "").strip()
    salt = os.urandom(_SALT)
    dig = pbkdf2_hmac("sha256", pw.encode("utf-8"), salt, _ITER)
    return base64.b64encode(salt + dig).decode("ascii")

def verify_password(stored: str, candidate: str) -> Tuple[bool, bool]:
    """Return tuple(valid, needs_rehash).

    When stored is legacy plain-text and matches, needs_rehash=True.
    """
    stored = (stored or "").strip()
    candidate = (candidate or "").strip()
    if not stored or not candidate:
        return False, False
    try:
        raw = base64.b64decode(stored.encode("ascii"), validate=True)
        salt, dig = raw[:_SALT], raw[_SALT:]
        cand = pbkdf2_hmac("sha256", candidate.encode("utf-8"), salt, _ITER)
        return hmac.compare_digest(dig, cand), False
    except (binascii.Error, ValueError):
        match = stored == candidate
        return match, match

def create_access_token(sub: str, *, ttl: int | None = None, claims: Dict[str, Any] | None = None) -> str:
    return _create_access_token(subject=sub, ttl=ttl, claims=claims)


def create_refresh_token(sub: str, *, ttl: int | None = None, claims: Dict[str, Any] | None = None) -> str:
    return _create_refresh_token(subject=sub, ttl=ttl, claims=claims)


def verify_access_token(token: str) -> Dict[str, Any]:
    return _verify_access_token(token)


def verify_refresh_token(token: str) -> Dict[str, Any]:
    return _verify_refresh_token(token)


