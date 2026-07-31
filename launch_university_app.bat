@echo off
REM Launcher for a single university's Presence Scan app.
REM Set DATABASE_URL to that university's PostgreSQL database, then
REM double-click this file to run the custom app.

REM Always run from the folder where this script lives (project root)
cd /d "%~dp0"

set DATABASE_URL=postgresql://postgres:Speedster@localhost:5432/Presence_Scan

call ".venv\Scripts\activate.bat"

REM Change into the package folder so "python -m main.main" works
cd "qr_attendance_system"

REM Use pythonw so the console window closes once the app starts
pythonw -m main.main
