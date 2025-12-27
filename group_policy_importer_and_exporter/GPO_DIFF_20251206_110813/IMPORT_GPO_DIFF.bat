@echo off
:: Auto-generated Group Policy DIFF Import Script
:: Generated: Sat 12/06/2025 11:08:21.10

net session >nul 2>&1
if %errorLevel% neq 0 (
    echo ERROR: Administrator privileges required.
    pause
    exit /b 1
)

echo Importing Group Policy settings...

echo [1/4] Importing registry policies...
if exist "policies_hklm.reg" reg import "policies_hklm.reg" /reg:64
if exist "policies_hkcu.reg" reg import "policies_hkcu.reg"
if exist "policies_cv_hklm.reg" reg import "policies_cv_hklm.reg" /reg:64
if exist "policies_cv_hkcu.reg" reg import "policies_cv_hkcu.reg"
if exist "policies_ms_hklm.reg" reg import "policies_ms_hklm.reg" /reg:64
if exist "policies_ms_hkcu.reg" reg import "policies_ms_hkcu.reg"

echo [2/4] Importing security policy...
if exist "security_policy.inf" secedit /configure /db secedit.sdb /cfg "security_policy.inf" /overwrite /quiet

echo [3/4] Refreshing Group Policy...
gpupdate /force

echo [4/4] Complete
echo.
echo Group Policy settings have been imported.
echo A system restart is recommended for all settings to take effect.
echo.
pause
