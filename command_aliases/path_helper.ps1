# Adds a directory to the END of the user PATH, or removes it.
# Preserves the value type (REG_EXPAND_SZ) and unexpanded %VARS% in existing entries,
# then broadcasts WM_SETTINGCHANGE so new processes see the change without a logoff.
param(
    [Parameter(Mandatory)][ValidateSet('Add', 'Remove')][string]$Action,
    [Parameter(Mandatory)][string]$Dir
)
$ErrorActionPreference = 'Stop'

$key = [Microsoft.Win32.Registry]::CurrentUser.OpenSubKey('Environment', $true)
try {
    $raw = [string]$key.GetValue('Path', '', [Microsoft.Win32.RegistryValueOptions]::DoNotExpandEnvironmentNames)
    $kind = if ($key.GetValueNames() -contains 'Path') { $key.GetValueKind('Path') } else { [Microsoft.Win32.RegistryValueKind]::ExpandString }

    $target = $Dir.TrimEnd('\')
    $entries = @($raw -split ';' | Where-Object { $_ -and $_.TrimEnd('\') -ine $target })
    if ($Action -eq 'Add') { $entries += $target }
    $new = $entries -join ';'

    if ($new -ceq $raw) {
        Write-Output "[OK] User PATH already up to date."
        return
    }
    $key.SetValue('Path', $new, $kind)
} finally {
    $key.Close()
}

Add-Type -Namespace Win32 -Name Native -MemberDefinition @'
[DllImport("user32.dll", CharSet = CharSet.Unicode, SetLastError = true)]
public static extern IntPtr SendMessageTimeout(IntPtr hWnd, uint Msg, UIntPtr wParam, string lParam, uint fuFlags, uint uTimeout, out UIntPtr lpdwResult);
'@
$result = [UIntPtr]::Zero
# HWND_BROADCAST, WM_SETTINGCHANGE, SMTO_ABORTIFHUNG, 5s
[void][Win32.Native]::SendMessageTimeout([IntPtr]0xffff, 0x1A, [UIntPtr]::Zero, 'Environment', 2, 5000, [ref]$result)

$verb = if ($Action -eq 'Add') { 'Appended' } else { 'Removed' }
Write-Output "[OK] $verb $target $(if ($Action -eq 'Add') { 'to' } else { 'from' }) user PATH."
