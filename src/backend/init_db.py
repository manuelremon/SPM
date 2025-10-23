from __future__ import annotations

import csv
import os
import sqlite3
import unicodedata
from typing import Callable, Iterable, Sequence

from .config import Settings
from .db import get_connection
from .security import hash_password

MigrationFn = Callable[[sqlite3.Connection], None]
MIGRATIONS: Sequence[tuple[int, MigrationFn]] = ()

CATEGORY_FALSE_TOKENS = {"0", "false", "no", "off", "inactivo", "inactive"}

CATALOG_CSV_SOURCES = {
    "catalog_centros": {
        "filename": "Centros.csv",
        "columns": ("codigo", "nombre", "descripcion", "notas", "activo"),
        "bools": {"activo"},
    },
    "catalog_almacenes": {
        "filename": "Almacenes.csv",
        "columns": ("codigo", "nombre", "centro_codigo", "descripcion", "activo"),
        "bools": {"activo"},
    },
    "catalog_roles": {
        "filename": "Roles.csv",
        "columns": ("nombre", "descripcion", "activo"),
        "bools": {"activo"},
    },
    "catalog_puestos": {
        "filename": "Puestos.csv",
        "columns": ("nombre", "descripcion", "activo"),
        "bools": {"activo"},
    },
    "catalog_sectores": {
        "filename": "Sectores.csv",
        "columns": ("nombre", "descripcion", "activo"),
        "bools": {"activo"},
    },
}


def _ensure_migration_table(con: sqlite3.Connection) -> None:
    con.execute(
        """
        CREATE TABLE IF NOT EXISTS schema_migrations(
            version INTEGER PRIMARY KEY,
            applied_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
        )
        """
    )


def _get_applied_versions(con: sqlite3.Connection) -> set[int]:
    _ensure_migration_table(con)
    rows = con.execute("SELECT version FROM schema_migrations").fetchall()
    return {int(row["version"]) for row in rows}


def _apply_migrations(con: sqlite3.Connection) -> None:
    applied = _get_applied_versions(con)
    for version, migration_fn in MIGRATIONS:
        if version in applied:
            continue
        try:
            migration_fn(con)
            con.execute("INSERT INTO schema_migrations(version) VALUES (?)", (version,))
            con.commit()
        except Exception:
            con.rollback()
            raise


def _normalize_key(value: str) -> str:
    try:
        if not value:
            return ""
        # Convertir a string primero para manejar cualquier tipo de entrada
        value_str = str(value)
        # Normalizar Unicode de forma segura
        normalized = unicodedata.normalize("NFKD", value_str)
        # Filtrar caracteres de combinación de forma segura
        result = []
        for ch in normalized:
            try:
                if not unicodedata.combining(ch):
                    result.append(ch)
            except (ValueError, TypeError):
                # Si hay problemas con un carácter, lo omitimos
                continue
        normalized = "".join(result)
    except (UnicodeError, UnicodeDecodeError, KeyboardInterrupt):
        # Fallback si hay problemas con Unicode
        normalized = str(value or "").replace(" ", "").replace("-", "").replace(".", "").replace("/", "").replace("\\", "").replace("\t", "")
    # Limpiar caracteres especiales
    for ch in (" ", "-", ".", "/", "\\", "\t"):
        normalized = normalized.replace(ch, "")
    return normalized.lower()


def _normalize_catalog_key(value: str) -> str:
    return _normalize_key(value)


def _load_csv(path: str) -> list[dict[str, str]]:
    if not os.path.exists(path):
        return []
    try:
        with open(path, "r", encoding="utf-8-sig", newline="", errors="replace") as handle:
            sample = handle.read(4096)
            handle.seek(0)
            delimiter = ";" if sample.count(";") > sample.count(",") else ","
            reader = csv.DictReader(handle, delimiter=delimiter)
            rows: list[dict[str, str]] = []
            for raw in reader:
                try:
                    normalized: dict[str, str] = {}
                    for key, value in (raw or {}).items():
                        if key is None:
                            continue
                        normalized[_normalize_key(str(key))] = (value or "").strip()
                    rows.append(normalized)
                except (KeyboardInterrupt, UnicodeError, UnicodeDecodeError):
                    # Si hay problemas con una fila específica, omitirla
                    continue
            return rows
    except (UnicodeError, UnicodeDecodeError, KeyboardInterrupt):
        # Si hay problemas con el archivo completo, devolver lista vacía
        return []


