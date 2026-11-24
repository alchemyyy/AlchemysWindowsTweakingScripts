@echo off
setlocal DisableDelayedExpansion

:: Turns each line of aliases.txt into a one-line .cmd shim in SHIM_DIR and appends
:: SHIM_DIR to the END of the user PATH. No per-console startup cost (unlike doskey
:: via AutoRun), and any real program with the same name takes precedence.
:: The shim folder is regenerated from scratch on every run: aliases.txt is the
:: single source of truth. No admin required.

:: === Configuration ===
set "SHIM_DIR=C:\Tools\AlchemysCMDMacros"
set "ALIASES_FILE=%~dp0aliases.txt"
set "PATH_HELPER=%~dp0path_helper.ps1"
:: cmd internal commands: always resolved before PATH, so shims with these names never run.
set "BUILTINS=assoc break call cd chdir cls color copy date del dir dpath echo endlocal erase exit for ftype goto if keys md mkdir mklink move path pause popd prompt pushd rd rem ren rename rmdir set setlocal shift start time title type ver verify vol"

cd /d "%~dp0" 2>nul

if not exist "%ALIASES_FILE%" (
    echo [ERROR] aliases.txt not found at: %ALIASES_FILE%
    pause
    exit /b 1
)

echo ============================================
echo   CMD Aliases Installer
echo ============================================
echo.

:: === Regenerate shim folder ===
if exist "%SHIM_DIR%" rd /s /q "%SHIM_DIR%"
mkdir "%SHIM_DIR%" 2>nul
if not exist "%SHIM_DIR%" (
    echo [ERROR] Could not create %SHIM_DIR%
    pause
    exit /b 1
)

echo [INFO] Writing shims to %SHIM_DIR%...
:: No CALL with alias bodies and no delayed expansion: either would mangle % and ! in them.
for /f "usebackq eol=# tokens=1,* delims==" %%A in ("%ALIASES_FILE%") do (
    call :check_name "%%A"
    if errorlevel 2 (
        echo [SKIP] %%A ^(name may only contain letters, digits, _ and -^)
    ) else if errorlevel 1 (
        echo [SKIP] %%A ^(cmd built-in, would never run^)
    ) else (
        >"%SHIM_DIR%\%%A.cmd" echo(@%%B
    )
)

:: === PATH ===
echo [INFO] Adding %SHIM_DIR% to the end of the user PATH...
powershell -NoProfile -ExecutionPolicy Bypass -File "%PATH_HELPER%" -Action Add -Dir "%SHIM_DIR%"
if errorlevel 1 echo [ERROR] Failed to update user PATH.

:: === Report shims overridden by earlier PATH entries (expected, informational) ===
set "PATH=%PATH%;%SHIM_DIR%"
for %%F in ("%SHIM_DIR%\*.cmd") do call :report_override "%%~nF"

:: === Clean up previous doskey-based installs ===
reg query "HKCU\Software\Microsoft\Command Processor" /v AutoRun 2>nul | findstr /i "cmd_aliases" >nul
if not errorlevel 1 (
    reg delete "HKCU\Software\Microsoft\Command Processor" /v AutoRun /f >nul 2>&1
    echo [OK] Removed old doskey AutoRun value.
)
if exist "%LOCALAPPDATA%\cmd_aliases" (
    rd /s /q "%LOCALAPPDATA%\cmd_aliases"
    echo [OK] Removed old %LOCALAPPDATA%\cmd_aliases.
)
if exist "C:\Windows\cmd_aliases.cmd" (
    del /f "C:\Windows\cmd_aliases.cmd" >nul 2>&1
    if exist "C:\Windows\cmd_aliases.cmd" (
        echo [WARN] Could not delete C:\Windows\cmd_aliases.cmd ^(needs admin^). It is no longer used.
    ) else (
        echo [OK] Removed old C:\Windows\cmd_aliases.cmd.
    )
)

echo.
echo ============================================
echo   Installation Complete
echo ============================================
echo   Shim folder: %SHIM_DIR%
echo   Open a NEW terminal window/tab to pick up the PATH change.
echo   Type 'alias' to see all available commands.
echo ============================================
echo.
pause
exit /b 0

:: %1 = quoted alias name. errorlevel 0 = ok, 1 = cmd built-in, 2 = invalid characters.
:check_name
echo(%~1| findstr /r /x "[A-Za-z0-9_-]*" >nul || exit /b 2
for %%I in (%BUILTINS%) do if /i "%~1"=="%%I" exit /b 1
exit /b 0

:: %1 = quoted alias name. Reports the first PATH match if it isn't our shim.
:report_override
for /f "delims=" %%W in ('where "$PATH:%~1" 2^>nul') do (
    if /i not "%%~dpW"=="%SHIM_DIR%\" echo [OVERRIDDEN] %~1 -^> %%W
    exit /b 0
)
exit /b 0
