from typing import List, Tuple

from database.db_config import get_cursor
from database.semester_db import get_active_semester_id, ensure_active_semester


# course_registrations table from db_init.py:
# student_id VARCHAR(20),
# course_id INT,
# semester_id INT,
# PRIMARY KEY (student_id, course_id, semester_id)


def register_student_to_course(student_id: str, course_code: str) -> None:
    """Register a student for a course using course_code."""
    semester_id = get_active_semester_id(create_if_missing=True)
    if semester_id is None:
        semester_id = int(ensure_active_semester()["semester_id"])

    with get_cursor() as cursor:
        cursor.execute("SELECT course_id FROM courses WHERE course_code = %s", (course_code,))
        row = cursor.fetchone()
        if not row:
            raise ValueError(f"No course found with code {course_code}")
        course_id = row["course_id"]

        cursor.execute(
            "INSERT INTO course_registrations (student_id, course_id, semester_id) VALUES (%s, %s, %s)\n"
            "ON CONFLICT (student_id, course_id, semester_id) DO NOTHING",
            (student_id, course_id, semester_id),
        )


def unregister_student_from_course(student_id: str, course_code: str) -> None:
    semester_id = get_active_semester_id(create_if_missing=True)
    if semester_id is None:
        semester_id = int(ensure_active_semester()["semester_id"])

    with get_cursor() as cursor:
        cursor.execute("SELECT course_id FROM courses WHERE course_code = %s", (course_code,))
        row = cursor.fetchone()
        if not row:
            return
        course_id = row["course_id"]

        cursor.execute(
            "DELETE FROM course_registrations WHERE student_id = %s AND course_id = %s AND semester_id = %s",
            (student_id, course_id, semester_id),
        )


def get_courses_for_student(student_id: str) -> List[Tuple[str, str]]:
    """Return list of (course_code, course_title) a student is registered for."""
    semester_id = get_active_semester_id(create_if_missing=True)
    if semester_id is None:
        semester_id = int(ensure_active_semester()["semester_id"])

    with get_cursor(commit=False) as cursor:
        cursor.execute(
            "SELECT c.course_code, c.course_title\n"
            "FROM course_registrations cr\n"
            "JOIN courses c ON cr.course_id = c.course_id\n"
            "WHERE cr.student_id = %s\n"
            "  AND cr.semester_id = %s\n"
            "ORDER BY c.course_code",
            (student_id, semester_id),
        )
        rows = cursor.fetchall()

    return [(r["course_code"], r["course_title"]) for r in rows]


def get_students_for_course(course_code: str) -> List[Tuple[str]]:
    """Return list of student_ids registered for a given course_code."""
    semester_id = get_active_semester_id(create_if_missing=True)
    if semester_id is None:
        semester_id = int(ensure_active_semester()["semester_id"])

    with get_cursor(commit=False) as cursor:
        cursor.execute("SELECT course_id FROM courses WHERE course_code = %s", (course_code,))
        row = cursor.fetchone()
        if not row:
            return []
        course_id = row["course_id"]

        cursor.execute(
            "SELECT student_id FROM course_registrations WHERE course_id = %s AND semester_id = %s",
            (course_id, semester_id),
        )
        rows = cursor.fetchall()

    return [r["student_id"] for r in rows]


def is_student_registered(student_id: str, course_code: str) -> bool:
    """Return True if the student is registered for the given course_code.

    This is optimised for the QR scanner path, which needs a quick
    yes/no check rather than a full list of registrations.
    """

    semester_id = get_active_semester_id(create_if_missing=True)
    if semester_id is None:
        semester_id = int(ensure_active_semester()["semester_id"])

    with get_cursor(commit=False) as cursor:
        cursor.execute(
            "SELECT course_id FROM courses WHERE course_code = %s",
            (course_code,),
        )
        row = cursor.fetchone()
        if not row:
            return False

        course_id = row["course_id"]

        cursor.execute(
            "SELECT 1 FROM course_registrations WHERE student_id = %s AND course_id = %s AND semester_id = %s",
            (student_id, course_id, semester_id),
        )
        return cursor.fetchone() is not None