def _to_float(raw: str | None) -> float:
    value = (raw or "").strip().replace(",", ".")
    try:
        return float(value)
    except Exception:
        return 0.0


def _to_bool(raw: object, default: bool = True) -> int:
    if raw is None:
        return 1 if default else 0
    if isinstance(raw, (int, float)):
        return 1 if int(raw) else 0
    text = str(raw).strip().lower()
    if not text:
        return 1 if default else 0
    return 0 if text in CATEGORY_FALSE_TOKENS else 1


def _prepare_material_values(rows: list[dict[str, str]]) -> list[tuple[object, ...]]:
    values: list[tuple[object, ...]] = []
    current: dict[str, object] | None = None

    def flush_current() -> None:
        nonlocal current
        if not current:
            return
        pieces = [p.strip() for p in current.get("desc_larga_parts", []) if isinstance(p, str) and p.strip()]
        descripcion_larga = "\n".join(pieces) if pieces else None
        values.append(
            (
                current.get("codigo"),
                current.get("descripcion"),
                descripcion_larga,
                current.get("centro"),
                current.get("sector"),
                current.get("unidad"),
                current.get("precio"),
            )
        )
        current = None

    for row in rows:
        codigo = row.get("codigo") or row.get("material") or ""
        descripcion_larga_piece = (row.get("textocompletomaterialespanol") or "").strip()
        if codigo:
            if current:
                flush_current()
            descripcion = row.get("descripcion") or row.get("textobrevematerial") or descripcion_larga_piece or ""
            if not descripcion:
                current = None
                continue
            current = {
                "codigo": codigo,
                "descripcion": descripcion,
                "centro": row.get("centro") or None,
                "sector": row.get("sector") or None,
                "unidad": row.get("unidaddemedida") or row.get("unidad") or None,
                "precio": _to_float(row.get("preciousd") or row.get("precio")),
                "desc_larga_parts": [descripcion_larga_piece] if descripcion_larga_piece else [],
            }
        elif current and descripcion_larga_piece:
            current.setdefault("desc_larga_parts", []).append(descripcion_larga_piece)
    flush_current()
    return values


def _parse_almacen_literal(value: str | None) -> tuple[str | None, str | None, str | None]:
    literal = (value or "").strip()
    if not literal:
        return None, None, None
    code = literal
    name = literal
    description = None
    if "-" in literal:
        left, right = literal.split("-", 1)
        code = left.strip() or code
        name = right.strip() or name
    if "(" in name and name.endswith(")"):
        base, _, rest = name.partition("(")
        name = base.strip() or name
        description = rest.rstrip(")").strip() or None
    return code or None, name or None, description


def _insert_ignore_many(
    con: sqlite3.Connection,
    table: str,
    columns: Iterable[str],
    rows: Iterable[Sequence[object]],
) -> None:
    cached_rows = list(rows)
    if not cached_rows:
        return
    column_tuple = tuple(columns)
    placeholder = ",".join(["?"] * len(column_tuple))
    column_list = ",".join(column_tuple)
    sql = f"INSERT OR IGNORE INTO {table} ({column_list}) VALUES ({placeholder})"
    con.executemany(sql, cached_rows)


