# WindhawkBAR

WindhawkBAR is a small command-line backup and restore helper for Windhawk.

It creates `WindhawkBARResult.zip`. Inside the zip, processed installation
state is stored in `backup.json`, hard files such as mod source files and
compiled DLLs are stored under `assets/`, and a copy of this tool is included
for convenience. On restore, catalog mods are installed from the live Windhawk
mod repository by default, so they come back as the latest available versions
instead of the archived versions from the backup.

## Usage

Create a backup:

```bat
python windhawk_bar.py backup
```

Restore a backup:

```bat
python windhawk_bar.py restore WindhawkBARResult.zip
```

Preview a restore without changing files:

```bat
python windhawk_bar.py restore WindhawkBARResult.zip --dry-run
```

Show what is in a backup:

```bat
python windhawk_bar.py list WindhawkBARResult.zip
```

Restore from `backup.json` only, without an `assets` folder:

```bat
python windhawk_bar.py restore backup.json --json-only
```

Install Windhawk automatically before restore if it is missing:

```bat
python windhawk_bar.py restore backup.json --json-only --install-windhawk-if-missing
```

## Notes

- Default Windhawk data path is `%ProgramData%\Windhawk`.
- Default backup output is `WindhawkBARResult.zip`.
- Standard installs use `HKLM\SOFTWARE\Windhawk` for mod configuration.
- Portable installs use INI files under the Windhawk data path.
- Restoring a standard install writes to HKLM and usually requires an elevated
  terminal.
- Local mods and unavailable catalog mods are restored from `assets`
  automatically.
- Use `--offline` during restore to restore every mod from archived assets
  instead of downloading latest catalog versions.
- Use `--json-only` to restore from only `backup.json`. Catalog mods are
  downloaded, asset fallback is disabled, and local mods are skipped.
- Use `--no-asset-fallback` to fail when a catalog mod cannot be downloaded.
- Use `--install-windhawk-if-missing` during restore to download the latest
  `windhawk_setup.exe` from GitHub releases and run it silently. Standard
  installs require an elevated terminal; portable installs are selected when
  restoring a portable backup or when `--portable` is provided.
