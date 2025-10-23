@echo off
setlocal
if exist ".venv\Scripts\activate.bat" (
  call .venv\Scripts\activate
) else (
  echo Virtual environment not found. Run recrear_venv.ps1 first.
  exit /b 1
)
set FLASK_APP=src.backend.app
set FLASK_ENV=development
set PORT=10000
python -m src.backend.app
