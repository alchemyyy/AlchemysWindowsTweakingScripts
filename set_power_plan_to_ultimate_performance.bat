@echo off
:: Check for admin privileges
net session >nul 2>&1
if %errorlevel% neq 0 (
    echo This script requires administrator privileges.
    echo Right-click and select "Run as administrator"
    pause
    exit /b 1
)

echo Enabling Ultimate Performance power plan...

:: Add the Ultimate Performance power plan (it's hidden by default)
powercfg -duplicatescheme e9a42b02-d5df-448d-aa00-03f14749eb61 >nul 2>&1

:: Activate Ultimate Performance
powercfg -setactive e9a42b02-d5df-448d-aa00-03f14749eb61

if %errorlevel% equ 0 (
    echo Ultimate Performance power plan activated successfully!
) else (
    echo Failed to activate. Trying alternative method...
    for /f "tokens=4" %%a in ('powercfg -list ^| findstr "Ultimate"') do (
        powercfg -setactive %%a
    )
)

echo.
echo Current power plan:
powercfg -getactivescheme

pause