from __future__ import annotations

import json
import logging
from typing import Any, Dict, Optional, Tuple

from flask import Blueprint, current_app, g, jsonify, make_response, request

from ..auth import (
    auth_required,
    authenticate_request,
    authenticate_user,
    clear_auth_cookie,
    get_current_user,
    get_current_user_id,
    issue_token,
    set_auth_cookie,
)
from ..db import get_connection
from ..schemas import AdditionalCentersRequest, RegisterRequest, UpdateMailRequest, UpdatePhoneRequest
from ..security import hash_password

bp = Blueprint("auth", __name__, url_prefix="/api")
logger = logging.getLogger(__name__)


@bp.before_app_request
def _inject_auth_context() -> None:
    path = (request.path or "").lower()
    if not path.startswith("/api"):
        return
    authenticate_request()


def _public_profile(user: Dict[str, Any]) -> Dict[str, Any]:
    return {
        "id": user.get("id"),
        "id_spm": user.get("id_spm"),
        "username": user.get("username"),
        "nombre": user.get("nombre"),
        "apellido": user.get("apellido"),
        "rol": user.get("rol"),
        "mail": user.get("mail"),
        "telefono": user.get("telefono"),
        "sector": user.get("sector"),
        "posicion": user.get("posicion"),
        "centros": user.get("centros"),
        "id_red": user.get("id_red") or user.get("id_ypf"),
        "jefe": user.get("jefe"),
        "gerente1": user.get("gerente1"),
        "gerente2": user.get("gerente2"),
    }


@bp.route("/login", methods=["POST"])
def login():
    payload = request.get_json(silent=True) or {}
    username = (payload.get("username") or payload.get("id") or payload.get("usuario") or "").strip()
    password = payload.get("password") or payload.get("contrasena") or ""
    if not username or not password:
        return jsonify(error="invalid_credentials"), 401
    user = authenticate_user(username, password)
    if not user:
        return jsonify(error="invalid_credentials"), 401
    extra_claims = {"rol": user.get("rol"), "mail": user.get("mail")}
    token = issue_token(user["id"], extra=extra_claims)
    response = make_response(jsonify(ok=True, user=_public_profile(user)))
    set_auth_cookie(response, token)
    return response


@bp.route("/logout", methods=["POST"])
def logout():
    response = make_response(jsonify(ok=True))
    clear_auth_cookie(response)
    return response


@bp.route("/refresh", methods=["POST"])
def refresh():
    return jsonify(error="unsupported_operation"), 400


@bp.route("/register", methods=["POST"])
def register():
    payload = RegisterRequest(**request.get_json(force=True))
    with get_connection() as con:
        try:
            mail = None
            if "@" in payload.id:
                mail = payload.id.lower()
            con.execute(
                """
                INSERT INTO usuarios (id_spm, nombre, apellido, rol, contrasena, mail, estado_registro)
                VALUES (?,?,?,?,?,?,?)
                """,
                (
                    payload.id,
                    payload.nombre,
                    payload.apellido,
                    payload.rol,
                    hash_password(payload.password),
                    mail,
                    "Pendiente",
                ),
            )
            con.commit()
            return {"ok": True}, 201
        except Exception:
            con.rollback()
            return {"ok": False, "error": {"code": "DUP", "message": "Usuario ya existe o datos inválidos"}}, 409


@bp.get("/me")
@auth_required
def me_v2():
    user = get_current_user()
    if not user:
        return jsonify(error="unauthorized"), 401
    return jsonify(_public_profile(user))


@bp.route("/usuarios/me", methods=["GET"])
@auth_required
def me_legacy():
    return me_v2()


def _update_profile_fields(data: Dict[str, Any]) -> Tuple[Optional[Dict[str, Any]], Optional[Tuple[str, str, int]]]:
    profile_data = data or {}
    uid = get_current_user_id()
    if not uid:
        return None, ("NOAUTH", "No autenticado", 401)
    updates: Dict[str, Any] = {}
    if "mail" in profile_data and isinstance(profile_data["mail"], str):
        mail_value = profile_data["mail"].strip().lower()
        if mail_value:
            updates["mail"] = mail_value
    if "telefono" in profile_data and isinstance(profile_data["telefono"], str):
        telefono_value = profile_data["telefono"].strip()
        if telefono_value:
            updates["telefono"] = telefono_value
    if not updates:
        return None, ("NOFIELDS", "No hay campos para actualizar", 400)
    assignments = ", ".join(f"{field}=?" for field in updates)
    values = list(updates.values())
    values.append(uid)
    with get_connection() as con:
        con.execute(f"UPDATE usuarios SET {assignments} WHERE id_spm=?", values)
        con.commit()
    authenticate_request()  # refresh cached user/profile
    updated = get_current_user()
    return updated, None


