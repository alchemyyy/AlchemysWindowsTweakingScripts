@echo off
net session >nul 2>&1
if %errorlevel% neq 0 (
    echo This script must be run as Administrator
    pause
    exit /b 1
)

set "DLL_NAME=NewFileAndFolderShellExtension.dll"
set "UNINSTALL_NAME=Uninstall_NewFileAndFolderShellExtension.bat"
set "DEST_DIR=C:\Windows"

echo Copying files to %DEST_DIR%...

copy /Y "%~dp0%DLL_NAME%" "%DEST_DIR%\%DLL_NAME%" >nul
if %errorlevel% neq 0 (
    echo Failed to copy DLL to %DEST_DIR%
    pause
    exit /b 1
)

copy /Y "%~dp0uninstall.bat" "%DEST_DIR%\%UNINSTALL_NAME%" >nul
if %errorlevel% neq 0 (
    echo Failed to copy uninstall script to %DEST_DIR%
    pause
    exit /b 1
)

echo Registering shell extension...

regsvr32 /s "%DEST_DIR%\%DLL_NAME%"

if %errorlevel% equ 0 (
    echo.
    echo Shell extension installed successfully!
    echo   DLL: %DEST_DIR%\%DLL_NAME%
    echo   Uninstaller: %DEST_DIR%\%UNINSTALL_NAME%
    echo.
    echo You may need to restart Explorer for changes to take effect.
    echo.
    choice /c YN /m "Restart Explorer now"
    if errorlevel 2 goto :end
    taskkill /f /im explorer.exe
    start explorer.exe
) else (
    echo Registration failed.
)

:end
pause
