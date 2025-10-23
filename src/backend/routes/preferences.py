from __future__ import annotations

import json
from typing import Any, Dict

from flask import Blueprint, current_app, jsonify, request

from ..auth import auth_required, get_current_user_id
from ..db import get_connection

bp = Blueprint("preferences", __name__, url_prefix="/api")

PREFERENCE_DEFAULTS: Dict[str, Any] = {
    "emailAlerts": True,
    "realtimeToasts": True,
    "approvalDigest": False,
    "digestHour": "08:30",
    "theme": "auto",
    "density": "comfortable",
    "rememberFilters": True,
    "keyboardShortcuts": False,
    "effectsEnabled": True,
}

ALLOWED_THEMES = {"auto", "light", "dark"}
ALLOWED_DENSITY = {"comfortable", "compact", "extended"}


def _ensure_table(con) -> None:
    con.execute(
        """
        CREATE TABLE IF NOT EXISTS user_preferences (
            user_id TEXT NOT NULL,
            key TEXT NOT NULL,
            value TEXT NOT NULL,
            PRIMARY KEY(user_id, key)
        )
        """
    )


def _load_preferences(user_id: str) -> Dict[str, Any]:
    with get_connection() as con:
        _ensure_table(con)
        rows = con.execute(
            "SELECT key, value FROM user_preferences WHERE user_id = ?",
            (user_id,),
        ).fetchall()
    prefs = dict(PREFERENCE_DEFAULTS)
    for row in rows:
        key = row.get("key")
        value = row.get("value")
        if not key:
            continue
        try:
            prefs[key] = json.loads(value)
        except Exception:
            prefs[key] = value
    return prefs


def _validate_payload(payload: Dict[str, Any]) -> Dict[str, Any]:
    cleaned: Dict[str, Any] = {}
    for key, value in payload.items():
        if key not in PREFERENCE_DEFAULTS:
            continue
        if key in {"emailAlerts", "realtimeToasts", "approvalDigest", "rememberFilters", "keyboardShortcuts", "effectsEnabled"}:
            cleaned[key] = bool(value)
        elif key == "digestHour":
            if not isinstance(value, str) or len(value.strip()) != 5:
                raise ValueError("digestHour debe tener formato HH:MM")
            cleaned[key] = value.strip()
        elif key == "theme":
            if value not in ALLOWED_THEMES:
                raise ValueError("theme inválido")
            cleaned[key] = value
        elif key == "density":
            if value not in ALLOWED_DENSITY:
                raise ValueError("density inválida")
            cleaned[key] = value
        else:
            cleaned[key] = value
    return cleaned


@bp.get("/preferencias")
@auth_required
def get_preferences():
    user_id = get_current_user_id()
    if not user_id:
        return jsonify(error="unauthorized"), 401
    prefs = _load_preferences(user_id)
    return jsonify(prefs)


@bp.patch("/preferencias")
@auth_required
def patch_preferences():
    user_id = get_current_user_id()
    if not user_id:
        return jsonify(error="unauthorized"), 401
    payload = request.get_json(silent=True) or {}
    if not isinstance(payload, dict):
        return jsonify(error="invalid_payload"), 400
    try:
        validated = _validate_payload(payload)
    except ValueError as exc:
        return jsonify(error=str(exc)), 400
    if not validated:
        return jsonify(ok=True, updated=[]), 200
    with get_connection() as con:
        _ensure_table(con)
        for key, value in validated.items():
            con.execute(
                """
                INSERT INTO user_preferences (user_id, key, value)
                VALUES (?, ?, ?)
                ON CONFLICT(user_id, key)
                DO UPDATE SET value = excluded.value
                """,
                (user_id, key, json.dumps(value, ensure_ascii=False)),
            )
        con.commit()
    current_app.logger.info("Updated preferences for %s: %s", user_id, ", ".join(validated.keys()))
    return jsonify(ok=True, updated=list(validated.keys()))
