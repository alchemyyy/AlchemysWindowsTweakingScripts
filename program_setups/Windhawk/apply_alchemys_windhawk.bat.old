@echo off
setlocal

net session >nul 2>&1
if not "%errorlevel%"=="0" (
    powershell -NoProfile -ExecutionPolicy Bypass -Command "Start-Process -FilePath '%~f0' -Verb RunAs"
    exit /b
)

cd /d "%~dp0"
python "%~dp0windhawk_bar.py" restore "%~dp0alchemys_windhawk_settings.json" --standard --json-only --install-windhawk-if-missing
pause
