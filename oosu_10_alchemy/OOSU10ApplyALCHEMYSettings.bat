@echo off

:: Check if OOSU10.exe exists, download if missing
if not exist "OOSU10.exe" (
    echo OOSU10.exe not found. Downloading...
    powershell -Command "Invoke-WebRequest -Uri 'https://dl5.oo-software.com/files/ooshutup10/OOSU10.exe' -OutFile 'OOSU10.exe'"
    if exist "OOSU10.exe" (
        echo Download complete.
    ) else (
        echo Download failed.
        echo Please download OOSU10.exe manually from https://www.oo-software.com/
        echo and place it in this folder: %~dp0
        pause
        exit /b 1
    )
)

OOSU10.exe ooshutup10.cfg