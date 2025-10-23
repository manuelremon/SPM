"""
Fix mojibake and encoding issues in SPM database.
Run this script to repair text columns with Latin1-encoded UTF-8 or replacement chars.
Back up the database before running!
"""
import sqlite3
import re

TARGETS = {
    "usuarios": ["nombre", "apellido", "mail", "sector", "posicion"],
    "almacenes": ["nombre"],
    "catalog_centros": ["nombre"],
    "solicitudes": ["justificacion", "objeto_imputacion"],
}

def looks_mojibake(s: str) -> bool:
    if not s:
        return False
    return "�" in s or re.search(r"(Ã.|Ã±|Â·|Â°|Â¡|Â¿)", s) is not None

def fix_text(s: str) -> str:
    try:
        # Common double-encoding pattern: Latin1 bytes decoded as UTF-8
        return s.encode("latin-1").decode("utf-8")
    except (UnicodeDecodeError, UnicodeEncodeError):
        return s

def run(db="src/backend/data/spm.db"):
    con = sqlite3.connect(db)
    con.row_factory = sqlite3.Row
    total = 0
    for table, cols in TARGETS.items():
        try:
            rows = con.execute(f"SELECT rowid, {', '.join(cols)} FROM {table}").fetchall()
        except sqlite3.Error:
            print(f"Skipping {table}: table or columns not found")
            continue
        for r in rows:
            updates = {}
            for c in cols:
                v = r[c]
                if isinstance(v, str) and looks_mojibake(v):
                    nv = fix_text(v)
                    if nv != v:
                        updates[c] = nv
            if updates:
                sets = ", ".join([f"{c} = ?" for c in updates.keys()])
                con.execute(f"UPDATE {table} SET {sets} WHERE rowid = ?", [*updates.values(), r["rowid"]])
                total += 1
                print(f"Fixed {table} rowid {r['rowid']}: {updates}")
    con.commit()
    print(f"Total repaired rows: {total}")

if __name__ == "__main__":
    import sys
    db_path = sys.argv[1] if len(sys.argv) > 1 else "src/backend/data/spm.db"
    run(db_path)
