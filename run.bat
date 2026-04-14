@echo off
REM FindMyForce - Run both API bridge server and Web frontend
REM Usage: run.bat

echo ========================================
echo   FindMyForce - Common Operating Picture
echo ========================================
echo.

set SCRIPT_DIR=%~dp0
set API_DIR=%SCRIPT_DIR%FindMyForce-API
set WEB_DIR=%SCRIPT_DIR%FindMyForce-Web

REM Install web dependencies if needed
if not exist "%WEB_DIR%\node_modules\leaflet" (
    echo [WEB] Installing npm dependencies...
    cd /d "%WEB_DIR%"
    call npm install
)

REM Start API bridge server in a new window
echo [API] Starting bridge server on http://localhost:5000 ...
start "FindMyForce-API" cmd /c "cd /d %API_DIR% && python -m findmyforce.web_server"

REM Give the API server a moment
timeout /t 3 /nobreak > nul

REM Start web dev server in a new window
echo [WEB] Starting Vite dev server...
start "FindMyForce-Web" cmd /c "cd /d %WEB_DIR% && npm run dev"

echo.
echo Services running:
echo   API Bridge:   http://localhost:5000
echo   Web Frontend: http://localhost:5173
echo.
echo Close the API and Web windows to stop, or press any key to exit this launcher.
pause > nul
