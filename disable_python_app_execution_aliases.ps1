# PowerShell script to disable Python app execution aliases in Windows 11
# This script will restart Explorer to release file locks

Write-Host "Disabling Python app execution aliases..." -ForegroundColor Cyan
Write-Host ""

# Check if running as Administrator
$isAdmin = ([Security.Principal.WindowsPrincipal] [Security.Principal.WindowsIdentity]::GetCurrent()).IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)

if (-not $isAdmin) {
    Write-Host "This script requires Administrator privileges." -ForegroundColor Red
    Write-Host "Please run PowerShell as Administrator and try again." -ForegroundColor Yellow
    exit 1
}

# Function to restart Explorer
function Restart-Explorer {
    Write-Host "Stopping Windows Explorer..." -ForegroundColor Yellow
    Stop-Process -Name explorer -Force -ErrorAction SilentlyContinue
    Start-Sleep -Seconds 2
    Write-Host "Starting Windows Explorer..." -ForegroundColor Yellow
    Start-Process explorer.exe
    Start-Sleep -Seconds 2
}

# Restart Explorer to release file locks
Restart-Explorer

# Disable via renaming the alias files
$appxPath = "$env:LOCALAPPDATA\Microsoft\WindowsApps"
$pythonAliases = @("python.exe", "python3.exe", "python3.11.exe", "python3.12.exe")

Write-Host "Disabling Python aliases..." -ForegroundColor Cyan

foreach ($alias in $pythonAliases) {
    $fullPath = Join-Path $appxPath $alias
    if (Test-Path $fullPath) {
        try {
            $disabledPath = "$fullPath.disabled"
            if (Test-Path $disabledPath) {
                Remove-Item $disabledPath -Force -ErrorAction SilentlyContinue
            }
            Rename-Item -Path $fullPath -NewName "$alias.disabled" -Force -ErrorAction Stop
            Write-Host "  Disabled: $alias" -ForegroundColor Green
        }
        catch {
            Write-Host "  Failed to disable: $alias - $($_.Exception.Message)" -ForegroundColor Red
        }
    } else {
        Write-Host "  Not found: $alias (already disabled or not present)" -ForegroundColor Gray
    }
}

Write-Host ""
Write-Host "Done! Python app execution aliases have been disabled." -ForegroundColor Green
Write-Host "Restart your terminal to see the changes." -ForegroundColor Cyan