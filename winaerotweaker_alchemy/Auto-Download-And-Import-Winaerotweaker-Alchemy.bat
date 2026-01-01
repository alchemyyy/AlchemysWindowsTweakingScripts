@echo off
setlocal enabledelayedexpansion

echo Checking for WinaeroTweaker.exe...

REM Check if winaerotweaker.exe exists in current directory
if exist "%~dp0winaerotweaker.exe" (
    echo WinaeroTweaker.exe found!
    goto :RunImport
)

echo WinaeroTweaker.exe not found. Downloading...

REM Download using PowerShell (built-in to Windows 11)
powershell -Command "Invoke-WebRequest -Uri 'https://winaerotweaker.com/download/winaerotweaker.zip' -OutFile '%~dp0winaerotweaker.zip'"

if not exist "%~dp0winaerotweaker.zip" (
    echo ERROR: Failed to download WinaeroTweaker.
    pause
    exit /b 1
)

echo Download complete. Extracting...

REM Extract using PowerShell's Expand-Archive (built-in to Windows 11)
powershell -Command "Expand-Archive -Path '%~dp0winaerotweaker.zip' -DestinationPath '%~dp0winaerotweaker_temp' -Force"

if not exist "%~dp0winaerotweaker_temp" (
    echo ERROR: Failed to extract archive.
    pause
    exit /b 1
)

echo Extraction complete. Running setup in portable extract mode...

REM Find the setup executable in the extracted folder
set "SETUPFILE="
for /r "%~dp0winaerotweaker_temp" %%f in (*setup.exe) do (
    set "SETUPFILE=%%f"
    echo Found setup file: %%f
    goto :RunSetup
)

REM If no setup file found, look for any exe that isn't winaerotweaker.exe
if not defined SETUPFILE (
    for /r "%~dp0winaerotweaker_temp" %%f in (*.exe) do (
        if /i "%%~nxf" NEQ "winaerotweaker.exe" (
            set "SETUPFILE=%%f"
            echo Found installer: %%f
            goto :RunSetup
        )
    )
)

REM If winaerotweaker.exe is already extracted, just copy it
if not defined SETUPFILE (
    for /r "%~dp0winaerotweaker_temp" %%f in (winaerotweaker.exe) do (
        echo Found extracted executable, copying to current directory...
        xcopy "%%~dpf*.*" "%~dp0\" /E /I /Y >nul
        goto :CleanupTemp
    )
)

:RunSetup
if not defined SETUPFILE (
    echo ERROR: No setup file found in extracted archive.
    pause
    exit /b 1
)

REM Run setup in portable mode to extract to current directory
echo Running portable extraction...
"%SETUPFILE%" /SP- /VERYSILENT /PORTABLE /DIR="%~dp0"

echo Waiting for extraction to complete...
timeout /t 5 /nobreak >nul

REM Wait for winaerotweaker.exe to appear (max 30 seconds)
set /a counter=0
:WaitLoop
if exist "%~dp0winaerotweaker.exe" goto :CleanupTemp
timeout /t 1 /nobreak >nul
set /a counter+=1
if %counter% LSS 30 goto :WaitLoop

echo ERROR: WinaeroTweaker.exe not found after extraction.
pause
exit /b 1

:CleanupTemp
echo Cleaning up temporary files...
if exist "%~dp0winaerotweaker.zip" del /q "%~dp0winaerotweaker.zip"
if exist "%~dp0winaerotweaker_temp" rd /s /q "%~dp0winaerotweaker_temp"

:RunImport
echo Looking for INI file to import...

REM Find the first .ini file in current directory
set "INIFILE="
for %%i in ("%~dp0*.ini") do (
    set "INIFILE=%%i"
    goto :FoundINI
)

echo ERROR: No INI file found in current directory.
pause
exit /b 1

:FoundINI
echo Found INI file: %INIFILE%
echo Running WinaeroTweaker with import...

REM Run WinaeroTweaker with import argument
"%~dp0winaerotweaker.exe" /import="%INIFILE%"

echo Done!
pause
