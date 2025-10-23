from __future__ import annotations

from functools import wraps
from flask import request, jsonify
from typing import Any, Callable, TypeVar

from flask import jsonify

F = TypeVar("F", bound=Callable[..., Any])


def require_auth(fn: F) -> F:
    """Flask view decorator that ensures the request has a valid access token."""

    @wraps(fn)
    def wrapper(*args: Any, **kwargs: Any):
        from flask import g

        # Import locally to avoid circular imports on module load
        from .auth import authenticate_request

        if not authenticate_request():
            return jsonify(error="unauthorized"), 401
        if getattr(g, "user", None) is None:
            return jsonify(error="unauthorized"), 401
        return fn(*args, **kwargs)

    return wrapper  # type: ignore[return-value]


def require_roles(*allowed):
    def deco(fn):
        @wraps(fn)
        def wrapper(*args, **kwargs):
            token = request.cookies.get('spm_token')
            if not token:
                return jsonify({'error':'unauthorized'}), 401
            payload = verify_token(token)
            if not payload:
                return jsonify({'error':'unauthorized'}), 401
            roles = payload.get('roles', [])
            if allowed and not any(r in roles for r in allowed):
                return jsonify({'error':'forbidden', 'need_any_of': allowed}), 403
            request.user = {'username': payload.get('sub'), 'roles': roles}
            return fn(*args, **kwargs)
        return wrapper
    return deco
