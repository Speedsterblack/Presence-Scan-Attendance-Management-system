import qrcode
import os
import shutil

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
# Primary folder (kept for backwards compatibility)
QR_FOLDER = os.path.join(BASE_DIR, "qr_codes")
# Also mirror into assets/qrcodes to support legacy display utilities
ASSETS_QR_FOLDER = os.path.join(BASE_DIR, "assets", "qrcodes")

os.makedirs(QR_FOLDER, exist_ok=True)
os.makedirs(ASSETS_QR_FOLDER, exist_ok=True)


def generate_qr(student_id):
    """Generate a QR PNG for `student_id`.

    The file is written to the canonical `qr_codes/` folder and mirrored
    into `assets/qrcodes/` for compatibility with display utilities.
    Returns the path to the primary file in `qr_codes/`.
    """
    file_path = os.path.join(QR_FOLDER, f"{student_id}.png")

    # Prevent duplicate QR
    if os.path.exists(file_path):
        # Ensure mirror exists too
        try:
            mirror = os.path.join(ASSETS_QR_FOLDER, f"{student_id}.png")
            if not os.path.exists(mirror):
                shutil.copyfile(file_path, mirror)
        except Exception:
            pass
        return file_path

    qr = qrcode.make(student_id)
    qr.save(file_path)

    # Mirror to assets folder if possible (non-fatal)
    try:
        mirror_path = os.path.join(ASSETS_QR_FOLDER, f"{student_id}.png")
        shutil.copyfile(file_path, mirror_path)
    except Exception:
        # Don't fail the generation on mirror errors
        pass

    return file_path
