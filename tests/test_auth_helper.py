from __future__ import annotations

from flask import request

from src.backend.auth_helpers import TOKEN_COOKIE_NAME, extract_bearer_token


def test_extract_bearer_token_from_header(app):
    with app.test_request_context(headers={"Authorization": "Bearer test-header"}):
        assert extract_bearer_token(request) == "test-header"


def test_extract_bearer_token_from_cookie(app):
    cookie_env = {"HTTP_COOKIE": f"{TOKEN_COOKIE_NAME}=cookie-token"}
    with app.test_request_context(environ_overrides=cookie_env):
        assert extract_bearer_token(request) == "cookie-token"


def test_extract_bearer_token_missing(app):
    with app.test_request_context():
        assert extract_bearer_token(request) is None
