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

The app creates its local sqlite database automatically on first run, so no
separate database server or manual schema setup is required.

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

This project now includes an Inno Setup based GUI installer definition in:

- [installer/presence_scan.iss](installer/presence_scan.iss)

Build script:

- [installer/build_installer.ps1](installer/build_installer.ps1)

### Build the GUI installer

1. Install **Inno Setup 6**: https://jrsoftware.org/isdl.php
2. From project root run:

```powershell
powershell -ExecutionPolicy Bypass -File .\installer\build_installer.ps1
```

3. Output file:

- `dist\PresenceScanInstaller.exe`

### What the GUI installer does

- Installs app files to `Program Files\Presence Scan`
- Creates Start Menu shortcuts
- Optionally creates a desktop shortcut
- Launches first-time setup wizard (`install_prototype.ps1`) after install

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
