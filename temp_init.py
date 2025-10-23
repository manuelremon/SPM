# Script temporal para inicializar la base de datos
import sys
import os
import csv
import sqlite3
import unicodedata
from typing import Callable, Iterable, Sequence

# Configuración básica
class Settings:
    DATA_DIR = 'src/backend/data'
    DATABASE_URL = 'src/backend/spm.db'

def get_connection():
    return sqlite3.connect(Settings.DATABASE_URL)

def hash_password(password: str) -> str:
    import hashlib
    return hashlib.sha256(password.encode()).hexdigest()

def _normalize_key(value: str) -> str:
    try:
        if not value:
            return ''
        value_str = str(value)
        normalized = unicodedata.normalize('NFKD', value_str)
        result = []
        for ch in normalized:
            try:
                if not unicodedata.combining(ch):
                    result.append(ch)
            except (ValueError, TypeError):
                continue
        normalized = ''.join(result)
    except (UnicodeError, UnicodeDecodeError, KeyboardInterrupt):
        normalized = str(value or '').replace(' ', '').replace('-', '').replace('.', '').replace('/', '').replace('\\', '').replace('\t', '')
    for ch in (' ', '-', '.', '/', '\\', '\t'):
        normalized = normalized.replace(ch, '')
    return normalized.lower()

def _load_csv(path: str) -> list[dict[str, str]]:
    if not os.path.exists(path):
        return []
    try:
        with open(path, 'r', encoding='utf-8-sig', newline='', errors='replace') as handle:
            sample = handle.read(4096)
            handle.seek(0)
            delimiter = ';' if sample.count(';') > sample.count(',') else ','
            reader = csv.DictReader(handle, delimiter=delimiter)
            rows: list[dict[str, str]] = []
            for raw in reader:
                try:
                    normalized: dict[str, str] = {}
                    for key, value in (raw or {}).items():
                        if key is None:
                            continue
                        normalized[_normalize_key(str(key))] = (value or '').strip()
                    rows.append(normalized)
                except (KeyboardInterrupt, UnicodeError, UnicodeDecodeError):
                    continue
            return rows
    except Exception:
        return []

def init_database():
    con = get_connection()
    try:
        # Crear tablas básicas
        con.execute('''
            CREATE TABLE IF NOT EXISTS usuarios(
                id_spm TEXT PRIMARY KEY,
                nombre TEXT NOT NULL,
                apellido TEXT NOT NULL,
                rol TEXT NOT NULL DEFAULT 'Solicitante',
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
                id_ypf TEXT,
                created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
            )
        ''')

        con.execute('''
            CREATE TABLE IF NOT EXISTS planificadores(
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                usuario_id TEXT NOT NULL UNIQUE,
                nombre TEXT NOT NULL,
                activo BOOLEAN DEFAULT 1,
                created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY(usuario_id) REFERENCES usuarios(id_spm)
            )
        ''')

        con.execute('''
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
            )
        ''')

        # Cargar usuarios
        usuarios_csv = os.path.join(Settings.DATA_DIR, 'Usuarios.csv')
        usuarios_rows = _load_csv(usuarios_csv)

        if usuarios_rows:
            inserts = []
            for row in usuarios_rows:
                usuario_id = (row.get('idspm') or row.get('id') or '').strip().lower()
                nombre = (row.get('nombre') or '').strip()
                apellido = (row.get('apellido') or '').strip()
                if not usuario_id or not nombre or not apellido:
                    continue
                rol = (row.get('rol') or 'Solicitante').strip() or 'Solicitante'
                password_raw = (row.get('contrasena') or row.get('password') or '').strip()
                mail = (row.get('mail') or row.get('email') or '').strip()
                posicion = (row.get('posicion') or '').strip() or None
                sector = (row.get('sector') or '').strip() or None
                centros_raw = row.get('centro') or row.get('centros') or None
                centros = None
                if centros_raw:
                    tokens = [token.strip() for token in centros_raw.replace(';', ',').split(',') if token.strip()]
                    centros = ','.join(tokens) if tokens else None

                hashed_password = hash_password(password_raw or 'changeme123')
                inserts.append((
                    usuario_id, nombre, apellido, rol, hashed_password,
                    mail.lower() if mail else None, posicion, sector, centros
                ))

            if inserts:
                con.executemany(
                    '''INSERT OR REPLACE INTO usuarios
                       (id_spm, nombre, apellido, rol, contrasena, mail, posicion, sector, centros)
                       VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)''',
                    inserts
                )

        # Procesar planificadores
        planificadores_inserts = []
        asignaciones_inserts = []
        for row in usuarios_rows:
            rol = (row.get('rol') or 'Solicitante').strip()
            posicion = (row.get('posicion') or '').strip()
            # Buscar planificadores por rol O por posición
            if ('Planificador' in rol or 'planificador' in rol.lower() or
                'Planificador' in posicion or 'planificador' in posicion.lower()):
                usuario_id = (row.get('idspm') or row.get('id') or '').strip().lower()
                nombre = f"{(row.get('nombre') or '').strip()} {(row.get('apellido') or '').strip()}".strip()
                if usuario_id and nombre:
                    planificadores_inserts.append((usuario_id, nombre))

                    # Crear asignaciones por defecto basadas en centros del planificador
                    centros_raw = row.get('centro') or row.get('centros') or ''
                    if centros_raw:
                        tokens = [token.strip() for token in centros_raw.replace(';', ',').split(',') if token.strip()]
                        for centro in tokens:
                            asignaciones_inserts.append((usuario_id, centro, None, None, 1))

        if planificadores_inserts:
            con.executemany(
                'INSERT OR IGNORE INTO planificadores (usuario_id, nombre) VALUES (?, ?)',
                planificadores_inserts,
            )

        if asignaciones_inserts:
            con.executemany(
                '''INSERT OR IGNORE INTO planificador_asignaciones
                   (planificador_id, centro, sector, almacen_virtual, prioridad)
                   VALUES (?, ?, ?, ?, ?)''',
                asignaciones_inserts,
            )

        con.commit()
        print('Base de datos inicializada correctamente')

    except Exception as e:
        con.rollback()
        print(f'Error: {e}')
        raise
    finally:
        con.close()

if __name__ == '__main__':
    init_database()