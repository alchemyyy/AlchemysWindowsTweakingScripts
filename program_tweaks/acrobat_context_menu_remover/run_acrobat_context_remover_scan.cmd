@echo off
setlocal
cd /d "%~dp0"
where py >nul 2>nul
if %errorlevel%==0 (
  py -3 "%~dp0acrobat_context_menu_nuke.py" --scan --deep
) else (
  python "%~dp0acrobat_context_menu_nuke.py" --scan --deep
)
echo.
pause
