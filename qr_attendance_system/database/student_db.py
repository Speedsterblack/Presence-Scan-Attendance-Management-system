from typing import List, Optional, Tuple

from database.db_config import get_cursor
from database.department_db import get_department 
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

    student_id = str(student_id or "").strip()
    if not student_id.isdigit() or len(student_id) != 8:
        raise ValueError("Student ID must contain exactly 8 digits")

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

def _row_value(r, key, idx):
    """Read a column from a dict row (case-insensitive) or a tuple row."""
    if isinstance(r, dict):
        for k, v in r.items():
            if str(k).lower() == key.lower():
                return v
        return None
    return r[idx]

def get_all_students() -> List[Tuple[str, str, str, str]]:
    """Return list of (id, name, Department, level)."""
    admin_department_id = None
    admin_department_name = ""

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

    if admin_department_id is not None:
        try:
            dept = get_department(admin_department_id)  # (id, name, university_id)
            if dept and len(dept) > 1:
                admin_department_name = str(dept[1] or "").strip()
        except Exception:
            admin_department_name = ""

    # Default: all students
    query = """
        SELECT s.student_id, s.student_name, s.Department, s.level
        FROM students s
    """
    params: Tuple[object, ...] = ()

    # Admin/HOD: students in their department, either registered for one of
    # its courses this semester OR assigned to the department at import.
    if admin_department_id is not None:
        semester_id = get_active_semester_id(create_if_missing=True)
        if semester_id is None:
            semester_id = int(ensure_active_semester()["semester_id"])

        query = """
            SELECT DISTINCT s.student_id, s.student_name, s.Department, s.level
            FROM students s
            LEFT JOIN course_registrations cr
                ON cr.student_id = s.student_id AND cr.semester_id = %s
            LEFT JOIN courses c
                ON c.course_id = cr.course_id
            WHERE c.department_id = %s
        """
        params = (semester_id, admin_department_id)

        if admin_department_name:
            query += " OR LOWER(TRIM(COALESCE(s.Department, ''))) = LOWER(TRIM(%s))"
            params += (admin_department_name,)

    query += " ORDER BY s.student_id"

    with get_cursor(commit=False) as cursor:
        cursor.execute(query, params)
        rows = cursor.fetchall()

    return [
        (
            str(_row_value(r, "student_id", 0)or ""),
            str(_row_value(r, "student_name", 1) or ""),
            _row_value(r, "Department", 2) or "",
            _row_value(r, "level", 3) or "",
        )
        for r in rows
    ]

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
