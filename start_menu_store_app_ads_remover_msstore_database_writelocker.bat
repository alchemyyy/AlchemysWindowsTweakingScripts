@echo off
:: --- Elevate to Administrator ---
net session >nul 2>&1
if %errorlevel% neq 0 (
    powershell -Command "Start-Process '%~f0' -Verb RunAs"
    exit /b
)
setlocal enabledelayedexpansion
cls
echo Cleaning Windows Store search history...
timeout /t 1 >nul

:: --- Run PowerShell logic ---
powershell -NoProfile -ExecutionPolicy Bypass -Command ^
"if ((Get-PackageProvider -ListAvailable -Name 'NuGet' -ErrorAction SilentlyContinue) -eq $null) { Install-PackageProvider -Name NuGet -Force ^| Out-Null }; ^
 if ((Get-Module PSSQLite -ListAvailable) -eq $null) { Install-Module PSSQLite -Scope CurrentUser -Force ^| Out-Null }; ^
 $db = \"$env:LOCALAPPDATA\Packages\Microsoft.WindowsStore_8wekyb3d8bbwe\LocalState\store.db\"; ^
 try { ^
     Invoke-SqliteQuery -DataSource $db -Query 'DELETE FROM SearchProducts'; ^
     Write-Output 'Deleted all entries from SearchProducts.'; ^
     Set-ItemProperty -Path $db -Name IsReadOnly -Value $true; ^
     Write-Output 'store.db is now read-only.'; ^
 } catch { Write-Output $_.Exception.Message }"

exit