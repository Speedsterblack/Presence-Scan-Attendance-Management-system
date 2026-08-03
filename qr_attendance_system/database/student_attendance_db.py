from __future__ import annotations

from collections import Counter
from datetime import date, timedelta
from typing import List, Optional, Tuple

from database.db_config import get_cursor
from database.hod_db import get_hod_department
from database.lecturer_db import get_lecturer_courses
from database.semester_db import get_active_semester_id, ensure_active_semester
from database import special_days_db
from utils import session
from config import settings as app_settings
from config.settings import get_semester_weeks


StudentRow = Tuple[str, str, str, str]
# course_code, course_title, present, late, absent, observed_sessions, expected_sessions
CourseSummaryRow = Tuple[str, str, int, int, int, int, int]


_DAY_NAME_TO_WEEKDAY = {
    "Mon": 0,
    "Tue": 1,
    "Wed": 2,
    "Thu": 3,
    "Fri": 4,
    "Sat": 5,
    "Sun": 6,
}


def _count_observed_sessions(course_code: str, department_id: Optional[int], semester_id: int) -> int:
    """Count observed timetable sessions for a course.

    A session is observed when the timetable says the course should run on
    that date and the date is not marked as a special day for the course's
    department.
    """

    if department_id is None:
        return 0

    with get_cursor(commit=False) as cursor:
        cursor.execute(
            """
            SELECT MIN(a.attendance_date) AS first_date
            FROM attendance a
            JOIN timetable t ON a.timetable_id = t.timetable_id
            JOIN courses c ON t.course_id = c.course_id
            WHERE c.course_code = %s
              AND c.department_id = %s
                            AND a.semester_id = %s
            """,
                        (course_code, department_id, semester_id),
        )
        first_row = cursor.fetchone() or {}

        first_date = first_row.get("first_date")
        if not first_date:
            return 0

        cursor.execute(
            """
            SELECT t.day_of_week
            FROM timetable t
            JOIN courses c ON t.course_id = c.course_id
            WHERE c.course_code = %s
              AND c.department_id = %s
            ORDER BY t.timetable_id
            """,
            (course_code, department_id),
        )
        timetable_rows = cursor.fetchall()

    if not timetable_rows:
        return 0

    day_counts = Counter()
    for row in timetable_rows:
        day_name = str(row.get("day_of_week", "")).strip()
        if day_name in _DAY_NAME_TO_WEEKDAY:
            day_counts[day_name] += 1

    if not day_counts:
        return 0

    observed = 0
    current_day = first_date
    today = date.today()
    weekday_names = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]
    while current_day <= today:
        if special_days_db.get_special_day(current_day, department_id=department_id) is None:
            observed += day_counts.get(weekday_names[current_day.weekday()], 0)
        current_day += timedelta(days=1)

    return observed


def _get_current_scope() -> tuple[Optional[int], List[str]]:
    """Return the current department id or lecturer course list."""

    try:
        user = getattr(session, "current_user", None)
    except Exception:
        return None, []

    if not isinstance(user, dict):
        return None, []

    role = str(user.get("role", "")).lower()
    user_id = str(user.get("id", "")).strip()
    if not user_id:
        return None, []

    if role == "admin":
        try:
            dept_id = get_hod_department(user_id)
        except Exception:
            dept_id = None
        return (int(dept_id) if dept_id is not None else None, [])

    if role == "lecturer":
        try:
            course_codes = [str(code).strip() for code in get_lecturer_courses(user_id)]
        except Exception:
            course_codes = []
        return None, [code for code in course_codes if code]

    return None, []


