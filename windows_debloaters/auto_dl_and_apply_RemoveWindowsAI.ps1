# Downloads the latest RemoveWindowsAI (https://github.com/zoicware/RemoveWindowsAI) and runs it non-interactively,
# without the parts that break File Explorer on Windows 11 25H2 (26200.9278 and later):
# - Microsoft.AIFabric.CBS is kept. File Explorer depends on it; without it Explorer falls back to the Windows 10
#   ribbon UI and classic context menu. The feature overrides RemoveWindowsAI applies for that removal are skipped too.
# - PreventAIPackageReinstall is not run. Its update-blocker package (ZoicwareRemoveWindowsAI 1.0.0.1) replaces the
#   Microsoft.AIFabric.CBS component.
# Afterwards undo_RemoveWindowsAI_AIFabric_removal.ps1 makes sure Microsoft.AIFabric.CBS is registered and that
# RemoveWindowsAI's update-cleanup logon task keeps it.

$sourceUrl = 'https://raw.githubusercontent.com/zoicware/RemoveWindowsAI/main/RemoveWindowsAi.ps1'
$options = @(
    'DisableRegKeys'
    'DisableCopilotPolicies'
    'RemoveAppxPackages'
    'RemoveRecallFeature'
    'RemoveCBSPackages'
    'RemoveAIFiles'
    'HideAIComponents'
    'DisableRewrite'
    'RemoveWindowsAITasks'
    'UpdateCleanupCheck'
)

# RemoveWindowsAI requires Windows PowerShell 5.1 and administrator privileges.
$isAdmin = ([Security.Principal.WindowsPrincipal] [Security.Principal.WindowsIdentity]::GetCurrent()).IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)
if (-not $isAdmin -or $PSVersionTable.PSEdition -ne 'Desktop') {
    $arguments = "-NoExit -NoProfile -ExecutionPolicy Bypass -File `"$PSCommandPath`""
    if ($isAdmin) {
        Start-Process powershell.exe -ArgumentList $arguments
    }
    else {
        Start-Process powershell.exe -ArgumentList $arguments -Verb RunAs
    }
    exit
}

Write-Host "Downloading the latest RemoveWindowsAI..." -ForegroundColor Cyan
try {
    $source = (Invoke-WebRequest -Uri $sourceUrl -UseBasicParsing -ErrorAction Stop).Content
}
catch {
    Write-Host "Download failed: $($_.Exception.Message)" -ForegroundColor Red
    exit 1
}

$patched = $source -replace "(?m)^([ \t]*)'(Microsoft\.AIFabric\.CBS\*?)'", '$1#''$2'' kept: File Explorer depends on it'
$patched = $patched -replace "(?m)^([ \t]*)(Set-FeatureID -disable -FeatureId (?:58375086|63366798|58375066|61199980|40012896)\b)", '$1#$2 skipped: only needed when Microsoft.AIFabric.CBS is removed'

# Refuse to run a version that touches Microsoft.AIFabric.CBS in a way the patterns above don't cover.
$remaining = @($patched -split "\r?\n" | Where-Object { $_ -match 'Microsoft\.AIFabric' -and $_.TrimStart() -notlike '#*' })
if ($remaining) {
    Write-Host "The latest RemoveWindowsAI still references Microsoft.AIFabric.CBS, so it was not run:" -ForegroundColor Red
    $remaining | ForEach-Object { Write-Host "  $($_.Trim())" -ForegroundColor Yellow }
    exit 1
}

$tokens = $null
$parseErrors = $null
$ast = [System.Management.Automation.Language.Parser]::ParseInput($patched, [ref]$tokens, [ref]$parseErrors)
if ($parseErrors) {
    Write-Host "The downloaded RemoveWindowsAI does not parse: $($parseErrors[0].Message)" -ForegroundColor Red
    exit 1
}

$optionsParameter = $ast.ParamBlock.Parameters | Where-Object { $_.Name.VariablePath.UserPath -eq 'Options' }
$validOptions = @($optionsParameter.Attributes | Where-Object { $_.TypeName.Name -eq 'ValidateSet' } | ForEach-Object { $_.PositionalArguments.Value })
$unknownOptions = @($options | Where-Object { $validOptions -notcontains $_ })
if ($unknownOptions) {
    Write-Host "RemoveWindowsAI no longer has these options: $($unknownOptions -join ', ')" -ForegroundColor Red
    exit 1
}
$skippedOptions = @($validOptions | Where-Object { $options -notcontains $_ })

$workDir = Join-Path $env:TEMP 'RemoveWindowsAI'
$scriptPath = Join-Path $workDir 'RemoveWindowsAi.ps1'
New-Item -ItemType Directory -Force -Path $workDir | Out-Null
[IO.File]::WriteAllText($scriptPath, $patched, (New-Object System.Text.UTF8Encoding $true))

Write-Host "Running $scriptPath" -ForegroundColor Cyan
Write-Host "  Options: $($options -join ', ')" -ForegroundColor Gray
if ($skippedOptions) {
    Write-Host "  Not run: $($skippedOptions -join ', ')" -ForegroundColor Gray
}
Write-Host ""

$undoScript = Join-Path $PSScriptRoot 'undo_RemoveWindowsAI_AIFabric_removal.ps1'
try {
    & $scriptPath -nonInteractive -Options $options
}
finally {
    Write-Host ""
    if (Test-Path -LiteralPath $undoScript) {
        & $undoScript
    }
    else {
        Write-Host "$undoScript not found, so Microsoft.AIFabric.CBS was not checked." -ForegroundColor Red
    }
}
