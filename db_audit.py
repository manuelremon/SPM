"""
SPM SQLite Database Audit Tool
Author: GitHub Copilot

This script audits a SQLite database for schema, data quality, constraints, indexes, encoding, and security issues.
Outputs:
  - ./db_audit/report.md
  - ./db_audit/findings.json
  - ./db_audit/fixes.sql
  - ./db_audit/indexes.sql
  - ./db_audit/seed_suspects.sql
  - ./db_audit/erd.txt (and erd.dot if graphviz is available)

Usage:
    python db_audit.py --db ./spm.db
"""
import os
import json
import sqlite3
from collections import defaultdict
from contextlib import closing

# ========== Helpers ==========
def ensure_dir(path):
    if not os.path.exists(path):
        os.makedirs(path)

def query_all(con, sql, params=None):
    with closing(con.cursor()) as cur:
        cur.execute(sql, params or ())
        return [dict(r) for r in cur.fetchall()]

def get_tables(con):
    return [r[0] for r in query_all(con, "SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%' ORDER BY name")]

def get_views(con):
    return [r[0] for r in query_all(con, "SELECT name FROM sqlite_master WHERE type='view'")]

def get_triggers(con):
    return [r[0] for r in query_all(con, "SELECT name FROM sqlite_master WHERE type='trigger'")]

def get_indexes(con, table):
    return [r[1] for r in query_all(con, f"PRAGMA index_list('{table}')")]

def get_columns(con, table):
    return query_all(con, f"PRAGMA table_info('{table}')")

def get_fks(con, table):
    return query_all(con, f"PRAGMA foreign_key_list('{table}')")

def sample(con, table, n=1000):
    return query_all(con, f"SELECT * FROM {table} LIMIT {n}")

def has_index_on(con, table, cols):
    idxs = query_all(con, f"PRAGMA index_list('{table}')")
    for idx in idxs:
        idxname = idx[1]
        idxinfo = query_all(con, f"PRAGMA index_info('{idxname}')")
        idxcols = tuple(i[2] for i in idxinfo)
        if tuple(cols) == idxcols:
            return True
    return False

def get_pragma(con, name):
    return query_all(con, f"PRAGMA {name}")

def row_to_dict(row):
    return dict(row) if row else None

def rows_to_dicts(rows):
    return [dict(r) for r in rows]

