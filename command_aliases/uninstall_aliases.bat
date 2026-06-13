@echo off
setlocal

:: === Configuration ===
set "DOSKEY_FILE=C:\Windows\cmd_aliases.cmd"

:: === Check for admin privileges ===
net session >nul 2>&1
if %errorlevel% neq 0 (
    echo [ERROR] This script requires administrator privileges.
    echo         Right-click and select "Run as administrator"
    pause
    exit /b 1
)

echo ============================================
echo   CMD Aliases Uninstaller
echo ============================================
echo.

:: === Confirm ===
echo This will remove:
echo   - Registry key: HKCU\Software\Microsoft\Command Processor\AutoRun
echo   - Doskey file:  %DOSKEY_FILE%
echo.
set /p "confirm=Are you sure? (Y/N): "
if /i not "%confirm%"=="Y" (
    echo Cancelled.
    pause
    exit /b 0
)

echo.

:: === Remove registry key ===
echo [INFO] Removing registry AutoRun value...
reg delete "HKCU\Software\Microsoft\Command Processor" /v AutoRun /f >nul 2>&1
if %errorlevel% equ 0 (
    echo [OK] Registry value removed.
) else (
    echo [WARN] Registry value not found or already removed.
)

:: === Delete doskey file ===
echo [INFO] Deleting doskey file...
if exist "%DOSKEY_FILE%" (
    del /f "%DOSKEY_FILE%" >nul 2>&1
    if exist "%DOSKEY_FILE%" (
        echo [ERROR] Failed to delete %DOSKEY_FILE%
    ) else (
        echo [OK] Doskey file deleted.
    )
) else (
    echo [WARN] Doskey file not found or already deleted.
)

:: === Done ===
echo.
echo ============================================
echo   Uninstallation Complete
echo ============================================
echo   CMD aliases have been removed.
echo   Open a new CMD window to verify.
echo ============================================
echo.
pause
