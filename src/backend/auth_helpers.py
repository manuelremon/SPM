from __future__ import annotations

from typing import Optional

from flask import Request

TOKEN_COOKIE_NAME = "access_token"


def extract_bearer_token(req: Request) -> Optional[str]:
    """Return the bearer token from Authorization header or access_token cookie."""
    if req is None:
        return None

    auth_header = (req.headers.get("Authorization") or "").strip()
    if auth_header.lower().startswith("bearer "):
        token = auth_header.split(" ", 1)[1].strip()
        if token:
            return token

    cookie_token = (req.cookies.get(TOKEN_COOKIE_NAME) or "").strip()
    if cookie_token:
        return cookie_token

    return None
