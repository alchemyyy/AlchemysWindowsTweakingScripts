@echo off
net session >nul 2>&1
if %ERRORLEVEL% NEQ 0 (
    echo Please right-click and Run as administrator.
    pause
    exit /b 1
)
more +11 "%~f0" > "C:\Windows\vs.cmd"
echo Installed vs.cmd to C:\Windows
pause
exit /b
@echo off
setlocal
set "VSWHERE=C:\Program Files (x86)\Microsoft Visual Studio\Installer\vswhere.exe"
if not exist "%VSWHERE%" (
    echo vswhere.exe not found
    exit /b 1
)
for /f "tokens=*" %%i in ('"%VSWHERE%" -latest -property installationPath') do set "VS_PATH=%%i"
if not defined VS_PATH (
    echo No Visual Studio installation found.
    exit /b 1
)
start "" "%VS_PATH%\Common7\IDE\devenv.exe" "%CD%"
