from __future__ import annotations

import csv
import os
import sqlite3

from flask import Blueprint, jsonify
from .decorators import require_roles
bp = Blueprint('export', __name__, url_prefix='/api/export')

@bp.get('/solicitudes')
@require_roles('admin')
def exportar():
    rows = _fetch_rows()
    if not csv_path:
        base_dir = getattr(Settings, "BASE_DIR", Settings.DATA_DIR)
        csv_path = os.path.join(base_dir, "data", "solicitudes_export.csv")
    os.makedirs(os.path.dirname(csv_path), exist_ok=True)

    fieldnames = rows[0].keys() if rows else []
    with open(csv_path, "w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        for row in rows:
            writer.writerow(dict(row))
    return jsonify({'ok': True})


if __name__ == "__main__":
    output_path = export_solicitudes()
    print(f"Archivo generado: {output_path}")
