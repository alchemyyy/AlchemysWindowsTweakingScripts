@echo off
setlocal
pushd "%~dp0" || exit /b 1

set PYTHONDONTWRITEBYTECODE=1
start "7zip_context_menu_extension\install.bat" %*
set "RESULT=%ERRORLEVEL%"

popd
exit /b %RESULT%