@bp.patch("/me/fields")
@auth_required
def update_me_fields():
    payload = request.get_json(silent=True) or {}
    updated, error = _update_profile_fields(payload)
    if error:
        code, message, status = error
        if status == 401:
            return jsonify(error="unauthorized"), 401
        return jsonify(error=message, code=code), status
    return jsonify(_public_profile(updated or {}))


def _persist_additional_centers(uid: str, payload: AdditionalCentersRequest) -> None:
    content = {"centros": payload.centros, "motivo": payload.motivo}
    with get_connection() as con:
        con.execute(
            """
            INSERT INTO user_profile_requests (usuario_id, tipo, payload, estado)
            VALUES (?, ?, ?, 'pendiente')
            """,
            (uid, "centros", json.dumps(content)),
        )
        display_row = con.execute(
            "SELECT nombre, apellido FROM usuarios WHERE id_spm=?",
            (uid,),
        ).fetchone()
        display_name = None
        if display_row:
            nombre = (display_row["nombre"] or "").strip()
            apellido = (display_row["apellido"] or "").strip()
            display_name = " ".join(part for part in (nombre, apellido) if part)
        requester = display_name or uid
        mensaje = f"{requester} solicitó acceso a los centros {payload.centros}"
        if payload.motivo:
            mensaje += f" (Motivo: {payload.motivo})"
        if len(mensaje) > 480:
            mensaje = mensaje[:477] + "..."
        admin_rows = con.execute(
            "SELECT id_spm FROM usuarios WHERE lower(COALESCE(rol,'')) LIKE ?",
            ("%admin%",),
        ).fetchall()
        notified = set()
        uid_lower = uid.strip().lower()
        for row in admin_rows:
            dest = (row["id_spm"] or "").strip().lower()
            if not dest or dest == uid_lower or dest in notified:
                continue
            con.execute(
                "INSERT INTO notificaciones (destinatario_id, solicitud_id, mensaje, leido) VALUES (?,?,?,0)",
                (dest, None, mensaje),
            )
            notified.add(dest)
        con.commit()


@bp.post("/me/change-requests")
@auth_required
def create_change_request():
    uid = get_current_user_id()
    if not uid:
        return jsonify(error="unauthorized"), 401
    payload = request.get_json(force=True)
    change_kind = str(payload.get("type") or payload.get("kind") or "centros").lower()
    if change_kind in {"centros", "centers"}:
        centers_payload = AdditionalCentersRequest(**payload)
        _persist_additional_centers(uid, centers_payload)
        return jsonify({"type": "centros", "centros": centers_payload.centros, "motivo": centers_payload.motivo})
    return jsonify(error="unsupported_change_request", code="UNSUPPORTED"), 400


@bp.route("/me/telefono", methods=["POST"])
@auth_required
def update_phone():
    payload = UpdatePhoneRequest(**request.get_json(force=True))
    updated, error = _update_profile_fields({"telefono": payload.telefono})
    if error:
        code, msg, status = error
        return {"ok": False, "error": {"code": code, "message": msg}}, status
    telefono = (updated or {}).get("telefono", payload.telefono)
    return {"ok": True, "telefono": telefono}


@bp.route("/me/mail", methods=["POST"])
@auth_required
def update_mail():
    payload = UpdateMailRequest(**request.get_json(force=True))
    updated, error = _update_profile_fields({"mail": payload.mail.strip().lower()})
    if error:
        code, msg, status = error
        return {"ok": False, "error": {"code": code, "message": msg}}, status
    mail_value = (updated or {}).get("mail", payload.mail.strip().lower())
    return {"ok": True, "mail": mail_value}


@bp.route("/me/centros/solicitud", methods=["POST"])
@auth_required
def request_additional_centers():
    uid = get_current_user_id()
    if not uid:
        return {"ok": False, "error": {"code": "NOAUTH", "message": "No autenticado"}}, 401
    payload = AdditionalCentersRequest(**request.get_json(force=True))
    _persist_additional_centers(uid, payload)
    return {"ok": True}
