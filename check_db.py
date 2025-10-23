import sqlite3
import os

# Conectar a la base de datos
DB_PATH = os.getenv('SPM_DB_PATH')
if not DB_PATH:
    try:
        from src.backend.config import Settings
        DB_PATH = Settings.DB_PATH
    except Exception:
        DB_PATH = os.path.join(os.path.dirname(__file__), 'src', 'backend', 'spm.db')

conn = sqlite3.connect(DB_PATH)
cursor = conn.cursor()

# Verificar si existe la tabla materiales
cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='materiales';")
table_exists = cursor.fetchone()

if table_exists:
    print("La tabla 'materiales' existe.")
    # Contar registros
    cursor.execute("SELECT COUNT(*) FROM materiales;")
    count = cursor.fetchone()[0]
    print(f"Registros en la tabla: {count}")

    if count > 0:
        # Mostrar algunos registros
        cursor.execute("SELECT codigo, descripcion FROM materiales LIMIT 5;")
        rows = cursor.fetchall()
        print("Primeros 5 registros:")
        for row in rows:
            print(f"  {row[0]}: {row[1]}")
else:
    print("La tabla 'materiales' NO existe.")

# Verificar almacenes
cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='almacenes';")
table_exists = cursor.fetchone()

if table_exists:
    print("La tabla 'almacenes' existe.")
    cursor.execute("SELECT COUNT(*) FROM almacenes;")
    count = cursor.fetchone()[0]
    print(f"Registros en la tabla: {count}")
    cursor.execute("SELECT * FROM almacenes LIMIT 5;")
    rows = cursor.fetchall()
    print("Primeros 5 registros:")
    for row in rows:
        print(f"  {row}")
else:
    print("La tabla 'almacenes' no existe.")

# Verificar catalog_almacenes
cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='catalog_almacenes';")
table_exists = cursor.fetchone()

if table_exists:
    print("La tabla 'catalog_almacenes' existe.")
    cursor.execute("SELECT COUNT(*) FROM catalog_almacenes;")
    count = cursor.fetchone()[0]
    print(f"Registros en la tabla: {count}")
    cursor.execute("SELECT * FROM catalog_almacenes LIMIT 5;")
    rows = cursor.fetchall()
    print("Primeros 5 registros:")
    for row in rows:
        print(f"  {row}")
else:
    print("La tabla 'catalog_almacenes' no existe.")

# Verificar catalog_centros
cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='catalog_centros';")
table_exists = cursor.fetchone()

if table_exists:
    print("La tabla 'catalog_centros' existe.")
    cursor.execute("SELECT COUNT(*) FROM catalog_centros;")
    count = cursor.fetchone()[0]
    print(f"Registros en la tabla: {count}")
    cursor.execute("SELECT * FROM catalog_centros LIMIT 5;")
    rows = cursor.fetchall()
    print("Primeros 5 registros:")
    for row in rows:
        print(f"  {row}")
else:
    print("La tabla 'catalog_centros' no existe.")

conn.close()
