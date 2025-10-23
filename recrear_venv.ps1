# Script: recrear_venv.ps1
# Ejecutar como Administrador si es necesario.

Write-Host "=== REPARANDO ENTORNO PYTHON ===" -ForegroundColor Cyan

# Ruta del proyecto (ajustá si tu carpeta cambia)
$projectPath = "E:\GitHub\SPM-2"
$venvPath = "$projectPath\.venv"

# 1. Tomar propiedad y asignar permisos
Write-Host "→ Tomando propiedad de la carpeta..."
takeown /F "$projectPath" /R /A | Out-Null
icacls "$projectPath" /grant "$($env:USERNAME):(F)" /T | Out-Null

# 2. Eliminar entorno viejo
if (Test-Path $venvPath) {
    Write-Host "→ Eliminando entorno previo (.venv)..."
    Remove-Item -Recurse -Force $venvPath
} else {
    Write-Host "→ No hay entorno previo, continuando..."
}

# 3. Crear entorno nuevo
Write-Host "→ Creando nuevo entorno virtual..."
python -m venv $venvPath

# 4. Confirmar creación
if (Test-Path "$venvPath\Scripts\activate") {
    Write-Host "✅ Entorno creado correctamente." -ForegroundColor Green
    Write-Host "→ Abriendo nueva sesión con el entorno activado..."
    Start-Process powershell -ArgumentList "-NoExit", "Set-Location '$projectPath'; .\.venv\Scripts\activate"
} else {
    Write-Host "❌ Error: No se pudo crear el entorno virtual." -ForegroundColor Red
}
