# Export Visual Effects Settings - Creates a .ini file
param(
    [string]$OutputPath = (Join-Path $PSScriptRoot "visual_effects.ini")
)

Write-Host "Exporting Windows Visual Effects Settings..." -ForegroundColor Cyan

$Desktop = "HKCU:\Control Panel\Desktop"
$WindowMetrics = "HKCU:\Control Panel\Desktop\WindowMetrics"
$Advanced = "HKCU:\Software\Microsoft\Windows\CurrentVersion\Explorer\Advanced"
$DWM = "HKCU:\Software\Microsoft\Windows\DWM"

# Get UserPreferencesMask as byte array and convert to comma-separated decimal
$UPM = (Get-ItemProperty -Path $Desktop -Name UserPreferencesMask -ErrorAction SilentlyContinue).UserPreferencesMask
if (-not $UPM) {
    Write-Host "ERROR: Could not read UserPreferencesMask" -ForegroundColor Red
    exit 1
}
$UPM_String = $UPM -join ","

# Get all other values
$FontSmoothing = (Get-ItemProperty -Path $Desktop -Name FontSmoothing -ErrorAction SilentlyContinue).FontSmoothing
$FontSmoothingType = (Get-ItemProperty -Path $Desktop -Name FontSmoothingType -ErrorAction SilentlyContinue).FontSmoothingType
$DragFullWindows = (Get-ItemProperty -Path $Desktop -Name DragFullWindows -ErrorAction SilentlyContinue).DragFullWindows
$MinAnimate = (Get-ItemProperty -Path $WindowMetrics -Name MinAnimate -ErrorAction SilentlyContinue).MinAnimate
$TaskbarAnimations = (Get-ItemProperty -Path $Advanced -Name TaskbarAnimations -ErrorAction SilentlyContinue).TaskbarAnimations
$ListviewAlphaSelect = (Get-ItemProperty -Path $Advanced -Name ListviewAlphaSelect -ErrorAction SilentlyContinue).ListviewAlphaSelect
$ListviewShadow = (Get-ItemProperty -Path $Advanced -Name ListviewShadow -ErrorAction SilentlyContinue).ListviewShadow
$IconsOnly = (Get-ItemProperty -Path $Advanced -Name IconsOnly -ErrorAction SilentlyContinue).IconsOnly
$EnableAeroPeek = (Get-ItemProperty -Path $DWM -Name EnableAeroPeek -ErrorAction SilentlyContinue).EnableAeroPeek
$AlwaysHibernateThumbnails = (Get-ItemProperty -Path $DWM -Name AlwaysHibernateThumbnails -ErrorAction SilentlyContinue).AlwaysHibernateThumbnails

@"
; Visual Effects Settings
; Generated: $(Get-Date)
; Import with: powershell -ExecutionPolicy Bypass -File import_visual_effects.ps1

[Desktop]
UserPreferencesMask=$UPM_String
FontSmoothing=$FontSmoothing
FontSmoothingType=$FontSmoothingType
DragFullWindows=$DragFullWindows

[WindowMetrics]
MinAnimate=$MinAnimate

[Advanced]
TaskbarAnimations=$TaskbarAnimations
ListviewAlphaSelect=$ListviewAlphaSelect
ListviewShadow=$ListviewShadow
IconsOnly=$IconsOnly

[DWM]
EnableAeroPeek=$EnableAeroPeek
AlwaysHibernateThumbnails=$AlwaysHibernateThumbnails
"@ | Out-File -FilePath $OutputPath -Encoding UTF8

Write-Host "Exported to: $OutputPath" -ForegroundColor Green
