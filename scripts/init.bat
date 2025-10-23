@echo off
setlocal

for %%I in ("%~dp0..") do set "ROOT_DIR=%%~fI"
set "COMPOSE_FILE=%ROOT_DIR%\infra\docker\docker-compose.yml"

echo Stopping existing containers...
docker compose -f "%COMPOSE_FILE%" down

echo Starting SPM stack...
docker compose -f "%COMPOSE_FILE%" up --build -d

timeout /t 3 >nul
start "" "http://localhost:8080"

echo.
echo SPM disponible en http://localhost:8080

endlocal
