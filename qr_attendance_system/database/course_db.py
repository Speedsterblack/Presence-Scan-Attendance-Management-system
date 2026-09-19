from typing import List, Optional, Tuple

from database.db_config import get_cursor
from database.hod_db import get_hod_department
from utils import session


# courses table from db_init.py:
# course_id SERIAL PRIMARY KEY,
# course_code VARCHAR(20) NOT NULL,
# course_title VARCHAR(150) NOT NULL,
# department_id INT NOT NULL,
# lecturer_id VARCHAR(20) NOT NULL


def add_course(
    course_code: str,
    title: str,
    _unused_lecturer_id: Optional[str],
    credit_hours: int,
    lecturer_name: str,
    grace_minutes: int = 0,
    department_id: Optional[int] = None,
) -> None:
    """Insert a course.

    The UI currently passes lecturer_name; here we treat it as lecturer_id.
    department_id is required and should come from the current admin's department.
    """
    if department_id is None:
        raise ValueError("Department ID is required when adding a course")
    
    with get_cursor() as cursor:
        cursor.execute(
            "INSERT INTO courses (course_code, course_title, department_id, lecturer_id, credit_hours, grace_minutes)\n"
            "VALUES (%s, %s, %s, %s, %s, %s)\n"
            "ON CONFLICT (course_code) DO NOTHING",
            (course_code, title, department_id, lecturer_name, credit_hours, grace_minutes),
        )


def get_all_courses() -> List[Tuple[str, str, int, str, int, int]]:
    """Return list of (course_code, title, department_id, lecturer_id, credit_hours, grace_minutes)."""
    dept_filter = None
    try:
        user = getattr(session, "current_user", None)
        if isinstance(user, dict) and str(user.get("role", "")).lower() == "admin":
            hod_id = str(user.get("id", "")).strip()
            if hod_id:
                dept_filter = get_hod_department(hod_id)
    except Exception:
        dept_filter = None

    query = "SELECT course_code, course_title, department_id, lecturer_id, credit_hours, grace_minutes FROM courses"
    params: Tuple[object, ...] = ()
    if dept_filter is not None:
        query += " WHERE department_id = %s"
        params = (dept_filter,)
    query += " ORDER BY course_code"

    with get_cursor(commit=False) as cursor:
        cursor.execute(query, params)
        rows = cursor.fetchall()
    return [
        (
            r["course_code"],
            r["course_title"],
            r["department_id"],
            r["lecturer_id"],
            r["credit_hours"],
            r["grace_minutes"],
        )
        for r in rows
    ]


def get_course(course_code: str) -> Optional[Tuple[str, str, int, str, int, int]]:
    with get_cursor(commit=False) as cursor:
        cursor.execute(
            "SELECT course_code, course_title, department_id, lecturer_id, credit_hours, grace_minutes "
            "FROM courses WHERE course_code = %s",
            (course_code,),
        )
        r = cursor.fetchone()
    if not r:
        return None
    return (
        r["course_code"],
        r["course_title"],
        r["department_id"],
        r["lecturer_id"],
        r["credit_hours"],
        r["grace_minutes"],
    )


def update_course(
    course_code: str,
    title: str,
    _unused_lecturer_id: Optional[str],
    credit_hours: int,
    lecturer_name: str,
    grace_minutes: Optional[int] = None,
) -> None:
    """Update a course.

    If grace_minutes is None, the existing grace value is preserved.
    """
    with get_cursor() as cursor:
        if grace_minutes is None:
            cursor.execute(
                "UPDATE courses SET course_title = %s, lecturer_id = %s, credit_hours = %s "
                "WHERE course_code = %s",
                (title, lecturer_name, credit_hours, course_code),
            )
        else:
            cursor.execute(
                "UPDATE courses SET course_title = %s, lecturer_id = %s, credit_hours = %s, grace_minutes = %s "
                "WHERE course_code = %s",
                (title, lecturer_name, credit_hours, grace_minutes, course_code),
            )


def delete_course(course_code: str) -> None:
    with get_cursor() as cursor:
        cursor.execute("DELETE FROM courses WHERE course_code = %s", (course_code,))
