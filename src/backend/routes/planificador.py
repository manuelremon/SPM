from __future__ import annotations

import json
from flask import Blueprint, request

from ..auth import authenticate_request, get_current_user, get_current_user_id
from ..db import get_connection

bp = Blueprint("spm_planner_blueprint", __name__, url_prefix="/api/planificador")

def _require_planner():
    user = get_current_user()
    if not user:
        authenticate_request()
        user = get_current_user()
    if not user:
        return None, ({"ok": False, "error": {"code": "unauthorized", "message": "Unauthorized"}}, 401)
    uid = (get_current_user_id() or "").strip()
    if not uid:
        return None, ({"ok": False, "error": {"code": "unauthorized", "message": "Unauthorized"}}, 401)
    with get_connection() as con:
        row = con.execute("SELECT rol FROM usuarios WHERE lower(id_spm)=?", (uid.lower(),)).fetchone()
        if not row:
            return None, ({"ok": False, "error": {"code": "forbidden", "message": "Forbidden"}}, 403)
        role = (row["rol"] or "").lower()
        if not any(r in role for r in ["planner", "planificador", "admin", "administrador"]):
            return None, ({"ok": False, "error": {"code": "forbidden", "message": "Forbidden"}}, 403)
    return uid, None

def _log_event(con, solicitud_id, planner_id, tipo, payload: dict | None = None):
    pj = json.dumps(payload or {}, ensure_ascii=False)
    con.execute("""
        INSERT INTO solicitud_tratamiento_eventos (solicitud_id, planner_id, tipo, payload_json)
        VALUES (?, ?, ?, ?)
    """, (solicitud_id, planner_id.lower(), tipo, pj))

def _recalcular_total(con, solicitud_id, items_originales):
    # Leer rows de solicitud_items_tratamiento y combinar con items_originales
    # Para 'stock' usar 0, para 'compra'/'equivalente' usar precio estimado o el original
    # UPDATE solicitudes SET total_monto=?, updated_at=CURRENT_TIMESTAMP WHERE id=?
    rows = con.execute("""
        SELECT item_index, decision, cantidad_aprobada, precio_unitario_estimado
        FROM solicitud_items_tratamiento
        WHERE solicitud_id = ?
    """, (solicitud_id,)).fetchall()
    total = 0.0
    for row in rows:
        idx = row["item_index"]
        decision = row["decision"]
        cant = row["cantidad_aprobada"]
        precio_est = row["precio_unitario_estimado"]
        if decision in ("compra", "equivalente", "servicio"):
            # Usar precio estimado si existe, sino el original
            precio = precio_est if precio_est is not None else items_originales[idx].get("precio_unitario", 0)
            total += cant * precio
        # Para stock, 0
    con.execute("""
        UPDATE solicitudes SET total_monto = ?, updated_at = CURRENT_TIMESTAMP WHERE id = ?
    """, (total, solicitud_id))

