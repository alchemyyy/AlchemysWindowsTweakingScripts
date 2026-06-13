@echo off
setlocal EnableExtensions

set "REG_DIR=%~dp0recommended_reg_files"
set /a COUNT=0
set /a FAILS=0

if not exist "%REG_DIR%\" (
    echo Could not find "%REG_DIR%".
    pause
    exit /b 1
)

net session >nul 2>&1
if errorlevel 1 (
    echo Requesting administrator privileges...
    set "__BAT_PATH=%~f0"
    set "__BAT_DIR=%~dp0"
    powershell -NoProfile -ExecutionPolicy Bypass -Command "Start-Process -FilePath $env:__BAT_PATH -Verb RunAs -WorkingDirectory $env:__BAT_DIR"
    exit /b
)

for %%F in ("%REG_DIR%\*.reg") do (
    if exist "%%~fF" (
        set /a COUNT+=1
        echo Importing %%~nxF
        reg import "%%~fF" >nul
        if errorlevel 1 (
            echo   FAILED
            set /a FAILS+=1
        ) else (
            echo   OK
        )
    )
)

if %COUNT% EQU 0 (
    echo No .reg files found in "%REG_DIR%".
    pause
    exit /b 1
)

echo.
echo Imported %COUNT% .reg file(s), with %FAILS% failure(s).
pause
exit /b %FAILS%
