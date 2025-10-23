from __future__ import annotations
import json
from datetime import datetime
from flask import Blueprint, request
from ..db import get_connection
from ..schemas import CentroRequestDecision
from ..auth import authenticate_request, get_current_user_id
from .solicitudes import STATUS_PENDING

bp = Blueprint("notificaciones", __name__, url_prefix="/api")


def _parse_centros_value(raw) -> list[str]:
    """Normalise the stored centres list into a clean sequence."""
    if not raw:
        return []
    if isinstance(raw, (list, tuple, set)):
        iterable = raw
    else:
        text = str(raw).replace(";", ",").strip()
        if not text:
            return []
        if "," in text:
            iterable = text.split(",")
        else:
            iterable = [text]
    cleaned: list[str] = []
    seen = set()
    for value in iterable:
        text = str(value).strip()
        if not text:
            continue
        key = text.lower()
        if key in seen:
            continue
        seen.add(key)
        cleaned.append(text)
    return cleaned


def _require_auth() -> str | None:
    uid = get_current_user_id()
    if uid:
        return uid
    authenticate_request()
    uid = get_current_user_id()
    return uid


@bp.get("/notificaciones")
def listar_notificaciones():
    uid = _require_auth()
    if not uid:
        return {"ok": False, "error": {"code": "NOAUTH", "message": "No autenticado"}}, 401
    with get_connection() as con:
        user_row = con.execute(
            "SELECT id_spm, nombre, apellido, rol, mail FROM usuarios WHERE lower(id_spm)=?",
            (uid.lower(),),
        ).fetchone()
        if not user_row:
            return {"ok": False, "error": {"code": "NOUSER", "message": "Usuario no encontrado"}}, 404
        role_value = (user_row.get("rol") or "").lower()
        is_admin = "admin" in role_value
        rows = con.execute(
            """
            SELECT id, solicitud_id, mensaje, leido, created_at
            FROM notificaciones
            WHERE lower(destinatario_id)=?
            ORDER BY datetime(created_at) DESC, id DESC
            """,
            (uid.lower(),),
        ).fetchall()
        items = []
        unread = 0
        for row in rows:
            leido = bool(row.get("leido"))
            if not leido:
                unread += 1
            items.append(
                {
                    "id": row["id"],
                    "solicitud_id": row["solicitud_id"],
                    "mensaje": row["mensaje"],
                    "leido": leido,
                    "created_at": row["created_at"],
                }
            )
        if is_admin:
            pending_query = """
                SELECT id, centro, sector, justificacion, total_monto, created_at, status, id_usuario, aprobador_id
                  FROM solicitudes
                 WHERE status=?
                 ORDER BY datetime(created_at) DESC, id DESC
            """
            pending_params = (STATUS_PENDING,)
        else:
            pending_query = """
                SELECT id, centro, sector, justificacion, total_monto, created_at, status, id_usuario, aprobador_id
                  FROM solicitudes
                 WHERE lower(aprobador_id)=? AND status=?
                 ORDER BY datetime(created_at) DESC, id DESC
            """
            pending_params = (uid.lower(), STATUS_PENDING)
        pending_rows = con.execute(pending_query, pending_params).fetchall()
        pendientes = [dict(r) for r in pending_rows]
        admin_summary = None
        if is_admin:
            centro_requests = []
            for row in con.execute(
                """
                SELECT upr.id,
                       upr.usuario_id,
                       upr.payload,
                       upr.created_at,
                       COALESCE(u.nombre || ' ' || u.apellido, u.nombre, upr.usuario_id) AS solicitante,
                       u.mail
                  FROM user_profile_requests upr
                  LEFT JOIN usuarios u ON lower(u.id_spm)=lower(upr.usuario_id)
                 WHERE upr.tipo='centros' AND upr.estado='pendiente'
                 ORDER BY datetime(upr.created_at) DESC, upr.id DESC
                """
            ):
                payload_raw = row.get("payload") or "{}"
                try:
                    payload = json.loads(payload_raw)
                except json.JSONDecodeError:
                    payload = {}
                centros = payload.get("centros") or ""
                motivo = payload.get("motivo")
                centro_requests.append(
                    {
                        "id": row["id"],
                        "usuario_id": row["usuario_id"],
                        "solicitante": row["solicitante"],
                        "mail": row.get("mail"),
                        "centros": [part.strip() for part in str(centros).split(",") if part.strip()],
                        "motivo": motivo,
                        "created_at": row["created_at"],
                    }
                )
            new_users = []
            for row in con.execute(
                """
                SELECT id_spm, nombre, apellido, mail, rol, estado_registro
                  FROM usuarios
                 WHERE LOWER(COALESCE(estado_registro,'')) NOT IN ('activo','aprobado')
                 ORDER BY rowid DESC
                """
            ):
                new_users.append(
                    {
                        "id": row["id_spm"],
                        "nombre": row["nombre"],
                        "apellido": row["apellido"],
                        "mail": row.get("mail"),
                        "rol": row.get("rol"),
                        "estado": row.get("estado_registro") or "",
                    }
                )
            admin_summary = {
                "centro_requests": centro_requests,
                "new_users": new_users,
                "is_admin": True,
            }
    return {
        "ok": True,
        "unread": unread,
        "items": items,
        "pending": pendientes,
        "admin": admin_summary,
    }


