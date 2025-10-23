@echo off
setlocal
start cmd /k "call .venv\Scripts\activate && set FLASK_APP=src.backend.app && set FLASK_ENV=development && set SPM_DEV_MODE=proxy && set PORT=10000 && python -m src.backend.app"
timeout /t 2 >nul
npm run dev
