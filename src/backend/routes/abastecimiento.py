from __future__ import annotations

import json
from flask import Blueprint, request, jsonify
from ..db import get_connection
from ..auth import authenticate_request, get_current_user, get_current_user_id
from ..roles import has_role
from ..schemas import (
    TrasladoCreate, TrasladoUpdate, SolpedCreate, SolpedUpdate,
    PurchaseOrderCreate, PurchaseOrderUpdate
)

bp = Blueprint("abastecimiento", __name__, url_prefix="/api/abastecimiento")

def _require_planner():
    user = get_current_user()
    if not user:
        authenticate_request()
        user = get_current_user()
    if not user:
        return None, ({"ok": False, "error": {"code": "unauthorized", "message": "Unauthorized"}}, 401)
    if not has_role(user, "planner", "planificador", "admin", "administrador"):
        return None, ({"ok": False, "error": {"code": "forbidden", "message": "Forbidden"}}, 403)
    uid_value = (get_current_user_id() or "").strip()
    if not uid_value:
        return None, ({"ok": False, "error": {"code": "unauthorized", "message": "Unauthorized"}}, 401)
    user = dict(user)
    user.setdefault("uid", uid_value)
    return user, None

def _require_admin():
    user = get_current_user()
    if not user:
        authenticate_request()
        user = get_current_user()
    if not user:
        return None, ({"ok": False, "error": {"code": "unauthorized", "message": "Unauthorized"}}, 401)
    if not has_role(user, "planner", "planificador", "admin", "administrador"):
        return None, ({"ok": False, "error": {"code": "forbidden", "message": "Forbidden"}}, 403)
    uid_value = (get_current_user_id() or "").strip()
    if not uid_value:
        return None, ({"ok": False, "error": {"code": "unauthorized", "message": "Unauthorized"}}, 401)
    user = dict(user)
    user.setdefault("uid", uid_value)
    return user, None

def _log(con, sol_id, uid, tipo, item_index=None, estado=None, payload=None):
    con.execute("""
        INSERT INTO solicitud_tratamiento_log (solicitud_id, item_index, actor_id, tipo, estado, payload_json)
        VALUES (?, ?, ?, ?, ?, ?)
    """, (sol_id, item_index, uid.lower(), tipo, estado, json.dumps(payload or {}, ensure_ascii=False)))

@bp.get("/timeline/<int:sol_id>")
def timeline(sol_id):
    user, err = _require_planner()
    if err:
        return err
    with get_connection() as con:
        rows = con.execute("""
            SELECT id, item_index, actor_id, tipo, estado, payload_json, created_at
            FROM solicitud_tratamiento_log
            WHERE solicitud_id = ? ORDER BY datetime(created_at)
        """, (sol_id,)).fetchall()
        out = []
        for r in rows:
            out.append({
                "id": r["id"], "item_index": r["item_index"],
                "actor": r["actor_id"], "tipo": r["tipo"], "estado": r["estado"],
                "payload": json.loads(r["payload_json"] or "{}"),
                "ts": r["created_at"]
            })
        return jsonify({"ok": True, "timeline": out})

@bp.post("/timeline/<int:sol_id>/nota")
def add_nota(sol_id):
    user, err = _require_planner()
    if err:
        return err
    data = request.get_json() or {}
    if not isinstance(data.get("texto"), str) or not data["texto"].strip():
        return jsonify({"ok": False, "error": {"code": "invalid_data", "message": "Texto requerido"}}), 400

    item_index = data.get("item_index")
    if item_index is not None and not isinstance(item_index, int):
        return jsonify({"ok": False, "error": {"code": "invalid_data", "message": "item_index debe ser entero o null"}}), 400

    with get_connection() as con:
        _log(con, sol_id, user["uid"], "nota", item_index, None, {"texto": data["texto"].strip()})
        con.commit()
    return jsonify({"ok": True})

