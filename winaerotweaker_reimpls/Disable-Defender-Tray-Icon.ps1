# Disable Windows Defender/Security Tray Icon - PowerShell Script
# Run as Administrator
# For Windows 11 25H2

#Requires -RunAsAdministrator

Write-Host "Disabling Windows Security Tray Icon..." -ForegroundColor Cyan

# Disable via registry
$regPaths = @{
    "HKLM:\SOFTWARE\Policies\Microsoft\Windows Defender Security Center\Systray" = @{
        "HideSystray" = 1
    }
    "HKLM:\SOFTWARE\Microsoft\Windows Defender Security Center\Notifications" = @{
        "DisableNotifications" = 1
    }
}

foreach ($path in $regPaths.Keys) {
    if (!(Test-Path $path)) {
        New-Item -Path $path -Force | Out-Null
    }
    foreach ($name in $regPaths[$path].Keys) {
        Set-ItemProperty -Path $path -Name $name -Value $regPaths[$path][$name] -Type DWord -Force
        Write-Host "  Set $path\$name = $($regPaths[$path][$name])" -ForegroundColor Green
    }
}

# Disable startup entry
$startupPath = "HKLM:\SOFTWARE\Microsoft\Windows\CurrentVersion\Run"
Remove-ItemProperty -Path $startupPath -Name "SecurityHealth" -ErrorAction SilentlyContinue
Write-Host "  Removed SecurityHealth from startup" -ForegroundColor Green

Write-Host "`nWindows Security tray icon has been disabled." -ForegroundColor Green
Write-Host "A restart or log off may be required for changes to take effect." -ForegroundColor Yellow