def _get_visible_students(limit: Optional[int] = None) -> List[StudentRow]:
    """Return students currently visible to the logged-in user."""

    dept_id, course_codes = _get_current_scope()
    semester_id = get_active_semester_id(create_if_missing=True)
    if semester_id is None:
        semester_id = int(ensure_active_semester()["semester_id"])

    with get_cursor(commit=False) as cursor:
        if dept_id is not None:
            cursor.execute(
                """
                SELECT DISTINCT s.student_id, s.student_name,
                                COALESCE(s.Department, '') AS Department,
                                COALESCE(s.level, '') AS level
                FROM students s
                JOIN course_registrations cr ON cr.student_id = s.student_id
                JOIN courses c ON c.course_id = cr.course_id
                WHERE c.department_id = %s AND cr.semester_id = %s
                ORDER BY s.student_name, s.student_id
                """,
                (dept_id, semester_id),
            )
        elif course_codes:
            placeholders = ", ".join(["%s"] * len(course_codes))
            cursor.execute(
                f"""
                SELECT DISTINCT s.student_id, s.student_name,
                                COALESCE(s.Department, '') AS Department,
                                COALESCE(s.level, '') AS level
                FROM students s
                JOIN course_registrations cr ON cr.student_id = s.student_id
                JOIN courses c ON c.course_id = cr.course_id
                WHERE c.course_code IN ({placeholders}) AND cr.semester_id = %s
                ORDER BY s.student_name, s.student_id
                """,
                (*course_codes, semester_id),
            )
        else:
            return []

        rows = cursor.fetchall()

    result: List[StudentRow] = [
        (
            str(row.get("student_id") if isinstance(row, dict) else row[0] or ""),
            str(row.get("student_name") if isinstance(row, dict) else row[1] or ""),
            str((row.get("Department") or row.get("department") if isinstance(row, dict) else row[2]) or ""),
            str((row.get("level") or row.get("Level") if isinstance(row, dict) else row[3]) or ""),
        )
        for row in rows
    ]

    if limit is not None:
        return result[:limit]
    return result


def get_visible_students() -> List[StudentRow]:
    """Return all students visible to the logged-in user."""

    return _get_visible_students()


def search_students(query: str, limit: int = 50) -> List[StudentRow]:
    """Search students visible to the logged-in user by name or ID."""

    query = (query or "").strip()
    if not query:
        return []

    dept_id, course_codes = _get_current_scope()
    like = f"%{query.lower()}%"
    semester_id = get_active_semester_id(create_if_missing=True)
    if semester_id is None:
        semester_id = int(ensure_active_semester()["semester_id"])

    with get_cursor(commit=False) as cursor:
        if dept_id is not None:
            # Admin: students registered to any course in their department
            cursor.execute(
                """
                SELECT DISTINCT s.student_id, s.student_name,
                                COALESCE(s.Department, '') AS Department,
                                COALESCE(s.level, '') AS level
                FROM students s
                JOIN course_registrations cr ON cr.student_id = s.student_id
                JOIN courses c ON c.course_id = cr.course_id
                WHERE c.department_id = %s
                                    AND cr.semester_id = %s
                  AND (LOWER(s.student_id) LIKE %s OR LOWER(s.student_name) LIKE %s)
                ORDER BY s.student_name, s.student_id
                LIMIT %s
                """,
                                (dept_id, semester_id, like, like, limit),
            )
        elif course_codes:
            # Lecturer: only students registered to their courses
            placeholders = ", ".join(["%s"] * len(course_codes))
            cursor.execute(
                f"""
                SELECT DISTINCT s.student_id, s.student_name,
                                COALESCE(s.Department, '') AS Department,
                                COALESCE(s.level, '') AS level
                FROM students s
                JOIN course_registrations cr ON cr.student_id = s.student_id
                JOIN courses c ON c.course_id = cr.course_id
                WHERE c.course_code IN ({placeholders})
                                    AND cr.semester_id = %s
                  AND (LOWER(s.student_id) LIKE %s OR LOWER(s.student_name) LIKE %s)
                ORDER BY s.student_name, s.student_id
                LIMIT %s
                """,
                                (*course_codes, semester_id, like, like, limit),
            )
        else:
            return []

        rows = cursor.fetchall()

    return [
        (
            str(row.get("student_id") if isinstance(row, dict) else row[0] or ""),
            str(row.get("student_name") if isinstance(row, dict) else row[1] or ""),
            str((row.get("Department") or row.get("department") if isinstance(row, dict) else row[2]) or ""),
            str((row.get("level") or row.get("Level") if isinstance(row, dict) else row[3]) or ""),
        )
        for row in rows
    ]