@bp.post("/traslados")
def create_traslado():
    user, err = _require_planner()
    if err:
        return err
    data = request.get_json() or {}
    try:
        validated = TrasladoCreate(**data)
    except Exception as e:
        return jsonify({"ok": False, "error": {"code": "validation_error", "message": str(e)}}), 400

    with get_connection() as con:
        con.execute("BEGIN IMMEDIATE")
        try:
            cursor = con.execute("""
                INSERT INTO traslados (
                    solicitud_id, item_index, material, um, cantidad,
                    origen_centro, origen_almacen, origen_lote,
                    destino_centro, destino_almacen, created_by
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                validated.solicitud_id, validated.item_index, validated.material.upper(),
                validated.um, validated.cantidad, validated.origen_centro,
                validated.origen_almacen, validated.origen_lote, validated.destino_centro,
                validated.destino_almacen, user["uid"]
            ))
            traslado_id = cursor.lastrowid
            _log(con, validated.solicitud_id, user["uid"], "traslado_creado", validated.item_index, None, {
                "traslado_id": traslado_id,
                "origen": f"{validated.origen_centro}-{validated.origen_almacen}",
                "destino": f"{validated.destino_centro}-{validated.destino_almacen}",
                "cantidad": validated.cantidad
            })
            con.commit()
            return jsonify({"ok": True, "traslado_id": traslado_id})
        except Exception as e:
            con.rollback()
            return jsonify({"ok": False, "error": {"code": "db_error", "message": str(e)}}), 500

@bp.patch("/traslados/<int:traslado_id>")
def update_traslado(traslado_id):
    user, err = _require_planner()
    if err:
        return err
    data = request.get_json() or {}
    try:
        validated = TrasladoUpdate(**data)
    except Exception as e:
        return jsonify({"ok": False, "error": {"code": "validation_error", "message": str(e)}}), 400

    with get_connection() as con:
        con.execute("BEGIN IMMEDIATE")
        try:
            row = con.execute("SELECT solicitud_id, item_index, status FROM traslados WHERE id = ?", (traslado_id,)).fetchone()
            if not row:
                return jsonify({"ok": False, "error": {"code": "not_found", "message": "Traslado no encontrado"}}), 404

            con.execute("""
                UPDATE traslados SET status = ?, referencia = ?, updated_at = CURRENT_TIMESTAMP
                WHERE id = ?
            """, (validated.status, validated.referencia, traslado_id))

            if validated.status == "recibido":
                _log(con, row["solicitud_id"], user["uid"], "traslado_recibido", row["item_index"], None, {
                    "traslado_id": traslado_id,
                    "referencia": validated.referencia
                })

            con.commit()
            return jsonify({"ok": True})
        except Exception as e:
            con.rollback()
            return jsonify({"ok": False, "error": {"code": "db_error", "message": str(e)}}), 500

@bp.post("/solpeds")
def create_solped():
    user, err = _require_planner()
    if err:
        return err
    data = request.get_json() or {}
    try:
        validated = SolpedCreate(**data)
    except Exception as e:
        return jsonify({"ok": False, "error": {"code": "validation_error", "message": str(e)}}), 400

    with get_connection() as con:
        con.execute("BEGIN IMMEDIATE")
        try:
            cursor = con.execute("""
                INSERT INTO solpeds (
                    solicitud_id, item_index, material, um, cantidad,
                    precio_unitario_est, created_by
                ) VALUES (?, ?, ?, ?, ?, ?, ?)
            """, (
                validated.solicitud_id, validated.item_index, validated.material.upper(),
                validated.um, validated.cantidad, validated.precio_unitario_est or 0, user["uid"]
            ))
            solped_id = cursor.lastrowid
            _log(con, validated.solicitud_id, user["uid"], "solped_creada", validated.item_index, None, {
                "solped_id": solped_id,
                "numero": validated.numero
            })
            con.commit()
            return jsonify({"ok": True, "solped_id": solped_id})
        except Exception as e:
            con.rollback()
            return jsonify({"ok": False, "error": {"code": "db_error", "message": str(e)}}), 500

@bp.patch("/solpeds/<int:solped_id>")
def update_solped(solped_id):
    user, err = _require_planner()
    if err:
        return err
    data = request.get_json() or {}
    try:
        validated = SolpedUpdate(**data)
    except Exception as e:
        return jsonify({"ok": False, "error": {"code": "validation_error", "message": str(e)}}), 400

    with get_connection() as con:
        con.execute("BEGIN IMMEDIATE")
        try:
            row = con.execute("SELECT solicitud_id, item_index FROM solpeds WHERE id = ?", (solped_id,)).fetchone()
            if not row:
                return jsonify({"ok": False, "error": {"code": "not_found", "message": "SOLPED no encontrada"}}), 404

            con.execute("""
                UPDATE solpeds SET status = ?, numero = ?, updated_at = CURRENT_TIMESTAMP
                WHERE id = ?
            """, (validated.status, validated.numero, solped_id))

            if validated.status == "liberada":
                _log(con, row["solicitud_id"], user["uid"], "solped_liberada", row["item_index"], None, {
                    "solped_id": solped_id,
                    "numero": validated.numero
                })

            con.commit()
            return jsonify({"ok": True})
        except Exception as e:
            con.rollback()
            return jsonify({"ok": False, "error": {"code": "db_error", "message": str(e)}}), 500

@bp.post("/po")
def create_po():
    user, err = _require_planner()
    if err:
        return err
    data = request.get_json() or {}
    try:
        validated = PurchaseOrderCreate(**data)
    except Exception as e:
        return jsonify({"ok": False, "error": {"code": "validation_error", "message": str(e)}}), 400

    with get_connection() as con:
        con.execute("BEGIN IMMEDIATE")
        try:
            cursor = con.execute("""
                INSERT INTO purchase_orders (
                    solped_id, solicitud_id, proveedor_email, proveedor_nombre,
                    numero, subtotal, moneda, created_by
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                validated.solped_id, validated.solicitud_id, validated.proveedor_email,
                validated.proveedor_nombre, validated.numero, validated.subtotal or 0,
                validated.moneda or "USD", user["uid"]
            ))
            po_id = cursor.lastrowid
            _log(con, validated.solicitud_id, user["uid"], "po_emitida", None, None, {
                "po_id": po_id,
                "solped_id": validated.solped_id,
                "numero": validated.numero,
                "proveedor": validated.proveedor_email
            })
            con.commit()
            return jsonify({"ok": True, "po_id": po_id})
        except Exception as e:
            con.rollback()
            return jsonify({"ok": False, "error": {"code": "db_error", "message": str(e)}}), 500

