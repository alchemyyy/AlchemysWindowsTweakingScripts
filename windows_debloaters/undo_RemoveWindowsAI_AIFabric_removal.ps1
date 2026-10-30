# Restores the Microsoft.AIFabric.CBS framework package that RemoveWindowsAI removes, and stops RemoveWindowsAI's
# update-cleanup logon task from removing it again. On Windows 11 25H2 (26200.9278 and later) File Explorer depends on
# it. Without it Explorer falls back to the Windows 10 ribbon UI, which only has the classic context menu.
# If RemoveWindowsAI deleted the package files, they're rebuilt from the copy Windows keeps in its component store (WinSxS).
# auto_dl_and_apply_RemoveWindowsAI.ps1 runs this after every RemoveWindowsAI run.

Write-Host "Restoring Microsoft.AIFabric.CBS for File Explorer..." -ForegroundColor Cyan
Write-Host ""

$isAdmin = ([Security.Principal.WindowsPrincipal] [Security.Principal.WindowsIdentity]::GetCurrent()).IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)

if (-not $isAdmin) {
    Write-Host "This script requires Administrator privileges." -ForegroundColor Red
    Write-Host "Please run PowerShell as Administrator and try again." -ForegroundColor Yellow
    exit 1
}

# The logon task re-runs RemoveWindowsAI's removal list after every Windows update.
$cleanupScript = "$env:ProgramData\RemoveAI-UpdateCleanup.ps1"
if (Test-Path -LiteralPath $cleanupScript) {
    $text = [IO.File]::ReadAllText($cleanupScript)
    $patched = $text -replace "(?m)^([ \t]*)'(Microsoft\.AIFabric\.CBS\*?)'", '$1#''$2'' kept: File Explorer depends on it'
    $patched = $patched -replace "(?m)^([ \t]*)(Set-FeatureID -disable -FeatureId (?:58375086|63366798|58375066|61199980|40012896)\b)", '$1#$2 skipped: only needed when Microsoft.AIFabric.CBS is removed'
    if ($patched -ne $text) {
        [IO.File]::WriteAllText($cleanupScript, $patched)
        Write-Host "Kept Microsoft.AIFabric.CBS in RemoveWindowsAI's update cleanup task ($cleanupScript)" -ForegroundColor Green
    }
}

# RemoveWindowsAI's update blocker 1.0.0.1 and later also replaces Microsoft.AIFabric.CBS in the component store.
$blocker = Get-ChildItem 'HKLM:\SOFTWARE\Microsoft\Windows\CurrentVersion\Component Based Servicing\Packages' |
    Where-Object { $_.PSChildName -like 'ZoicwareRemoveWindowsAI~*' -and [version]$_.PSChildName.Split('~')[-1] -ge [version]'1.0.0.1' } |
    Select-Object -First 1
if ($blocker) {
    Write-Host "RemoveWindowsAI's update blocker ($($blocker.PSChildName)) replaces Microsoft.AIFabric.CBS, so Windows Update won't update or repair it on this PC." -ForegroundColor Yellow
    Write-Host "  Removing the blocker lets Windows manage it again: DISM /Online /Remove-Package /PackageName:$($blocker.PSChildName), then restart. Windows Update may then reinstall other AI packages." -ForegroundColor Yellow
}

function Test-PlainExecutable([string]$Path) {
    $stream = [IO.File]::OpenRead($Path)
    try { $stream.ReadByte() -eq 0x4D -and $stream.ReadByte() -eq 0x5A }
    finally { $stream.Dispose() }
}

function Get-StoredPackageCopy([string]$ComponentStore, [string]$Architecture) {
    # Newest copy of each Microsoft.AIFabric.CBS package whose executables are stored as plain files ('MZ' header).
    Get-ChildItem -LiteralPath $ComponentStore -Directory -Filter '*_microsoft-aifabric-cbs*' -ErrorAction SilentlyContinue | ForEach-Object {
        $manifestPath = Join-Path $_.FullName 'AppxManifest.xml'
        if (-not (Test-Path -LiteralPath $manifestPath) -or -not (Test-Path -LiteralPath (Join-Path $_.FullName 'AppxBlockMap.xml'))) { return }
        try { $identity = ([xml](Get-Content -LiteralPath $manifestPath -Raw)).Package.Identity } catch { return }
        if ($identity.ProcessorArchitecture -ne $Architecture) { return }
        if (Get-ChildItem -LiteralPath $_.FullName -File -Force | Where-Object { $_.Extension -in '.dll', '.exe' -and -not (Test-PlainExecutable $_.FullName) }) { return }
        [pscustomobject]@{ Name = $identity.Name; Version = [version]$identity.Version; Path = $_.FullName }
    } | Group-Object Name | ForEach-Object { $_.Group | Sort-Object Version -Descending | Select-Object -First 1 }
}

