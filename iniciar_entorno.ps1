# Script: iniciar_entorno.ps1
# Propósito: activar entorno, abrir VS Code y preparar flujo de trabajo.

Write-Host "=== INICIANDO ENTORNO DE DESARROLLO SPM ===" -ForegroundColor Cyan

# Ruta base del proyecto
$projectPath = "E:\GitHub\SPM-2"
Set-Location $projectPath

# 1. Activar entorno virtual
if (Test-Path ".venv\Scripts\activate") {
    Write-Host "→ Activando entorno virtual..."
    .\.venv\Scripts\activate
    Write-Host "✅ Entorno activado." -ForegroundColor Green
} else {
    Write-Host "❌ No se encontró .venv. Ejecute 'recrear_venv.ps1' primero." -ForegroundColor Red
    exit
}

# 2. Abrir VS Code en la carpeta del proyecto
Write-Host "→ Abriendo Visual Studio Code..."
Start-Process code -ArgumentList "."

# 3. (Opcional) Sincronizar con GitHub
Write-Host "→ Verificando cambios de Git..."
git status
Write-Host "`nSi desea subir los cambios, use:" -ForegroundColor Yellow
Write-Host "  git add ."
Write-Host "  git commit -m 'mensaje'"
Write-Host "  git push`n"

# 4. (Opcional) Despliegue manual en Render
Write-Host "¿Desea ejecutar un despliegue manual en Render? (s/n)"
$response = Read-Host
if ($response -eq "s") {
    Write-Host "→ Iniciando despliegue Render (requiere render-cli instalado)..."
    render deploy . | Out-Host
}
