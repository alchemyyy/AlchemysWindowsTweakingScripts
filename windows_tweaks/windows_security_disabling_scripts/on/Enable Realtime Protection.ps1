# Requires -RunAsAdmin

$DefenderPolicyPath = "HKLM:\SOFTWARE\Policies\Microsoft\Windows Defender"
$RealTimePath       = "$DefenderPolicyPath\Real-Time Protection"
$DevDrivePath       = "$DefenderPolicyPath\DevDrive"

Write-Host "Reverting Local Group Policies for Windows Defender..." -ForegroundColor Yellow

# 1. Remove the overrides
# Deleting these keys removes the "Managed by your organization" lock
if (Test-Path $RealTimePath) {
    Remove-Item -Path $RealTimePath -Recurse -Force
    Write-Host "Real-Time Protection policy removed." -ForegroundColor Green
}

if (Test-Path $DevDrivePath) {
    Remove-Item -Path $DevDrivePath -Recurse -Force
    Write-Host "Dev Drive protection policy removed." -ForegroundColor Green
}

# 2. Clean up base settings
if (Test-Path "$DefenderPolicyPath\DisableAntiSpyware") {
    Remove-ItemProperty -Path $DefenderPolicyPath -Name "DisableAntiSpyware" -ErrorAction SilentlyContinue
}

# 3. Refresh policy engine
Write-Host "Refreshing local Group Policy..." -ForegroundColor Cyan
gpupdate /force

Write-Host "Reversal complete. You may need to toggle protections on/off in the Windows Security UI." -ForegroundColor Green