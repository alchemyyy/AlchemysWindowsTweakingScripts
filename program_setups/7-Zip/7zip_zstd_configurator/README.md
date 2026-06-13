# 7-Zip Zstandard Configurator

Applies preferred 7-Zip ZS settings and all-user file associations for an
installed 7-Zip Zstandard instance.

## Usage

Run from the parent `7zip_zstd_alchemys_preferred_setup` directory:

```bat
run_7zip_zstd_configurator.cmd
```

Preview without writing registry values:

```bat
run_7zip_zstd_configurator.cmd --dry-run
```

Or call Python directly:

```bat
python 7zip_zstd_configurator\configure_7zip_zs.py
```

## What It Sets

The script writes settings serialized by 7-Zip ZS under
`HKCU\Software\7-Zip-Zstandard`:

- `LargePages = 1`
- `Extraction\MemLimit = 25%` of detected physical RAM, rounded up to whole GB
- `Options\MenuIcons = 1`
- `ColorMode = 1` for dark mode

It also grants `SeLockMemoryPrivilege` to the current account, writes all-user
file associations under `HKLM\Software\Classes`, and refreshes Explorer
association/icon state.

The requested association set includes both `.pcio` and `.cpio`; `.cpio` is the
extension listed in 7-Zip's format table.
