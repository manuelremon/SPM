param(
  [switch]$NoInstall
)

if (-not (Test-Path ".venv")) {
  python -m venv .venv
}

& .\.venv\Scripts\Activate.ps1

if (-not $NoInstall) {
  python -m pip install --upgrade pip
  pip install -r requirements.txt
}

if (-not $env:SPM_ENV) { $env:SPM_ENV = "development" }
if (-not $env:SPM_DEBUG) { $env:SPM_DEBUG = "1" }
if (-not $env:PORT) { $env:PORT = "5001" }
$env:PYTHONPATH = (Get-Location).Path

python src\backend\app.py
