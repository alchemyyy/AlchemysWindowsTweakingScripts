@echo off
setlocal EnableDelayedExpansion

:: === Configuration ===
set "DOSKEY_FILE=C:\Windows\cmd_aliases.cmd"
set "ALIASES_FILE=%~dp0aliases.txt"

:: === Change to script directory (suppresses drive errors) ===
cd /d "%~dp0" 2>nul

:: === Check for admin privileges ===
net session >nul 2>&1
if %errorlevel% neq 0 (
    echo [ERROR] This script requires administrator privileges.
    echo         Right-click and select "Run as administrator"
    pause
    exit /b 1
)

:: === Check aliases.txt exists ===
if not exist "%ALIASES_FILE%" (
    echo [ERROR] aliases.txt not found at: %ALIASES_FILE%
    pause
    exit /b 1
)

echo ============================================
echo   CMD Aliases Installer
echo ============================================
echo.

:: === Load existing aliases into environment variables ===
set "count_existing=0"
if exist "%DOSKEY_FILE%" (
    echo [INFO] Loading existing aliases...
    for /f "usebackq tokens=1,* delims= " %%A in ("%DOSKEY_FILE%") do (
        if /i "%%A"=="doskey" (
            for /f "tokens=1 delims==" %%N in ("%%B") do (
                set "existing_%%N=%%B"
                set /a count_existing+=1
            )
        )
    )
    echo       Found !count_existing! existing aliases.
)

:: === Load new aliases from txt file ===
echo [INFO] Loading aliases from aliases.txt...
set "count_new=0"
set "count_updated=0"

for /f "usebackq tokens=* eol=#" %%L in ("%ALIASES_FILE%") do (
    set "line=%%L"
    if not "!line!"=="" (
        for /f "tokens=1 delims==" %%N in ("!line!") do (
            set "alias_name=%%N"
            
            :: Check if exists and if value changed
            if defined existing_!alias_name! (
                set "old_val=!existing_%alias_name%!"
                if "!old_val!"=="!line!" (
                    rem Same value, no change
                ) else (
                    echo [UPDATE] !alias_name!
                    set /a count_updated+=1
                )
                :: Clear so we know it's been processed
                set "existing_!alias_name!="
            ) else (
                echo [NEW] !alias_name!
                set /a count_new+=1
            )
            
            :: Store the alias for final output
            set "final_!alias_name!=!line!"
        )
    )
)

:: === Preserve aliases that were in existing file but not in txt ===
set "count_preserved=0"
for /f "tokens=1,* delims==" %%N in ('set existing_ 2^>nul') do (
    set "varname=%%N"
    set "varvalue=%%O"
    :: Extract actual alias name (remove "existing_" prefix)
    set "pname=!varname:existing_=!"
    if defined varvalue (
        if not defined final_!pname! (
            set "final_!pname!=!varvalue!"
            echo [KEEP] !pname!
            set /a count_preserved+=1
        )
    )
)

:: === Write final doskey file ===
echo.
echo [INFO] Writing %DOSKEY_FILE%...

:: Write header
echo @echo off>"%DOSKEY_FILE%"

:: Write all aliases
for /f "tokens=1,* delims==" %%N in ('set final_ 2^>nul') do (
    set "fullvalue=%%O"
    echo doskey !fullvalue!>>"%DOSKEY_FILE%"
)

:: === Set up registry ===
echo [INFO] Setting up registry AutoRun...
reg add "HKCU\Software\Microsoft\Command Processor" /v AutoRun /t REG_SZ /d "%DOSKEY_FILE%" /f >nul 2>&1
if %errorlevel% equ 0 (
    echo [OK] Registry updated successfully.
) else (
    echo [ERROR] Failed to update registry.
)

:: === Summary ===
echo.
echo ============================================
echo   Installation Complete
echo ============================================
echo   New aliases:       %count_new%
echo   Updated aliases:   %count_updated%
echo   Preserved aliases: %count_preserved%
echo.
echo   Doskey file: %DOSKEY_FILE%
echo   Open a new CMD window to use your aliases.
echo   Type 'alias' to see all available commands.
echo ============================================
echo.
pause