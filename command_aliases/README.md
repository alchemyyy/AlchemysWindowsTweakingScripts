# command_aliases

Unix-style aliases (`ls`, `cat`, `grep`, `up`, …) for `cmd.exe`, implemented as one-line `.cmd` shims in a folder at the **end** of the user PATH.

## Files

| File | Purpose |
|---|---|
| `aliases.txt` | Source of truth. `name=command` per line (batch syntax); `#` comments and blank lines ignored. |
| `install_aliases.bat` | Regenerates the shim folder and appends it to the user PATH. No admin needed. |
| `uninstall_aliases.bat` | Deletes the shim folder (and `C:\Tools` if empty) and removes it from the user PATH. |
| `path_helper.ps1` | Adds or removes a user PATH entry. Used by both scripts. |

## What gets installed

- `C:\Tools\AlchemysCMDMacros\<name>.cmd` for each alias, containing `@<command>`.
- That folder is appended to `HKCU\Environment\Path`. The value type (`REG_EXPAND_SZ`) and any unexpanded `%VARS%` in other entries are left untouched. `WM_SETTINGCHANGE` is broadcast, so new terminals pick it up without logging off. Already-open windows keep their old PATH.

The folder is deleted and rebuilt on every install, so removing a line from `aliases.txt` and reinstalling removes that alias.

## Writing aliases

`aliases.txt` lines are **batch syntax**, written verbatim into the shim:

- `%*` = all arguments, `%1` / `%~1` = single arguments (`%~1` strips quotes).
- `%VAR%` expands when the alias runs, e.g. `delnul=del "\\?\%CD%\nul"`.
- FOR variables need doubling as in any batch file: `%%F`.
- `!` is fine (the installer doesn't use delayed expansion).
- One line per alias; use `&`, `&&`, `||`, or `if … (…) else (…)` for more logic.

Names may only contain letters, digits, `_` and `-`. The installer skips anything else (e.g. `..`, `~`), and also skips cmd built-ins (`dir`, `cd`, `copy`, `rmdir`, …). Built-ins are resolved before PATH, so a shim with that name would never run.

Navigation aliases (`up`, `up2`, `up3`, `home`) work because a batch file runs inside the calling cmd process. Without `setlocal`, a `cd` in it persists. Never add `setlocal` to such an alias.

## Precedence: anything else wins

cmd resolves a command in this order: built-in → current directory → PATH entries in order (system PATH, then user PATH). The shim folder is last, so **any real program with the same name takes precedence**. This keeps normal app behavior intact. The installer prints `[OVERRIDDEN] name -> path` for every alias currently shadowed.

Example: with Git for Windows installed with "Use Git and optional Unix tools from the Command Prompt", `C:\Program Files\Git\usr\bin` is on the system PATH. Then `ls`, `cat`, `cp`, `mv`, `rm`, `grep`, `ps`, `kill`, `pwd`, `touch`, `which` and `clear` run the GNU/MSYS tools, not these shims. Note that MSYS `ps`/`kill` use MSYS PIDs, not Windows ones. Use `tasklist`/`taskkill` directly, or rename those aliases, if you want the Windows tools.

## Differences from the old doskey approach

The previous version loaded doskey macros via `HKCU\Software\Microsoft\Command Processor\AutoRun`. The installer removes that AutoRun value (only if it references `cmd_aliases`), `%LOCALAPPDATA%\cmd_aliases`, and `C:\Windows\cmd_aliases.cmd`.

| | doskey via AutoRun | `.cmd` shims on PATH |
|---|---|---|
| Startup cost | every cmd instance, including non-interactive `cmd /c` from other programs | none |
| Per-command cost | none | one extra folder searched on PATH lookups that reach the end of PATH |
| Names like `..`, `~` | allowed | not possible (renamed to `up`, `home`) |
| Override built-ins / PATH programs | yes (macros match typed text first) | no (last in precedence) |
| Visible to scripts/programs | no, interactive input only | yes, they are real commands |
| From another batch file | n/a | must use `call alias`, or the calling script ends after it |

Original problem, for reference: the first version ran `doskey.exe` once per alias (28 processes) in every cmd. That cost about 1,000–1,900 ms per new Windows Terminal tab, varying with system load and Defender scanning.

## Troubleshooting slow terminal startup

- **Compare** `1..5 | % { (Measure-Command { cmd /c exit }).TotalMilliseconds }` against the same with `cmd /d /c exit` (skips AutoRun). A large gap means something in AutoRun is slow.
- **Occasional ~300 ms spikes** happen even with nothing in AutoRun. They're system-level: Defender scanning `cmd.exe`/`conhost.exe` startup, general load, or Windows Terminal itself.
- **Windows Terminal profile command line:** profiles launching `VsDevCmd.bat`, Clink, or other init scripts add their own cost.
- **Other AutoRun locations** run in addition to HKCU:

  ```bat
  reg query "HKCU\Software\Microsoft\Command Processor" /v AutoRun
  reg query "HKLM\Software\Microsoft\Command Processor" /v AutoRun
  reg query "HKLM\Software\WOW6432Node\Microsoft\Command Processor" /v AutoRun
  ```

- **PATH length is rarely the cause.** About 2,600 characters across about 60 entries is normal. What costs time is PATH entries pointing to missing folders, network shares (UNC), or removable or disconnected drives. Command lookups probe them, and a disconnected drive or share can stall. To list them:

  ```powershell
  $p = [Environment]::GetEnvironmentVariable("Path","Machine") + ";" + [Environment]::GetEnvironmentVariable("Path","User")
  $p -split ";" | ? { $_ } | % {
      $x = [Environment]::ExpandEnvironmentVariables($_)
      if (-not (Test-Path -LiteralPath $x)) { "MISSING: $_" } elseif ($x -match '^\\\\') { "UNC: $_" }
  }
  ```

  Remove stale entries via *System Properties → Environment Variables*.
