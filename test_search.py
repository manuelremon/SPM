import sqlite3
import os

# Conectar a la base de datos
db_path = os.path.join(os.path.dirname(__file__), 'src', 'backend', 'spm.db')
conn = sqlite3.connect(db_path)
cursor = conn.cursor()

# Probar la búsqueda actual
print("=== Prueba de búsqueda actual ===")
search_term = "valvula"
like_desc = f"%{search_term.lower()}%"
print(f"Buscando: {like_desc}")

cursor.execute("SELECT codigo, descripcion FROM materiales WHERE lower(descripcion) LIKE ?", (like_desc,))
results = cursor.fetchall()
print(f"Resultados encontrados: {len(results)}")
for row in results:
    print(f"  {row[0]}: {row[1]}")

print("\n=== Prueba con acentos ===")
search_term = "válvula"
like_desc = f"%{search_term.lower()}%"
print(f"Buscando: {like_desc}")

cursor.execute("SELECT codigo, descripcion FROM materiales WHERE lower(descripcion) LIKE ?", (like_desc,))
results = cursor.fetchall()
print(f"Resultados encontrados: {len(results)}")
for row in results:
    print(f"  {row[0]}: {row[1]}")

print("\n=== Verificación de datos en BD ===")
cursor.execute("SELECT codigo, descripcion, lower(descripcion) FROM materiales WHERE descripcion LIKE '%Válvula%'")
results = cursor.fetchall()
print("Registros con 'Válvula':")
for row in results:
    print(f"  {row[0]}: '{row[1]}' -> lower: '{row[2]}'")

conn.close()