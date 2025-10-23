from __future__ import annotations

import jwt
import pytest

from src.backend.config import Settings
from src.backend.jwt_utils import (
    create_access_token,
    create_refresh_token,
    verify_access_token,
)


def test_verify_access_token_ok(app):
    token = create_access_token(subject="user-123", claims={"roles": ["planner"]})
    claims = verify_access_token(token)
    assert claims["sub"] == "user-123"
    assert claims["typ"] == "access"
    assert claims["uid"] == "user-123"
    assert claims["id_spm"] == "user-123"
    assert "exp" in claims


def test_verify_access_token_rejects_refresh_token(app):
    refresh = create_refresh_token(subject="user-123")
    with pytest.raises(jwt.InvalidTokenError):
        verify_access_token(refresh)


def test_verify_access_token_requires_access_type(app):
    raw = jwt.encode({"sub": "user-abc"}, Settings.SECRET_KEY, algorithm="HS256")
    with pytest.raises(jwt.InvalidTokenError):
        verify_access_token(raw)
