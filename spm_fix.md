# Tarea Codex/Copilot — Auditoría, corrección y mejoras del proyecto **SPM (Solicitudes Puntuales de Materiales)**

**Rol:** Actúa como un *ingeniero de software senior full‑stack* (Python/Flask + HTML/JS/CSS) con foco en calidad, seguridad y DX (developer experience). Tu objetivo es **dejar el proyecto funcionando de punta a punta**, con *build reproducible*, *tests básicos*, *logs útiles* y *UI responsive*, corrigiendo errores y aplicando mejoras pragmáticas sin romper compatibilidad.

## Contexto del repo
- Backend: Python (Flask) ejecutado con `python src/backend/app.py`.
- Frontend: HTML/JS “vanilla” servido como estáticos (bandejas, editor de solicitud, listados).
- Autenticación: JWT en cookies; endpoint `/api/me` usado en el inicio de sesión de `mi-cuenta.html`.
- Problema observado: expiración del JWT (TTL) provoca `state.me = null` y redirección a `index.html`.
- Objetivo de despliegue local: Windows (PowerShell / .bat) y compatibilidad con Linux.
- Nombre del repo: `spm222`.

> Si alguna ruta/archivo difiere, **detéctalo y ajústalo**; no te quedes bloqueado por supuestos.

## Tareas (en este orden)

1. **Arranque y diagnóstico**
   - Detecta y documenta la versión mínima de Python.
   - Genera/actualiza `requirements.txt` y `pip-tools` opcional (`requirements.in` + `pip-compile`) para *pinning*.
   - Crea/actualiza `.env.example` con variables necesarias (SECRET_KEY, JWT_TTL, REFRESH_TTL, LOG_LEVEL, PORT, etc.).
   - Ejecuta el backend en modo dev. Si falla, **corrige import paths, app factory, CORS, y manejo de estáticos**.
   - Verifica el frontend sirviendo desde el backend y también en modo `file://` (si aplica la lógica de `API` ya existente).

2. **Autenticación y sesión**
   - Revisa middleware/blueprint de auth.
   - Asegura **JWT en cookie HttpOnly + Secure + SameSite=Lax** (o `None` si hay cross-site necesario).
   - Implementa/ajusta **refresh tokens** con rotación segura (lista de bloqueados o *JTI*) y **gracia de expiración** configurable.
   - Endpoint `/api/me`: devuelve 200 con datos del usuario si el access token es válido; 401 con JSON consistente si no lo es. Nunca HTML.
   - TTL por defecto: `ACCESS_TTL=24h`, `REFRESH_TTL=7d` (parametrizable en `.env`).
   - Mensajes de error **uniformes** (`{"error":"...", "code":"..."}`).

3. **Manejo de errores y logging**
   - Implementa `@app.errorhandler` global para 400/401/403/404/500 con JSON consistente.
   - Logging estructurado (JSON) a consola con nivel configurable; agrega *correlation id* por request.
   - En frontend, conserva el *toast*/banner de errores y **no** filtren stack traces al usuario en prod.

4. **Rutas API y contratos**
   - Enumera y valida endpoints existentes. Para cada endpoint:
     - Especifica **contratos request/response** (incluye ejemplos).
     - Valida inputs (tipos, rangos, required). Usa `pydantic` o `marshmallow`.
     - Responde con **códigos HTTP correctos** y sin ambigüedades.
   - Añade **tests mínimos** (pytest) para auth, `/api/me` y un endpoint de negocio.

5. **Frontend (HTML/JS/CSS)**
   - Corrige referencias rotas, selectores, y *race conditions* de carga.
   - Asegura **responsive design**: *meta viewport*, layout fluido, tipografías y espaciados consistentes. Evita *layout shift*.
   - Extra: activa un efecto de *smooth scrolling* **solo** cuando sea apropiado y sin degradar rendimiento.
   - Donde `API` calcula la base URL, garantiza que funcione en `file://` y detrás de Nginx/Render.

