@echo off
setlocal

set "REG_KEY=HKLM\SOFTWARE\Policies\Microsoft\Windows\Personalization"
set "REG_VALUE=LockScreenImage"

:: This key is under HKLM, so the script must run elevated.
net session >nul 2>&1
if errorlevel 1 (
    echo This script requires administrator privileges.
    echo Right-click this file and select "Run as administrator".
    pause
    exit /b 1
)

echo Set default lock screen background image
echo.
echo Enter the full path to the image file.
echo Example: C:\Images\lockscreen.png
echo You can drag and drop the image file into this window.
echo.

:prompt
set "IMAGE_PATH="
set /p "IMAGE_PATH=Image path: "
if errorlevel 1 (
    echo.
    echo No image path was provided.
    pause
    exit /b 1
)

if not defined IMAGE_PATH (
    echo Please enter an image path.
    echo.
    goto prompt
)

:: Remove quotes added by drag-and-drop, if present.
set "IMAGE_PATH=%IMAGE_PATH:"=%"

if exist "%IMAGE_PATH%" goto set_registry_value

echo.
echo File not found:
echo "%IMAGE_PATH%"
echo.
goto prompt

:set_registry_value
reg add "%REG_KEY%" /v "%REG_VALUE%" /t REG_SZ /d "%IMAGE_PATH%" /f >nul
if errorlevel 1 (
    echo.
    echo Failed to set the lock screen image registry policy.
    pause
    exit /b 1
)

echo.
echo Default lock screen image set to:
echo "%IMAGE_PATH%"
echo.
echo You may need to sign out, restart, or lock Windows again before the change appears.
pause
exit /b 0