@bp.route("/queue", methods=["GET"])
def get_queue():
    uid, err = _require_planner()
    if err:
        return err
    # Filtros
    centro = request.args.get("centro", "").strip()
    sector = request.args.get("sector", "").strip()
    almacen = request.args.get("almacen_virtual", "").strip()
    criticidad = request.args.get("criticidad", "").strip()
    q = request.args.get("q", "").strip()
    desde = request.args.get("desde", "").strip()
    hasta = request.args.get("hasta", "").strip()
    limit = min(int(request.args.get("limit", 20)), 100)
    offset_mias = int(request.args.get("offset_mias", 0))
    offset_pend = int(request.args.get("offset_pend", 0))

    with get_connection() as con:
        # Mis solicitudes
        query_mias = """
            SELECT s.id, s.centro, s.sector, s.criticidad, s.total_monto, s.updated_at, COUNT(si.id) as items_count
            FROM solicitudes s
            LEFT JOIN solicitud_items_tratamiento si ON s.id = si.solicitud_id
            WHERE s.status = 'en_tratamiento' AND lower(s.planner_id) = ?
        """
        params_mias = [uid.lower()]
        if centro:
            query_mias += " AND s.centro = ?"
            params_mias.append(centro)
        if sector:
            query_mias += " AND s.sector = ?"
            params_mias.append(sector)
        if almacen:
            query_mias += " AND s.almacen_virtual = ?"
            params_mias.append(almacen)
        if criticidad:
            query_mias += " AND s.criticidad = ?"
            params_mias.append(criticidad)
        if q:
            query_mias += " AND (s.id LIKE ? OR s.justificacion LIKE ?)"
            params_mias.extend([f"%{q}%", f"%{q}%"])
        if desde:
            query_mias += " AND s.updated_at >= ?"
            params_mias.append(desde)
        if hasta:
            query_mias += " AND s.updated_at <= ?"
            params_mias.append(hasta)
        query_mias += " GROUP BY s.id ORDER BY s.updated_at DESC LIMIT ? OFFSET ?"
        params_mias.extend([limit, offset_mias])
        mias = con.execute(query_mias, params_mias).fetchall()

        # Pendientes
        query_pend = """
            SELECT s.id, s.centro, s.sector, s.criticidad, s.total_monto, s.updated_at, COUNT(si.id) as items_count
            FROM solicitudes s
            LEFT JOIN solicitud_items_tratamiento si ON s.id = si.solicitud_id
            WHERE s.status = 'en_tratamiento' AND (s.planner_id IS NULL OR s.planner_id = '')
            AND EXISTS (
                SELECT 1 FROM planificador_asignaciones pa
                WHERE pa.planificador_id = ? AND pa.activo = 1
                AND (pa.centro IS NULL OR pa.centro = s.centro)
                AND (pa.sector IS NULL OR pa.sector = s.sector)
                AND (pa.almacen_virtual IS NULL OR pa.almacen_virtual = s.almacen_virtual)
            )
        """
        params_pend = [uid.lower()]
        if centro:
            query_pend += " AND s.centro = ?"
            params_pend.append(centro)
        if sector:
            query_pend += " AND s.sector = ?"
            params_pend.append(sector)
        if almacen:
            query_pend += " AND s.almacen_virtual = ?"
            params_pend.append(almacen)
        if criticidad:
            query_pend += " AND s.criticidad = ?"
            params_pend.append(criticidad)
        if q:
            query_pend += " AND (s.id LIKE ? OR s.justificacion LIKE ?)"
            params_pend.extend([f"%{q}%", f"%{q}%"])
        if desde:
            query_pend += " AND s.updated_at >= ?"
            params_pend.append(desde)
        if hasta:
            query_pend += " AND s.updated_at <= ?"
            params_pend.append(hasta)
        query_pend += " GROUP BY s.id ORDER BY s.updated_at DESC LIMIT ? OFFSET ?"
        params_pend.extend([limit, offset_pend])
        pendientes = con.execute(query_pend, params_pend).fetchall()

        # Counts
        count_mias = len(mias)  # Para simplificar, usar len; en prod contar total sin limit
        count_pend = len(pendientes)

    return {"ok": True, "mias": [dict(r) for r in mias], "pendientes": [dict(r) for r in pendientes], "count": {"mias": count_mias, "pendientes": count_pend}}

@bp.route("/solicitudes/<int:solicitud_id>/tomar", methods=["PATCH"])
def tomar_solicitud(solicitud_id):
    uid, err = _require_planner()
    if err:
        return err
    with get_connection() as con:
        row = con.execute("SELECT status, planner_id FROM solicitudes WHERE id = ?", (solicitud_id,)).fetchone()
        if not row:
            return {"ok": False, "error": {"code": "not_found", "message": "Solicitud no encontrada"}}, 404
        if row["status"] != "en_tratamiento":
            return {"ok": False, "error": {"code": "invalid_status", "message": "Estado inválido"}}, 400
        if row["planner_id"] and row["planner_id"].lower() != uid.lower():
            return {"ok": False, "error": {"code": "already_assigned", "message": "Ya asignada a otro planner"}}, 400
        con.execute("UPDATE solicitudes SET planner_id = ? WHERE id = ?", (uid, solicitud_id))
        _log_event(con, solicitud_id, uid, "tomar")
        # Notificar solicitante
        sol_row = con.execute("SELECT id_usuario FROM solicitudes WHERE id = ?", (solicitud_id,)).fetchone()
        if sol_row:
            con.execute("""
                INSERT INTO notificaciones (destinatario_id, solicitud_id, mensaje)
                VALUES (?, ?, ?)
            """, (sol_row["id_usuario"], solicitud_id, f"Solicitud #{solicitud_id} tomada por planificador"))
    return {"ok": True}

