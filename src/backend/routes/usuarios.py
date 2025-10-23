from __future__ import annotations

from typing import Any, Dict, List, Optional, Tuple

import re

from flask import Blueprint, current_app, request, jsonify

from ..db import get_connection
from ..auth import authenticate_request, get_current_user_id
from ..security import hash_password, verify_password

bp = Blueprint("usuarios", __name__, url_prefix="/api/usuarios")

SELF_EDITABLE_FIELDS = {"telefono", "mail"}
ADMIN_REVIEW_FIELDS = {"rol", "posicion", "sector", "jefe", "gerente1", "gerente2"}
SUPPORTED_FIELDS = SELF_EDITABLE_FIELDS | ADMIN_REVIEW_FIELDS
REASSIGN_CANDIDATES: Dict[str, Tuple[str, ...]] = {
    "solicitudes": ("id_usuario", "aprobador_id", "responsable_id", "planner_id"),
    "planificador_asignaciones": ("usuario_id", "asignado_a", "planificador_id"),
}


bp_me = Blueprint("usuarios_me", __name__, url_prefix="/api/me")

PHONE_ALLOWED_RE = re.compile(r"^[0-9+()\-\s]{0,25}$")
EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")


def _require_user_id() -> Tuple[Optional[str], Optional[Tuple[str, str, int]]]:
    user_id = get_current_user_id()
    if user_id:
        return user_id, None
    authenticate_request()
    user_id = get_current_user_id()
    if not user_id:
        return None, ("NOAUTH", "No autenticado", 401)
    return user_id, None


def _serialize_user(row: Dict[str, Any]) -> Dict[str, Any]:
    centros_raw = row.get("centros")
    centros: List[str] = []
    if isinstance(centros_raw, str) and centros_raw.strip():
        centros = [
            part.strip()
            for part in centros_raw.replace(";", ",").split(",")
            if part.strip()
        ]
    return {
        "id": row.get("id_spm"),
        "nombre": row.get("nombre"),
        "apellido": row.get("apellido"),
        "rol": row.get("rol"),
        "posicion": row.get("posicion"),
        "sector": row.get("sector"),
        "mail": row.get("mail"),
        "telefono": row.get("telefono"),
        "id_red": row.get("id_ypf"),
        "jefe": row.get("jefe"),
        "gerente1": row.get("gerente1"),
        "gerente2": row.get("gerente2"),
        "centros": centros,
        "estado_registro": row.get("estado_registro"),
    }


def _get_user(con, user_id: str) -> Optional[Dict[str, Any]]:
    row = con.execute(
        """
        SELECT id_spm, nombre, apellido, rol, posicion, sector, mail, telefono,
               id_ypf, jefe, gerente1, gerente2, centros, estado_registro, contrasena
          FROM usuarios
         WHERE id_spm = ?
        """,
        (user_id,),
    ).fetchone()
    return dict(row) if row else None


def _ensure_user_change_table(con) -> None:
    con.execute(
        """
        CREATE TABLE IF NOT EXISTS user_change_requests(
          id INTEGER PRIMARY KEY AUTOINCREMENT,
          user_id TEXT NOT NULL,
          campo TEXT NOT NULL,
          valor_actual TEXT,
          valor_nuevo TEXT NOT NULL,
          estado TEXT NOT NULL DEFAULT 'pendiente',
          created_at TEXT DEFAULT CURRENT_TIMESTAMP,
          resolved_at TEXT,
          resolved_by TEXT
        )
        """
    )


def _is_admin(con, user_id: str) -> bool:
    row = con.execute(
        """
        SELECT 1
          FROM usuarios
         WHERE id_spm = ? COLLATE NOCASE
           AND estado_registro != 'Eliminado'
           AND lower(COALESCE(rol,'')) = 'administrador'
        """,
        (user_id,),
    ).fetchone()
    return bool(row)


def _get_admin_user_id(con, *, exclude: Optional[str] = None) -> Optional[str]:
    params: Tuple[Any, ...]
    if exclude:
        params = (exclude,)
        where = "AND lower(id_spm) != lower(?)"
    else:
        params = tuple()
        where = ""
    row = con.execute(
        f"""
        SELECT id_spm
          FROM usuarios
         WHERE estado_registro != 'Eliminado'
           AND lower(COALESCE(rol,'')) = 'administrador'
         {where}
         ORDER BY COALESCE(nombre,''), id_spm
         LIMIT 1
        """,
        params,
    ).fetchone()
    return row["id_spm"] if row else None


