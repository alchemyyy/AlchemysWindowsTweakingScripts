@echo off
:: Batch Script to Modify Password Policies
:: Auto-elevates to Administrator if needed

:: Check for admin rights
net session >nul 2>&1
if %errorLevel% neq 0 (
    echo Requesting administrative privileges...
    echo.
    
    :: Create VBS script for elevation
    echo Set UAC = CreateObject^("Shell.Application"^) > "%temp%\getadmin.vbs"
    echo UAC.ShellExecute "%~s0", "", "", "runas", 1 >> "%temp%\getadmin.vbs"
    
    "%temp%\getadmin.vbs"
    del "%temp%\getadmin.vbs"
    exit /B
)

:: If we're here, we have admin rights
title Password Policy Modifier
color 0B
cls

echo ========================================
echo   Windows Password Policy Modifier
echo ========================================
echo.
echo This script will:
echo  - Disable password expiration
echo  - Disable password complexity
echo  - Remove password length requirements
echo  - Disable password history
echo.
echo Press any key to continue or Ctrl+C to cancel...
pause >nul

cls
echo.
echo [1/4] Exporting current security policy...
secedit /export /cfg "%temp%\secpol.cfg" >nul 2>&1

if not exist "%temp%\secpol.cfg" (
    echo ERROR: Failed to export security policy!
    echo.
    pause
    exit /B 1
)

echo [2/4] Modifying password policy settings...

:: Create modified security policy file
(
    for /f "tokens=*" %%a in (%temp%\secpol.cfg) do (
        set "line=%%a"
        setlocal enabledelayedexpansion
        
        :: Replace password policy settings
        if "!line:~0,18!"=="MaximumPasswordAge" (
            echo MaximumPasswordAge = -1
        ) else if "!line:~0,18!"=="MinimumPasswordAge" (
            echo MinimumPasswordAge = 0
        ) else if "!line:~0,21!"=="MinimumPasswordLength" (
            echo MinimumPasswordLength = 0
        ) else if "!line:~0,18!"=="PasswordComplexity" (
            echo PasswordComplexity = 0
        ) else if "!line:~0,19!"=="PasswordHistorySize" (
            echo PasswordHistorySize = 0
        ) else (
            echo !line!
        )
        endlocal
    )
) > "%temp%\secpol_modified.cfg"

echo [3/4] Applying new password policy...
secedit /configure /db secedit.sdb /cfg "%temp%\secpol_modified.cfg" /areas SECURITYPOLICY >nul 2>&1

if %errorLevel% neq 0 (
    echo ERROR: Failed to apply security policy!
    echo.
    goto cleanup
)

echo [4/4] Refreshing Group Policy...
gpupdate /force >nul 2>&1

:cleanup
:: Clean up temporary files
del "%temp%\secpol.cfg" >nul 2>&1
del "%temp%\secpol_modified.cfg" >nul 2>&1

cls
echo.
echo ========================================
echo   Password Policy Successfully Updated
echo ========================================
echo.
echo Changes Applied:
echo  [+] Password never expires (Max age: Unlimited)
echo  [+] Minimum password age: 0 days
echo  [+] Minimum password length: 0 characters
echo  [+] Password complexity: DISABLED
echo  [+] Password history: DISABLED
echo.
echo ========================================
echo   Current Password Policy Status
echo ========================================
echo.
net accounts
echo.
echo ========================================
echo.
echo NOTE: These changes affect LOCAL accounts only.
echo Domain password policies are controlled by Domain Controllers.
echo.
echo Script completed successfully!
echo.
pause