# ========== Main Audit Logic ==========
def run_audit(db_path):
    outdir = "./db_audit"
    ensure_dir(outdir)
    summary = {}
    # 1. Connection & PRAGMAs
    uri = f"file:{os.path.abspath(db_path)}?mode=ro"
    con = sqlite3.connect(uri, uri=True)
    con.row_factory = sqlite3.Row
    pragmas = {}
    for p in ["user_version", "foreign_keys", "journal_mode", "synchronous", "page_size", "cache_size", "encoding", "auto_vacuum"]:
        pragmas[p] = get_pragma(con, p)
    integrity = get_pragma(con, "integrity_check")
    quick = get_pragma(con, "quick_check")
    summary["pragmas"] = pragmas
    summary["integrity_check"] = integrity
    summary["quick_check"] = quick

    # 2. Schema inventory
    tables = get_tables(con)
    views = get_views(con)
    triggers = get_triggers(con)
    schema = {}
    suspicious_columns = defaultdict(list)
    for t in tables:
        cols = get_columns(con, t)
        fks = get_fks(con, t)
        idxs = get_indexes(con, t)
        schema[t] = {
            "columns": cols,
            "fks": fks,
            "indexes": idxs,
        }
        # Detect suspicious columns
        for c in cols:
            name, typ, notnull, dflt = c[1], c[2], c[3], c[4]
            if typ.upper() == "TEXT" and name.lower() in ("activo", "habilitado", "flag", "is_active"):
                suspicious_columns[t].append(name)
            if typ.upper() == "TEXT" and ("json" in name.lower() or "data" in name.lower()):
                suspicious_columns[t].append(name)
            if name.lower() in ("email", "mail") and (notnull == 0 or not dflt):
                suspicious_columns[t].append(name)
            if name.lower() in ("telefono", "phone") and (notnull == 0 or not dflt):
                suspicious_columns[t].append(name)
            if "timestamp" in name.lower() and not dflt:
                suspicious_columns[t].append(name)
    summary["schema"] = schema
    summary["suspicious_columns"] = suspicious_columns
    summary["tables"] = tables
    summary["views"] = views
    summary["triggers"] = triggers

    # 3. Expected domain
    expected = ["usuarios", "roles", "posiciones", "sectores", "centros", "catalog_centros", "almacenes", "solicitudes", "solicitud_items", "adjuntos", "notificaciones", "change_requests", "aprobaciones", "presupuestos"]
    missing = [e for e in expected if e not in tables]
    summary["expected_missing"] = missing

    # 4. Data quality checks
    dq = {}
    for t in tables:
        dq[t] = {}
        # Row count
        try:
            cnt = query_all(con, f"SELECT COUNT(*) FROM {t}")[0][0]
        except Exception:
            cnt = None
        dq[t]["row_count"] = cnt
        # Nullability
        cols = get_columns(con, t)
        for c in cols:
            if c[3] == 1:  # notnull
                nulls = query_all(con, f"SELECT COUNT(*) FROM {t} WHERE {c[1]} IS NULL")[0][0]
                if nulls > 0:
                    dq[t].setdefault("null_violations", []).append({"column": c[1], "count": nulls})
        # Orphans
        fks = get_fks(con, t)
        for fk in fks:
            from_col, ref_table, to_col = fk[3], fk[2], fk[4]
            try:
                orphans = query_all(con, f"SELECT {from_col} FROM {t} LEFT JOIN {ref_table} ON {t}.{from_col} = {ref_table}.{to_col} WHERE {ref_table}.{to_col} IS NULL AND {t}.{from_col} IS NOT NULL LIMIT 50")
                if orphans:
                    dq[t].setdefault("orphans", []).append({"fk": f"{from_col}->{ref_table}.{to_col}", "rows": [o[0] for o in orphans]})
            except Exception:
                continue
        # Duplicates (simple heuristics)
        if t == "usuarios":
            dups = query_all(con, "SELECT mail, COUNT(*) FROM usuarios GROUP BY mail HAVING COUNT(*) > 1")
            if dups:
                dq[t]["duplicates"] = [d[0] for d in dups]
        if t == "almacenes":
            dups = query_all(con, "SELECT codigo, centro, COUNT(*) FROM almacenes GROUP BY codigo, centro HAVING COUNT(*) > 1")
            if dups:
                dq[t]["duplicates"] = [f"{d[0]}@{d[1]}" for d in dups]
        # Value patterns
        for c in cols:
            if c[1].lower() in ("mail", "email"):
                # SQLite no soporta REGEXP por defecto, así que solo chequeamos presencia de '@' y '.'
                bad = query_all(con, f"SELECT {c[1]} FROM {t} WHERE {c[1]} IS NOT NULL AND (instr({c[1]}, '@') = 0 OR instr({c[1]}, '.') = 0) LIMIT 10")
                if bad:
                    dq[t].setdefault("invalid_email", []).extend([b[0] for b in bad])
            if c[1].lower() in ("telefono", "phone"):
                # Solo permitimos dígitos, espacios, paréntesis, + y -
                bad = query_all(con, f"SELECT {c[1]} FROM {t} WHERE {c[1]} IS NOT NULL AND {c[1]} GLOB '*[^0-9 ()+-]*' LIMIT 10")
                if bad:
                    dq[t].setdefault("invalid_phone", []).extend([b[0] for b in bad])
        # Encoding scan
        for c in cols:
            if c[2].upper() == "TEXT":
                bad = query_all(con, f"SELECT COUNT(*) FROM {t} WHERE {c[1]} LIKE '%�%'")[0][0]
                if bad:
                    dq[t].setdefault("mojibake", []).append({"column": c[1], "count": bad})
    summary["data_quality"] = dq

    # 5. Performance & indexes
    idx_suggestions = []
    for t in tables:
        fks = get_fks(con, t)
        for fk in fks:
            from_col = fk[3]
            if not has_index_on(con, t, [from_col]):
                idx_suggestions.append({"table": t, "column": from_col, "sql": f"CREATE INDEX IF NOT EXISTS idx_{t}_{from_col} ON {t}({from_col});", "reason": "FK column, improves JOINs and deletes."})
    summary["index_suggestions"] = idx_suggestions

    # 6. Normalization & constraints
    norm = []
    for t in tables:
        cols = get_columns(con, t)
        for c in cols:
            if c[2].upper() == "TEXT" and c[1].lower() in ("estado", "status"):
                norm.append({"table": t, "column": c[1], "suggest": f"Consider CHECK constraint for allowed values on {t}.{c[1]}"})
    summary["normalization"] = norm

    # 7. Security & auditability
    sec = []
    if "usuarios" in tables:
        cols = get_columns(con, "usuarios")
        if not any("hash" in c[1].lower() for c in cols):
            sec.append("usuarios table: password should be hashed, not plaintext.")
    summary["security"] = sec

    # 8. Seed & reference data
    seeds = []
    for t in ("roles", "sectores", "posiciones", "catalog_centros"):
        if t in tables:
            cnt = query_all(con, f"SELECT COUNT(*) FROM {t}")[0][0]
            if cnt == 0:
                seeds.append(f"-- INSERT INTO {t} ...")
    summary["seed_suspects"] = seeds

    # 9. ERD (ASCII)
    erd_lines = ["# ERD (ASCII)"]
    for t in tables:
        erd_lines.append(f"* {t}")
        cols = get_columns(con, t)
        for c in cols:
            erd_lines.append(f"    - {c[1]}: {c[2]}")
        fks = get_fks(con, t)
        for fk in fks:
            erd_lines.append(f"    -> FK: {fk[3]} -> {fk[2]}.{fk[4]}")
    with open(os.path.join(outdir, "erd.txt"), "w", encoding="utf-8") as f:
        f.write("\n".join(erd_lines))

    # Write outputs
    with open(os.path.join(outdir, "findings.json"), "w", encoding="utf-8") as f:
        json.dump(summary, f, indent=2, ensure_ascii=False)
    with open(os.path.join(outdir, "report.md"), "w", encoding="utf-8") as f:
        f.write("# SPM DB Audit Report\n\n")
        f.write(f"## PRAGMAs\n{json.dumps(pragmas, indent=2, ensure_ascii=False)}\n\n")
        f.write(f"## Integrity\n{integrity}\n\n")
        f.write(f"## Schema\n{json.dumps(schema, indent=2, ensure_ascii=False)}\n\n")
        f.write(f"## Suspicious Columns\n{json.dumps(suspicious_columns, indent=2, ensure_ascii=False)}\n\n")
        f.write(f"## Expected Domain\nMissing: {missing}\n\n")
        f.write(f"## Data Quality\n{json.dumps(dq, indent=2, ensure_ascii=False)}\n\n")
        f.write(f"## Index Suggestions\n{json.dumps(idx_suggestions, indent=2, ensure_ascii=False)}\n\n")
        f.write(f"## Normalization\n{json.dumps(norm, indent=2, ensure_ascii=False)}\n\n")
        f.write(f"## Security\n{json.dumps(sec, indent=2, ensure_ascii=False)}\n\n")
        f.write(f"## Seed Suspects\n{json.dumps(seeds, indent=2, ensure_ascii=False)}\n\n")
        f.write("## ERD\n\n" + "\n".join(erd_lines) + "\n")
    with open(os.path.join(outdir, "fixes.sql"), "w", encoding="utf-8") as f:
        for n in norm:
            f.write(f"-- {n['suggest']}\n")
        for s in sec:
            f.write(f"-- {s}\n")
    with open(os.path.join(outdir, "indexes.sql"), "w", encoding="utf-8") as f:
        for idx in idx_suggestions:
            f.write(f"{idx['sql']} -- {idx['reason']}\n")
    with open(os.path.join(outdir, "seed_suspects.sql"), "w", encoding="utf-8") as f:
        for s in seeds:
            f.write(f"{s}\n")
    print(f"Audit complete. Outputs written to {outdir}/\n  - report.md\n  - findings.json\n  - fixes.sql\n  - indexes.sql\n  - seed_suspects.sql\n  - erd.txt\n")

if __name__ == "__main__":
    import argparse
    p = argparse.ArgumentParser(description="SPM SQLite DB Audit Tool")
    p.add_argument("--db", default="./spm.db", help="Path to SQLite DB file")
    args = p.parse_args()
    run_audit(args.db)
