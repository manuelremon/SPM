# Plan de migración y verificación

1. Aplicar diff generado: `git apply fix-repo-structure.diff`
2. Verificar cambios: `git status --porcelain`
3. Instalar dependencias Python: `python -m pip install -r requirements/backend.txt` (opcional)
4. Ejecutar tests: `python -m pytest -q`
5. Build frontend: `cd src\frontend ; npm ci ; npm run build`
6. Verificar que las DB y logs estén en `src/backend/data` y `src/backend/logs`.

Rollback rápido:

- Para revertir aplicar el patch inverso: `git apply -R fix-repo-structure.diff`
- Restaurar backups: buscar archivos `*.codexbackup` y moverlos a su ruta original.
