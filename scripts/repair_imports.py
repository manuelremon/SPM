#!/usr/bin/env python3
"""Detecta imports rotos por movimiento de carpetas y sugiere cambios.

No aplica cambios automáticamente; imprime sugerencias.
"""
import ast
import sys
from pathlib import Path


def find_py_files(root: Path):
    for p in root.rglob('*.py'):
        yield p


def analyze(root: Path):
    fixes = []
    for f in find_py_files(root):
        try:
            src = f.read_text(encoding='utf-8')
            tree = ast.parse(src)
        except Exception:
            continue
        for node in ast.walk(tree):
            if isinstance(node, ast.ImportFrom):
                mod = node.module or ''
                if 'src.src' in mod:
                    fixes.append((str(f), mod, mod.replace('src.src', 'src')))
    return fixes


def main(argv=None):
    root = Path(__file__).resolve().parents[1]
    fixes = analyze(root)
    if not fixes:
        print('No se detectaron imports obvios a corregir.')
        return 0
    print('Imports sugeridos a corregir:')
    for f, old, new in fixes:
        print(f"{f}: {old} -> {new}")
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
