# 7-Zip Zstandard Preferred Setup

This folder contains a few separate tools:

- `7zip_zstd_iconpatcher`: patches installed 7-Zip ZS binary icon resources.
- `7zip_zstd_configurator`: applies preferred 7-Zip ZS registry settings and
  all-user file associations.
- `install_7zip_zstd.py`: downloads and installs the latest x64 7-Zip ZS
  release from GitHub.
- `7zip_context_menu_extension`: installs a small shell extension I made to add zip/unzip root entries to the context menu of zips

Convenience launchers are available at this folder root:

```bat
run_7zip_zstd_installer.cmd
run_7zip_zstd_configurator.cmd
run_7zip_zstd_iconpatcher.cmd
run_7zip_zstd_context_menu_extension_install.cmd
```
