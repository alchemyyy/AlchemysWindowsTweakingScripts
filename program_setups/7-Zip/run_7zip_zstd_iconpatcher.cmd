@echo off
setlocal
pushd "%~dp0" || exit /b 1

set PYTHONDONTWRITEBYTECODE=1
python -m 7zip_zstd_iconpatcher %*
set "RESULT=%ERRORLEVEL%"

popd
exit /b %RESULT%