@bp.route(
    "/notificaciones/centros/<int:request_id>/decision",
    methods=["POST", "OPTIONS"],
)
@bp.route(
    "/notificaciones/centros/<int:request_id>/decision/",
    methods=["POST", "OPTIONS"],
)
def decidir_solicitud_centros(request_id: int):
    if request.method == "OPTIONS":
        # Permite preflight CORS
        return "", 204
    uid = _require_auth()
    if not uid:
        return {"ok": False, "error": {"code": "NOAUTH", "message": "No autenticado"}}, 401
    decision = CentroRequestDecision(**(request.get_json(force=True) or {}))
    with get_connection() as con:
        actor_row = con.execute(
            "SELECT id_spm, rol, nombre, apellido FROM usuarios WHERE lower(id_spm)=?",
            (uid.lower(),),
        ).fetchone()
        if not actor_row:
            return {"ok": False, "error": {"code": "NOUSER", "message": "Usuario no encontrado"}}, 404
        role_value = (actor_row.get("rol") or "").lower()
        if "admin" not in role_value:
            return {
                "ok": False,
                "error": {"code": "FORBIDDEN", "message": "No tiene permisos para realizar esta accion"},
            }, 403
        row = con.execute(
            """
            SELECT id, usuario_id, payload, estado
              FROM user_profile_requests
             WHERE id=? AND tipo='centros'
            """,
            (request_id,),
        ).fetchone()
        if not row:
            return {"ok": False, "error": {"code": "NOTFOUND", "message": "Solicitud no encontrada"}}, 404
        estado_actual = (row.get("estado") or "").lower()
        if estado_actual != "pendiente":
            return {
                "ok": False,
                "error": {"code": "NOTPENDING", "message": "La solicitud ya fue procesada"},
            }, 409
        payload_raw = row.get("payload") or "{}"
        try:
            request_payload = json.loads(payload_raw)
        except json.JSONDecodeError:
            request_payload = {}
        centros_solicitados = _parse_centros_value(request_payload.get("centros"))
        solicitante_id = (row.get("usuario_id") or "").strip()
        if not solicitante_id:
            return {
                "ok": False,
                "error": {"code": "BADREQUEST", "message": "Solicitud incompleta"},
            }, 400

        estado_nuevo = "aprobado" if decision.accion == "aprobar" else "rechazado"
        centros_actualizados: list[str] | None = None
        if decision.accion == "aprobar":
            if not centros_solicitados:
                return {
                    "ok": False,
                    "error": {"code": "NOCENTROS", "message": "La solicitud no contiene centros validos"},
                }, 400
            target_row = con.execute(
                "SELECT centros FROM usuarios WHERE lower(id_spm)=?",
                (solicitante_id.lower(),),
            ).fetchone()
            if not target_row:
                return {
                    "ok": False,
                    "error": {"code": "USERMISSING", "message": "El usuario solicitante no existe"},
                }, 404
            existentes = _parse_centros_value(target_row.get("centros"))
            existentes_keys = {value.lower() for value in existentes}
            for centro in centros_solicitados:
                key = centro.lower()
                if key in existentes_keys:
                    continue
                existentes.append(centro)
                existentes_keys.add(key)
            centros_actualizados = existentes
            con.execute(
                "UPDATE usuarios SET centros=? WHERE lower(id_spm)=?",
                (", ".join(existentes), solicitante_id.lower()),
            )

        request_payload = request_payload if isinstance(request_payload, dict) else {}
        decision_record = {
            "accion": decision.accion,
            "comentario": decision.comentario,
            "resuelto_por": actor_row.get("id_spm"),
            "resuelto_en": datetime.utcnow().isoformat(timespec="seconds"),
        }
        request_payload["_decision"] = decision_record
        con.execute(
            """
            UPDATE user_profile_requests
               SET estado=?,
                   payload=?,
                   updated_at=CURRENT_TIMESTAMP
             WHERE id=?
            """,
            (estado_nuevo, json.dumps(request_payload), request_id),
        )

        mensaje_parts = [
            "Tu solicitud de acceso a centros",
            ", ".join(centros_solicitados) if centros_solicitados else "",
            f"fue {estado_nuevo}.",
        ]
        if decision.comentario:
            mensaje_parts.append(f"Comentario: {decision.comentario}")
        mensaje = " ".join(part for part in mensaje_parts if part).strip()
        if len(mensaje) > 480:
            mensaje = mensaje[:477] + "..."
        con.execute(
            """
            INSERT INTO notificaciones (destinatario_id, solicitud_id, mensaje, leido)
            VALUES (?, NULL, ?, 0)
            """,
            (solicitante_id.lower(), mensaje),
        )
        con.commit()

    return {
        "ok": True,
        "estado": estado_nuevo,
        "usuario_id": solicitante_id,
        "centros": centros_actualizados,
    }


@bp.route("/notificaciones/marcar", methods=["POST", "OPTIONS"])
def marcar_notificaciones():
    if request.method == "OPTIONS":
        return "", 204
    uid = _require_auth()
    if not uid:
        return {"ok": False, "error": {"code": "NOAUTH", "message": "No autenticado"}}, 401
    payload = request.get_json(silent=True) or {}
    ids = payload.get("ids") or []
    mark_all = bool(payload.get("mark_all"))
    cleaned_ids: list[int] = []
    for value in ids:
        try:
            cleaned_ids.append(int(value))
        except (TypeError, ValueError):
            continue
    with get_connection() as con:
        if mark_all or not cleaned_ids:
            con.execute(
                "UPDATE notificaciones SET leido=1 WHERE lower(destinatario_id)=?",
                (uid.lower(),),
            )
        else:
            placeholders = ",".join(["?"] * len(cleaned_ids))
            con.execute(
                f"UPDATE notificaciones SET leido=1 WHERE lower(destinatario_id)=? AND id IN ({placeholders})",
                (uid.lower(), *cleaned_ids),
            )
        con.commit()
        remaining = con.execute(
            "SELECT COUNT(*) AS c FROM notificaciones WHERE lower(destinatario_id)=? AND leido=0",
            (uid.lower(),),
        ).fetchone()["c"]
    return {"ok": True, "unread": remaining}
