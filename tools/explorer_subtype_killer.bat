@echo off
setlocal enabledelayedexpansion

echo Searching for explorer.exe processes with "/factory" in the command line...

:: Use PowerShell to find and terminate the specific processes
powershell -NoProfile -ExecutionPolicy Bypass -Command ^
    "Get-CimInstance Win32_Process -Filter \"Name = 'explorer.exe'\" | " ^
    "Where-Object { $_.CommandLine -like '*/factory*' } | " ^
    "ForEach-Object { Stop-Process -Id $_.ProcessId -Force; Write-Host 'Killed process ID:' $_.ProcessId }"

echo Task complete.
pause