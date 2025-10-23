from __future__ import annotations
from collections import defaultdict
from datetime import datetime, date
import unicodedata
from flask import Blueprint, request
from ..db import get_connection
from ..auth import authenticate_request, get_current_user_id
from ..schemas import BudgetIncreaseCreate, BudgetIncreaseDecision

bp = Blueprint("presupuestos", __name__, url_prefix="/api")


def _require_auth() -> str | None:
    uid = get_current_user_id()
    if uid:
        return uid
    authenticate_request()
    uid = get_current_user_id()
    return uid


def _parse_datetime(value: str | None) -> datetime | None:
    if not value:
        return None
    value = value.strip()
    if not value:
        return None
    for fmt in ("%Y-%m-%dT%H:%M:%S", "%Y-%m-%dT%H:%M:%S.%f", "%Y-%m-%d %H:%M:%S", "%Y-%m-%d"):
        try:
            return datetime.strptime(value.replace("Z", ""), fmt)
        except ValueError:
            continue
    return None


def _normalize_text(value: object) -> str:
    raw = str(value or "").strip()
    if not raw:
        return ""
    normalized = unicodedata.normalize("NFKD", raw)
    return "".join(ch for ch in normalized if not unicodedata.combining(ch)).lower()


def _parse_centros(raw: object) -> list[str]:
    if raw is None:
        return []
    if isinstance(raw, str):
        return [part.strip() for part in raw.replace(";", ",").split(",") if part.strip()]
    if isinstance(raw, (list, tuple)):
        return [str(part).strip() for part in raw if str(part).strip()]
    return []


def _can_request_increase(user: dict[str, object]) -> bool:
    role = _normalize_text(user.get("rol"))
    pos = _normalize_text(user.get("posicion"))
    return "jefe" in pos or "gerente1" in pos or "gerente1" in role


def _can_approve_increase(user: dict[str, object]) -> bool:
    role = _normalize_text(user.get("rol"))
    pos = _normalize_text(user.get("posicion"))
    return "administrador" in role or "admin" in role or "gerente2" in pos or "gerente2" in role


def _is_budget_manager(user: dict[str, object]) -> bool:
    role = _normalize_text(user.get("rol"))
    pos = _normalize_text(user.get("posicion"))
    if _can_request_increase(user) or _can_approve_increase(user):
        return True
    if "gerente" in pos:
        return True
    if "presupuesto" in role:
        return True
    return False


def _serialize_increase(row: dict[str, object] | None) -> dict[str, object] | None:
    if not row:
        return None
    return {
        "id": row.get("id"),
        "centro": row.get("centro"),
        "sector": row.get("sector"),
        "monto": float(row.get("monto") or 0.0),
        "motivo": row.get("motivo"),
        "estado": row.get("estado"),
        "solicitante_id": row.get("solicitante_id"),
        "aprobador_id": row.get("aprobador_id"),
        "comentario": row.get("comentario"),
        "created_at": row.get("created_at"),
        "updated_at": row.get("updated_at"),
        "resolved_at": row.get("resolved_at"),
    }


