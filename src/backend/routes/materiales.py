from __future__ import annotations
from flask import Blueprint, request
from ..db import get_connection
from ..schemas import MaterialSearchQuery

bp = Blueprint("materiales", __name__, url_prefix="/api")

@bp.get("/materiales")
def search_materiales():
    params = MaterialSearchQuery(**request.args.to_dict())
    clauses: list[str] = []
    args: list[str] = []
    if params.codigo:
        like_code = f"%{params.codigo}%"
        clauses.append("codigo LIKE ? COLLATE NOCASE")
        args.append(like_code)
    if params.descripcion:
        like_desc = f"%{params.descripcion}%"
        clauses.append("descripcion LIKE ? COLLATE NOCASE")
        args.append(like_desc)
    if params.q:
        like_any = f"%{params.q}%"
        clauses.append("(codigo LIKE ? COLLATE NOCASE OR descripcion LIKE ? COLLATE NOCASE)")
        args.extend([like_any, like_any])
    where = " AND ".join(clauses) if clauses else "1=1"
    # Ajustar el límite de resultados según el tipo de búsqueda para permitir
    # catálogos más extensos cuando se usan filtros amplios (p.ej. un solo dígito).
    # Queremos ofrecer catálogos extensos cuando la búsqueda es amplia.
    # Garantizamos al menos 10.000 filas para que el frontend no se quede corto
    # al momento de autocompletar (el usuario reportó que sólo veía 2 ítems).
    limit = max(params.limit, 10_000)
    if params.codigo and not params.q and not params.descripcion and len(params.codigo.strip()) <= 2:
        limit = min(100_000, max(limit, 20_000))
    elif params.descripcion and not params.q and len(params.descripcion.strip()) <= 3:
        limit = min(100_000, max(limit, 15_000))
    else:
        limit = min(limit, 100_000)

    with get_connection() as con:
        cur = con.execute(
            """
            SELECT codigo, descripcion, descripcion_larga, unidad, precio_usd
            FROM materiales
            WHERE {where}
            ORDER BY descripcion COLLATE NOCASE, codigo COLLATE NOCASE
            LIMIT ?
            """.format(where=where), (*args, limit)
        )
        return [dict(r) for r in cur.fetchall()]