def _column_cache(con) -> Dict[str, set]:
    cache: Dict[str, set] = {}
    for table in REASSIGN_CANDIDATES:
        cols = con.execute(f"PRAGMA table_info({table})").fetchall()
        cache[table] = {col["name"] for col in cols}
    return cache


def _reassign_user_work(con, source_user: str, target_user: str) -> None:
    column_cache = _column_cache(con)
    for table, columns in REASSIGN_CANDIDATES.items():
        available = column_cache.get(table, set())
        for column in columns:
            if column not in available:
                continue
            try:
                con.execute(
                    f"UPDATE {table} SET {column}=? WHERE {column}=?",
                    (target_user, source_user),
                )
            except Exception as exc:  # pragma: no cover - defensive logging
                current_app.logger.warning(
                    "No se pudo reasignar %s.%s: %s", table, column, exc
                )


@bp.get("/me")
def obtener_mi_usuario():
    uid, error = _require_user_id()
    if error:
        code, msg, status = error
        return jsonify({"ok": False, "error": {"code": code, "message": msg}}), status
    with get_connection() as con:
        user = _get_user(con, uid)
        if not user:
            return {
                "ok": False,
                "error": {"code": "NOUSER", "message": "Usuario no encontrado"},
            }, 404
        return {"ok": True, "usuario": _serialize_user(user)}


@bp.patch("/me")
def actualizar_mi_usuario():
    uid, error = _require_user_id()
    if error:
        code, msg, status = error
        return jsonify({"ok": False, "error": {"code": code, "message": msg}}), status
    payload = request.get_json(silent=True) or {}
    updates: Dict[str, Any] = {}
    for field in SELF_EDITABLE_FIELDS:
        if field in payload:
            value = (payload[field] or "").strip()
            if field == "mail":
                if not value or "@" not in value:
                    return {
                        "ok": False,
                        "error": {"code": "BADMAIL", "message": "Correo inválido"},
                    }, 400
                value = value.lower()
            elif field == "telefono":
                if not value:
                    return {
                        "ok": False,
                        "error": {"code": "BADPHONE", "message": "Teléfono inválido"},
                    }, 400
            updates[field] = value
    if not updates:
        return {
            "ok": False,
            "error": {
                "code": "NOFIELDS",
                "message": "No se enviaron campos modificables",
            },
        }, 400
    with get_connection() as con:
        con.execute("BEGIN")
        user = _get_user(con, uid)
        if not user:
            return {
                "ok": False,
                "error": {"code": "NOUSER", "message": "Usuario no encontrado"},
            }, 404
        assignments = ", ".join(f"{field}=?" for field in updates)
        params = tuple(updates[field] for field in updates) + (uid,)
        con.execute(f"UPDATE usuarios SET {assignments} WHERE id_spm=?", params)
        con.commit()
        user.update(updates)
        return {"ok": True, "usuario": _serialize_user(user)}


@bp.post("/me/cambiar-password")
def cambiar_password():
    uid, error = _require_user_id()
    if error:
        code, msg, status = error
        return {"ok": False, "error": {"code": code, "message": msg}}, status
    payload = request.get_json(silent=True) or {}
    current_password = (payload.get("current_password") or "").strip()
    new_password = (payload.get("new_password") or "").strip()
    repeat_password = (payload.get("repeat_password") or "").strip()
    if not current_password or not new_password:
        return {
            "ok": False,
            "error": {
                "code": "BADREQUEST",
                "message": "Debe completar la contraseña actual y la nueva",
            },
        }, 400
    if repeat_password and repeat_password != new_password:
        return {
            "ok": False,
            "error": {"code": "MISMATCH", "message": "Las contraseñas no coinciden"},
        }, 400
    if len(new_password) < 8:
        return {
            "ok": False,
            "error": {
                "code": "WEAKPWD",
                "message": "La nueva contraseña debe tener al menos 8 caracteres",
            },
        }, 400
    with get_connection() as con:
        user = _get_user(con, uid)
        if not user:
            return {
                "ok": False,
                "error": {"code": "NOUSER", "message": "Usuario no encontrado"},
            }, 404
        valid, _needs_rehash = verify_password(user.get("contrasena"), current_password)
        if not valid:
            return {
                "ok": False,
                "error": {
                    "code": "BADPWD",
                    "message": "La contraseña actual es incorrecta",
                },
            }, 400
        new_hash = hash_password(new_password)
        con.execute(
            "UPDATE usuarios SET contrasena=? WHERE id_spm=?",
            (new_hash, uid),
        )
        con.commit()
    return {"ok": True}