def get_student_course_summary(student_id: str) -> List[CourseSummaryRow]:
    """Return per-course attendance totals for a single student, scoped to current user's access."""

    student_id = (student_id or "").strip()
    if not student_id:
        return []

    dept_id, course_codes = _get_current_scope()
    if dept_id is None and not course_codes:
        # No scope means unauthenticated or invalid role
        return []

    semester_id = get_active_semester_id(create_if_missing=True)
    if semester_id is None:
        semester_id = int(ensure_active_semester()["semester_id"])

    # Verify that the student is in scope before proceeding
    with get_cursor(commit=False) as cursor:
        if dept_id is not None:
            cursor.execute(
                """
                SELECT 1
                FROM students s
                JOIN course_registrations cr ON cr.student_id = s.student_id
                JOIN courses c ON c.course_id = cr.course_id
                WHERE s.student_id = %s AND c.department_id = %s AND cr.semester_id = %s
                LIMIT 1
                """,
                (student_id, dept_id, semester_id),
            )
        else:
            placeholders = ", ".join(["%s"] * len(course_codes))
            cursor.execute(
                f"""
                SELECT 1
                FROM students s
                JOIN course_registrations cr ON cr.student_id = s.student_id
                JOIN courses c ON c.course_id = cr.course_id
                WHERE s.student_id = %s AND c.course_code IN ({placeholders}) AND cr.semester_id = %s
                LIMIT 1
                """,
                (student_id, *course_codes, semester_id),
            )
        if not cursor.fetchone():
            # Student is not in scope; return empty summary
            return []

    course_query = """
            SELECT DISTINCT c.course_code, c.course_title, c.department_id
        FROM course_registrations cr
        JOIN courses c ON c.course_id = cr.course_id
        WHERE cr.student_id = %s
          AND cr.semester_id = %s
    """

    params: list[object] = [student_id, semester_id]

    if dept_id is not None:
        course_query += " AND c.department_id = %s"
        params.append(dept_id)
    elif course_codes:
        placeholders = ", ".join(["%s"] * len(course_codes))
        course_query += f" AND c.course_code IN ({placeholders})"
        params.extend(course_codes)

    course_query += " ORDER BY c.course_code"

    with get_cursor(commit=False) as cursor:
        cursor.execute(course_query, tuple(params))
        course_rows = cursor.fetchall()

    summary: List[CourseSummaryRow] = []
    with get_cursor(commit=False) as cursor:
        for course in course_rows:
            course_code = course["course_code"]
            course_title = course["course_title"]
            course_department_id = int(course["department_id"])
            # Apply scope constraints to attendance query for defense-in-depth
            attendance_query = """
                SELECT
                    COUNT(DISTINCT (a.timetable_id, a.attendance_date)) FILTER (
                        WHERE a.student_id = %s AND a.status = 'Present'
                    ) AS present_count,
                    COUNT(DISTINCT (a.timetable_id, a.attendance_date)) FILTER (
                        WHERE a.student_id = %s AND a.status = 'Late'
                    ) AS late_count
                FROM attendance a
                JOIN timetable t ON a.timetable_id = t.timetable_id
                JOIN courses c ON t.course_id = c.course_id
                WHERE c.course_code = %s
                  AND a.semester_id = %s
            """
            attendance_params = [student_id, student_id, course_code, semester_id]
            
            # Enforce scope: admin sees only department courses, lecturer sees only their courses
            if dept_id is not None:
                attendance_query += " AND c.department_id = %s"
                attendance_params.append(dept_id)
            elif course_codes:
                placeholders = ", ".join(["%s"] * len(course_codes))
                attendance_query += f" AND c.course_code IN ({placeholders})"
                attendance_params.extend(course_codes)
            
            cursor.execute(attendance_query, tuple(attendance_params))
            row = cursor.fetchone() or {}
            present_count = int(row.get("present_count") or 0)
            late_count = int(row.get("late_count") or 0)
            session_count = _count_observed_sessions(course_code, course_department_id, int(semester_id))
            absent_count = max(session_count - present_count - late_count, 0)
            # determine expected sessions for the semester based on weekly timetable
            cursor.execute(
                """
                SELECT COUNT(*) AS sessions_per_week
                FROM timetable t
                JOIN courses c ON t.course_id = c.course_id
                WHERE c.course_code = %s
                """,
                (course_code,),
            )
            tw = cursor.fetchone() or {}
            sessions_per_week = int(tw.get("sessions_per_week") or 0)
            # default semester weeks (fallback to 15 when not configured)
            # use settings helper for role-aware value
            try:
                sem_weeks = int(get_semester_weeks())
            except Exception:
                sem_weeks = 15
            expected_total = sessions_per_week * max(sem_weeks, 0)

            summary.append((course_code, course_title, present_count, late_count, absent_count, session_count, expected_total))

    return summary
