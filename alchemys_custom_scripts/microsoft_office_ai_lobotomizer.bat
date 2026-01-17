@echo off

:: Define the target path
set "TARGET_PATH=C:\Program Files\Microsoft Office\root\vfs\ProgramFilesCommonX64\Microsoft Shared\Office16\AI"

echo ============================================
echo Terminating processes with target path...
echo ============================================

:: Use WMIC to find and kill processes with the target path in their command line
for /f "tokens=2 delims==" %%p in ('wmic process where "CommandLine like '%%Office16\\AI%%'" get ProcessId /value 2^>nul ^| find "="') do (
    echo Killing process with PID: %%p
    taskkill /F /PID %%p >nul 2>&1
)

:: Alternative method using PowerShell for more reliable command line matching
powershell -Command "Get-WmiObject Win32_Process | Where-Object { $_.CommandLine -like '*Microsoft Shared\Office16\AI*' } | ForEach-Object { Write-Host 'Terminating:' $_.ProcessId $_.Name; Stop-Process -Id $_.ProcessId -Force -ErrorAction SilentlyContinue }"

echo.
echo ============================================
echo Taking ownership and removing directory...
echo ============================================

:: Check if directory exists
if not exist "%TARGET_PATH%" (
    echo Directory does not exist: %TARGET_PATH%
    goto :end
)

:: Take ownership of the directory and all contents
echo Taking ownership...
takeown /F "%TARGET_PATH%" /R /A /D Y >nul 2>&1

:: Grant full control to Administrators
echo Granting permissions...
icacls "%TARGET_PATH%" /grant Administrators:F /T /C /Q >nul 2>&1

:: Remove any read-only attributes
echo Removing read-only attributes...
attrib -R -S -H "%TARGET_PATH%\*.*" /S /D >nul 2>&1

:: Force delete the directory
echo Deleting directory...
rd /S /Q "%TARGET_PATH%" 2>nul

:: Verify deletion
if exist "%TARGET_PATH%" (
    echo Warning: Directory still exists. Trying alternative method...
    del /F /S /Q "%TARGET_PATH%\*.*" >nul 2>&1
    rd /S /Q "%TARGET_PATH%" 2>nul
)

if not exist "%TARGET_PATH%" (
    echo Success: Directory has been deleted.
) else (
    echo Failed: Could not delete directory. It may be locked by a system process.
    echo Try running this script again after a reboot, or in Safe Mode.
)

:end
echo.
echo ============================================
echo Operation complete.
echo ============================================
pause