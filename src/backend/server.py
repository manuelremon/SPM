from fastapi import FastAPI, Query, HTTPException
from typing import Optional, List
import sqlite3

from .config import Settings

app = FastAPI(title="SPM Local API", version="1.1")

DB_PATH = Settings.DB_PATH

def rows_to_dicts(cur):
    cur.row_factory = sqlite3.Row
    return [dict(r) for r in cur.fetchall()]

@app.get("/")
def root():
    return {"status": "Servidor MCP SPM activo 🚀"}

@app.get("/usuarios")
def get_usuarios(limit: int = Query(50, ge=1, le=200), offset: int = Query(0, ge=0)):
    con = sqlite3.connect(DB_PATH)
    con.row_factory = sqlite3.Row
    cur = con.cursor()
    cur.execute("SELECT id_spm, nombre, apellido FROM usuarios LIMIT ? OFFSET ?", (limit, offset))
    data = [dict(r) for r in cur.fetchall()]
    con.close()
    return {"count": len(data), "usuarios": data}

@app.get("/solicitudes")
def get_solicitudes(
    status: Optional[str] = Query(None, description="pendiente|aprobada|en_tratamiento|rechazada"),
    centro: Optional[str] = Query(None),
    planner_id: Optional[int] = Query(None, ge=0),
    fecha_desde: Optional[str] = Query(None, description="YYYY-MM-DD"),
    fecha_hasta: Optional[str] = Query(None, description="YYYY-MM-DD"),
    q: Optional[str] = Query(None, description="busca en justificacion"),
    order_by: str = Query("created_at", description="campo para ordenar"),
    order: str = Query("desc", regex="^(asc|desc)$"),
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
):
    # Campos permitidos para ordenar (para evitar SQL injection)
    allowed_order_by = {"id", "status", "centro", "planner_id", "created_at", "updated_at", "total_monto"}
    if order_by not in allowed_order_by:
        raise HTTPException(status_code=400, detail=f"order_by inválido. Permitidos: {sorted(list(allowed_order_by))}")

    where: List[str] = []
    params: List = []

    if status:
        where.append("status = ?")
        params.append(status)

    if centro:
        where.append("centro = ?")
        params.append(centro)

    if planner_id is not None:
        where.append("planner_id = ?")
        params.append(planner_id)

    # Fechas (asumiendo columnas created_at/updated_at en formato ISO)
    if fecha_desde:
        where.append("(date(created_at) >= date(?))")
        params.append(fecha_desde)
    if fecha_hasta:
        where.append("(date(created_at) <= date(?))")
        params.append(fecha_hasta)

    if q:
        where.append("lower(justificacion) LIKE lower(?)")
        params.append(f"%{q}%")

    sql = "SELECT * FROM solicitudes"
    if where:
        sql += " WHERE " + " AND ".join(where)

    # Orden + paginación
    sql += f" ORDER BY {order_by} {order.upper()} LIMIT ? OFFSET ?"
    params.extend([limit, offset])

    con = sqlite3.connect(DB_PATH)
    con.row_factory = sqlite3.Row
    cur = con.cursor()
    cur.execute(sql, params)
    data = [dict(r) for r in cur.fetchall()]
    con.close()

    return {"count": len(data), "items": data, "meta": {"limit": limit, "offset": offset, "order_by": order_by, "order": order}}

@app.get("/solicitudes/{sol_id}")
def get_solicitud(sol_id: int):
    con = sqlite3.connect(DB_PATH)
    con.row_factory = sqlite3.Row
    cur = con.cursor()
    cur.execute("SELECT * FROM solicitudes WHERE id = ?", (sol_id,))
    row = cur.fetchone()
    con.close()
    if not row:
        raise HTTPException(status_code=404, detail="Solicitud no encontrada")
    return {"solicitud": dict(row)}

@app.get("/materiales")
def get_materiales(
    codigo: Optional[str] = Query(None, description="Filtra por código exacto o parcial"),
    descripcion: Optional[str] = Query(None, description="Busca texto en la descripción"),
    unidad: Optional[str] = Query(None, description="Filtra por unidad de medida"),
    centro: Optional[str] = Query(None, description="Filtra por centro (si existe el campo)"),
    criticidad: Optional[str] = Query(None, description="Alta, Media, Baja"),
    order_by: str = Query("codigo", description="Campo para ordenar"),
    order: str = Query("asc", regex="^(asc|desc)$"),
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
):
    allowed_order_by = {"codigo", "descripcion", "unidad", "created_at"}
    if order_by not in allowed_order_by:
        raise HTTPException(status_code=400, detail=f"order_by inválido. Permitidos: {sorted(list(allowed_order_by))}")

    sql = "SELECT * FROM materiales"
    where = []
    params = []

    if codigo:
        where.append("codigo LIKE ?")
        params.append(f"%{codigo}%")

    if descripcion:
        where.append("descripcion LIKE ?")
        params.append(f"%{descripcion}%")

    if unidad:
        where.append("unidad = ?")
        params.append(unidad)

    if centro:
        where.append("centro = ?")
        params.append(centro)

    if criticidad:
        where.append("criticidad = ?")
        params.append(criticidad)

    if where:
        sql += " WHERE " + " AND ".join(where)

    sql += f" ORDER BY {order_by} {order.upper()} LIMIT ? OFFSET ?"
    params.extend([limit, offset])

    con = sqlite3.connect(DB_PATH)
    con.row_factory = sqlite3.Row
    cur = con.cursor()
    cur.execute(sql, params)
    data = [dict(r) for r in cur.fetchall()]
    con.close()

    return {
        "count": len(data),
        "items": data,
        "meta": {
            "limit": limit,
            "offset": offset,
            "order_by": order_by,
            "order": order,
            "filters": {k: v for k, v in locals().items() if k in ['codigo','descripcion','unidad','centro','criticidad'] and v}
        }
    }

