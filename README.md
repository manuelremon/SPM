# SPM · Solicitudes (CSV)

Aplicación mínima para cargar y listar solicitudes de materiales basada en Flask (API + estáticos) y JS vanilla.

## Requisitos

- Python 3.12+
- (Opcional) Docker / Docker Compose v2

## Ejecución local (todo-en-uno)

```bash
# 1) Crear entorno e instalar dependencias del backend
python -m venv .venv
. .venv/bin/activate  # En Windows: .venv\Scripts\activate
pip install -r requirements/backend.txt

# 2) Variables de entorno (opcional)
export SPM_SECRET_KEY="cambia-esto"
export SPM_CORS_ORIGINS="http://localhost:8080,http://127.0.0.1:5173"

# 3) Levantar el backend (sirve el frontend desde /)
python src/backend/app.py

# 4) Modo producción opcional
PYTHONPATH=src gunicorn backend.app:create_app
```

Abrí <http://localhost:5000/> en el navegador.

> **Nota**: La base `src/backend/data/spm.db` ya viene incluida con datos de ejemplo. Si querés regenerarla desde los CSV, borra el archivo `spm.db` y el backend la creará al iniciar.

## Docker

```bash
docker build -t spm-backend -f infra/docker/backend.Dockerfile .
docker run --rm -p 5000:5000 -e SPM_SECRET_KEY="cambia-esto" spm-backend
```

Para levantar backend + Nginx en modo desarrollo:

```bash
docker compose -f infra/docker/docker-compose.yml up --build
```

O bien usar el script cross-platform:

```bash
# Linux / macOS
./scripts/init.sh

# Windows (PowerShell / CMD)
scripts\\init.bat
```

## Endpoints rápidos (para probar)

```bash
curl -i http://localhost:5000/api/health

# Login
curl -i -X POST http://localhost:5000/api/login \
  -H 'Content-Type: application/json' \
  -d '{"id":"usuario1","password":"changeme123"}'

# Búsqueda de materiales
curl -i 'http://localhost:5000/api/materiales?q=valvula&limit=5'
```

## Estructura

- `src/backend/`: API Flask, base SQLite y cargas desde CSV.
- `src/backend/data/Centros.csv`, `Almacenes.csv`, `Roles.csv`, `Puestos.csv`, `Sectores.csv`: catálogos editables sincronizados con Admin > Configuración (corre `python -m backend.init_db` si los modificás manualmente).
- `src/frontend/`: HTML/CSS/JS estático que se sirve desde Flask o Nginx.
- `src/agent/`: prototipos FastAPI auxiliares (no requeridos por la app principal, instalar con `pip install -r requirements/agent.txt`).
- `infra/`: definición de Docker, Nginx y despliegues (Render).
- `requirements/`: archivos de dependencias segmentados.
- `scripts/`: utilidades para levantar o detener el stack.
- `docs/`: material auxiliar y vistas previas.

---

Hecho con cariño y obsesión por los bordes extraños del mundo del software. :)
