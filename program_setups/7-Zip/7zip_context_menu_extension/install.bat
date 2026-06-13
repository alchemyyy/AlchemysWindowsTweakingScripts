@echo off
setlocal

net session >nul 2>&1
if %errorlevel% neq 0 (
    echo Requesting administrator privileges...
    powershell -NoProfile -Command "Start-Process -FilePath '%~f0' -Verb RunAs"
    exit /b
)

set "DLL_NAME=7ZipZSContextMenuExtension.dll"
set "SOURCE_DIR=%~dp0"
set "INSTALL_DIR="

for /f "tokens=2,*" %%A in ('reg query "HKLM\SOFTWARE\7-Zip-Zstandard" /v Path64 2^>nul') do set "INSTALL_DIR=%%B"
if not defined INSTALL_DIR for /f "tokens=2,*" %%A in ('reg query "HKLM\SOFTWARE\7-Zip-Zstandard" /v Path 2^>nul') do set "INSTALL_DIR=%%B"
if not defined INSTALL_DIR for /f "tokens=2,*" %%A in ('reg query "HKCU\Software\7-Zip-Zstandard" /v Path64 2^>nul') do set "INSTALL_DIR=%%B"
if not defined INSTALL_DIR for /f "tokens=2,*" %%A in ('reg query "HKCU\Software\7-Zip-Zstandard" /v Path 2^>nul') do set "INSTALL_DIR=%%B"
if not defined INSTALL_DIR set "INSTALL_DIR=%ProgramFiles%\7-Zip-Zstandard"

if "%INSTALL_DIR:~-1%"=="\" set "INSTALL_DIR=%INSTALL_DIR:~0,-1%"

echo.
echo ========================================
echo  7-Zip ZS Quick Context Menu - Installer
echo ========================================
echo.

if not exist "%INSTALL_DIR%\7zG.exe" (
    echo ERROR: 7-Zip ZS was not found at "%INSTALL_DIR%".
    echo Install 7-Zip-Zstandard or update INSTALL_DIR in this script.
    pause
    exit /b 1
)

if not exist "%SOURCE_DIR%%DLL_NAME%" (
    echo ERROR: %DLL_NAME% not found.
    echo Run build.bat first.
    pause
    exit /b 1
)

echo Stopping Explorer...
taskkill /f /im explorer.exe >nul 2>&1
timeout /t 2 /nobreak >nul

echo Copying %DLL_NAME% to "%INSTALL_DIR%"...
copy /y "%SOURCE_DIR%%DLL_NAME%" "%INSTALL_DIR%\%DLL_NAME%" >nul
if %errorlevel% neq 0 (
    echo ERROR: Failed to copy DLL.
    start explorer.exe
    pause
    exit /b 1
)

echo Registering shell extension...
regsvr32 /s "%INSTALL_DIR%\%DLL_NAME%"
if %errorlevel% neq 0 (
    echo ERROR: Failed to register DLL.
    start explorer.exe
    pause
    exit /b 1
)

echo Restarting Explorer...
start explorer.exe

echo.
echo Installation complete.
echo.
echo New context menu options:
echo   Archives: Extract to same-named folder
echo   Files:    Zip to parent.zip
echo   Folders:  Zip folder / zip each separately / zip all
echo.
pause
