# Requires -RunAsAdmin

# Define the Registry paths for Group Policy overrides
$DefenderPolicyPath = "HKLM:\SOFTWARE\Policies\Microsoft\Windows Defender"
$RealTimePath       = "$DefenderPolicyPath\Real-Time Protection"
$DevDrivePath       = "$DefenderPolicyPath\DevDrive"

Write-Host "Configuring Local Group Policies for Windows Defender..." -ForegroundColor Cyan

# 1. Ensure the base Policy paths exist
if (-not (Test-Path $DefenderPolicyPath)) { New-Item -Path $DefenderPolicyPath -Force | Out-Null }
if (-not (Test-Path $RealTimePath))       { New-Item -Path $RealTimePath -Force | Out-Null }
if (-not (Test-Path $DevDrivePath))       { New-Item -Path $DevDrivePath -Force | Out-Null }

# 2. Disable Real-Time Protection via GPO
# This mirrors: Computer Configuration -> Administrative Templates -> Windows Components -> Microsoft Defender Antivirus -> Real-time Protection
Set-ItemProperty -Path $DefenderPolicyPath -Name "DisableAntiSpyware" -Value 1 -Type DWord -Force
Set-ItemProperty -Path $RealTimePath -Name "DisableRealtimeMonitoring" -Value 1 -Type DWord -Force
Set-ItemProperty -Path $RealTimePath -Name "DisableBehaviorMonitoring" -Value 1 -Type DWord -Force
Set-ItemProperty -Path $RealTimePath -Name "DisableScanOnRealtimeEnable" -Value 1 -Type DWord -Force

# 3. Disable Dev Drive Protection (or adjust performance mode filters)
# This mirrors: Computer Configuration -> Administrative Templates -> Windows Components -> Microsoft Defender Antivirus -> Dev Drive
# Setting to 0 disables Dev Drive protection/asynchronous scanning optimizations, or sets the policy to "Disabled"
Set-ItemProperty -Path $DevDrivePath -Name "DevDriveProtectionMode" -Value 0 -Type DWord -Force

Write-Host "Registry policies written successfully." -ForegroundColor Green

# 4. Force local Group Policy engine to refresh and apply changes
Write-Host "Refreshing local Group Policy..." -ForegroundColor Cyan
gpupdate /force

Write-Host "Task complete. Please verify status in Windows Security settings." -ForegroundColor Green