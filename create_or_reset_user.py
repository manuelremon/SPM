from src.backend.security import hash_password
import argparse
import sqlite3
import os
from dotenv import load_dotenv

# === Carga de entorno ===
load_dotenv()
# Preferir variable de entorno centralizada; Settings en src.backend.config define rutas por defecto.
DB_PATH = os.getenv("SPM_DB_PATH")
if not DB_PATH:
    try:
        from src.backend.config import Settings
        DB_PATH = Settings.DB_PATH
    except Exception:
        DB_PATH = os.path.join('.', 'src', 'backend', 'spm.db')

# === Funciones utilitarias ===
def connect_db():
    if not os.path.exists(DB_PATH):
        raise FileNotFoundError(f"No se encontró la base de datos en {DB_PATH}")
    return sqlite3.connect(DB_PATH)

def create_or_update_user(nombre, apellido, contrasena, rol="Solicitante", mail=None):
    con = connect_db()
    cur = con.cursor()

    cur.execute("SELECT nombre FROM usuarios WHERE nombre = ?", (nombre,))
    exists = cur.fetchone()

    if exists:
        cur.execute("UPDATE usuarios SET contrasena = ? WHERE nombre = ?", (contrasena, nombre))
        print(f"🔁 Contraseña actualizada para usuario existente: {nombre}")
    else:
        cur.execute(
            """
            INSERT INTO usuarios (id_spm, nombre, apellido, rol, contrasena, mail, estado_registro)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (f"USR_{nombre.upper()}", nombre, apellido, rol, contrasena, mail, "Activo"),
        )
        print(f"✅ Usuario creado: {nombre}")

    con.commit()
    con.close()

def list_users():
    con = connect_db()
    users = con.execute("SELECT nombre, apellido, rol FROM usuarios").fetchall()
    con.close()

    print("👥 Usuarios registrados:")
    for u in users:
        print(f" - {u[0]} {u[1]} ({u[2]})")

# === Programa principal ===
if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Crear o actualizar usuarios en SPM-2")
    parser.add_argument("--user", help="Nombre de usuario", required=False)
    parser.add_argument("--last", help="Apellido del usuario", required=False)
    parser.add_argument("--password", help="Contraseña", required=False)
    parser.add_argument("--role", help="Rol (por defecto: Solicitante)", default="Solicitante")
    parser.add_argument("--list", action="store_true", help="Listar usuarios existentes")

    args = parser.parse_args()

    if args.list:
        list_users()
    elif args.user and args.last and args.password:
        hashed = hash_password(args.password)
        create_or_update_user(args.user, args.last, hashed, args.role)
    else:
        print("⚠️ Uso: python create_or_reset_user.py --user Juan --last Perez --password 1234")
        print("     o: python create_or_reset_user.py --list para listar usuarios")
