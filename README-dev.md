## Desarrollo local

SPM ahora puede ejecutarse en un Ãºnico origen (opciÃ³n recomendada) o con dos servidores coordinados mediante un proxy. Ambas configuraciones sirven los mismos archivos front-end desde `src/frontend` y exponen la API Flask bajo `/api`.

### Requisitos previos
- Python 3.11 con entorno virtual en `.venv`
- Dependencias backend instaladas (`pip install -r requirements.txt`)
- Node.js 18+ si deseas usar la opciÃ³n con dos servidores (`npm install`)

### OpciÃ³n A Â· Un solo origen (Flask)
1. Ejecuta `run_dev.bat`.
2. Flask se iniciarÃ¡ en `http://127.0.0.1:10000` sirviendo HTML, CSS, JS y API desde el mismo host/puerto.
3. El banner de arranque mostrarÃ¡: `SPM dev server -> http://127.0.0.1:10000  |  API base -> /api  |  Single-origin ON`.

**Verificaciones**
- Navega a `http://127.0.0.1:10000/home.html` sin errores 404.
- Revisa `http://127.0.0.1:10000/api/health` â†’ `{"ok": true}`.
- Los formularios de login POSTean a `http://127.0.0.1:10000/api/login`.

### OpciÃ³n B Â· Dos servidores con proxy (Vite + Flask)
1. Instala dependencias front-end: `npm install`.
2. Ejecuta `run_dev_two_servers.bat`. El script abre Flask (API en :10000) y luego Vite (front en :5173).
3. El banner de Flask indica: `SPM -> API http://127.0.0.1:10000/api  |  Front dev http://127.0.0.1:5173  |  Proxy /api activo`.
4. Accede a `http://127.0.0.1:5173/home.html`. Todas las llamadas a `/api` se enrutan por el proxy hacia Flask.

**Verificaciones**
- `http://127.0.0.1:5173/api/health` responde 200 porque Vite reenvÃ­a al backend.
- Assets y HTML usan rutas relativas (`/styles.css`, `/app.js`), por lo que no hay puertos hardcodeados.

### AutenticaciÃ³n
- `POST /api/login` emite la cookie HttpOnly `access_token`; no se almacenan tokens en `localStorage`.
- Las pÃ¡ginas protegidas usan `GET /api/me` (o el shim `/api/usuarios/me`) para recuperar el perfil; un 401 redirige de nuevo a `index.html`.
- `POST /api/logout` elimina la cookie `access_token`; el frontend limpia el estado local y vuelve al inicio.

### Health check y rutas clave
- `GET /api/health` -> `{"ok": true}`
- Al iniciar, Flask lista una vez las rutas relevantes (`ROUTE /...`).

### SoluciÃ³n de problemas comunes
- **404 en home.html**: confirma que `src/frontend/home.html` existe y que lanzaste la opciÃ³n correcta.
- **405 en mÃ©todos PATCH/PUT**: verifica que el endpoint estÃ© expuesto por los blueprints y que el proxy (opciÃ³n B) no reescriba el mÃ©todo.
- **Errores CORS**: no deberÃ­an ocurrir en la opciÃ³n A. En la opciÃ³n B, asegÃºrate de usar el proxy `/api` provisto por Vite y no llamar a `http://127.0.0.1:10000` directamente desde el navegador.
- **Texto mal codificado**: las respuestas JSON y HTML se envÃ­an con `charset=utf-8`; revisa encabezados personalizados que puedas estar agregando.

### Pasos rapidos (PowerShell)

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
cd src/frontend
npm ci
npm run build
cd ..\..
$env:SPM_SECRET_KEY='dev-temp-key'
$env:SPM_DEBUG='true'
python .\src\backend\app.py
Invoke-WebRequest http://127.0.0.1:10000/healthz | % Content
```

- Abre `http://127.0.0.1:10000/` en el navegador para validar el front-end.