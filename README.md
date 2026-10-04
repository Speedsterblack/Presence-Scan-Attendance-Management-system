# Final-Year-Project

## Running the app

From the project root (this folder), create and activate a virtual
environment, install dependencies and run the main app:

```bash
python -m venv .venv
".venv/Scripts/activate"  # Windows PowerShell / CMD
pip install -r requirements.txt
cd qr_attendance_system
python -m main.main
```

The app uses a local SQLite database and does not require internet access or an
online database. All users, courses, registrations, timetables, attendance,
reports, and institution settings are stored locally on the desktop.

Each desktop has its own database. To move data between desktops, use the
existing local export/import tools or copy the database while the application
is closed. The application does not perform background synchronization.

Start the application with `launch_university_app.bat`. Do not commit or
share the database password.

## Local network communication

The optional mobile QR scanner communicates with the desktop over the local
Wi-Fi or LAN only. Start the scanner from the lecturer screen and open the
displayed address on a phone connected to the same network. Scanned attendance
is written directly to the desktop's local SQLite database.

The phone and desktop do not need internet access. They only need to be on the
same local network, and Windows Firewall must allow the scanner port.

## Local attendance cache

Attendance is written to the desktop database directly. The cache remains as a
local recovery mechanism for temporary local database failures; it is never
uploaded or synchronized online.

To change the retention period or cache location, set these environment
variables before starting the app:

```powershell
$env:ATTENDANCE_CACHE_DAYS = "7"
$env:ATTENDANCE_CACHE_PATH = "C:\path\to\attendance_cache.db"
```

Only attendance cache data is retained temporarily. Students, courses,
registrations, semesters, timetables, and other master data remain in the
local SQLite database.

## Local prototype installer (Windows)

Use the guided installer script from the project root:

```powershell
powershell -ExecutionPolicy Bypass -File .\install_prototype.ps1
```

What it does:

- Creates `.venv` if needed
- Installs base + dev dependencies
- Runs schema initialization (`python -m database.db_init`)
- Seeds default admin (`python -m scripts.seed_admin`)
- Leaves the application configured for local SQLite

The installer accepts the existing `-NonInteractive`, `-SkipSeed`, and
`-SkipRun` flags. Database connection flags are no longer needed.

```powershell
powershell -ExecutionPolicy Bypass -File .\install_prototype.ps1 -NonInteractive
```

Optional flags:

- `-SkipSeed` to skip default admin seeding
- `-SkipRun` to skip app launch prompt at the end

## Real GUI installer package (Windows .exe)

This project now includes Inno Setup based GUI installers for both application entry points:

- [installer/presence_scan.iss](installer/presence_scan.iss)
- [installer/presence_scan_developer.iss](installer/presence_scan_developer.iss)

Build script:

- [installer/build_installer.ps1](installer/build_installer.ps1)

### Build the GUI installer

1. Install **Inno Setup 6**: https://jrsoftware.org/isdl.php
2. From project root run:

```powershell
powershell -ExecutionPolicy Bypass -File .\installer\build_installer.ps1
```

3. Output files:

- `dist\PresenceScanInstaller.exe`
- `dist\PresenceScanDeveloperInstaller.exe`

### What the GUI installer does

- Builds and installs the normal login app and the developer institution-setup app separately
- Creates Start Menu shortcuts for both apps
- Optionally creates per-user desktop shortcuts
- Installs to a writable per-user application directory for local SQLite database support

## Semester lifecycle (current behavior)

The system is now semester-aware. Key rules:

- Student master data is retained across semesters.
- Course registrations are semester-scoped (`student_id + course_id + semester_id`).
- Attendance records are semester-scoped (`semester_id` attached to each attendance row).
- Closing a semester does **not** delete historical records; it marks the semester as `closed` and starts a new `active` semester.
- Admin must confirm their PIN/password before closing the current semester from Settings.

### Registration rules after semester rollover

- Registration remains **course-level**, not department-level.
- Students do **not** re-register for department membership.
- Students must be registered to their new-semester courses to appear in active attendance workflows and analytics.

### Where to manage it in the UI

- Open `Settings` as Admin.
- Use **Semester management**:
  - `Close current & start next` (requires admin PIN/password confirmation)
  - `Open semester archive` (read-only historical summary)

### Newly added admin tools

- Separate admin PIN management for semester rollover and sensitive actions.
- Audit log viewer for administrative actions.
- Re-register the latest closed semester's course registrations into the active semester.
- Semester archive export to CSV.
- Transcript history viewer for student course/attendance history.
- Low-attendance notification banner on the admin dashboard.
- Dedicated Import Center for student/course/registration CSV imports.

## Local database mode

The current build runs in single-database local mode. On startup it creates a
sqlite database file inside `qr_attendance_system/database/` and seeds the
default university, department and active semester rows automatically.

Use `launch_university_app.bat` or `python -m main.main` to start the app; no
external database URL is required for normal use.
