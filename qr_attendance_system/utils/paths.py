import os
import sys
from pathlib import Path

# Project root (the qr_attendance_system folder) when running from source.
# This file is expected at qr_attendance_system/utils/paths.py.
BASE_DIR = Path(__file__).resolve().parent.parent


def is_frozen() -> bool:
    """True when running as a PyInstaller exe."""
    return bool(getattr(sys, "frozen", False))


def app_data_dir() -> Path:
    """Writable folder for settings, QR codes, logs and other app data.

    Installed exe: %LOCALAPPDATA%\\Presence Scan  (or ...\\Presence Scan Head
    for the Head of University exe).
    From source: the project folder, so development behaves as before.

    Do not use the folder next to the code for anything the app writes: in a
    single-file exe that folder is temporary and is deleted when the app closes.
    """
    if not is_frozen():
        return BASE_DIR

    base = Path(os.environ.get("LOCALAPPDATA") or Path.home())
    exe_name = Path(sys.executable).stem.lower()
    folder = "Presence Scan Head" if "head" in exe_name else "Presence Scan"
    return base / folder


def default_reports_dir() -> Path:
    """Default folder for exported reports/CSVs."""
    if is_frozen():
        return Path.home() / "Documents" / "Presence Scan" / "reports"
    return BASE_DIR / "reports"
