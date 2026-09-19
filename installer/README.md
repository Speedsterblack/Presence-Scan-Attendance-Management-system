# Presence Scan GUI Installers

This folder contains a real GUI Windows installer setup based on Inno Setup.

## Files

- `presence_scan.iss` - main application installer definition
- `presence_scan_developer.iss` - developer application installer definition
- `build_installer.ps1` - builds both PyInstaller executables and invokes `ISCC.exe`
- `..\qr_attendance_system\PresenceScan.spec` - main application executable definition
- `..\qr_attendance_system\DeveloperPresenceScan.spec` - developer application executable definition

## Build Steps

1. Install **Inno Setup 6** from: https://jrsoftware.org/isdl.php
2. From project root, run:

```powershell
powershell -ExecutionPolicy Bypass -File .\installer\build_installer.ps1
```

3. Two installer executables will be generated in `dist`:

- `dist\PresenceScanInstaller.exe`
- `dist\PresenceScanDeveloperInstaller.exe`

## Install Experience

The generated installer:

- Builds and installs the normal login application.
- Builds and installs the separate developer institution-setup application.
- Creates Start Menu shortcuts for each application.
- Optionally creates a per-user desktop shortcut.
- Installs into the current user's local application directory so the existing local SQLite database can be written without administrator access.

## Notes

- The build machine needs Python, PyInstaller, and Inno Setup 6.
- The generated installers bundle the applications and do not require Python on the target machine.
- Install build dependencies with `pip install -r requirements-dev.txt` before running the build script.