def _create_user_change_request(uid: str, campo: str, valor_nuevo: str):
    if campo not in ADMIN_REVIEW_FIELDS:
        return {"ok": False, "error": {"code": "BADFIELD", "message": "El campo no admite solicitudes de cambio"}}, 400
    if not valor_nuevo:
        return {"ok": False, "error": {"code": "NOVALUE", "message": "Debe indicar el nuevo valor"}}, 400
    with get_connection() as con:
        con.execute("BEGIN")
        _ensure_user_change_table(con)
        user = _get_user(con, uid)
        if not user:
            con.rollback()
            return {"ok": False, "error": {"code": "NOUSER", "message": "Usuario no encontrado"}}, 404
        valor_actual = (user.get(campo) or "").strip() or None
        content = {"user_id": uid, "campo": campo, "valor_actual": valor_actual, "valor_nuevo": valor_nuevo}
        con.execute("""
            INSERT INTO user_change_requests (user_id, campo, valor_actual, valor_nuevo, estado)
            VALUES (:user_id, :campo, :valor_actual, :valor_nuevo, 'pendiente')
        """, content)
        request_id = con.execute("SELECT last_insert_rowid() AS rid").fetchone()["rid"]
        con.commit()
    return {"ok": True, "request_id": request_id}, 200


@bp_me.route("/fields", methods=["PATCH", "POST"])
def update_me_fields():
    uid, error = _require_user_id()
    if error:
        code, msg, status = error
        return jsonify({"ok": False, "error": {"code": code, "message": msg}}), status
    data = request.get_json(silent=True) or {}
    field = (data.get("field") or "").strip().lower()
    value = data.get("value", "")
    if field not in SELF_EDITABLE_FIELDS:
        return jsonify({"ok": False, "error": "Campo no editable"}), 400
    if field == "telefono":
        value = re.sub(r"[^0-9+()\-\s]", "", str(value or "")).strip()
        if not value or len(value) > 25 or not PHONE_ALLOWED_RE.fullmatch(value):
            return jsonify({"ok": False, "error": "Telefono invalido"}), 400
    else:  # mail
        value = str(value or "").strip().lower()
        if not EMAIL_RE.fullmatch(value):
            return jsonify({"ok": False, "error": "Email invalido"}), 400
    with get_connection() as con:
        con.execute(f"UPDATE usuarios SET {field} = ? WHERE id_spm = ?", (value, uid))
        con.commit()
    return jsonify({"ok": True, "field": field, "value": value})


@bp_me.route("/change-requests", methods=["POST"])
def create_me_change_request():
    uid, error = _require_user_id()
    if error:
        code, msg, status = error
        return jsonify({"ok": False, "error": {"code": code, "message": msg}}), status
    data = request.get_json(silent=True) or {}
    campo = (data.get("field") or "").strip()
    valor_nuevo = (data.get("value") or "").strip()
    response, status = _create_user_change_request(uid, campo, valor_nuevo)
    if isinstance(response, dict):
        return jsonify(response), status
    return response, status


@bp.post("/me/cambios-pendientes")
def crear_cambio_pendiente():
    uid, error = _require_user_id()
    if error:
        code, msg, status = error
        return jsonify({"ok": False, "error": {"code": code, "message": msg}}), status
    payload = request.get_json(silent=True) or {}
    campo = (payload.get("campo") or "").strip()
    valor_nuevo = (payload.get("valor_nuevo") or "").strip()
    response, status = _create_user_change_request(uid, campo, valor_nuevo)
    if isinstance(response, dict):
        return jsonify(response), status
    return response, status