@bp.get("/presupuestos/mis")
def obtener_presupuestos_propios():
    uid = _require_auth()
    if not uid:
        return {"ok": False, "error": {"code": "NOAUTH", "message": "No autenticado"}}, 401
    inc_rows: list[dict[str, object]] = []
    with get_connection() as con:
        user = con.execute(
            "SELECT id_spm, rol, posicion, centros FROM usuarios WHERE lower(id_spm)=?",
            (uid.lower(),),
        ).fetchone()
        if not user:
            return {"ok": False, "error": {"code": "NOUSER", "message": "Usuario no encontrado"}}, 404
        if not _is_budget_manager(user):
            return {"ok": False, "error": {"code": "FORBIDDEN", "message": "Sin permisos para el módulo de presupuestos"}}, 403
        centros = _parse_centros(user.get("centros"))
        if not centros:
            empty_response = {
                "ok": True,
                "summary": {
                    "total_presupuestos": 0,
                    "monto_total": 0.0,
                    "utilizado_total": 0.0,
                    "saldo_total": 0.0,
                    "ultima_actualizacion": None,
                },
                "presupuestos": [],
                "historial": [],
                "proximos_vencimientos": [],
                "incorporaciones": {
                    "puede_solicitar": _can_request_increase(user),
                    "puede_aprobar": _can_approve_increase(user),
                    "mis": [],
                    "pendientes": [],
                    "todas": [],
                },
            }
            return empty_response
        placeholders = ",".join(["?"] * len(centros))
        presup_rows = con.execute(
            f"""
            SELECT centro, sector, monto_usd, saldo_usd
              FROM presupuestos
             WHERE centro IN ({placeholders})
          ORDER BY centro, sector
            """,
            tuple(centros),
        ).fetchall()
        history_rows = con.execute(
            f"""
            SELECT id, centro, sector, status, total_monto, fecha_necesidad, created_at, updated_at, justificacion
              FROM solicitudes
             WHERE centro IN ({placeholders})
          ORDER BY datetime(created_at) DESC, id DESC
             LIMIT 200
            """,
            tuple(centros),
        ).fetchall()

        if centros:
            inc_rows = con.execute(
                f"""
                SELECT id, centro, sector, monto, motivo, estado, solicitante_id, aprobador_id, comentario, created_at, updated_at, resolved_at
                  FROM presupuesto_incorporaciones
                 WHERE centro IN ({placeholders}) OR lower(solicitante_id)=?
              ORDER BY datetime(created_at) DESC, id DESC
                 LIMIT 200
                """,
                (*centros, uid.lower()),
            ).fetchall()
        else:
            inc_rows = []

    history_by_key: defaultdict[tuple[str, str], list[dict[str, object]]] = defaultdict(list)
    proximos: list[dict[str, object]] = []
    today = date.today()
    ultima_global: datetime | None = None

    historial: list[dict[str, object]] = []
    for row in history_rows:
        entry = {
            "id": row["id"],
            "centro": row["centro"],
            "sector": row["sector"],
            "status": row["status"],
            "total_monto": float(row.get("total_monto") or 0.0),
            "fecha_necesidad": row.get("fecha_necesidad"),
            "created_at": row.get("created_at"),
            "updated_at": row.get("updated_at"),
            "justificacion": row.get("justificacion"),
        }
        historial.append(entry)
        history_by_key[(row["centro"], row["sector"])].append(entry)
        updated_dt = _parse_datetime(row.get("updated_at"))
        if updated_dt and (ultima_global is None or updated_dt > ultima_global):
            ultima_global = updated_dt
        fecha_necesidad = row.get("fecha_necesidad")
        if fecha_necesidad:
            fecha_dt = _parse_datetime(fecha_necesidad)
            if fecha_dt and fecha_dt.date() >= today and (row.get("status") or "").lower() != "cancelada":
                proximos.append(
                    {
                        "id": row["id"],
                        "centro": row["centro"],
                        "sector": row["sector"],
                        "fecha": fecha_necesidad,
                        "status": row.get("status"),
                        "monto": float(row.get("total_monto") or 0.0),
                    }
                )

    proximos.sort(key=lambda item: (_parse_datetime(item.get("fecha")) or datetime.max))
    proximos = proximos[:20]

    summary = {
        "total_presupuestos": len(presup_rows),
        "monto_total": 0.0,
        "utilizado_total": 0.0,
        "saldo_total": 0.0,
        "ultima_actualizacion": ultima_global.isoformat() if ultima_global else None,
    }

    presupuestos: list[dict[str, object]] = []
    for row in presup_rows:
        monto = float(row.get("monto_usd") or 0.0)
        saldo = float(row.get("saldo_usd") or 0.0)
        utilizado = max(0.0, monto - saldo)
        avance = round(utilizado / monto * 100, 2) if monto else 0.0
        key = (row["centro"], row["sector"])
        detalle_historial = history_by_key.get(key, [])
        ultima_local: datetime | None = None
        for item in detalle_historial:
            parsed = _parse_datetime(item.get("updated_at"))
            if parsed and (ultima_local is None or parsed > ultima_local):
                ultima_local = parsed
        entry = {
            "centro": row["centro"],
            "sector": row["sector"],
            "monto_total": monto,
            "saldo": saldo,
            "utilizado": utilizado,
            "avance": avance,
            "ultima_actualizacion": ultima_local.isoformat() if ultima_local else None,
            "historial": detalle_historial[:10],
        }
        presupuestos.append(entry)
        summary["monto_total"] += monto
        summary["utilizado_total"] += utilizado
        summary["saldo_total"] += saldo

    historial = historial[:50]

    increases_all = [_serialize_increase(row) for row in inc_rows]
    increases_all = [row for row in increases_all if row]
    increases_mine = [row for row in increases_all if row.get("solicitante_id", "").lower() == uid.lower()]
    increases_pending = [row for row in increases_all if (row.get("estado") or "").lower() == "pendiente"]

    response_increases = {
        "puede_solicitar": _can_request_increase(user),
        "puede_aprobar": _can_approve_increase(user),
        "mis": increases_mine[:50],
        "pendientes": increases_pending[:50],
        "todas": increases_all[:100],
    }

    response = {
        "ok": True,
        "summary": summary,
        "presupuestos": presupuestos,
        "historial": historial,
        "proximos_vencimientos": proximos,
        "incorporaciones": response_increases,
    }
    return response


