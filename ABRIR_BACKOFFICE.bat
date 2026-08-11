@echo off
setlocal EnableExtensions
cd /d "%~dp0"

title Diomika Backoffice
echo.
echo  === Diomika Backoffice (local only) ===
echo.

REM Health check correcto (curl -f falha se nao for 2xx)
curl.exe -sf http://127.0.0.1:8001/health >NUL 2>&1
if errorlevel 1 (
  echo  API offline em 127.0.0.1:8001 — a arrancar...
  python "%~dp0deploy\start_local_api.py"
  if errorlevel 1 (
    echo.
    echo  Falhou o arranque da API.
    echo  Alternativa: python INICIAR_DIOMIKA.py
    echo.
    pause
    exit /b 1
  )
) else (
  echo  API OK em http://127.0.0.1:8001/health
)

cd /d "%~dp0backoffice-desktop"
if not exist node_modules (
  echo  A instalar dependencias do backoffice...
  call npm install
  if errorlevel 1 (
    echo  Falhou npm install
    pause
    exit /b 1
  )
)

if exist "release\Diomika-Backoffice.exe" (
  echo  A abrir Diomika-Backoffice.exe ...
  echo  Login local + MFA. Proxy /api -^> 127.0.0.1:8001
  start "" "%~dp0backoffice-desktop\release\Diomika-Backoffice.exe"
  exit /b 0
)

echo  EXE em falta — a abrir Electron (npm run start^)...
call npm run start
endlocal
