from __future__ import annotations
from typing import Dict, Iterable, Optional
from logging import Logger
from .config import Settings
from .db import get_connection

CATALOG_TABLES: Dict[str, str] = {
    "catalog_centros": """
        CREATE TABLE IF NOT EXISTS catalog_centros (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            codigo TEXT UNIQUE NOT NULL,
            nombre TEXT,
            descripcion TEXT,
            notas TEXT,
            activo INTEGER DEFAULT 1,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP,
            updated_at TEXT DEFAULT CURRENT_TIMESTAMP
        )
    """,
    "catalog_almacenes": """
        CREATE TABLE IF NOT EXISTS catalog_almacenes (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            codigo TEXT UNIQUE NOT NULL,
            nombre TEXT,
            centro_codigo TEXT,
            descripcion TEXT,
            activo INTEGER DEFAULT 1,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP,
            updated_at TEXT DEFAULT CURRENT_TIMESTAMP
        )
    """,
    "catalog_roles": """
        CREATE TABLE IF NOT EXISTS catalog_roles (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            nombre TEXT UNIQUE NOT NULL,
            descripcion TEXT,
            activo INTEGER DEFAULT 1,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP,
            updated_at TEXT DEFAULT CURRENT_TIMESTAMP
        )
    """,
    "catalog_puestos": """
        CREATE TABLE IF NOT EXISTS catalog_puestos (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            nombre TEXT UNIQUE NOT NULL,
            descripcion TEXT,
            activo INTEGER DEFAULT 1,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP,
            updated_at TEXT DEFAULT CURRENT_TIMESTAMP
        )
    """,
    "catalog_sectores": """
        CREATE TABLE IF NOT EXISTS catalog_sectores (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            nombre TEXT UNIQUE NOT NULL,
            descripcion TEXT,
            activo INTEGER DEFAULT 1,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP,
            updated_at TEXT DEFAULT CURRENT_TIMESTAMP
        )
    """,
}

CATALOG_INDEXES: Dict[str, Iterable[str]] = {
    "catalog_centros": (
        "CREATE UNIQUE INDEX IF NOT EXISTS idx_catalog_centros_codigo ON catalog_centros(codigo)",
    ),
    "catalog_almacenes": (
        "CREATE UNIQUE INDEX IF NOT EXISTS idx_catalog_almacenes_codigo ON catalog_almacenes(codigo)",
        "CREATE INDEX IF NOT EXISTS idx_catalog_almacenes_centro ON catalog_almacenes(centro_codigo)",
    ),
    "catalog_roles": (
        "CREATE UNIQUE INDEX IF NOT EXISTS idx_catalog_roles_nombre ON catalog_roles(nombre)",
    ),
    "catalog_puestos": (
        "CREATE UNIQUE INDEX IF NOT EXISTS idx_catalog_puestos_nombre ON catalog_puestos(nombre)",
    ),
    "catalog_sectores": (
        "CREATE UNIQUE INDEX IF NOT EXISTS idx_catalog_sectores_nombre ON catalog_sectores(nombre)",
    ),
}

SEED_DATA = {
    "catalog_centros": (
        {"codigo": "CENTRAL", "nombre": "Centro Principal", "activo": 1},
    ),
    "catalog_roles": (
        {"nombre": "Solicitante", "descripcion": "Rol basico", "activo": 1},
    ),
}


def _apply_schema():
    with get_connection() as con:
        for table, ddl in CATALOG_TABLES.items():
            con.execute(ddl)
        for table, statements in CATALOG_INDEXES.items():
            for statement in statements:
                con.execute(statement)
        con.commit()


def _seed_if_empty(logger: Optional[Logger] = None) -> None:
    if not Settings.DEBUG:
        return
    with get_connection() as con:
        for table, rows in SEED_DATA.items():
            count = len(con.execute(f"SELECT 1 FROM {table}").fetchall())
            if count:
                continue
            for row in rows:
                columns = ", ".join(row.keys())
                placeholders = ", ".join(["?"] * len(row))
                con.execute(
                    f"INSERT INTO {table} ({columns}) VALUES ({placeholders})",
                    tuple(row.values()),
                )
            con.commit()
            if logger:
                logger.info("Seeded %s with %d filas", table, len(rows))


def ensure_catalog_tables(logger: Optional[Logger] = None) -> None:
    _apply_schema()
    _seed_if_empty(logger)
