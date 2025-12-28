# Import Visual Effects Settings - Reads .ini file and applies immediately
param(
    [string]$InputPath = (Join-Path $PSScriptRoot "visual_effects.ini")
)

Add-Type -TypeDefinition @'
using System;
using System.Runtime.InteropServices;

[StructLayout(LayoutKind.Sequential)]
public struct ANIMATIONINFO {
    public uint cbSize;
    public int iMinAnimate;
}

public class NativeMethods {
    [DllImport("user32.dll", SetLastError = true, EntryPoint = "SystemParametersInfo")]
    public static extern bool SystemParametersInfoInt(uint uiAction, uint uiParam, int pvParam, uint fWinIni);

    [DllImport("user32.dll", SetLastError = true, EntryPoint = "SystemParametersInfo")]
    public static extern bool SystemParametersInfoBool(uint uiAction, uint uiParam, bool pvParam, uint fWinIni);

    [DllImport("user32.dll", SetLastError = true, EntryPoint = "SystemParametersInfo")]
    public static extern bool SystemParametersInfoAnim(uint uiAction, uint uiParam, ref ANIMATIONINFO pvParam, uint fWinIni);

    [DllImport("user32.dll", SetLastError = true, CharSet = CharSet.Auto)]
    public static extern IntPtr SendMessageTimeout(IntPtr hWnd, uint Msg, UIntPtr wParam, string lParam, uint fuFlags, uint uTimeout, out UIntPtr lpdwResult);

    public const uint SPI_SETANIMATION = 0x0049;
    public const uint SPI_SETDRAGFULLWINDOWS = 0x0025;
    public const uint SPI_SETFONTSMOOTHING = 0x004B;
    public const uint SPI_SETDROPSHADOW = 0x1025;
    public const uint SPI_SETCOMBOBOXANIMATION = 0x1005;
    public const uint SPI_SETLISTBOXSMOOTHSCROLLING = 0x1007;
    public const uint SPI_SETGRADIENTCAPTIONS = 0x1009;
    public const uint SPI_SETKEYBOARDCUES = 0x100B;
    public const uint SPI_SETHOTTRACKING = 0x100F;
    public const uint SPI_SETMENUFADE = 0x1013;
    public const uint SPI_SETSELECTIONFADE = 0x1015;
    public const uint SPI_SETTOOLTIPANIMATION = 0x1017;
    public const uint SPI_SETTOOLTIPFADE = 0x1019;
    public const uint SPI_SETCURSORSHADOW = 0x101B;
    public const uint SPI_SETUIEFFECTS = 0x103F;
    public const uint SPI_SETMENUANIMATION = 0x1003;
    public const uint SPI_SETCLIENTAREAANIMATION = 0x1043;

    public const uint SPIF_UPDATEINIFILE = 0x01;
    public const uint SPIF_SENDCHANGE = 0x02;
    public const int HWND_BROADCAST = 0xffff;
    public const uint WM_SETTINGCHANGE = 0x001A;
    public const uint SMTO_ABORTIFHUNG = 0x0002;
}
'@

if (-not (Test-Path $InputPath)) {
    Write-Host "ERROR: File not found: $InputPath" -ForegroundColor Red
    exit 1
}

Write-Host "Importing Visual Effects from: $InputPath" -ForegroundColor Cyan

# Parse .ini file
$config = @{}
$section = ""
Get-Content $InputPath | ForEach-Object {
    $line = $_.Trim()
    if ($line -match '^\[(.+)\]$') {
        $section = $Matches[1]
        $config[$section] = @{}
    }
    elseif ($line -match '^([^;=]+)=(.*)$') {
        $config[$section][$Matches[1].Trim()] = $Matches[2].Trim()
    }
}

# Registry paths
$Desktop = "HKCU:\Control Panel\Desktop"
$WindowMetrics = "HKCU:\Control Panel\Desktop\WindowMetrics"
$VisualEffects = "HKCU:\Software\Microsoft\Windows\CurrentVersion\Explorer\VisualEffects"
$Advanced = "HKCU:\Software\Microsoft\Windows\CurrentVersion\Explorer\Advanced"
$DWM = "HKCU:\Software\Microsoft\Windows\DWM"

# Parse UserPreferencesMask from comma-separated string to byte array
$UPM = [byte[]]($config["Desktop"]["UserPreferencesMask"] -split "," | ForEach-Object { [byte]$_ })

# Apply to registry
Set-ItemProperty -Path $VisualEffects -Name VisualFXSetting -Value 3 -Type DWord
Set-ItemProperty -Path $Desktop -Name UserPreferencesMask -Value $UPM -Type Binary
Set-ItemProperty -Path $Desktop -Name FontSmoothing -Value $config["Desktop"]["FontSmoothing"] -Type String
Set-ItemProperty -Path $Desktop -Name FontSmoothingType -Value ([int]$config["Desktop"]["FontSmoothingType"]) -Type DWord
Set-ItemProperty -Path $Desktop -Name DragFullWindows -Value $config["Desktop"]["DragFullWindows"] -Type String
Set-ItemProperty -Path $WindowMetrics -Name MinAnimate -Value $config["WindowMetrics"]["MinAnimate"] -Type String
Set-ItemProperty -Path $Advanced -Name TaskbarAnimations -Value ([int]$config["Advanced"]["TaskbarAnimations"]) -Type DWord
Set-ItemProperty -Path $Advanced -Name ListviewAlphaSelect -Value ([int]$config["Advanced"]["ListviewAlphaSelect"]) -Type DWord
Set-ItemProperty -Path $Advanced -Name ListviewShadow -Value ([int]$config["Advanced"]["ListviewShadow"]) -Type DWord
Set-ItemProperty -Path $Advanced -Name IconsOnly -Value ([int]$config["Advanced"]["IconsOnly"]) -Type DWord
Set-ItemProperty -Path $DWM -Name EnableAeroPeek -Value ([int]$config["DWM"]["EnableAeroPeek"]) -Type DWord
Set-ItemProperty -Path $DWM -Name AlwaysHibernateThumbnails -Value ([int]$config["DWM"]["AlwaysHibernateThumbnails"]) -Type DWord

