@echo off
setlocal
pushd "%~dp0" || exit /b 1

set PYTHONDONTWRITEBYTECODE=1
python "install_7zip_zstd.py" %*
set "RESULT=%ERRORLEVEL%"

popd
exit /b %RESULT%