@bp.route("/solicitudes/<int:solicitud_id>/liberar", methods=["PATCH"])
def liberar_solicitud(solicitud_id):
    uid, err = _require_planner()
    if err:
        return err
    with get_connection() as con:
        row = con.execute("SELECT status, planner_id FROM solicitudes WHERE id = ?", (solicitud_id,)).fetchone()
        if not row or row["status"] != "en_tratamiento" or row["planner_id"].lower() != uid.lower():
            return {"ok": False, "error": {"code": "forbidden", "message": "No autorizado"}}, 403
        con.execute("UPDATE solicitudes SET planner_id = NULL WHERE id = ?", (solicitud_id,))
        _log_event(con, solicitud_id, uid, "liberar")
    return {"ok": True}

@bp.route("/solicitudes/<int:solicitud_id>/tratamiento", methods=["GET"])
def get_tratamiento(solicitud_id):
    uid, err = _require_planner()
    if err:
        return err
    with get_connection() as con:
        sol = con.execute("""
            SELECT id, centro, sector, justificacion, status, data_json, total_monto
            FROM solicitudes WHERE id = ?
        """, (solicitud_id,)).fetchone()
        if not sol:
            return {"ok": False, "error": {"code": "not_found", "message": "Solicitud no encontrada"}}, 404
        trat = con.execute("""
            SELECT item_index, decision, cantidad_aprobada, codigo_equivalente, proveedor_sugerido, precio_unitario_estimado, comentario, updated_at
            FROM solicitud_items_tratamiento WHERE solicitud_id = ?
        """, (solicitud_id,)).fetchall()
    return {"ok": True, "solicitud": dict(sol), "tratamiento": [dict(r) for r in trat]}

@bp.route("/solicitudes/<int:solicitud_id>/tratamiento/items", methods=["PATCH"])
def update_items(solicitud_id):
    uid, err = _require_planner()
    if err:
        return err
    data = request.get_json()
    if not data or "items" not in data:
        return {"ok": False, "error": {"code": "bad_request", "message": "Faltan items"}}, 400
    items = data["items"]
    with get_connection() as con:
        sol = con.execute("SELECT status, planner_id, data_json FROM solicitudes WHERE id = ?", (solicitud_id,)).fetchone()
        if not sol or sol["status"] != "en_tratamiento" or sol["planner_id"].lower() != uid.lower():
            return {"ok": False, "error": {"code": "forbidden", "message": "No autorizado"}}, 403
        items_originales = json.loads(sol["data_json"])["items"]
        for item in items:
            idx = item["item_index"]
            if idx < 0 or idx >= len(items_originales):
                return {"ok": False, "error": {"code": "bad_request", "message": f"Ítem {idx} inválido"}}, 400
            con.execute("""
                INSERT OR REPLACE INTO solicitud_items_tratamiento
                (solicitud_id, item_index, decision, cantidad_aprobada, codigo_equivalente, proveedor_sugerido, precio_unitario_estimado, comentario, updated_by, updated_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP)
            """, (
                solicitud_id, idx, item["decision"], item["cantidad_aprobada"],
                item.get("codigo_equivalente"), item.get("proveedor_sugerido"),
                item.get("precio_unitario_estimado"), item.get("comentario"), uid
            ))
        _recalcular_total(con, solicitud_id, items_originales)
        _log_event(con, solicitud_id, uid, "editar_item", {"items": items})
    return {"ok": True}

