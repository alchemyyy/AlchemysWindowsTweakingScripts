# Disable Windows Telemetry - PowerShell Script
# Run as Administrator
# For Windows 11 25H2

#Requires -RunAsAdministrator

Write-Host "Disabling Windows Telemetry..." -ForegroundColor Cyan

# Disable telemetry services
$services = @(
    "DiagTrack"                    # Connected User Experiences and Telemetry
    "dmwappushservice"             # WAP Push Message Routing Service
)

foreach ($service in $services) {
    $svc = Get-Service -Name $service -ErrorAction SilentlyContinue
    if ($svc) {
        Stop-Service -Name $service -Force -ErrorAction SilentlyContinue
        Set-Service -Name $service -StartupType Disabled -ErrorAction SilentlyContinue
        Write-Host "  Disabled service: $service" -ForegroundColor Green
    }
}

# Disable scheduled tasks related to telemetry
$tasks = @(
    "\Microsoft\Windows\Application Experience\Microsoft Compatibility Appraiser"
    "\Microsoft\Windows\Application Experience\ProgramDataUpdater"
    "\Microsoft\Windows\Autochk\Proxy"
    "\Microsoft\Windows\Customer Experience Improvement Program\Consolidator"
    "\Microsoft\Windows\Customer Experience Improvement Program\UsbCeip"
    "\Microsoft\Windows\DiskDiagnostic\Microsoft-Windows-DiskDiagnosticDataCollector"
    "\Microsoft\Windows\Feedback\Siuf\DmClient"
    "\Microsoft\Windows\Feedback\Siuf\DmClientOnScenarioDownload"
)

foreach ($task in $tasks) {
    Disable-ScheduledTask -TaskName $task -ErrorAction SilentlyContinue | Out-Null
    Write-Host "  Disabled task: $task" -ForegroundColor Green
}

# Apply registry settings
$regKeys = @{
    "HKLM:\SOFTWARE\Policies\Microsoft\Windows\DataCollection" = @{
        "AllowTelemetry" = 0
        "MaxTelemetryAllowed" = 0
    }
    "HKLM:\SOFTWARE\Microsoft\Windows\CurrentVersion\Policies\DataCollection" = @{
        "AllowTelemetry" = 0
        "MaxTelemetryAllowed" = 0
    }
    "HKCU:\Software\Microsoft\Windows\CurrentVersion\Privacy" = @{
        "TailoredExperiencesWithDiagnosticDataEnabled" = 0
    }
    "HKLM:\SOFTWARE\Policies\Microsoft\SQMClient\Windows" = @{
        "CEIPEnable" = 0
    }
    "HKLM:\SOFTWARE\Policies\Microsoft\Windows\AppCompat" = @{
        "AITEnable" = 0
        "DisableInventory" = 1
        "DisableUAR" = 1
    }
}

foreach ($path in $regKeys.Keys) {
    if (!(Test-Path $path)) {
        New-Item -Path $path -Force | Out-Null
    }
    foreach ($name in $regKeys[$path].Keys) {
        Set-ItemProperty -Path $path -Name $name -Value $regKeys[$path][$name] -Type DWord -Force
    }
}

Write-Host "`nTelemetry has been disabled." -ForegroundColor Green
Write-Host "A restart may be required for all changes to take effect." -ForegroundColor Yellow
