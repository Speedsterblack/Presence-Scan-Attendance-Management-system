from typing import List, Optional, Tuple

from database.db_config import get_cursor
from database.hod_db import get_hod_department
from database.semester_db import get_active_semester_id, ensure_active_semester
from utils import session


# Students table as defined in db_init.py:
# student_id VARCHAR(20) PRIMARY KEY,
# student_name VARCHAR(150) NOT NULL,
# Department VARCHAR(150),
# level VARCHAR(50),
# qr_code VARCHAR(255) UNIQUE


def add_student(student_id: str, name: str, Department: str, level: str) -> None:
    """Insert or update a student with explicit Department and level.

    The qr_code column is kept for backwards compatibility and is set to
    the student_id so it remains unique per student without encoding
    Department/level anymore.
    """

    qr_val = student_id
    with get_cursor() as cursor:
        cursor.execute(
            """
            INSERT INTO students (student_id, student_name, Department, level, qr_code)
            VALUES (%s, %s, %s, %s, %s)
            ON CONFLICT (student_id) DO UPDATE
            SET student_name = EXCLUDED.student_name,
                Department = EXCLUDED.Department,
                level = EXCLUDED.level,
                qr_code = EXCLUDED.qr_code
            """,
            (student_id, name, Department, level, qr_val),
        )


def get_all_students() -> List[Tuple[str, str, str, str]]:
    """Return list of (id, name, Department, level)."""
    admin_department_id = None
    try:
        user = getattr(session, "current_user", None)
        if isinstance(user, dict) and str(user.get("role", "")).lower() == "admin":
            hod_id = str(user.get("id", "")).strip()
            if hod_id:
                dept_id = get_hod_department(hod_id)
                if dept_id is not None:
                    admin_department_id = int(dept_id)
    except Exception:
        admin_department_id = None

    query = "SELECT student_id, student_name, Department, level FROM students"
    params: Tuple[object, ...] = ()
    if admin_department_id is not None:
        semester_id = get_active_semester_id(create_if_missing=True)
        if semester_id is None:
            semester_id = int(ensure_active_semester()["semester_id"])
        query = (
            "SELECT DISTINCT s.student_id, s.student_name, s.Department, s.level "
            "FROM students s "
            "JOIN course_registrations cr ON cr.student_id = s.student_id "
            "JOIN courses c ON c.course_id = cr.course_id "
            "WHERE c.department_id = %s AND cr.semester_id = %s"
        )
        params = (admin_department_id, semester_id)
    query += " ORDER BY s.student_id"

    with get_cursor(commit=False) as cursor:
        cursor.execute(query, params)
        rows = cursor.fetchall()

    result: List[Tuple[str, str, str, str]] = []
    for r in rows:
        Department = (r.get("Department") if isinstance(r, dict) else r[2]) or ""
        level = (r.get("level") if isinstance(r, dict) else r[3]) or ""
        result.append((r["student_id"], r["student_name"], Department, level))
    return result


def get_student(student_id: str) -> Optional[Tuple[str, str, str, str]]:
    with get_cursor(commit=False) as cursor:
        cursor.execute(
            "SELECT student_id, student_name, Department, level FROM students WHERE student_id = %s",
            (student_id,),
        )
        row = cursor.fetchone()

    if not row:
        return None

    Department = (row.get("Department") if isinstance(row, dict) else row[2]) or ""
    level = (row.get("level") if isinstance(row, dict) else row[3]) or ""
    return (row["student_id"], row["student_name"], Department, level)


def delete_student(student_id: str) -> None:
    with get_cursor() as cursor:
        cursor.execute("DELETE FROM students WHERE student_id = %s", (student_id,))
