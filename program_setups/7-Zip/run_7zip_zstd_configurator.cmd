@echo off
setlocal
pushd "%~dp0" || exit /b 1

set PYTHONDONTWRITEBYTECODE=1
python "7zip_zstd_configurator\configure_7zip_zs.py" %*
set "RESULT=%ERRORLEVEL%"

popd
exit /b %RESULT%