function Restore-PackageFiles([string]$Source, [string]$Destination) {
    # The component store keeps the package files in one flat folder. Each file's folder inside the package comes from
    # the block map; the code integrity catalog always lives in AppxMetadata.
    $packagePaths = @{ 'CodeIntegrity.cat' = 'AppxMetadata\CodeIntegrity.cat' }
    foreach ($entry in ([xml](Get-Content -LiteralPath (Join-Path $Source 'AppxBlockMap.xml') -Raw)).BlockMap.File) {
        $packagePaths[(Split-Path $entry.Name -Leaf)] = $entry.Name
    }
    foreach ($file in Get-ChildItem -LiteralPath $Source -File -Force) {
        $relativePath = if ($packagePaths.ContainsKey($file.Name)) { $packagePaths[$file.Name] } else { $file.Name }
        $target = Join-Path $Destination $relativePath
        New-Item -ItemType Directory -Force -Path (Split-Path $target) | Out-Null
        Copy-Item -LiteralPath $file.FullName -Destination $target -Force
    }
}

$store = 'HKLM:\SOFTWARE\Microsoft\Windows\CurrentVersion\Appx\AppxAllUserStore'
$systemApps = "$env:windir\SystemApps"
$packageDirs = @(Get-ChildItem $systemApps -Directory -Filter 'Microsoft.AIFabric.CBS*' |
    Where-Object { Test-Path (Join-Path $_.FullName 'AppxManifest.xml') })

if (-not $packageDirs) {
    # RemoveWindowsAI deletes the package folder, but Windows keeps a copy in its component store.
    $copies = @(Get-StoredPackageCopy "$env:windir\WinSxS" "$([Runtime.InteropServices.RuntimeInformation]::OSArchitecture)")
    if (-not $copies) {
        if (Get-ChildItem "$env:windir\WinSxS\Manifests" -Filter '*_microsoft-aifabric-cbs*' -ErrorAction SilentlyContinue) {
            Write-Host "No usable copy of Microsoft.AIFabric.CBS is left on this PC." -ForegroundColor Red
            Write-Host "Copy the $systemApps\Microsoft.AIFabric.CBS.* folder from a working PC on the same Windows version to the same place here, then run this again." -ForegroundColor Yellow
            exit 1
        }
        Write-Host "Microsoft.AIFabric.CBS isn't part of this Windows build; nothing to restore." -ForegroundColor Gray
        exit 0
    }
    foreach ($copy in $copies) {
        # 8wekyb3d8bbwe is the publisher ID of Microsoft packages.
        $packageDir = Join-Path $systemApps "$($copy.Name)_8wekyb3d8bbwe"
        Write-Host "Rebuilding $($copy.Name) $($copy.Version) from the Windows component store..." -ForegroundColor Cyan
        Restore-PackageFiles $copy.Path $packageDir
        Write-Host "  Restored $packageDir" -ForegroundColor Green
        $packageDirs += Get-Item -LiteralPath $packageDir
    }
}

# Remove the markers that make the AppX service uninstall the package again.
Write-Host "Removing deprovision and end-of-life markers..." -ForegroundColor Cyan
$markers = @(Get-ChildItem "$store\Deprovisioned" -ErrorAction SilentlyContinue | Where-Object { $_.PSChildName -like 'Microsoft.AIFabric.CBS*' })
foreach ($root in "$store\EndOfLife", "$store\Deleted\EndOfLife") {
    $markers += @(Get-ChildItem $root -ErrorAction SilentlyContinue | ForEach-Object {
        Get-ChildItem $_.PSPath | Where-Object { $_.PSChildName -like 'Microsoft.AIFabric.CBS*' }
    })
}
foreach ($marker in $markers) {
    Remove-Item -LiteralPath $marker.PSPath -Recurse -Force
    Write-Host "  Removed: $($marker.Name)" -ForegroundColor Green
}
if (-not $markers) {
    Write-Host "  None found" -ForegroundColor Gray
}

