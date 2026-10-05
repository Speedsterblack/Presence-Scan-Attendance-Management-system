# Presence Scan GUI Installers

This folder contains two independent GUI Windows installers based on Inno Setup.

## Files

- `presence_scan.iss` - main application installer definition
- `presence_scan_head.iss` - Head of University application installer definition
- `build_installer.ps1` - builds both PyInstaller executables and invokes `ISCC.exe`
- `..\qr_attendance_system\PresenceScan.spec` - main application executable definition
- `..\qr_attendance_system\HeadOfUniversity.spec` - Head of University executable definition

## Build Steps

1. Install **Inno Setup 6** from: https://jrsoftware.org/isdl.php
2. From project root, run:

```powershell
powershell -ExecutionPolicy Bypass -File .\installer\build_installer.ps1
```

3. Two installer executables will be generated in `dist`:

- `dist\PresenceScanInstaller.exe`
- `dist\PresenceScanHeadInstaller.exe`

## Install Experience

The generated installer:

- The main installer installs only `PresenceScan.exe`.
- The Head installer installs only `HeadOfUniversity.exe`.
- Both installers can be installed side by side with separate Start Menu shortcuts.
- Each installer can optionally create its own per-user desktop shortcut.
- The Head application asks for the university code and name on first launch.
- The main installer asks for the Head hub URL and stores it for the lecturer app.
- The Head application starts a local LAN hub on port `8765`.
- Lecturer applications connect through Settings using the Head hub URL and pairing token.
- No internet, PostgreSQL, or Supabase configuration is required.
- Installs into the current user's local application directory so the existing local SQLite database can be written without administrator access.
- The main app database is at `%LOCALAPPDATA%\Presence Scan\data\presence_scan.db`.
- The Head app database is at `%LOCALAPPDATA%\Presence Scan Head\data\presence_scan.db`.
- Each database is kept outside its installation directory so updates and reinstalls do not remove local data.
- The build script creates a fresh schema-only SQLite database and both installers include it for new installations.
- Existing local databases are preserved by the `onlyifdoesntexist` installer flag.

## Notes

- The build machine needs Python, PyInstaller, and Inno Setup 6.
- The generated installers bundle the applications and do not require Python on the target machine.
- Install build dependencies with `pip install -r requirements-dev.txt` before running the build script.
