# Presence Scan GUI Installer

This folder contains a real GUI Windows installer setup based on Inno Setup.

## Files

- `presence_scan.iss` - Inno Setup installer definition
- `build_installer.ps1` - build helper script that invokes `ISCC.exe`

## Build Steps

1. Install **Inno Setup 6** from: https://jrsoftware.org/isdl.php
2. From project root, run:

```powershell
powershell -ExecutionPolicy Bypass -File .\installer\build_installer.ps1
```

3. Output installer will be generated at:

- `dist\PresenceScanInstaller.exe`

## Install Experience

The generated installer:

- Installs app files to `Program Files\Presence Scan`
- Creates Start Menu shortcuts
- Optionally creates desktop shortcut
- Automatically launches `install_prototype.ps1` after install for first-time setup (venv, dependencies, schema init, admin seed)

## Notes

- The installer does not bundle Python itself.
- End-users should have Python installed before running the first-time setup wizard.