6. **DX (developer experience)**
   - Añade scripts:
     - `scripts/dev.ps1` y `scripts/dev.sh` para levantar entorno.
     - `run-dev.bat` en la raíz que:
       1) activa venv,
       2) instala deps si faltan,
       3) ejecuta `python src/backend/app.py`,
       4) abre el navegador en la URL local.
   - Documenta en `README.md` cómo correr, testear y configurar.

7. **Seguridad y calidad**
   - Cookies seguras; no exponer secretos en cliente.
   - CORS mínimo necesario.
   - Rate limit básico para login.
   - Dependabot/`pip-audit` o `safety` para vulnerabilidades.
   - Linter (`ruff`) y formatter (`black`); `pre-commit` opcional.

8. **Entrega de artefactos**
   - Crea los archivos/fixes necesarios.
   - Emite **un diff unificado** con todos los cambios (compatible `git apply`).
   - Incluye **mensaje(s) de commit** claros.
   - Escribe un **resumen final** con:
     - Qué estaba roto y cómo se arregló.
     - Cómo iniciar localmente.
     - Check de endpoints y pruebas que pasan.

## Criterios de éxito (debes verificar)

- `python src/backend/app.py` levanta sin errores con un `.env` configurado.
- Login/logout funcionan; `/api/me` responde estable y no se cae por TTL corto.
- Frontend se ve y usa bien en desktop y móvil (layout fluido).
- Tests básicos pasan: `pytest -q`.
- Logs útiles en consola; errores devuelven JSON coherente.
- README actualizado y scripts de arranque listos (Windows y Linux).

## Reglas de edición
- Prioriza **mínimos cambios efectivos**; no rehagas el mundo.
- Mantén nombres y estructura cuando sea razonable; si mueves algo, explica por qué.
- Donde dudes, **elige la opción más simple** que pase criterios de éxito.
- Evita dependencias pesadas para un problema pequeño.

## Formato de salida requerido

1) **Resumen técnico** (máx. 200 líneas): diagnóstico, decisiones y trade-offs.  
2) **Instrucciones de ejecución local** (paso a paso).  
3) **Unified diff** aplicable con `git apply` (incluye nuevos archivos).  
4) **Comandos útiles** (crear venv, correr tests, linters, scripts).  
5) **Siguientes mejoras sugeridas** (lista corta, priorizada).

### Snippets que puedes generar (y adaptar al repo existente)

**`run-dev.bat`**
```bat
@echo off
setlocal
IF NOT EXIST .venv (
  py -m venv .venv
)
call .venv\Scripts\activate
py -m pip install --upgrade pip
pip install -r requirements.txt
set FLASK_ENV=development
set PYTHONPATH=%cd%
start "" http://127.0.0.1:5001/
python src\backend\app.py
```

**`scripts/dev.sh`**
```bash
#!/usr/bin/env bash
set -euo pipefail
python3 -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
pip install -r requirements.txt
export FLASK_ENV=development
export PYTHONPATH="$PWD"
python src/backend/app.py
```

**`.env.example`**
```
SECRET_KEY=replace_me
ACCESS_TTL_SECONDS=86400
REFRESH_TTL_SECONDS=604800
LOG_LEVEL=INFO
PORT=5001
CORS_ORIGINS=http://localhost:5001
```

**`pytest` ejemplo para `/api/me`**
```python
def test_me_requires_auth(client):
    r = client.get("/api/me")
    assert r.status_code == 401
    assert "error" in r.get_json()
```
---

## Lista de verificación diaria (salud del proyecto)

- [ ] `pytest -q` pasa localmente.
- [ ] `ruff check .` y `black --check .` sin errores.
- [ ] `pip-audit` o `safety check` sin vulnerabilidades críticas.
- [ ] `python src/backend/app.py` inicia y responde `/api/health` con 200.
- [ ] Último commit incluye mensaje claro y diff legible.
- [ ] `README.md` actualizado si hubo cambios en scripts o variables.
- [ ] Frontend carga en móvil (inspeccionar con devtools emulando 375×812).
- [ ] Logs de error recientes revisados; issues abiertos si aplica.
