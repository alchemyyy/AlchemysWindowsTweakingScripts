@echo off
setlocal

net session >nul 2>&1
if %errorlevel% neq 0 (
    echo Requesting administrator privileges...
    powershell -NoProfile -Command "Start-Process -FilePath '%~f0' -Verb RunAs"
    exit /b
)

set "DLL_NAME=7ZipZSContextMenuExtension.dll"
set "INSTALL_DIR="

for /f "tokens=2,*" %%A in ('reg query "HKLM\SOFTWARE\7-Zip-Zstandard" /v Path64 2^>nul') do set "INSTALL_DIR=%%B"
if not defined INSTALL_DIR for /f "tokens=2,*" %%A in ('reg query "HKLM\SOFTWARE\7-Zip-Zstandard" /v Path 2^>nul') do set "INSTALL_DIR=%%B"
if not defined INSTALL_DIR for /f "tokens=2,*" %%A in ('reg query "HKCU\Software\7-Zip-Zstandard" /v Path64 2^>nul') do set "INSTALL_DIR=%%B"
if not defined INSTALL_DIR for /f "tokens=2,*" %%A in ('reg query "HKCU\Software\7-Zip-Zstandard" /v Path 2^>nul') do set "INSTALL_DIR=%%B"
if not defined INSTALL_DIR set "INSTALL_DIR=%ProgramFiles%\7-Zip-Zstandard"

if "%INSTALL_DIR:~-1%"=="\" set "INSTALL_DIR=%INSTALL_DIR:~0,-1%"

echo.
echo ==========================================
echo  7-Zip ZS Quick Context Menu - Uninstaller
echo ==========================================
echo.

echo Stopping Explorer...
taskkill /f /im explorer.exe >nul 2>&1
timeout /t 2 /nobreak >nul

if exist "%INSTALL_DIR%\%DLL_NAME%" (
    echo Unregistering shell extension...
    regsvr32 /s /u "%INSTALL_DIR%\%DLL_NAME%"
    del /f "%INSTALL_DIR%\%DLL_NAME%"
) else (
    echo DLL was not found at "%INSTALL_DIR%\%DLL_NAME%".
)

echo Restarting Explorer...
start explorer.exe

echo.
echo Uninstallation complete.
echo.
pause