@bp.get("/cambios-pendientes")
def listar_cambios_pendientes():
    uid, error = _require_user_id()
    if error:
        code, msg, status = error
        return {"ok": False, "error": {"code": code, "message": msg}}, status
    with get_connection() as con:
        if not _is_admin(con, uid):
            return {
                "ok": False,
                "error": {"code": "FORBIDDEN", "message": "Acceso restringido"},
            }, 403
        _ensure_user_change_table(con)
        rows = con.execute(
            """
            SELECT r.id, r.user_id, r.campo, r.valor_actual, r.valor_nuevo, r.estado,
                   r.created_at, r.resolved_at, r.resolved_by,
                   u.nombre, u.apellido, u.rol
              FROM user_change_requests r
              LEFT JOIN usuarios u ON lower(u.id_spm) = lower(r.user_id)
             WHERE r.estado = 'pendiente'
             ORDER BY r.created_at ASC
            """
        ).fetchall()
    items = []
    for row in rows:
        data = dict(row)
        data["usuario"] = {
            "id": data.pop("user_id"),
            "nombre": data.pop("nombre"),
            "apellido": data.pop("apellido"),
            "rol": data.pop("rol"),
        }
        items.append(data)
    return {"ok": True, "items": items}


def _resolver_cambio(req_id: int, aprobar: bool):
    uid, error = _require_user_id()
    if error:
        code, msg, status = error
        return {"ok": False, "error": {"code": code, "message": msg}}, status
    with get_connection() as con:
        if not _is_admin(con, uid):
            return {
                "ok": False,
                "error": {"code": "FORBIDDEN", "message": "Acceso restringido"},
            }, 403
        _ensure_user_change_table(con)
        con.execute("BEGIN")
        row = con.execute(
            """
            SELECT id, user_id, campo, valor_nuevo, estado
              FROM user_change_requests
             WHERE id = ?
            """,
            (req_id,),
        ).fetchone()
        if not row:
            con.rollback()
            return {
                "ok": False,
                "error": {"code": "NOTFOUND", "message": "Solicitud no encontrada"},
            }, 404
        data = dict(row)
        if data["estado"] != "pendiente":
            con.rollback()
            return {
                "ok": False,
                "error": {
                    "code": "ALREADY",
                    "message": "La solicitud ya fue resuelta",
                },
            }, 409
        campo = data["campo"]
        if campo not in SUPPORTED_FIELDS:
            con.rollback()
            return {
                "ok": False,
                "error": {"code": "BADFIELD", "message": "Campo no soportado"},
            }, 400
        if aprobar:
            con.execute(
                f"UPDATE usuarios SET {campo}=? WHERE id_spm=?",
                (data["valor_nuevo"], data["user_id"]),
            )
        con.execute(
            """
            UPDATE user_change_requests
               SET estado = ?, resolved_at = CURRENT_TIMESTAMP, resolved_by = ?
             WHERE id = ?
            """,
            ("aprobado" if aprobar else "rechazado", uid, req_id),
        )
        con.commit()
    return {"ok": True}, 200


@bp.post("/cambios-pendientes/<int:req_id>/aprobar")
def aprobar_cambio(req_id: int):
    return _resolver_cambio(req_id, True)


@bp.post("/cambios-pendientes/<int:req_id>/rechazar")
def rechazar_cambio(req_id: int):
    return _resolver_cambio(req_id, False)


@bp.delete("/me")
def eliminar_cuenta():
    uid, error = _require_user_id()
    if error:
        code, msg, status = error
        return {"ok": False, "error": {"code": code, "message": msg}}, status
    with get_connection() as con:
        con.execute("BEGIN")
        user = _get_user(con, uid)
        if not user:
            return {
                "ok": False,
                "error": {"code": "NOUSER", "message": "Usuario no encontrado"},
            }, 404
        admin_id = _get_admin_user_id(con, exclude=uid)
        if not admin_id:
            con.rollback()
            return {
                "ok": False,
                "error": {
                    "code": "NOADMIN",
                    "message": "No hay administradores disponibles para reasignar las tareas",
                },
            }, 409
        _reassign_user_work(con, uid, admin_id)
        con.execute(
            """
            UPDATE usuarios
               SET estado_registro = 'Eliminado'
             WHERE id_spm = ?
            """,
            (uid,),
        )
        con.commit()
    return {"ok": True}