def _backfill_catalog_tables(con: sqlite3.Connection) -> None:
    existing_almacenes = {
        _normalize_catalog_key(row["codigo"])
        for row in con.execute("SELECT codigo FROM catalog_almacenes")
    }

    almacenes_detected: dict[str, dict[str, object]] = {}
    for row in con.execute(
        """
        SELECT almacen_virtual, centro
          FROM solicitudes
         WHERE almacen_virtual IS NOT NULL AND almacen_virtual <> ''
        """
    ):
        literal = row.get("almacen_virtual") or ""
        code, name, description = _parse_almacen_literal(literal)
        if not code:
            continue
        entry = almacenes_detected.setdefault(
            code,
            {"nombre": name or code, "descripcion": description, "centros": set()},
        )
        centro = (row.get("centro") or "").strip()
        if centro:
            entry["centros"].add(centro)

    almacen_rows = []
    for code, meta in sorted(almacenes_detected.items(), key=lambda item: item[0]):
        if _normalize_catalog_key(code) in existing_almacenes:
            continue
        centros = sorted(meta.get("centros") or [])
        centro_codigo = centros[0] if centros else None
        almacen_rows.append(
            (
                code,
                meta.get("nombre") or code,
                centro_codigo,
                meta.get("descripcion"),
                1,
            )
        )
    _insert_ignore_many(
        con,
        "catalog_almacenes",
        ("codigo", "nombre", "centro_codigo", "descripcion", "activo"),
        almacen_rows,
    )

    def _collect_simple_values(query: str, column: str) -> set[str]:
        values: set[str] = set()
        for row in con.execute(query):
            value = (row.get(column) or "").strip()
            if value:
                values.add(value)
        return values

    existing_roles = {
        _normalize_catalog_key(row["nombre"])
        for row in con.execute("SELECT nombre FROM catalog_roles")
    }
    role_rows = [
        (value, None, 1)
        for value in sorted(
            _collect_simple_values(
                "SELECT DISTINCT rol AS value FROM usuarios WHERE rol IS NOT NULL AND rol <> ''",
                "value",
            )
        )
        if _normalize_catalog_key(value) not in existing_roles
    ]
    _insert_ignore_many(con, "catalog_roles", ("nombre", "descripcion", "activo"), role_rows)

    existing_puestos = {
        _normalize_catalog_key(row["nombre"])
        for row in con.execute("SELECT nombre FROM catalog_puestos")
    }
    puesto_rows = [
        (value, None, 1)
        for value in sorted(
            _collect_simple_values(
                "SELECT DISTINCT posicion AS value FROM usuarios WHERE posicion IS NOT NULL AND posicion <> ''",
                "value",
            )
        )
        if _normalize_catalog_key(value) not in existing_puestos
    ]
    _insert_ignore_many(con, "catalog_puestos", ("nombre", "descripcion", "activo"), puesto_rows)

    existing_sectores = {
        _normalize_catalog_key(row["nombre"])
        for row in con.execute("SELECT nombre FROM catalog_sectores")
    }
    sectores_detectados = set()
    sectores_detectados.update(
        _collect_simple_values(
            "SELECT DISTINCT sector AS value FROM usuarios WHERE sector IS NOT NULL AND sector <> ''",
            "value",
        )
    )
    sectores_detectados.update(
        _collect_simple_values(
            "SELECT DISTINCT sector AS value FROM solicitudes WHERE sector IS NOT NULL AND sector <> ''",
            "value",
        )
    )
    sectores_detectados.update(
        _collect_simple_values(
            "SELECT DISTINCT sector AS value FROM presupuestos WHERE sector IS NOT NULL AND sector <> ''",
            "value",
        )
    )
    sector_rows = [
        (value, None, 1)
        for value in sorted(sectores_detectados)
        if _normalize_catalog_key(value) not in existing_sectores
    ]
    _insert_ignore_many(con, "catalog_sectores", ("nombre", "descripcion", "activo"), sector_rows)


