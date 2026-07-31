from typing import Optional, Tuple

from database.db_config import get_cursor
from utils.security import hash_password, is_hashed_password, verify_password


def authenticate_hod(user_id: str, password: str) -> Optional[Tuple[str, str, str]]:
    """Authenticate a HOD user from the hods table.

    Returns (id, name, role) with role fixed as 'admin' if credentials match,
    otherwise None.
    """
    query = "SELECT hod_id, hod_name, password FROM hods WHERE hod_id = %s"

    with get_cursor(commit=False) as cursor:
        cursor.execute(query, (user_id,))
        row = cursor.fetchone()

    if not row:
        return None

    stored_password = str(row.get("password") or "")
    if not verify_password(password, stored_password):
        return None

    # Migrate legacy plaintext password rows to hashed form on successful login.
    if not is_hashed_password(stored_password):
        try:
            update_password(user_id, password)
        except Exception:
            pass

    # Treat all HODs as admin users for the UI
    return (row["hod_id"], row["hod_name"], "admin")


def get_hod_department(hod_id: str) -> Optional[int]:
    """Return the department_id for a given HOD, or None if not found."""
    query = "SELECT department_id FROM hods WHERE hod_id = %s"

    with get_cursor(commit=False) as cursor:
        cursor.execute(query, (hod_id,))
        row = cursor.fetchone()

    if not row:
        return None

    return row["department_id"]


def update_password(user_id: str, new_password: str) -> None:
    """Update password for a HOD/admin user."""

    password_hash = hash_password(new_password)
    query = "UPDATE hods SET password = %s WHERE hod_id = %s"

    with get_cursor() as cursor:
        cursor.execute(query, (password_hash, user_id))


def upsert_hod_for_department(hod_id: str, hod_name: str, password: str, department_id: int) -> None:
    """Create or replace the HOD/admin record for a department.

    Ensures there is exactly one HOD per department by using the
    unique ``department_id`` constraint. Updating also refreshes the
    hod_id, name and password.
    """

    query = (
        "INSERT INTO hods (hod_id, hod_name, password, department_id) "
        "VALUES (%s, %s, %s, %s) "
        "ON CONFLICT (department_id) DO UPDATE SET "
        "hod_id = EXCLUDED.hod_id, "
        "hod_name = EXCLUDED.hod_name, "
        "password = EXCLUDED.password"
    )

    password_hash = hash_password(password)

    with get_cursor() as cursor:
        cursor.execute(query, (hod_id, hod_name, password_hash, department_id))

