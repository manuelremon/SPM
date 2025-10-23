from __future__ import annotations
import json
from typing import List, Dict
from urllib.parse import urljoin
import requests
from flask import Blueprint, request
from ..config import Settings
from ..auth import authenticate_request, get_current_user_id

bp = Blueprint("chatbot", __name__, url_prefix="/api")
_ALLOWED_ROLES = {"user", "assistant", "system"}
_SYSTEM_PROMPT = (
    "Actuás como especialista de SPM, enfocado en la aplicacion web y los flujos de "
    "solicitudes de materiales industriales para Oil & Gas. Guiá al usuario sobre el uso "
    "del sitio, procesos de catalogo y buenas practicas con materiales criticos. "
    "Responde siempre en español y mantente dentro del dominio Oil & Gas y la aplicacion."
)


def _require_user() -> str | None:
    uid = get_current_user_id()
    if uid:
        return uid
    authenticate_request()
    uid = get_current_user_id()
    return uid


def _sanitize_history(raw: List[Dict[str, str]]) -> List[Dict[str, str]]:
    safe_messages: List[Dict[str, str]] = []
    for item in raw[-10:]:
        role = str(item.get("role", "")).lower()
        content = str(item.get("content", "")).strip()
        if not content or role not in _ALLOWED_ROLES:
            continue
        safe_messages.append({"role": role, "content": content})
    has_system = any(msg["role"] == "system" for msg in safe_messages)
    if not has_system:
        safe_messages.insert(0, {"role": "system", "content": _SYSTEM_PROMPT})
    return safe_messages


def _resolve_ollama_url() -> str:
    base = (Settings.OLLAMA_ENDPOINT or "").strip() or "http://127.0.0.1:11434"
    if "://" not in base:
        base = f"http://{base}"
    base = base.rstrip("/") + "/"
    return urljoin(base, "api/chat")


def _resolve_ollama_model() -> str:
    model = (Settings.OLLAMA_MODEL or "").strip()
    if not model:
        return "llama3.1"
    return model


@bp.route("/chatbot", methods=["POST", "OPTIONS"])
def invoke_chatbot():
    if request.method == "OPTIONS":
        return "", 204
    user_sub = _require_user()
    if not user_sub:
        return {"ok": False, "error": {"code": "NOAUTH", "message": "No autenticado"}}, 401

    payload = request.get_json(silent=True) or {}
    message = str(payload.get("message", "")).strip()
    history_raw = payload.get("history") or []

    if not message:
        return {"ok": False, "error": {"code": "EMPTY", "message": "Ingresa un mensaje"}}, 400

    if len(message) > 4000:
        return {"ok": False, "error": {"code": "TOO_LONG", "message": "El mensaje es demasiado largo"}}, 400

    history = _sanitize_history(history_raw)
    history.append({"role": "user", "content": message})

    target = _resolve_ollama_url()
    body = {
        "model": _resolve_ollama_model(),
        "messages": history,
        "stream": False,
    }

    try:
        upstream = requests.post(target, json=body, timeout=(5, 120))
    except requests.RequestException as exc:
        bp.logger.warning("Ollama unreachable at %s: %s", target, exc)
        return {
            "ok": False,
            "error": {"code": "OLLAMA_UNREACHABLE", "message": "No se pudo conectar con Ollama"},
        }, 502

    if upstream.status_code >= 400:
        try:
            detail = upstream.json()
            message_error = detail.get("error") or detail.get("message") or "Error de Ollama"
        except Exception:
            message_error = "Error de Ollama"
        return {
            "ok": False,
            "error": {"code": "OLLAMA_ERROR", "message": str(message_error)},
        }, 502

    try:
        response_json = upstream.json()
    except json.JSONDecodeError:
        return {
            "ok": False,
            "error": {"code": "INVALID_RESP", "message": "Respuesta invalida de Ollama"},
        }, 502

    content = str(response_json.get("message", {}).get("content", "")).strip()
    if not content:
        content = "No obtuve una respuesta del modelo."

    return {
        "ok": True,
        "message": {
            "role": "assistant",
            "content": content,
        },
    }
