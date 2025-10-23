#!/usr/bin/env python3
"""Mover artefactos generados (DBs, uploads, logs) a la estructura nueva.

Este script hace copias de seguridad renombrando los archivos originales con
un sufijo .YYYYmmddHHMMSS.codexbackup antes de moverlos.
"""
from pathlib import Path
import shutil
import time


TS = time.strftime('%Y%m%d%H%M%S')
ROOT = Path(__file__).resolve().parents[1]
TARGET_DATA = ROOT / 'src' / 'backend' / 'data'
TARGET_UPLOADS = ROOT / 'src' / 'backend' / 'uploads'
TARGET_LOGS = ROOT / 'src' / 'backend' / 'logs'


def backup_and_move(src: Path, dst: Path):
    if not src.exists():
        return None
    dst.parent.mkdir(parents=True, exist_ok=True)
    backup = src.with_name(src.name + f'.{TS}.codexbackup')
    print(f'Backing up {src} -> {backup}')
    shutil.copy2(src, backup)
    final = dst
    if dst.exists():
        # if destination exists, add timestamp
        final = dst.with_name(dst.name + f'.{TS}')
    print(f'Moving {src} -> {final}')
    shutil.move(str(src), str(final))
    return final


def main():
    # Candidate files in repo root
    candidates = ['test.db', 'ai_assistant.db', 'spm.db', 'server.log', 'server_run.err', 'server_run.log']
    for name in candidates:
        p = ROOT / name
        if p.exists():
            if name.endswith('.db'):
                dst = TARGET_DATA / name
                backup_and_move(p, dst)
            else:
                dst = TARGET_LOGS / name
                backup_and_move(p, dst)

    # Move nested duplicate src/src/backend/spm.db if present
    dup = ROOT / 'src' / 'src' / 'backend' / 'spm.db'
    if dup.exists():
        backup_and_move(dup, TARGET_DATA / 'spm.db')

    # Move uploads/ if exists at repo root
    uploads = ROOT / 'uploads'
    if uploads.exists() and uploads.is_dir():
        for f in uploads.rglob('*'):
            if f.is_file():
                rel = f.relative_to(uploads)
                dst = TARGET_UPLOADS / rel
                dst.parent.mkdir(parents=True, exist_ok=True)
                backup = f.with_name(f.name + f'.{TS}.codexbackup')
                print(f'Backing up {f} -> {backup}')
                shutil.copy2(f, backup)
                print(f'Moving {f} -> {dst}')
                shutil.move(str(f), str(dst))

    print('Done. Verifica src/backend/data, src/backend/logs y src/backend/uploads')


if __name__ == '__main__':
    main()
