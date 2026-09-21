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

The app uses local SQLite by default. To use Supabase PostgreSQL, set
`DATABASE_URL` before starting the app and initialize the schema once:

```powershell
$env:DATABASE_URL = "postgresql://postgres:<password>@<project-ref>.pooler.supabase.com:6543/postgres?sslmode=require"
cd qr_attendance_system
python -m database.db_init
python -m main.main
```

Keep the connection string in an environment variable or a launcher-specific
secret store. Do not commit it to the repository. When `DATABASE_URL` is not
set, the app continues to use its local SQLite database.

## Set up a shared desktop installation

For multiple desktop machines, use one PostgreSQL or Supabase database and
configure each desktop with the same database connection. From the project
root, run PowerShell as the installing Windows user:

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
Set-ExecutionPolicy -Scope Process Bypass
.\configure_shared_desktop.ps1
```

The setup script prompts for the database connection, initializes the shared
schema, and stores the connection values in that Windows user's environment.
It keeps `LOCAL_PRIMARY=1`, so credentials are read locally and offline
attendance remains available while the background worker synchronizes shared
data. It also asks for the university code assigned to that desktop; only HOD
and lecturer credentials belonging to that university are imported and
synchronized. Run the script once on every desktop using the same database.

The university code must exactly match the `university_code` value in
Supabase. For example, if Supabase contains `UG001`, enter `UG001`, not a
different local code.

The developer installer is institution-wide: it asks for the database
connection only and synchronizes credentials across all universities.
The main app creates its own local SQLite database on first launch and imports
the relevant credentials from Supabase before showing the login screen.

Start the application with `launch_university_app.bat`. Do not commit or
share the database password.

## Local-first operation

The app keeps the interface responsive on slow connections by default when
PostgreSQL parameters are configured. It reads and writes local
SQLite during normal operation. A background worker mirrors local rows to
Supabase every 5 seconds; network failures are retried on the next cycle and
never block the UI.

To explicitly control this behavior, set `LOCAL_PRIMARY=1` for local-first
operation or `LOCAL_PRIMARY=0` to make the configured PostgreSQL database the
primary connection.

```powershell
$env:LOCAL_PRIMARY = "1"
```

The local database remains the fast working copy. Synchronization is
bidirectional for rows that do not already exist on the other side: remote
rows are imported locally, and local rows are uploaded to Supabase. When both
databases contain different values for the same primary key, the local row is
kept to avoid silently overwriting active local data.

## Attendance offline cache

When connected to PostgreSQL, the app keeps a local attendance cache at
`qr_attendance_system/database/attendance_cache.db`. Failed attendance writes
are queued there and retried when the app starts with a working connection.
Successfully synchronized cache rows are removed after seven days. Pending
rows are retained until they can be synchronized.

To change the retention period or cache location, set these environment
variables before starting the app:

```powershell
$env:ATTENDANCE_CACHE_DAYS = "7"
$env:ATTENDANCE_CACHE_PATH = "C:\path\to\attendance_cache.db"
```

Only attendance cache data is retained temporarily. Students, courses,
registrations, semesters, timetables, and other master data remain in the
Supabase database.

## One-step prototype installer (Windows)

Use the guided installer script from the project root:

```powershell
powershell -ExecutionPolicy Bypass -File .\install_prototype.ps1
```

What it does:

- Creates `.venv` if needed
- Installs base + dev dependencies
- Prompts for PostgreSQL connection values
- Sets `DATABASE_URL` for setup commands
- Runs schema initialization (`python -m database.db_init`)
- Seeds default admin (`python -m scripts.seed_admin`)
- Rewrites `launch_university_app.bat` with your DB connection

Useful flags:

```powershell
powershell -ExecutionPolicy Bypass -File .\install_prototype.ps1 -NonInteractive -DbHost localhost -DbPort 5432 -DbName Presence_Scan -DbUser postgres -DbPassword Speedster
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
