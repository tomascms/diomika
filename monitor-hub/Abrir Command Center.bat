@echo off
setlocal
cd /d "%~dp0"

if not exist "node_modules\electron\cli.js" (
  echo A instalar dependencias do Command Center...
  call npm install
  if errorlevel 1 (
    echo.
    echo Falhou o npm install. Abre um terminal em monitor-hub e corre: npm install
    pause
    exit /b 1
  )
)

set NODE_OPTIONS=--use-system-ca
call npm start
