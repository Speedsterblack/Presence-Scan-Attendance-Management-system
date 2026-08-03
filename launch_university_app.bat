@echo off
REM Launcher for a single university's Presence Scan app.
REM The app now creates a local sqlite database automatically, so no
REM PostgreSQL connection string is required.

REM Always run from the folder where this script lives (project root)
cd /d "%~dp0"

REM set DATABASE_URL=postgresql://postgres:Speedster@localhost:5432/Presence_Scan

call ".venv\Scripts\activate.bat"

REM Change into the package folder so "python -m main.main" works
cd "qr_attendance_system"

REM Use pythonw so the console window closes once the app starts
pythonw -m main.main