# InboxApplications is owned by TrustedInstaller, so the entry is written with SeRestorePrivilege.
Add-Type -TypeDefinition @'
using System;
using System.Runtime.InteropServices;
public static class AIFabricRestoreRegistry {
    [StructLayout(LayoutKind.Sequential, Pack = 4)]
    struct TOKEN_PRIVILEGES { public int Count; public long Luid; public int Attributes; }
    [DllImport("advapi32.dll", SetLastError = true)] static extern bool OpenProcessToken(IntPtr process, uint access, out IntPtr token);
    [DllImport("advapi32.dll", SetLastError = true, CharSet = CharSet.Unicode)] static extern bool LookupPrivilegeValue(string system, string name, out long luid);
    [DllImport("advapi32.dll", SetLastError = true)] static extern bool AdjustTokenPrivileges(IntPtr token, bool disableAll, ref TOKEN_PRIVILEGES state, int length, IntPtr previous, IntPtr returnLength);
    [DllImport("kernel32.dll")] static extern IntPtr GetCurrentProcess();
    [DllImport("kernel32.dll")] static extern bool CloseHandle(IntPtr handle);
    [DllImport("advapi32.dll", CharSet = CharSet.Unicode)] static extern int RegCreateKeyEx(IntPtr key, string subKey, int reserved, string cls, int options, int sam, IntPtr security, out IntPtr result, out int disposition);
    [DllImport("advapi32.dll", CharSet = CharSet.Unicode)] static extern int RegSetValueEx(IntPtr key, string name, int reserved, int type, byte[] data, int size);
    [DllImport("advapi32.dll")] static extern int RegCloseKey(IntPtr key);

    public static int EnableRestorePrivilege() {
        IntPtr token;
        if (!OpenProcessToken(GetCurrentProcess(), 0x0028, out token)) return Marshal.GetLastWin32Error();
        TOKEN_PRIVILEGES privileges = new TOKEN_PRIVILEGES { Count = 1, Attributes = 2 };
        int error = 0;
        if (!LookupPrivilegeValue(null, "SeRestorePrivilege", out privileges.Luid)) error = Marshal.GetLastWin32Error();
        else if (!AdjustTokenPrivileges(token, false, ref privileges, 0, IntPtr.Zero, IntPtr.Zero)) error = Marshal.GetLastWin32Error();
        else error = Marshal.GetLastWin32Error();
        CloseHandle(token);
        return error;
    }

    public static int SetLocalMachineString(string subKey, string name, string value) {
        IntPtr localMachine = new IntPtr(unchecked((int)0x80000002));
        IntPtr key;
        int disposition;
        int result = RegCreateKeyEx(localMachine, subKey, 0, null, 0x4 /* REG_OPTION_BACKUP_RESTORE */, 0, IntPtr.Zero, out key, out disposition);
        if (result != 0) return result;
        byte[] data = System.Text.Encoding.Unicode.GetBytes(value + "\0");
        result = RegSetValueEx(key, name, 0, 1 /* REG_SZ */, data, data.Length);
        RegCloseKey(key);
        return result;
    }
}
'@

$privilegeError = [AIFabricRestoreRegistry]::EnableRestorePrivilege()
if ($privilegeError -ne 0) {
    Write-Host "Could not enable SeRestorePrivilege (error $privilegeError)." -ForegroundColor Red
    exit 1
}

$failed = $false
foreach ($dir in $packageDirs) {
    $manifestPath = Join-Path $dir.FullName 'AppxManifest.xml'
    $identity = ([xml](Get-Content -LiteralPath $manifestPath -Raw)).Package.Identity
    $publisherId = $dir.Name.Split('_')[-1]
    $fullName = "$($identity.Name)_$($identity.Version)_$($identity.ProcessorArchitecture)__$publisherId"

    Write-Host "Registering $fullName..." -ForegroundColor Cyan
    $result = [AIFabricRestoreRegistry]::SetLocalMachineString("SOFTWARE\Microsoft\Windows\CurrentVersion\Appx\AppxAllUserStore\InboxApplications\$fullName", 'Path', $manifestPath)
    if ($result -ne 0) {
        Write-Host "  Failed to restore the InboxApplications entry (error $result)" -ForegroundColor Red
        $failed = $true
        continue
    }

    try {
        Add-AppxPackage -Register $manifestPath -DisableDevelopmentMode -ErrorAction Stop
        Write-Host "  Registered" -ForegroundColor Green
    }
    catch {
        Write-Host "  Failed to register: $($_.Exception.Message)" -ForegroundColor Red
        $failed = $true
    }
}

Write-Host ""
if ($failed) {
    Write-Host "Finished with errors." -ForegroundColor Red
    exit 1
}
Write-Host "Done! Restart File Explorer (Task Manager > Windows Explorer > Restart) or sign out and back in." -ForegroundColor Green
