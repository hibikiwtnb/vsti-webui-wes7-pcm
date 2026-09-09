@echo off
setlocal
cd /d "%~dp0"

echo [1/3] Checking local changes...
for /f "delims=" %%A in ('git status --porcelain') do (
    echo Local changes detected. Update cancelled to avoid overwriting them.
    echo.
    git status --short
    echo.
    pause
    exit /b 1
)

echo [2/3] Pulling latest code from GitHub...
git pull --ff-only origin main
if errorlevel 1 (
    echo.
    echo Git pull failed.
    pause
    exit /b 1
)

echo.
echo [3/3] Restarting VSTi WebUI...
powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%~dp0Start-VstiWebUi.ps1"
set "EXITCODE=%ERRORLEVEL%"

if not "%EXITCODE%"=="0" (
    echo.
    echo VSTi WebUI exited with code %EXITCODE%.
    pause
)

exit /b %EXITCODE%
