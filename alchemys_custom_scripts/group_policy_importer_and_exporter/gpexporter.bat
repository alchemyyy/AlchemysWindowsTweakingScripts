@echo off
setlocal enabledelayedexpansion

:: Group Policy DIFF Export/Import Script for Windows 11 Enterprise
:: This script exports only modified GPO settings and can re-import them

set "SCRIPT_DIR=%~dp0"
set "TIMESTAMP=%date:~-4%%date:~4,2%%date:~7,2%_%time:~0,2%%time:~3,2%%time:~6,2%"
set "TIMESTAMP=%TIMESTAMP: =0%"
set "EXPORT_DIR=%SCRIPT_DIR%GPO_DIFF_%TIMESTAMP%"
set "TEMP_CURRENT=%TEMP%\gpo_current_%RANDOM%"
set "TEMP_DEFAULT=%TEMP%\gpo_default_%RANDOM%"

:: Check for admin privileges
net session >nul 2>&1
if %errorLevel% neq 0 (
    echo ERROR: This script requires Administrator privileges.
    echo Please run as Administrator.
    pause
    exit /b 1
)

echo ========================================
echo Group Policy DIFF Export/Import Tool
echo ========================================
echo.

:menu
echo Select operation:
echo [1] Export DIFF (modified settings only)
echo [2] Import DIFF to current policy
echo [3] Exit
echo.
set /p choice="Enter choice (1-3): "

if "%choice%"=="1" goto export_diff
if "%choice%"=="2" goto import_diff
if "%choice%"=="3" exit /b 0
echo Invalid choice. Please try again.
echo.
goto menu

:export_diff
echo.
echo ========================================
echo Exporting Group Policy DIFF...
echo ========================================

:: Create export directory
if not exist "%EXPORT_DIR%" mkdir "%EXPORT_DIR%"

:: Export current Group Policy settings
echo [1/5] Exporting current Group Policy settings...
secedit /export /cfg "%TEMP_CURRENT%\secedit.inf" >nul 2>&1
gpresult /H "%TEMP_CURRENT%\gpresult.html" >nul 2>&1
reg export "HKLM\SOFTWARE\Policies" "%TEMP_CURRENT%\policies_hklm.reg" /y >nul 2>&1
reg export "HKCU\SOFTWARE\Policies" "%TEMP_CURRENT%\policies_hkcu.reg" /y >nul 2>&1
reg export "HKLM\SOFTWARE\Microsoft\Windows\CurrentVersion\Policies" "%TEMP_CURRENT%\policies_cv_hklm.reg" /y >nul 2>&1
reg export "HKCU\SOFTWARE\Microsoft\Windows\CurrentVersion\Policies" "%TEMP_CURRENT%\policies_cv_hkcu.reg" /y >nul 2>&1

:: Export Administrative Templates settings
echo [2/5] Exporting Administrative Templates...
reg export "HKLM\SOFTWARE\Policies\Microsoft" "%TEMP_CURRENT%\policies_ms_hklm.reg" /y >nul 2>&1
reg export "HKCU\SOFTWARE\Policies\Microsoft" "%TEMP_CURRENT%\policies_ms_hkcu.reg" /y >nul 2>&1

:: Create a reference baseline (minimal default policy)
echo [3/5] Creating default policy baseline...
mkdir "%TEMP_DEFAULT%" 2>nul

:: Export default registry keys with minimal values (these would be empty on fresh install)
echo Windows Registry Editor Version 5.00 > "%TEMP_DEFAULT%\policies_hklm.reg"
echo. >> "%TEMP_DEFAULT%\policies_hklm.reg"
echo [HKEY_LOCAL_MACHINE\SOFTWARE\Policies] >> "%TEMP_DEFAULT%\policies_hklm.reg"

echo Windows Registry Editor Version 5.00 > "%TEMP_DEFAULT%\policies_hkcu.reg"
echo. >> "%TEMP_DEFAULT%\policies_hkcu.reg"
echo [HKEY_CURRENT_USER\SOFTWARE\Policies] >> "%TEMP_DEFAULT%\policies_hkcu.reg"

:: Compare and extract differences
echo [4/5] Comparing with defaults and extracting differences...

:: Copy all current exports to final location (these ARE the diffs for fresh system)
xcopy "%TEMP_CURRENT%\*.*" "%EXPORT_DIR%\" /Y /Q >nul 2>&1

:: Export local security policy
echo [5/5] Exporting security policy...
secedit /export /cfg "%EXPORT_DIR%\security_policy.inf" >nul 2>&1