@bp.route("/presupuestos/incorporaciones", methods=["POST", "OPTIONS"])
def crear_incorporacion_presupuesto():
    if request.method == "OPTIONS":
        return "", 204
    uid = _require_auth()
    if not uid:
        return {"ok": False, "error": {"code": "NOAUTH", "message": "No autenticado"}}, 401
    data = BudgetIncreaseCreate(**request.get_json(force=True))
    with get_connection() as con:
        user = con.execute(
            "SELECT id_spm, rol, posicion, centros FROM usuarios WHERE lower(id_spm)=?",
            (uid.lower(),),
        ).fetchone()
        if not user:
            return {"ok": False, "error": {"code": "NOUSER", "message": "Usuario no encontrado"}}, 404
        if not _can_request_increase(user):
            return {"ok": False, "error": {"code": "FORBIDDEN", "message": "No puedes solicitar incorporaciones"}}, 403
        centros = _parse_centros(user.get("centros"))
        if data.centro not in centros:
            return {"ok": False, "error": {"code": "BAD_CENTER", "message": "Centro fuera de tu alcance"}}, 400
        cursor = con.execute(
            """
            INSERT INTO presupuesto_incorporaciones (centro, sector, monto, motivo, estado, solicitante_id)
            VALUES (?,?,?,?, 'pendiente', ?)
            """,
            (data.centro, (data.sector or None), float(data.monto), data.motivo, uid.lower()),
        )
        inc_id = cursor.lastrowid
        con.commit()
        row = con.execute(
            """
            SELECT id, centro, sector, monto, motivo, estado, solicitante_id, aprobador_id, comentario, created_at, updated_at, resolved_at
              FROM presupuesto_incorporaciones
             WHERE id=?
            """,
            (inc_id,),
        ).fetchone()
    return {"ok": True, "incorporacion": _serialize_increase(row)}, 201


