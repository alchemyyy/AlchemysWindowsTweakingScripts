@echo off
setlocal

:: === Configuration ===
set "SHIM_DIR=C:\Tools\AlchemysCMDMacros"
set "PATH_HELPER=%~dp0path_helper.ps1"

echo ============================================
echo   CMD Aliases Uninstaller
echo ============================================
echo.

echo This will remove:
echo   - Shim folder:     %SHIM_DIR%
echo   - User PATH entry: %SHIM_DIR%
echo.
set /p "confirm=Are you sure? (Y/N): "
if /i not "%confirm%"=="Y" (
    echo Cancelled.
    pause
    exit /b 0
)

echo.

echo [INFO] Deleting shim folder...
if exist "%SHIM_DIR%" (
    rd /s /q "%SHIM_DIR%" >nul 2>&1
    if exist "%SHIM_DIR%" (
        echo [ERROR] Failed to delete %SHIM_DIR%
    ) else (
        echo [OK] Shim folder deleted.
    )
) else (
    echo [WARN] Shim folder not found or already deleted.
)
:: Remove C:\Tools too, but only if nothing else lives there (rd without /s fails otherwise).
for %%P in ("%SHIM_DIR%\..") do rd "%%~fP" >nul 2>&1

echo [INFO] Removing %SHIM_DIR% from user PATH...
powershell -NoProfile -ExecutionPolicy Bypass -File "%PATH_HELPER%" -Action Remove -Dir "%SHIM_DIR%"
if errorlevel 1 echo [ERROR] Failed to update user PATH.

echo.
echo ============================================
echo   Uninstallation Complete
echo ============================================
echo   Open a NEW terminal window/tab to verify.
echo ============================================
echo.
pause
