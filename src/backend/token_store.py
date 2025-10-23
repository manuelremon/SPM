from __future__ import annotations

import time
from typing import Any, Dict, Optional, Tuple

from .config import Settings
from .db import get_connection


def init_refresh_token_store() -> None:
    """Ensure the refresh token persistence schema exists."""
    with get_connection() as con:
        con.execute(
            """
            CREATE TABLE IF NOT EXISTS refresh_tokens (
                jti TEXT PRIMARY KEY,
                user_id TEXT NOT NULL,
                issued_at INTEGER NOT NULL,
                expires_at INTEGER NOT NULL,
                rotated_at INTEGER,
                revoked_at INTEGER,
                revoke_reason TEXT,
                parent_jti TEXT,
                user_agent TEXT,
                ip TEXT
            )
            """
        )
        con.execute(
            """
            CREATE INDEX IF NOT EXISTS idx_refresh_tokens_user
            ON refresh_tokens(user_id)
            """
        )
        con.commit()


def prune_expired_tokens() -> None:
    """Remove refresh tokens that are past the grace window to keep the table compact."""
    boundary = int(time.time()) - Settings.REFRESH_GRACE_PERIOD
    with get_connection() as con:
        con.execute(
            "DELETE FROM refresh_tokens WHERE expires_at < ?", (boundary,)
        )
        con.commit()


def register_refresh_token(
    *,
    jti: str,
    user_id: str,
    expires_at: int,
    parent_jti: Optional[str],
    user_agent: Optional[str],
    ip: Optional[str],
) -> None:
    prune_expired_tokens()
    now = int(time.time())
    with get_connection() as con:
        con.execute(
            """
            INSERT INTO refresh_tokens (jti, user_id, issued_at, expires_at, parent_jti, user_agent, ip)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (jti, user_id, now, expires_at, parent_jti, user_agent, ip),
        )
        con.commit()


def revoke_token(jti: str, *, reason: str = "revoked") -> None:
    now = int(time.time())
    with get_connection() as con:
        con.execute(
            """
            UPDATE refresh_tokens
               SET revoked_at = ?,
                   revoke_reason = COALESCE(revoke_reason, ?)
             WHERE jti = ?
            """,
            (now, reason, jti),
        )
        con.commit()


def mark_rotated(jti: str) -> None:
    now = int(time.time())
    with get_connection() as con:
        con.execute(
            """
            UPDATE refresh_tokens
               SET rotated_at = ?,
                   revoked_at = COALESCE(revoked_at, ?),
                   revoke_reason = COALESCE(revoke_reason, 'rotated')
             WHERE jti = ?
            """,
            (now, now, jti),
        )
        con.commit()


def revoke_family(user_id: str, *, reason: str = "reused_token") -> None:
    now = int(time.time())
    with get_connection() as con:
        con.execute(
            """
            UPDATE refresh_tokens
               SET revoked_at = ?,
                   revoke_reason = ?
             WHERE user_id = ?
            """,
            (now, reason, user_id),
        )
        con.commit()


def get_refresh_token(jti: str) -> Optional[Dict[str, Any]]:
    with get_connection() as con:
        row = con.execute(
            "SELECT * FROM refresh_tokens WHERE jti = ?", (jti,)
        ).fetchone()
    return dict(row) if row else None


def is_active_token(jti: str) -> Tuple[bool, Optional[Dict[str, Any]]]:
    token = get_refresh_token(jti)
    if not token:
        return False, None

    now = int(time.time())
    expires_at = int(token["expires_at"])
    if token.get("revoked_at"):
        return False, token
    if expires_at + Settings.REFRESH_GRACE_PERIOD < now:
        return False, token
    return True, token
