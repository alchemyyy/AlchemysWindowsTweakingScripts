@echo off
setlocal
cd /d "%~dp0"
python "%~dp0setup_vencord.py" %*
pause
