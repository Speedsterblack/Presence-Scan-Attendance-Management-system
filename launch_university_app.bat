@echo off
REM Launcher for a single university's Presence Scan app.
REM Set DATABASE_URL below to use Supabase PostgreSQL. Leave it commented to
REM use the local SQLite database.

REM Always run from the folder where this script lives (project root)
cd /d "%~dp0"

REM set DATABASE_URL=postgresql://postgres:<password>@<project-ref>.pooler.supabase.com:6543/postgres?sslmode=require

REM Keep credentials and offline attendance local while syncing shared data.
set LOCAL_PRIMARY=1

call ".venv\Scripts\activate.bat"

REM Change into the package folder so "python -m main.main" works
cd "qr_attendance_system"

REM Use pythonw so the console window closes once the app starts
pythonw -m main.main
