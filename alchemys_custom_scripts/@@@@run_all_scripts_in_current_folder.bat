@echo off
setlocal enabledelayedexpansion

echo ========================================
echo Running All Scripts in Current Directory
echo ========================================
echo.

REM Run all .reg files
echo [1/3] Importing Registry Files (.reg)...
echo.
for %%f in (*.reg) do (
    echo Importing: %%f
    reg import "%%f"
    if errorlevel 1 (
        echo ERROR: Failed to import %%f
    ) else (
        echo SUCCESS: %%f imported
    )
    echo.
)

echo.
echo [2/3] Running Batch Files (.bat)...
echo.
for %%f in (*.bat) do (
    REM Skip running this script itself
    if /I not "%%f"=="%~nx0" (
        echo Running: %%f
        call "%%f"
        if errorlevel 1 (
            echo ERROR: Failed to run %%f
        ) else (
            echo SUCCESS: %%f completed
        )
        echo.
    )
)

echo.
echo [3/3] Running PowerShell Scripts (.ps1)...
echo.
for %%f in (*.ps1) do (
    echo Running: %%f
    powershell -ExecutionPolicy Bypass -File "%%f"
    if errorlevel 1 (
        echo ERROR: Failed to run %%f
    ) else (
        echo SUCCESS: %%f completed
    )
    echo.
)

echo.
echo ========================================
echo All Scripts Completed
echo ========================================
pause
