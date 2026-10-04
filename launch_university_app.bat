@echo off
REM Launcher for a single university's Presence Scan app.
REM This installation uses its local SQLite database and does not require internet access.

REM Always run from the folder where this script lives (project root)
cd /d "%~dp0"

call ".venv\Scripts\activate.bat"

REM Change into the package folder so "python -m main.main" works
cd "qr_attendance_system"

REM Use pythonw so the console window closes once the app starts
pythonw -m main.main
