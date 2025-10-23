@echo off
setlocal

IF NOT EXIST .venv (
  py -m venv .venv
)

call .venv\Scripts\activate
py -m pip install --upgrade pip
pip install -r requirements.txt

if "%SPM_ENV%"=="" set SPM_ENV=development
if "%SPM_DEBUG%"=="" set SPM_DEBUG=1
if "%PORT%"=="" set PORT=5001
set PYTHONPATH=%cd%

start "" http://127.0.0.1:%PORT%/
python src\backend\app.py
