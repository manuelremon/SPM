from __future__ import annotations
import sqlite3
from flask import Blueprint, request, current_app, jsonify
from typing import Any, Dict, Optional, Tuple
from ..db import get_connection
from ..auth import auth_required
from .admin import CATALOG_RESOURCES

bp = Blueprint("catalogos", __name__, url_prefix="/api/catalogos")
almacenes_bp = Blueprint("almacenes", __name__, url_prefix="/api/almacenes")

_ALLOWED_ORDER_SUFFIX = {"ASC", "DESC", "COLLATE", "NOCASE"}


def _row_to_item(meta: Dict[str, Any], row: Dict[str, Any]) -> Dict[str, Any]:
    item = dict(row)
    for boolean_field in meta.get("bools", ()):  # type: ignore[arg-type]
        if boolean_field in item:
            item[boolean_field] = bool(item[boolean_field])
    return item


def _table_exists(con: sqlite3.Connection, name: str) -> bool:
    try:
        row = con.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name=? LIMIT 1",
            (name,),
        ).fetchone()
    except sqlite3.Error:
        raise
    return bool(row)


def _sanitize_order_by(meta: Dict[str, Any]) -> str:
    raw = str(meta.get("order_by") or "id")
    columns = set(meta.get("fields", ())) | {"id"}
    segments = [segment.strip() for segment in raw.split(",") if segment.strip()]
    sanitized: list[str] = []
    for segment in segments or ["id"]:
        parts = segment.split()
        column = parts[0]
        if column not in columns:
            raise ValueError(f"order_by column '{column}' not allowed")
        extras = [token.upper() for token in parts[1:]]
        if any(token not in _ALLOWED_ORDER_SUFFIX for token in extras):
            raise ValueError(f"order_by modifier '{' '.join(parts[1:])}' not allowed")
        sanitized.append(" ".join([column] + parts[1:]))
    return ", ".join(sanitized) if sanitized else "id"


def _fetch_catalog(
    con: sqlite3.Connection,
    resource: str,
    *,
    include_inactive: bool = False,
) -> Tuple[Optional[list], Optional[Dict[str, Any]]]:
    meta = CATALOG_RESOURCES.get(resource)
    if not meta:
        return None, None
    table = meta["table"]
    if not _table_exists(con, table):
        current_app.logger.warning("Tabla de catalogo faltante: %s (resource=%s)", table, resource)
        return [], {"resource": resource, "message": f"Tabla {table} ausente"}
    try:
        order_by = _sanitize_order_by(meta)
    except ValueError as exc:
        current_app.logger.warning("Order by invalido para catalogo %s: %s", resource, exc)
        return [], {"resource": resource, "message": "Configuracion de orden invalida"}
    try:
        rows = con.execute(f"SELECT * FROM {table} ORDER BY {order_by}").fetchall()
    except sqlite3.Error:
        current_app.logger.exception("Error consultando catalogo %s", resource)
        raise
    items = []
    for row in rows:
        item = _row_to_item(meta, row)
        if not include_inactive and "activo" in meta.get("fields", ()):  # type: ignore[arg-type]
            if not item.get("activo", False):
                continue
        items.append(item)
    return items, None


@bp.get("")
@auth_required
def obtener_catalogos():
    include_inactive_raw = (request.args.get("include_inactive") or "0").lower()
    include_inactive = include_inactive_raw in {"1", "true", "si", "sí"}
    resource = (request.args.get("resource") or "").strip()
    try:
        with get_connection() as con:
            if resource:
                items, warning = _fetch_catalog(con, resource, include_inactive=include_inactive)
                if items is None:
                    return {"ok": False, "error": {"code": "UNKNOWN", "message": "Recurso desconocido"}}, 404
                if warning:
                    current_app.logger.warning("Catalog warning: %s", warning)
                return jsonify(items or [])
            data: Dict[str, Any] = {}
            warnings = []
            for name in CATALOG_RESOURCES:
                items, warning = _fetch_catalog(con, name, include_inactive=include_inactive)
                if warning:
                    warnings.append(warning)
                data[name] = items or []
    except sqlite3.Error as exc:
        current_app.logger.exception("Error consultando catalogos: %s", exc)
        return {"ok": False, "error": {"code": "DB_ERROR", "message": "DB error"}}, 500
    response: Dict[str, Any] = {"ok": True, "data": data}
    if warnings:
        response["warnings"] = warnings
    return response


@bp.get("/<resource>")
@auth_required
def obtener_catalogo(resource: str):
    include_inactive_raw = request.args.get("include_inactive", "0").lower()
    include_inactive = include_inactive_raw in {"1", "true", "si", "s\u00ed"}
    try:
        with get_connection() as con:
            items, warning = _fetch_catalog(con, resource, include_inactive=include_inactive)
            if items is None:
                return {"ok": False, "error": {"code": "UNKNOWN", "message": "Recurso desconocido"}}, 404
            response: Dict[str, Any] = {"ok": True, "items": items}
            if warning:
                response["warnings"] = [warning]
            return response
    except sqlite3.Error:
        current_app.logger.exception("Error consultando catalogo %s", resource)
        return {"ok": False, "error": {"code": "DB_ERROR", "message": "DB error"}}, 500


@almacenes_bp.get("")
@auth_required
def obtener_almacenes():
    raw = (request.args.get("centro") or "").strip()
    centro = None if not raw or raw.lower() == "todos" else raw
    params = (centro, centro)
    try:
        with get_connection() as con:
            rows = con.execute(
                """
                SELECT id, codigo, nombre, centro_codigo, activo
                FROM catalog_almacenes
                WHERE activo = 1
                  AND (? IS NULL OR centro_codigo = ?)
                ORDER BY nombre
                """,
                params,
            ).fetchall()
    except sqlite3.OperationalError:
        current_app.logger.warning("Tabla catalog_almacenes ausente")
        return jsonify([])
    except sqlite3.Error as exc:
        current_app.logger.exception("Error consultando almacenes: %s", exc)
        return jsonify([])
    items = []
    for row in rows:
        items.append(
            {
                "id": row.get("id"),
                "codigo": row.get("codigo") or row.get("id"),
                "nombre": row.get("nombre"),
                "centro": row.get("centro_codigo"),
                "activo": bool(row.get("activo", 0)),
            }
        )
    current_app.logger.debug("Almacenes devueltos: %d (centro=%s)", len(items), centro or "todos")
    return jsonify(items)
