@echo off
setlocal
if /i "%~1"=="ELEVATED" goto :run
net session >nul 2>nul
if not "%errorlevel%"=="0" (
  echo Requesting administrator privileges...
  powershell -NoProfile -ExecutionPolicy Bypass -Command "Start-Process -FilePath '%ComSpec%' -ArgumentList '/d /c ""%~f0"" ELEVATED' -Verb RunAs -Wait"
  exit /b
)
:run
cd /d "%~dp0"
where py >nul 2>nul
if %errorlevel%==0 (
  py -3 "%~dp0acrobat_context_menu_nuke.py" --apply --deep --quarantine-dlls --kill-acrobat --restart-explorer --no-elevate
) else (
  python "%~dp0acrobat_context_menu_nuke.py" --apply --deep --quarantine-dlls --kill-acrobat --restart-explorer --no-elevate
)
echo.
echo Done. Review the output above for the backup JSON path.
pause