@bp.route("/solicitudes/<int:solicitud_id>/finalizar", methods=["POST"])
def finalizar_solicitud(solicitud_id):
    uid, err = _require_planner()
    if err:
        return err
    with get_connection() as con:
        sol = con.execute("SELECT status, planner_id, id_usuario, aprobador_id FROM solicitudes WHERE id = ?", (solicitud_id,)).fetchone()
        if not sol or sol["status"] != "en_tratamiento" or sol["planner_id"].lower() != uid.lower():
            return {"ok": False, "error": {"code": "forbidden", "message": "No autorizado"}}, 403
        # Verificar que hay decisiones
        count = con.execute("SELECT COUNT(*) FROM solicitud_items_tratamiento WHERE solicitud_id = ?", (solicitud_id,)).fetchone()[0]
        if count == 0:
            # Aplicar defaults: compra con cantidades originales
            data_json = json.loads(con.execute("SELECT data_json FROM solicitudes WHERE id = ?", (solicitud_id,)).fetchone()["data_json"])
            for idx, it in enumerate(data_json["items"]):
                con.execute("""
                    INSERT INTO solicitud_items_tratamiento
                    (solicitud_id, item_index, decision, cantidad_aprobada, precio_unitario_estimado, updated_by)
                    VALUES (?, ?, 'compra', ?, ?, ?)
                """, (solicitud_id, idx, it["cantidad"], it.get("precio_unitario"), uid))
        con.execute("UPDATE solicitudes SET status = 'finalizada', updated_at = CURRENT_TIMESTAMP WHERE id = ?", (solicitud_id,))
        _log_event(con, solicitud_id, uid, "finalizar", {"total_monto": sol["total_monto"]})
        # Notificar
        for dest in [sol["id_usuario"], sol["aprobador_id"]]:
            if dest:
                con.execute("""
                    INSERT INTO notificaciones (destinatario_id, solicitud_id, mensaje)
                    VALUES (?, ?, ?)
                """, (dest, solicitud_id, f"Solicitud #{solicitud_id} finalizada por planificador"))
    return {"ok": True}

@bp.route("/solicitudes/<int:solicitud_id>/rechazar", methods=["POST"])
def rechazar_solicitud(solicitud_id):
    uid, err = _require_planner()
    if err:
        return err
    data = request.get_json()
    motivo = (data or {}).get("motivo", "").strip()
    if len(motivo) < 3 or len(motivo) > 500:
        return {"ok": False, "error": {"code": "bad_request", "message": "Motivo inválido"}}, 400
    with get_connection() as con:
        sol = con.execute("SELECT status, planner_id, id_usuario, aprobador_id FROM solicitudes WHERE id = ?", (solicitud_id,)).fetchone()
        if not sol or sol["status"] != "en_tratamiento" or sol["planner_id"].lower() != uid.lower():
            return {"ok": False, "error": {"code": "forbidden", "message": "No autorizado"}}, 403
        con.execute("UPDATE solicitudes SET status = 'rechazada' WHERE id = ?", (solicitud_id,))
        _log_event(con, solicitud_id, uid, "rechazar", {"motivo": motivo})
        # Notificar
        for dest in [sol["id_usuario"], sol["aprobador_id"]]:
            if dest:
                con.execute("""
                    INSERT INTO notificaciones (destinatario_id, solicitud_id, mensaje)
                    VALUES (?, ?, ?)
                """, (dest, solicitud_id, f"Solicitud #{solicitud_id} rechazada: {motivo}"))
    return {"ok": True}

@bp.route("/estadisticas", methods=["GET"])
def get_estadisticas():
    uid, err = _require_planner()
    if err:
        return err
    desde = request.args.get("desde", "").strip()
    hasta = request.args.get("hasta", "").strip()
    with get_connection() as con:
        query = """
            SELECT status, COUNT(*) as count
            FROM solicitudes
            WHERE planner_id = ?
        """
        params = [uid]
        if desde:
            query += " AND updated_at >= ?"
            params.append(desde)
        if hasta:
            query += " AND updated_at <= ?"
            params.append(hasta)
        query += " GROUP BY status"
        stats = {r["status"]: r["count"] for r in con.execute(query, params).fetchall()}
        # Tiempos promedio (simplificado)
        t_hrs = 0  # Placeholder
        # Top centros
        top = con.execute("""
            SELECT centro, COUNT(*) as count, SUM(total_monto) as monto
            FROM solicitudes
            WHERE planner_id = ? AND status IN ('finalizada', 'rechazada')
            GROUP BY centro ORDER BY count DESC LIMIT 5
        """, (uid,)).fetchall()
    return {
        "ok": True,
        "periodo": {"desde": desde or None, "hasta": hasta or None},
        "kpis": {
            "en_tratamiento": stats.get("en_tratamiento", 0),
            "finalizadas": stats.get("finalizada", 0),
            "rechazadas": stats.get("rechazada", 0),
            "t_hrs_promedio": t_hrs
        },
        "top_centros": [dict(r) for r in top]
    }