@bp.post("/po/<int:po_id>/enviar")
def send_po(po_id):
    user, err = _require_planner()
    if err:
        return err

    with get_connection() as con:
        con.execute("BEGIN IMMEDIATE")
        try:
            row = con.execute("""
                SELECT po.solicitud_id, po.numero, po.proveedor_email, po.proveedor_nombre,
                       s.centro, s.sector, sol.material, sol.cantidad, sol.precio_unitario_est
                FROM purchase_orders po
                JOIN solpeds sol ON po.solped_id = sol.id
                JOIN solicitudes s ON po.solicitud_id = s.id
                WHERE po.id = ?
            """, (po_id,)).fetchone()
            if not row:
                return jsonify({"ok": False, "error": {"code": "not_found", "message": "PO no encontrada"}}), 404

            # Crear email HTML simple
            subject = f"Pedido de Compra #{row['numero']}"
            body = f"""
            <html><body>
            <h2>Pedido de Compra #{row['numero']}</h2>
            <p>Proveedor: {row['proveedor_nombre']}</p>
            <p>Centro: {row['centro']} | Sector: {row['sector']}</p>
            <table border="1">
            <tr><th>Material</th><th>Cantidad</th><th>Precio Unit.</th><th>Total</th></tr>
            <tr>
                <td>{row['material']}</td>
                <td>{row['cantidad']}</td>
                <td>${row['precio_unitario_est']:.2f}</td>
                <td>${(row['cantidad'] * row['precio_unitario_est']):.2f}</td>
            </tr>
            </table>
            <p>Por favor confirme recepción y términos de entrega.</p>
            </body></html>
            """

            con.execute("""
                INSERT INTO outbox_emails (to_email, subject, body)
                VALUES (?, ?, ?)
            """, (row['proveedor_email'], subject, body))

            con.execute("UPDATE purchase_orders SET status = 'enviada' WHERE id = ?", (po_id,))

            _log(con, row['solicitud_id'], user["uid"], "po_enviada", None, None, {
                "po_id": po_id,
                "numero": row['numero']
            })

            con.commit()
            return jsonify({"ok": True})
        except Exception as e:
            con.rollback()
            return jsonify({"ok": False, "error": {"code": "db_error", "message": str(e)}}), 500

@bp.patch("/po/<int:po_id>")
def update_po(po_id):
    user, err = _require_planner()
    if err:
        return err
    data = request.get_json() or {}
    try:
        validated = PurchaseOrderUpdate(**data)
    except Exception as e:
        return jsonify({"ok": False, "error": {"code": "validation_error", "message": str(e)}}), 400

    with get_connection() as con:
        con.execute("BEGIN IMMEDIATE")
        try:
            row = con.execute("SELECT solicitud_id FROM purchase_orders WHERE id = ?", (po_id,)).fetchone()
            if not row:
                return jsonify({"ok": False, "error": {"code": "not_found", "message": "PO no encontrada"}}), 404

            con.execute("UPDATE purchase_orders SET status = ?, updated_at = CURRENT_TIMESTAMP WHERE id = ?", (validated.status, po_id))

            tipo_log = f"po_{validated.status.replace('_', '')}"
            _log(con, row['solicitud_id'], user["uid"], tipo_log, None, None, {
                "po_id": po_id
            })

            con.commit()
            return jsonify({"ok": True})
        except Exception as e:
            con.rollback()
            return jsonify({"ok": False, "error": {"code": "db_error", "message": str(e)}}), 500

@bp.post("/admin/outbox/send_all")
def send_all_emails():
    user, err = _require_admin()
    if err:
        return err

    with get_connection() as con:
        try:
            con.execute("""
                UPDATE outbox_emails SET status = 'sent', sent_at = CURRENT_TIMESTAMP
                WHERE status = 'queued'
            """)
            con.commit()
            return jsonify({"ok": True})
        except Exception as e:
            return jsonify({"ok": False, "error": {"code": "db_error", "message": str(e)}}), 500