@bp.route("/presupuestos/incorporaciones/<int:inc_id>/resolver", methods=["POST", "OPTIONS"])
def resolver_incorporacion_presupuesto(inc_id: int):
    if request.method == "OPTIONS":
        return "", 204
    uid = _require_auth()
    if not uid:
        return {"ok": False, "error": {"code": "NOAUTH", "message": "No autenticado"}}, 401
    payload = BudgetIncreaseDecision(**request.get_json(force=True))
    accion = payload.accion.lower()
    comentario = payload.comentario
    with get_connection() as con:
        user = con.execute(
            "SELECT id_spm, rol, posicion, centros FROM usuarios WHERE lower(id_spm)=?",
            (uid.lower(),),
        ).fetchone()
        if not user:
            return {"ok": False, "error": {"code": "NOUSER", "message": "Usuario no encontrado"}}, 404
        if not _can_approve_increase(user):
            return {"ok": False, "error": {"code": "FORBIDDEN", "message": "No puedes aprobar incorporaciones"}}, 403
        row = con.execute(
            """
            SELECT id, centro, sector, monto, motivo, estado, solicitante_id, aprobador_id, comentario, created_at, updated_at, resolved_at
              FROM presupuesto_incorporaciones
             WHERE id=?
            """,
            (inc_id,),
        ).fetchone()
        if not row:
            return {"ok": False, "error": {"code": "NOT_FOUND", "message": "Solicitud no encontrada"}}, 404
        if (row.get("estado") or "").lower() != "pendiente":
            return {"ok": False, "error": {"code": "ALREADY_PROCESSED", "message": "La solicitud ya fue procesada"}}, 400
        centro = row.get("centro")
        sector_raw = row.get("sector")
        sector = sector_raw.strip() if isinstance(sector_raw, str) else sector_raw
        monto = float(row.get("monto") or 0.0)
        if accion == "aprobar":
            if monto <= 0:
                return {"ok": False, "error": {"code": "INVALID_AMOUNT", "message": "Monto inválido"}}, 400
            con.execute(
                """
                UPDATE presupuesto_incorporaciones
                   SET estado='aprobada', aprobador_id=?, comentario=?, resolved_at=CURRENT_TIMESTAMP, updated_at=CURRENT_TIMESTAMP
                 WHERE id=?
                """,
                (uid.lower(), comentario, inc_id),
            )
            if sector:
                existing = con.execute(
                    "SELECT monto_usd, saldo_usd FROM presupuestos WHERE centro=? AND sector=?",
                    (centro, sector),
                ).fetchone()
                if existing:
                    con.execute(
                        "UPDATE presupuestos SET monto_usd=monto_usd+?, saldo_usd=saldo_usd+? WHERE centro=? AND sector=?",
                        (monto, monto, centro, sector),
                    )
                else:
                    con.execute(
                        "INSERT INTO presupuestos (centro, sector, monto_usd, saldo_usd) VALUES (?,?,?,?)",
                        (centro, sector, monto, monto),
                    )
            else:
                existing = con.execute(
                    "SELECT monto_usd, saldo_usd FROM presupuestos WHERE centro=? AND (sector IS NULL OR sector='')",
                    (centro,),
                ).fetchone()
                if existing:
                    con.execute(
                        "UPDATE presupuestos SET monto_usd=monto_usd+?, saldo_usd=saldo_usd+? WHERE centro=? AND (sector IS NULL OR sector='')",
                        (monto, monto, centro),
                    )
                else:
                    con.execute(
                        "INSERT INTO presupuestos (centro, sector, monto_usd, saldo_usd) VALUES (?,?,?,?)",
                        (centro, None, monto, monto),
                    )
        elif accion == "rechazar":
            con.execute(
                """
                UPDATE presupuesto_incorporaciones
                   SET estado='rechazada', aprobador_id=?, comentario=?, resolved_at=CURRENT_TIMESTAMP, updated_at=CURRENT_TIMESTAMP
                 WHERE id=?
                """,
                (uid.lower(), comentario, inc_id),
            )
        else:
            return {"ok": False, "error": {"code": "BAD_ACTION", "message": "Acción no soportada"}}, 400
        con.commit()
        updated = con.execute(
            """
            SELECT id, centro, sector, monto, motivo, estado, solicitante_id, aprobador_id, comentario, created_at, updated_at, resolved_at
              FROM presupuesto_incorporaciones
             WHERE id=?
            """,
            (inc_id,),
        ).fetchone()
    return {"ok": True, "incorporacion": _serialize_increase(updated)}