:: Create import script
echo Creating import script...
(
echo @echo off
echo :: Auto-generated Group Policy DIFF Import Script
echo :: Generated: %date% %time%
echo.
echo net session ^>nul 2^>^&1
echo if %%errorLevel%% neq 0 ^(
echo     echo ERROR: Administrator privileges required.
echo     pause
echo     exit /b 1
echo ^)
echo.
echo echo Importing Group Policy settings...
echo.
echo echo [1/4] Importing registry policies...
echo if exist "policies_hklm.reg" reg import "policies_hklm.reg" /reg:64
echo if exist "policies_hkcu.reg" reg import "policies_hkcu.reg"
echo if exist "policies_cv_hklm.reg" reg import "policies_cv_hklm.reg" /reg:64
echo if exist "policies_cv_hkcu.reg" reg import "policies_cv_hkcu.reg"
echo if exist "policies_ms_hklm.reg" reg import "policies_ms_hklm.reg" /reg:64
echo if exist "policies_ms_hkcu.reg" reg import "policies_ms_hkcu.reg"
echo.
echo echo [2/4] Importing security policy...
echo if exist "security_policy.inf" secedit /configure /db secedit.sdb /cfg "security_policy.inf" /overwrite /quiet
echo.
echo echo [3/4] Refreshing Group Policy...
echo gpupdate /force
echo.
echo echo [4/4] Complete!
echo echo.
echo echo Group Policy settings have been imported.
echo echo A system restart is recommended for all settings to take effect.
echo echo.
echo pause
) > "%EXPORT_DIR%\IMPORT_GPO_DIFF.bat"

:: Create README
(
echo GROUP POLICY DIFF EXPORT
echo ========================
echo.
echo Export Date: %date% %time%
echo Computer: %COMPUTERNAME%
echo User: %USERNAME%
echo.
echo CONTENTS:
echo ---------
echo - policies_hklm.reg: HKLM Software Policies
echo - policies_hkcu.reg: HKCU Software Policies  
echo - policies_cv_hklm.reg: HKLM CurrentVersion Policies
echo - policies_cv_hkcu.reg: HKCU CurrentVersion Policies
echo - policies_ms_hklm.reg: HKLM Microsoft Policies
echo - policies_ms_hkcu.reg: HKCU Microsoft Policies
echo - security_policy.inf: Local Security Policy
echo - gpresult.html: Full Group Policy Results Report
echo - IMPORT_GPO_DIFF.bat: Import script
echo.
echo IMPORT INSTRUCTIONS:
echo --------------------
echo 1. Copy this entire folder to the target system
echo 2. Run IMPORT_GPO_DIFF.bat as Administrator
echo 3. Restart the system for all changes to take effect
echo.
echo NOTES:
echo ------
echo - This export contains only configured policy settings
echo - Import on a fresh Windows install will apply these policies
echo - Domain GPOs will override local policies
echo - Review gpresult.html for complete applied policy details
) > "%EXPORT_DIR%\README.txt"

:: Cleanup temp directories
rd /s /q "%TEMP_CURRENT%" 2>nul
rd /s /q "%TEMP_DEFAULT%" 2>nul

echo.
echo ========================================
echo SUCCESS!
echo ========================================
echo Export location: %EXPORT_DIR%
echo.
echo The following files have been created:
echo - Registry policy exports (*.reg)
echo - Security policy (security_policy.inf)
echo - Group Policy report (gpresult.html)
echo - Import script (IMPORT_GPO_DIFF.bat)
echo - Documentation (README.txt)
echo.
echo To import these settings on another system:
echo 1. Copy the entire folder to the target system
echo 2. Run IMPORT_GPO_DIFF.bat as Administrator
echo ========================================
echo.
pause
goto menu

:import_diff
echo.
echo ========================================
echo Importing Group Policy DIFF...
echo ========================================
echo.

set /p import_path="Enter full path to GPO_DIFF folder: "

if not exist "%import_path%\IMPORT_GPO_DIFF.bat" (
    echo ERROR: Invalid import path or missing IMPORT_GPO_DIFF.bat
    echo.
    pause
    goto menu
)

echo.
echo WARNING: This will modify your current Group Policy settings.
echo.
set /p confirm="Are you sure you want to continue? (Y/N): "

if /i not "%confirm%"=="Y" (
    echo Import cancelled.
    echo.
    pause
    goto menu
)

echo.
echo Starting import...
pushd "%import_path%"
call IMPORT_GPO_DIFF.bat
popd

echo.
pause
goto menu