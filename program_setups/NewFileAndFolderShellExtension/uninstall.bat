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

echo Unregistering shell extension...

regsvr32 /u /s "%DEST_DIR%\%DLL_NAME%"

echo Restarting Explorer to release DLL...
taskkill /f /im explorer.exe >nul 2>&1
start explorer.exe

REM Wait for Explorer to release the DLL
timeout /t 2 /nobreak >nul

echo Removing files...

del /f "%DEST_DIR%\%DLL_NAME%" 2>nul
if exist "%DEST_DIR%\%DLL_NAME%" (
    echo Warning: Could not delete DLL. It may still be in use.
    echo Try running this script again after a reboot.
) else (
    echo DLL removed.
)

REM Delete this uninstall script from Windows directory
REM Use a delayed delete since we may be running from there
if /i "%~dp0"=="%DEST_DIR%\" (
    echo Uninstaller will be removed on next reboot.
    reg add "HKLM\SOFTWARE\Microsoft\Windows\CurrentVersion\RunOnce" /v "CleanupNewFileFolder" /t REG_SZ /d "cmd /c del \"%DEST_DIR%\%UNINSTALL_NAME%\"" /f >nul
) else (
    del /f "%DEST_DIR%\%UNINSTALL_NAME%" 2>nul
)

echo.
echo Shell extension uninstalled successfully!
echo.
pause
