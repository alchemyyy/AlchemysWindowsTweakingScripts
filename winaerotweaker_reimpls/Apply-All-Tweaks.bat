@echo off
:: Apply All Winaero Tweaks
:: Run as Administrator
:: For Windows 11 25H2

echo ============================================
echo   Applying All Winaero Tweaks
echo   Windows 11 25H2
echo ============================================
echo.

:: Check for admin rights
net session >nul 2>&1
if %errorlevel% neq 0 (
    echo ERROR: This script must be run as Administrator.
    echo Right-click and select "Run as administrator"
    pause
    exit /b 1
)

echo Applying registry tweaks...
echo.

:: Apply all .reg files
for %%f in ("%~dp0*.reg") do (
    echo Applying: %%~nxf
    regedit /s "%%f"
)

echo.
echo ============================================
echo   All registry tweaks applied!
echo ============================================
echo.
echo Some changes may require:
echo   - Logging off and back on
echo   - Restarting Explorer
echo   - Rebooting the computer
echo.
echo Press any key to restart Explorer now, or close this window to skip.
pause >nul

:: Restart Explorer
taskkill /f /im explorer.exe
start explorer.exe

echo Explorer restarted.
pause
