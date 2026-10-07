import os
import re

import qrcode

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
QR_FOLDER = os.path.join(BASE_DIR, "qr_codes")

# Only letters, digits, "_" and "-" are allowed, so an ID can never contain
# path characters such as "..", "/" or "\" and write outside QR_FOLDER.
_SAFE_ID = re.compile(r"^[A-Za-z0-9_-]+$")


def _clean_id(student_id) -> str:
    sid = str(student_id or "").strip()
    if not sid or not _SAFE_ID.match(sid):
        raise ValueError(f"Invalid student ID for QR code: {student_id!r}")
    return sid


def get_qr_path(student_id) -> str:
    """Return where this student's QR file lives (it may not exist yet).

    Use this everywhere instead of building the path by hand, so the whole
    app looks in the same absolute folder no matter where it was launched from.
    """
    return os.path.join(QR_FOLDER, f"{_clean_id(student_id)}.png")


def generate_qr(student_id) -> str:
    """Generate a QR PNG for `student_id` in the `qr_codes/` folder.

    Returns the path to the file. If a valid file already exists it is reused.
    """
    sid = _clean_id(student_id)

    # Create the folder when it is needed, not at import time.
    os.makedirs(QR_FOLDER, exist_ok=True)

    file_path = os.path.join(QR_FOLDER, f"{sid}.png")

    # Reuse an existing file, but not an empty/corrupt one from a failed save.
    if os.path.exists(file_path) and os.path.getsize(file_path) > 0:
        return file_path

    # Save to a temp file first, then rename. If saving fails halfway, no
    # broken PNG is left behind to be mistaken for a finished QR code.
    tmp_path = file_path + ".tmp"
    try:
        img = qrcode.make(sid)
        with open(tmp_path, "wb") as f:
            img.save(f)
        os.replace(tmp_path, file_path)
    finally:
        if os.path.exists(tmp_path):
            try:
                os.remove(tmp_path)
            except OSError:
                pass

    return file_path