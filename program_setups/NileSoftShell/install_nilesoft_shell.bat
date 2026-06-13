@echo off
setlocal EnableExtensions

set "TARGET=C:\Program Files\Nilesoft Shell"
set "ZIP=%~dp0nss_alchemy.zip"
set "SHELL_EXE=%TARGET%\shell.exe"

net session >nul 2>&1
if not "%errorlevel%"=="0" (
    echo Requesting administrator privileges...
    powershell -NoProfile -ExecutionPolicy Bypass -Command "Start-Process -FilePath '%~f0' -Verb RunAs"
    exit /b
)

if not exist "%ZIP%" (
    echo Could not find "%ZIP%".
    pause
    exit /b 1
)

where winget >nul 2>&1
if errorlevel 1 (
    echo winget was not found.
    pause
    exit /b 1
)

echo Installing Nilesoft Shell...
winget install nilesoft.shell --accept-package-agreements --accept-source-agreements
if errorlevel 1 (
    echo winget install failed.
    pause
    exit /b 1
)

if not exist "%TARGET%" (
    mkdir "%TARGET%"
    if errorlevel 1 (
        echo Failed to create "%TARGET%".
        pause
        exit /b 1
    )
)

echo Copying nss_alchemy.zip contents to "%TARGET%"...
set "ZIP_PATH=%ZIP%"
set "TARGET_PATH=%TARGET%"
powershell -NoProfile -ExecutionPolicy Bypass -Command "Expand-Archive -LiteralPath $env:ZIP_PATH -DestinationPath $env:TARGET_PATH -Force"
if errorlevel 1 (
    echo Failed to extract "%ZIP%" to "%TARGET%".
    pause
    exit /b 1
)

if not exist "%SHELL_EXE%" (
    echo Could not find "%SHELL_EXE%".
    pause
    exit /b 1
)

echo Registering and restarting Nilesoft Shell...
"%SHELL_EXE%" -register -restart
if errorlevel 1 (
    echo Nilesoft Shell registration failed.
    pause
    exit /b 1
)

echo Done.
pause
