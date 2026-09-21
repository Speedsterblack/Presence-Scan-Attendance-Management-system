# Presence Scan GUI Installers

This folder contains two independent GUI Windows installers based on Inno Setup.

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

- The main installer installs only `PresenceScan.exe`.
- The developer installer installs only `DeveloperPresenceScan.exe`.
- Both installers can be installed side by side with separate Start Menu shortcuts.
- Each installer can optionally create its own per-user desktop shortcut.
- The main installer wizard asks only for the university code and preserves the existing database connection settings.
- The developer installer wizard can configure the shared database connection and university code for a new machine.
- Installs into the current user's local application directory so the existing local SQLite database can be written without administrator access.
- The main app database is at `%LOCALAPPDATA%\Presence Scan\data\presence_scan.db`.
- The developer app database is at `%LOCALAPPDATA%\Presence Scan Developer\data\presence_scan.db`.
- Each database is kept outside its installation directory so updates and reinstalls do not remove local data.
- The build script creates a fresh schema-only SQLite database and both installers include it for new installations.
- Existing local databases are preserved by the `onlyifdoesntexist` installer flag.

## Notes

- The build machine needs Python, PyInstaller, and Inno Setup 6.
- The generated installers bundle the applications and do not require Python on the target machine.
- Install build dependencies with `pip install -r requirements-dev.txt` before running the build script.
