@echo off
setlocal EnableDelayedExpansion

:: Add IP Address to Trusted Intranet Sites (Zone 1)
:: Run as Administrator for HKLM changes, or run normally for current user only

set "IP=%~1"

if "%IP%"=="" (
    set /p "IP=Enter IP address to add to Intranet zone: "
)

if "%IP%"=="" (
    echo No IP address provided. Exiting.
    exit /b 1
)

:: Registry path for zone mappings
set "REGPATH=HKCU\Software\Microsoft\Windows\CurrentVersion\Internet Settings\ZoneMap\Ranges"

:: Find the next available Range number
set "RANGENUM=1"
:findRange
reg query "%REGPATH%\Range%RANGENUM%" >nul 2>&1
if %errorlevel%==0 (
    set /a RANGENUM+=1
    goto findRange
)

set "RANGEKEY=%REGPATH%\Range%RANGENUM%"

echo.
echo Adding %IP% to Local Intranet zone...
echo Registry key: %RANGEKEY%
echo.

:: Create the range key and add the IP with zone 1 (Local Intranet)
reg add "%RANGEKEY%" /v ":Range" /t REG_SZ /d "%IP%" /f
if %errorlevel% neq 0 (
    echo Failed to add IP range.
    exit /b 1
)

:: Set zone to 1 (Local Intranet) for all protocols
reg add "%RANGEKEY%" /v "http" /t REG_DWORD /d 1 /f
reg add "%RANGEKEY%" /v "https" /t REG_DWORD /d 1 /f
reg add "%RANGEKEY%" /v "file" /t REG_DWORD /d 1 /f
reg add "%RANGEKEY%" /v "*" /t REG_DWORD /d 1 /f

echo.
echo Successfully added %IP% to Local Intranet zone.
echo You may need to restart your browser for changes to take effect.
echo.

endlocal