def build_db(force: bool = False) -> None:
    Settings.ensure_dirs()
    if force and os.path.exists(Settings.DB_PATH):
        os.remove(Settings.DB_PATH)
    with get_connection() as con:
        con.executescript(
            """
            CREATE TABLE IF NOT EXISTS usuarios(
                id_spm TEXT PRIMARY KEY,
                nombre TEXT NOT NULL,
                apellido TEXT NOT NULL,
                rol TEXT NOT NULL,
                contrasena TEXT NOT NULL,
                mail TEXT,
                posicion TEXT,
                sector TEXT,
                centros TEXT,
                jefe TEXT,
                gerente1 TEXT,
                gerente2 TEXT,
                telefono TEXT,
                estado_registro TEXT,
                id_ypf TEXT
            );
            CREATE TABLE IF NOT EXISTS user_profile_requests(
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                usuario_id TEXT NOT NULL,
                tipo TEXT NOT NULL,
                payload TEXT,
                estado TEXT NOT NULL DEFAULT 'pendiente',
                created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY(usuario_id) REFERENCES usuarios(id_spm)
            );
            CREATE INDEX IF NOT EXISTS idx_profile_request_user ON user_profile_requests(usuario_id);
            CREATE INDEX IF NOT EXISTS idx_profile_request_estado ON user_profile_requests(estado);
            CREATE TABLE IF NOT EXISTS materiales(
                codigo TEXT PRIMARY KEY,
                descripcion TEXT NOT NULL,
                descripcion_larga TEXT,
                centro TEXT,
                sector TEXT,
                unidad TEXT,
                precio_usd REAL DEFAULT 0
            );
            CREATE TABLE IF NOT EXISTS presupuestos(
                centro TEXT,
                sector TEXT,
                monto_usd REAL DEFAULT 0,
                saldo_usd REAL DEFAULT 0,
                PRIMARY KEY(centro, sector)
            );
            CREATE TABLE IF NOT EXISTS solicitudes(
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                id_usuario TEXT NOT NULL,
                centro TEXT NOT NULL,
                sector TEXT NOT NULL,
                justificacion TEXT NOT NULL,
                centro_costos TEXT,
                almacen_virtual TEXT,
                criticidad TEXT NOT NULL DEFAULT 'Normal',
                fecha_necesidad TEXT,
                data_json TEXT NOT NULL,
                status TEXT NOT NULL DEFAULT 'draft',
                aprobador_id TEXT,
                planner_id TEXT,
                total_monto REAL DEFAULT 0,
                notificado_at TEXT,
                created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY(id_usuario) REFERENCES usuarios(id_spm),
                FOREIGN KEY(planner_id) REFERENCES usuarios(id_spm)
            );
            CREATE TABLE IF NOT EXISTS planificadores(
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                usuario_id TEXT NOT NULL UNIQUE,
                nombre TEXT NOT NULL,
                activo BOOLEAN DEFAULT 1,
                created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY(usuario_id) REFERENCES usuarios(id_spm)
            );
            CREATE TABLE IF NOT EXISTS planificador_asignaciones(
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                planificador_id TEXT NOT NULL,
                centro TEXT,
                sector TEXT,
                almacen_virtual TEXT,
                prioridad INTEGER DEFAULT 1,
                activo BOOLEAN DEFAULT 1,
                created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY(planificador_id) REFERENCES planificadores(usuario_id),
                UNIQUE(planificador_id, centro, sector, almacen_virtual)
            );
            CREATE INDEX IF NOT EXISTS idx_mat_desc ON materiales(descripcion);
            CREATE INDEX IF NOT EXISTS idx_sol_user ON solicitudes(id_usuario, created_at);
            CREATE TABLE IF NOT EXISTS notificaciones(
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                destinatario_id TEXT NOT NULL,
                solicitud_id INTEGER,
                mensaje TEXT NOT NULL,
                leido INTEGER NOT NULL DEFAULT 0,
                created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY(solicitud_id) REFERENCES solicitudes(id)
            );
            CREATE TABLE IF NOT EXISTS presupuesto_incorporaciones(
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                centro TEXT NOT NULL,
                sector TEXT,
                monto REAL NOT NULL,
                motivo TEXT,
                estado TEXT NOT NULL DEFAULT 'pendiente',
                solicitante_id TEXT NOT NULL,
                aprobador_id TEXT,
                comentario TEXT,
                created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                resolved_at TEXT,
                FOREIGN KEY(solicitante_id) REFERENCES usuarios(id_spm),
                FOREIGN KEY(aprobador_id) REFERENCES usuarios(id_spm)
            );
            CREATE INDEX IF NOT EXISTS idx_inc_estado ON presupuesto_incorporaciones(estado);
            CREATE INDEX IF NOT EXISTS idx_inc_centro ON presupuesto_incorporaciones(centro);
            CREATE TABLE IF NOT EXISTS catalog_centros(
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                codigo TEXT NOT NULL UNIQUE,
                nombre TEXT,
                descripcion TEXT,
                notas TEXT,
                activo INTEGER NOT NULL DEFAULT 1,
                created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
            );
            CREATE TABLE IF NOT EXISTS catalog_almacenes(
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                codigo TEXT NOT NULL UNIQUE,
                nombre TEXT,
                centro_codigo TEXT,
                descripcion TEXT,
                activo INTEGER NOT NULL DEFAULT 1,
                created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
            );
            CREATE TABLE IF NOT EXISTS catalog_roles(
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                nombre TEXT NOT NULL UNIQUE,
                descripcion TEXT,
                activo INTEGER NOT NULL DEFAULT 1,
                created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
            );
            CREATE TABLE IF NOT EXISTS catalog_puestos(
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                nombre TEXT NOT NULL UNIQUE,
                descripcion TEXT,
                activo INTEGER NOT NULL DEFAULT 1,
                created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
            );
            CREATE TABLE IF NOT EXISTS catalog_sectores(
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                nombre TEXT NOT NULL UNIQUE,
                descripcion TEXT,
                activo INTEGER NOT NULL DEFAULT 1,
                created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
            );
            CREATE INDEX IF NOT EXISTS idx_catalog_centros_codigo ON catalog_centros(codigo);
            CREATE INDEX IF NOT EXISTS idx_catalog_almacenes_codigo ON catalog_almacenes(codigo);
            CREATE INDEX IF NOT EXISTS idx_catalog_roles_nombre ON catalog_roles(nombre);
            CREATE INDEX IF NOT EXISTS idx_catalog_puestos_nombre ON catalog_puestos(nombre);
            CREATE INDEX IF NOT EXISTS idx_catalog_sectores_nombre ON catalog_sectores(nombre);
            CREATE TABLE IF NOT EXISTS archivos_adjuntos(
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                solicitud_id INTEGER NOT NULL,
                nombre_archivo TEXT NOT NULL,
                nombre_original TEXT NOT NULL,
                tipo_mime TEXT,
                tamano_bytes INTEGER,
                ruta_archivo TEXT NOT NULL,
                usuario_id TEXT NOT NULL,
                created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY(solicitud_id) REFERENCES solicitudes(id) ON DELETE CASCADE,
                FOREIGN KEY(usuario_id) REFERENCES usuarios(id_spm)
            );
            CREATE INDEX IF NOT EXISTS idx_archivos_solicitud ON archivos_adjuntos(solicitud_id);
            CREATE INDEX IF NOT EXISTS idx_archivos_usuario ON archivos_adjuntos(usuario_id);
            CREATE TABLE IF NOT EXISTS solicitud_items_tratamiento(
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                solicitud_id INTEGER NOT NULL,
                item_index INTEGER NOT NULL,
                decision TEXT NOT NULL,
                cantidad_aprobada REAL NOT NULL,
                codigo_equivalente TEXT,
                proveedor_sugerido TEXT,
                precio_unitario_estimado REAL,
                comentario TEXT,
                updated_by TEXT NOT NULL,
                updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                UNIQUE(solicitud_id, item_index),
                FOREIGN KEY(solicitud_id) REFERENCES solicitudes(id) ON DELETE CASCADE
            );
            CREATE INDEX IF NOT EXISTS idx_items_trat_sol ON solicitud_items_tratamiento(solicitud_id);
            CREATE TABLE IF NOT EXISTS solicitud_tratamiento_eventos(
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                solicitud_id INTEGER NOT NULL,
                planner_id TEXT NOT NULL,
                tipo TEXT NOT NULL,
                payload_json TEXT,
                created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY(solicitud_id) REFERENCES solicitudes(id) ON DELETE CASCADE
            );
            CREATE INDEX IF NOT EXISTS idx_trat_eventos_sol ON solicitud_tratamiento_eventos(solicitud_id);
            CREATE TABLE IF NOT EXISTS solicitud_tratamiento_log(
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                solicitud_id INTEGER NOT NULL,
                item_index INTEGER,
                actor_id TEXT NOT NULL,
                tipo TEXT NOT NULL,
                estado TEXT,
                payload_json TEXT,
                created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY(solicitud_id) REFERENCES solicitudes(id) ON DELETE CASCADE
            );
            CREATE INDEX IF NOT EXISTS idx_trat_log_sol ON solicitud_tratamiento_log(solicitud_id, created_at);
            CREATE TABLE IF NOT EXISTS traslados(
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                solicitud_id INTEGER NOT NULL,
                item_index INTEGER NOT NULL,
                material TEXT NOT NULL,
                um TEXT,
                cantidad REAL NOT NULL CHECK (cantidad>0),
                origen_centro TEXT NOT NULL,
                origen_almacen TEXT NOT NULL,
                origen_lote TEXT,
                destino_centro TEXT NOT NULL,
                destino_almacen TEXT NOT NULL,
                status TEXT NOT NULL DEFAULT 'planificado',
                referencia TEXT,
                created_by TEXT NOT NULL,
                updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY(solicitud_id) REFERENCES solicitudes(id) ON DELETE CASCADE
            );
            CREATE INDEX IF NOT EXISTS idx_tras_sol ON traslados(solicitud_id);
            CREATE TABLE IF NOT EXISTS solpeds(
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                solicitud_id INTEGER NOT NULL,
                item_index INTEGER NOT NULL,
                material TEXT NOT NULL,
                um TEXT,
                cantidad REAL NOT NULL CHECK (cantidad>0),
                precio_unitario_est REAL DEFAULT 0,
                status TEXT NOT NULL DEFAULT 'creada',
                numero TEXT,
                created_by TEXT NOT NULL,
                updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY(solicitud_id) REFERENCES solicitudes(id) ON DELETE CASCADE
            );
            CREATE INDEX IF NOT EXISTS idx_solped_sol ON solpeds(solicitud_id);
            CREATE TABLE IF NOT EXISTS purchase_orders(
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                solped_id INTEGER NOT NULL,
                solicitud_id INTEGER NOT NULL,
                proveedor_email TEXT,
                proveedor_nombre TEXT,
                numero TEXT,
                status TEXT NOT NULL DEFAULT 'emitida',
                subtotal REAL DEFAULT 0,
                moneda TEXT DEFAULT 'USD',
                created_by TEXT NOT NULL,
                updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY(solped_id) REFERENCES solpeds(id) ON DELETE CASCADE,
                FOREIGN KEY(solicitud_id) REFERENCES solicitudes(id) ON DELETE CASCADE
            );
            CREATE INDEX IF NOT EXISTS idx_po_sol ON purchase_orders(solicitud_id);
            CREATE TABLE IF NOT EXISTS outbox_emails(
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                to_email TEXT NOT NULL,
                subject TEXT NOT NULL,
                body TEXT NOT NULL,
                attachments_json TEXT,
                status TEXT NOT NULL DEFAULT 'queued',
                error TEXT,
                created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                sent_at TEXT
            );
            CREATE TABLE IF NOT EXISTS ai_suggestions_log (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                solicitud_id INTEGER NOT NULL,
                item_index INTEGER,
                suggestion_type TEXT NOT NULL,
                payload_json TEXT NOT NULL,
                confidence REAL NOT NULL,
                accepted INTEGER,
                actor_id TEXT,
                created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
            );
            CREATE INDEX IF NOT EXISTS idx_ai_sol ON ai_suggestions_log(solicitud_id);
            """
        )

        cols = {row["name"] for row in con.execute("PRAGMA table_info(usuarios)")}
        if "telefono" not in cols:
            con.execute("ALTER TABLE usuarios ADD COLUMN telefono TEXT")
        if "estado_registro" not in cols:
            con.execute("ALTER TABLE usuarios ADD COLUMN estado_registro TEXT")
        if "id_ypf" not in cols:
            con.execute("ALTER TABLE usuarios ADD COLUMN id_ypf TEXT")

        sol_cols = {row["name"] for row in con.execute("PRAGMA table_info(solicitudes)")}
        if "planner_id" not in sol_cols:
            con.execute("ALTER TABLE solicitudes ADD COLUMN planner_id TEXT")
        if "criticidad" not in sol_cols:
            con.execute("ALTER TABLE solicitudes ADD COLUMN criticidad TEXT DEFAULT 'Normal'")
        if "fecha_necesidad" not in sol_cols:
            con.execute("ALTER TABLE solicitudes ADD COLUMN fecha_necesidad TEXT")

        _apply_migrations(con)

        data_dir = Settings.DATA_DIR
        usuarios_csv = os.path.join(data_dir, "Usuarios.csv")
        materiales_csv = os.path.join(data_dir, "Materiales.csv")
        presupuestos_csv = os.path.join(data_dir, "Presupuestos.csv")
        catalog_csv_paths = {
            table: os.path.join(data_dir, meta["filename"])
            for table, meta in CATALOG_CSV_SOURCES.items()
        }

        usuarios_rows = _load_csv(usuarios_csv)
        if usuarios_rows:
            inserts = []
            updates = []
            for row in usuarios_rows:
                usuario_id = (row.get("id") or row.get("idspm") or "").strip().lower()
                nombre = (row.get("nombre") or "").strip()
                apellido = (row.get("apellido") or "").strip()
                if not usuario_id or not nombre or not apellido:
                    continue
                rol = (row.get("rol") or "Solicitante").strip() or "Solicitante"
                password_raw = (row.get("password") or row.get("contrasena") or "").strip()
                mail = (row.get("mail") or row.get("email") or "").strip()
                posicion = (row.get("posicion") or "").strip() or None
                sector = (row.get("sector") or "").strip() or None
                centros_raw = row.get("centro") or row.get("centros") or None
                centros = None
                if centros_raw:
                    tokens = [token.strip() for token in centros_raw.replace(";", ",").split(",") if token.strip()]
                    centros = ",".join(tokens) if tokens else None
                telefono = (row.get("telefono") or row.get("tel") or "").strip() or None
                estado_registro = (row.get("estado_registro") or row.get("estadoregistro") or "").strip() or None
                id_ypf = (row.get("id_ypf") or row.get("idypf") or "").strip() or None
                jefe = (row.get("jefe") or "").strip().lower() or None
                gerente1 = (row.get("gerente1") or "").strip().lower() or None
                gerente2 = (row.get("gerente2") or "").strip().lower() or None

                hashed_password = hash_password(password_raw or "changeme123")
                inserts.append(
                    (
                        usuario_id,
                        nombre,
                        apellido,
                        rol,
                        hashed_password,
                        mail.lower() if mail else None,
                        posicion,
                        sector,
                        centros,
                        jefe,
                        gerente1,
                        gerente2,
                        telefono,
                        estado_registro,
                        id_ypf,
                    )
                )

                if any(
                    [
                        posicion,
                        sector,
                        centros,
                        jefe,
                        gerente1,
                        gerente2,
                        telefono,
                        estado_registro,
                        id_ypf,
                    ]
                ):
                    updates.append(
                        (
                            posicion,
                            sector,
                            centros,
                            jefe,
                            gerente1,
                            gerente2,
                            telefono,
                            estado_registro,
                            id_ypf,
                            usuario_id,
                        )
                    )

            if inserts:
                con.executemany(
                    """
                    INSERT OR IGNORE INTO usuarios (
                        id_spm, nombre, apellido, rol, contrasena, mail,
                        posicion, sector, centros, jefe, gerente1, gerente2,
                        telefono, estado_registro, id_ypf
                    )
                    VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
                    """,
                    inserts,
                )
            if updates:
                con.executemany(
                    """
                    UPDATE usuarios
                       SET posicion=COALESCE(?, posicion),
                           sector=COALESCE(?, sector),
                           centros=COALESCE(?, centros),
                           jefe=COALESCE(?, jefe),
                           gerente1=COALESCE(?, gerente1),
                           gerente2=COALESCE(?, gerente2),
                           telefono=COALESCE(?, telefono),
                           estado_registro=COALESCE(?, estado_registro),
                           id_ypf=COALESCE(?, id_ypf)
                     WHERE id_spm=?
                    """,
                    updates,
                )

        # Procesar planificadores
        planificadores_inserts = []
        asignaciones_inserts = []
        for row in usuarios_rows:
            rol = (row.get("rol") or "Solicitante").strip()
            posicion = (row.get("posicion") or "").strip()
            # Buscar planificadores por rol O por posición
            if ("Planificador" in rol or "planificador" in rol.lower() or 
                "Planificador" in posicion or "planificador" in posicion.lower()):
                usuario_id = (row.get("id") or row.get("idspm") or "").strip().lower()
                nombre = f"{(row.get('nombre') or '').strip()} {(row.get('apellido') or '').strip()}".strip()
                if usuario_id and nombre:
                    planificadores_inserts.append((usuario_id, nombre))

                    # Crear asignaciones por defecto basadas en centros del planificador
                    centros_raw = row.get("centro") or row.get("centros") or ""
                    if centros_raw:
                        tokens = [token.strip() for token in centros_raw.replace(";", ",").split(",") if token.strip()]
                        for centro in tokens:
                            asignaciones_inserts.append((usuario_id, centro, None, None, 1))  # centro, sector, almacen, prioridad

        if planificadores_inserts:
            con.executemany(
                "INSERT OR IGNORE INTO planificadores (usuario_id, nombre) VALUES (?, ?)",
                planificadores_inserts,
            )

        if asignaciones_inserts:
            con.executemany(
                """
                INSERT OR IGNORE INTO planificador_asignaciones
                (planificador_id, centro, sector, almacen_virtual, prioridad)
                VALUES (?, ?, ?, ?, ?)
                """,
                asignaciones_inserts,
            )

        materiales_rows = _load_csv(materiales_csv)
        if len(materiales_rows) < 10:
            backup_csv = materiales_csv + ".bak"
            if os.path.exists(backup_csv):
                materiales_rows = _load_csv(backup_csv)
        if materiales_rows:
            material_values = _prepare_material_values(materiales_rows)
            if material_values:
                con.executemany(
                    """
                    INSERT INTO materiales (codigo, descripcion, descripcion_larga, centro, sector, unidad, precio_usd)
                    VALUES (?,?,?,?,?,?,?)
                    ON CONFLICT(codigo) DO UPDATE SET
                        descripcion=excluded.descripcion,
                        descripcion_larga=CASE
                            WHEN excluded.descripcion_larga IS NULL OR excluded.descripcion_larga=''
                            THEN materiales.descripcion_larga
                            ELSE excluded.descripcion_larga
                        END,
                        centro=CASE
                            WHEN excluded.centro IS NULL OR excluded.centro=''
                            THEN materiales.centro
                            ELSE excluded.centro
                        END,
                        sector=CASE
                            WHEN excluded.sector IS NULL OR excluded.sector=''
                            THEN materiales.sector
                            ELSE excluded.sector
                        END,
                        unidad=excluded.unidad,
                        precio_usd=excluded.precio_usd
                    """,
                    material_values,
                )

        for table, meta in CATALOG_CSV_SOURCES.items():
            path = catalog_csv_paths.get(table)
            if not path:
                continue
            csv_rows = _load_csv(path)
            if not csv_rows:
                continue
            columns = meta["columns"]
            bool_cols = set(meta.get("bools", ()))  # type: ignore[arg-type]
            records: list[tuple[object, ...]] = []
            for row in csv_rows:
                record: list[object] = []
                skip = False
                for col in columns:
                    key = _normalize_key(col)
                    value: object | None = row.get(key)
                    if col in bool_cols:
                        value = _to_bool(value)
                    else:
                        text = (value or "").strip() if isinstance(value, str) else value
                        value = text or None
                    if col == columns[0] and not value:
                        skip = True
                        break
                    record.append(value)
                if not skip:
                    records.append(tuple(record))
            if not records:
                continue
            placeholders = ",".join(["?"] * len(columns))
            update_parts = []
            for col in columns:
                if col in bool_cols:
                    update_parts.append(f"{col}=excluded.{col}")
                else:
                    update_parts.append(f"{col}=COALESCE(excluded.{col}, {table}.{col})")
            conflict_column = columns[0]
            con.executemany(
                f"""
                INSERT INTO {table} ({','.join(columns)}) VALUES ({placeholders})
                ON CONFLICT({conflict_column}) DO UPDATE SET {', '.join(update_parts)}
                """,
                records,
            )

        presupuestos_rows = _load_csv(presupuestos_csv)
        if presupuestos_rows:
            presupuesto_values = [
                (
                    (row.get("centro") or "").strip(),
                    (row.get("sector") or "").strip(),
                    _to_float(row.get("montousd")),
                    _to_float(row.get("saldousd")),
                )
                for row in presupuestos_rows
            ]
            if presupuesto_values:
                con.executemany(
                    "INSERT OR REPLACE INTO presupuestos (centro, sector, monto_usd, saldo_usd) VALUES (?,?,?,?)",
                    presupuesto_values,
                )

        _backfill_catalog_tables(con)
        con.commit()


if __name__ == "__main__":
    build_db(force=True)
