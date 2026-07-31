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

## Database per university (recommended deployment)

This project is designed so that **each university uses its own
PostgreSQL database**, all sharing the same schema. This avoids ID and
password conflicts between University (for example two admins both
using `1111 / 2468`).

### 1. Create a database for each university

For every university (e.g. `Harvard`):

1. In PostgreSQL, create a dedicated database, for example
   `presence_uni_harvard`.
2. From the `qr_attendance_system` folder, run the schema initialiser
   once **against that database**:

   ```powershell
   # In PowerShell from qr_attendance_system/
   $env:DATABASE_URL = "postgresql://postgres:PasswordHere@localhost:5432/presence_uni_harvard"
   python -m database.db_init
   ```

Repeat these steps for each university you want to support, changing
the database name in `DATABASE_URL`.

### 2. Create a launcher per university (Windows)

An example launcher script is provided at the project root:
`launch_example_university.bat`.

To create a launcher for a specific university:

1. Copy `launch_example_university.bat` and rename it, for example
   `PresenceScan_Harvard.bat`.
2. Edit the copied file and update the `DATABASE_URL` line to point to
   that university's database:

   ```bat
   set DATABASE_URL=postgresql://postgres:PasswordHere@localhost:5432/presence_uni_harvard
   ```

3. (Optional) adjust username, password, host or port if your
   PostgreSQL server is different.
4. Double‑click the `.bat` file to start the app for that university.

Each launcher binds the app to one database, so different University
can safely reuse the same admin or lecturer IDs and passwords without
any conflicts.

### 3. Using the developer Institution Setup

For each university database you should use the **Institution Setup**
developer UI to define:

- University (using a human‑readable University ID and name).
- Departments (with Department ID, name, and associated university).
- Admin (HOD) credentials for each department.

The developer UI is launched separately from the main app so normal
users never see it. From `qr_attendance_system/` (with the virtual
environment activated and `DATABASE_URL` pointing at the desired
university database), run:

```bash
python -m main.developer_main
```

These records live inside the chosen database, so each university keeps
its own structure and admin accounts fully isolated from the others.