Write-Host "Registry updated. Applying via Windows API..." -ForegroundColor Yellow

$flags = [NativeMethods]::SPIF_UPDATEINIFILE -bor [NativeMethods]::SPIF_SENDCHANGE

# Apply via SystemParametersInfo
[NativeMethods]::SystemParametersInfoInt([NativeMethods]::SPI_SETDRAGFULLWINDOWS, $(if ($config["Desktop"]["DragFullWindows"] -eq "1") { 1 } else { 0 }), 0, $flags) | Out-Null
[NativeMethods]::SystemParametersInfoInt([NativeMethods]::SPI_SETFONTSMOOTHING, $(if ($config["Desktop"]["FontSmoothing"] -eq "2") { 1 } else { 0 }), 0, $flags) | Out-Null

$animInfo = New-Object ANIMATIONINFO
$animInfo.cbSize = [System.Runtime.InteropServices.Marshal]::SizeOf($animInfo)
$animInfo.iMinAnimate = $(if ($config["WindowMetrics"]["MinAnimate"] -eq "1") { 1 } else { 0 })
[NativeMethods]::SystemParametersInfoAnim([NativeMethods]::SPI_SETANIMATION, $animInfo.cbSize, [ref]$animInfo, $flags) | Out-Null

[NativeMethods]::SystemParametersInfoBool([NativeMethods]::SPI_SETUIEFFECTS, 0, $(($UPM[0] -band 0x80) -ne 0), $flags) | Out-Null
[NativeMethods]::SystemParametersInfoBool([NativeMethods]::SPI_SETCLIENTAREAANIMATION, 0, $(($UPM[0] -band 0x02) -ne 0), $flags) | Out-Null
[NativeMethods]::SystemParametersInfoBool([NativeMethods]::SPI_SETCOMBOBOXANIMATION, 0, $(($UPM[0] -band 0x04) -ne 0), $flags) | Out-Null
[NativeMethods]::SystemParametersInfoBool([NativeMethods]::SPI_SETLISTBOXSMOOTHSCROLLING, 0, $(($UPM[0] -band 0x08) -ne 0), $flags) | Out-Null
[NativeMethods]::SystemParametersInfoBool([NativeMethods]::SPI_SETGRADIENTCAPTIONS, 0, $(($UPM[0] -band 0x10) -ne 0), $flags) | Out-Null
[NativeMethods]::SystemParametersInfoBool([NativeMethods]::SPI_SETHOTTRACKING, 0, $(($UPM[0] -band 0x20) -ne 0), $flags) | Out-Null
[NativeMethods]::SystemParametersInfoBool([NativeMethods]::SPI_SETMENUANIMATION, 0, $(($UPM[1] -band 0x01) -ne 0), $flags) | Out-Null
[NativeMethods]::SystemParametersInfoBool([NativeMethods]::SPI_SETMENUFADE, 0, $(($UPM[1] -band 0x02) -ne 0), $flags) | Out-Null
[NativeMethods]::SystemParametersInfoBool([NativeMethods]::SPI_SETSELECTIONFADE, 0, $(($UPM[1] -band 0x04) -ne 0), $flags) | Out-Null
[NativeMethods]::SystemParametersInfoBool([NativeMethods]::SPI_SETTOOLTIPANIMATION, 0, $(($UPM[1] -band 0x08) -ne 0), $flags) | Out-Null
[NativeMethods]::SystemParametersInfoBool([NativeMethods]::SPI_SETTOOLTIPFADE, 0, $(($UPM[1] -band 0x10) -ne 0), $flags) | Out-Null
[NativeMethods]::SystemParametersInfoBool([NativeMethods]::SPI_SETCURSORSHADOW, 0, $(($UPM[1] -band 0x20) -ne 0), $flags) | Out-Null
[NativeMethods]::SystemParametersInfoBool([NativeMethods]::SPI_SETDROPSHADOW, 0, $(($UPM[1] -band 0x04) -ne 0), $flags) | Out-Null

# Broadcast WM_SETTINGCHANGE
$result = [UIntPtr]::Zero
[NativeMethods]::SendMessageTimeout([IntPtr][NativeMethods]::HWND_BROADCAST, [NativeMethods]::WM_SETTINGCHANGE, [UIntPtr]::Zero, "Environment", [NativeMethods]::SMTO_ABORTIFHUNG, 5000, [ref]$result) | Out-Null

Write-Host "Done! Visual effects applied." -ForegroundColor Green
