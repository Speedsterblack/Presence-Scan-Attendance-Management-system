from typing import List, Tuple
from datetime import datetime, date

from database.db_config import get_cursor
from database import special_days_db
from database.hod_db import get_hod_department
from database.semester_db import get_active_semester_id, ensure_active_semester
from utils import session


# Simple analytics on top of attendance + courses tables


def _get_current_admin_department_id() -> int | None:
    """Return the logged-in admin's department, or None if unavailable."""

    try:
        user = getattr(session, "current_user", None)
    except Exception:
        return None

    if not isinstance(user, dict):
        return None
    if str(user.get("role", "")).lower() != "admin":
        return None

    hod_id = str(user.get("id", "")).strip()
    if not hod_id:
        return None

    try:
        dept_id = get_hod_department(hod_id)
    except Exception:
        return None

    return int(dept_id) if dept_id is not None else None


def has_classes_on(target_date: date | None = None) -> bool:
    """Return True if there is at least one timetable slot today.

    Weekends (Saturday/Sunday) are treated as "no classes" even if
    rows exist, since the timetable is intended for Monday–Friday.
    """

    if target_date is None:
        target_date = date.today()

    weekday = target_date.weekday()
    # 0=Mon, 1=Tue, 2=Wed, 3=Thu, 4=Fri, 5=Sat, 6=Sun
    if weekday >= 5:
        return False

    day_names = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]
    today_name = day_names[weekday]

    dept_id = _get_current_admin_department_id()
    if dept_id is None:
        return False

    # Special days explicitly marked as no-school always win,
    # regardless of the timetable or historical attendance.
    try:
        if special_days_db.is_no_school_day(target_date, dept_id):
            return False
    except Exception:
        pass

    with get_cursor(commit=False) as cursor:
        cursor.execute(
            """
            SELECT 1
            FROM timetable t
            JOIN courses c ON t.course_id = c.course_id
            WHERE t.day_of_week = %s
              AND c.department_id = %s
            LIMIT 1
            """,
            (today_name, dept_id),
        )
        row2 = cursor.fetchone()

    return bool(row2)


def has_classes_today() -> bool:
    """Backwards-compatible helper that checks for classes today."""

    return has_classes_on()


def get_attendance_count_per_course(for_date: date | None = None) -> List[Tuple[str, int]]:
    """Return list of (course_code, attendance_count)."""
    # Only consider courses that are actually scheduled for the
    # requested date (defaults to today).
    if for_date is None:
        for_date = date.today()

    dept_id = _get_current_admin_department_id()
    if dept_id is None:
        return []

    semester_id = get_active_semester_id(create_if_missing=True)
    if semester_id is None:
        semester_id = int(ensure_active_semester()["semester_id"])

    day_names = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]
    today_name = day_names[for_date.weekday()]
    with get_cursor(commit=False) as cursor:
        cursor.execute(
            "SELECT c.course_code, COUNT(*) AS cnt\n"
            "FROM attendance a\n"
            "JOIN timetable t ON a.timetable_id = t.timetable_id\n"
            "JOIN courses c ON t.course_id = c.course_id\n"
            "WHERE a.status = 'Present'\n"
            "  AND a.attendance_date = %s\n"
            "  AND a.semester_id = %s\n"
            "  AND t.day_of_week = %s\n"
            "  AND c.department_id = %s\n"
            "GROUP BY c.course_code\n"
            "ORDER BY c.course_code",
            (for_date, semester_id, today_name, dept_id),
        )
        rows = cursor.fetchall()

    return [(r["course_code"], r["cnt"]) for r in rows]


def get_late_count_per_course(for_date: date | None = None) -> List[Tuple[str, int]]:
    """Placeholder for late arrival counts (no explicit late flag in schema).

    Currently returns zero counts for all courses that have attendance."""
    # Only courses scheduled for the given date (defaults to today)
    if for_date is None:
        for_date = date.today()

    dept_id = _get_current_admin_department_id()
    if dept_id is None:
        return []

    day_names = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]
    today_name = day_names[for_date.weekday()]
    with get_cursor(commit=False) as cursor:
        cursor.execute(
            "SELECT DISTINCT c.course_code\n"
            "FROM timetable t\n"
            "JOIN courses c ON t.course_id = c.course_id\n"
            "WHERE t.day_of_week = %s\n"
            "  AND c.department_id = %s\n"
            "ORDER BY c.course_code",
            (today_name, dept_id),
        )
        rows = cursor.fetchall()

    return [(r["course_code"], 0) for r in rows]


def get_attendance_breakdown_per_course(for_date: date | None = None) -> List[Tuple[str, int, int, int, int]]:
    """Return per-course attendance breakdown.

    The result is a list of tuples::

        (course_code, present_count, absent_count, late_count, total_registered)

    ``total_registered`` is the number of distinct students registered for
    the course (from ``course_registrations``). ``present_count`` is the
    number of distinct students who have at least one ``Present`` record in
    the attendance table for that course. ``late_count`` is currently
    reported as zero because the schema does not distinguish late records;
    it can be wired up in future once such data is available.
    """

    # Only include courses that are actually scheduled for the given
    # date (defaults to today).
    if for_date is None:
        for_date = date.today()

    dept_id = _get_current_admin_department_id()
    if dept_id is None:
        return []

    semester_id = get_active_semester_id(create_if_missing=True)
    if semester_id is None:
        semester_id = int(ensure_active_semester()["semester_id"])

    # If this date is explicitly marked as a no-school special day,
    # treat it as having no classes at all so the dashboard shows
    # "No classes scheduled" instead of 100% absent bars.
    try:
        if special_days_db.is_no_school_day(for_date, dept_id):
            return []
    except Exception:
        pass

    day_names = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]
    today_name = day_names[for_date.weekday()]

    with get_cursor(commit=False) as cursor:
        # total registered students per course (only courses scheduled today)
        cursor.execute(
            """
            SELECT c.course_code, COUNT(DISTINCT cr.student_id) AS total_students
            FROM timetable t
            JOIN courses c ON t.course_id = c.course_id
            LEFT JOIN course_registrations cr ON cr.course_id = c.course_id AND cr.semester_id = %s
            WHERE t.day_of_week = %s
                            AND c.department_id = %s
            GROUP BY c.course_code
            ORDER BY c.course_code
            """,
                        (semester_id, today_name, dept_id),
        )
        total_rows = cursor.fetchall()

        # distinct students marked present/late per course
        cursor.execute(
            """
            SELECT c.course_code,
                   COUNT(DISTINCT a.student_id) FILTER (WHERE a.status = 'Present') AS present_count,
                   COUNT(DISTINCT a.student_id) FILTER (WHERE a.status = 'Late') AS late_count
            FROM attendance a
            JOIN timetable t ON a.timetable_id = t.timetable_id
            JOIN courses c ON t.course_id = c.course_id
            WHERE a.status IN ('Present', 'Late')
                AND a.attendance_date = %s
                AND a.semester_id = %s
                AND t.day_of_week = %s
                AND c.department_id = %s
            GROUP BY c.course_code
            """,
            (for_date, semester_id, today_name, dept_id),
        )
        rows = cursor.fetchall()
        pres_map = {r["course_code"]: int(r["present_count"] or 0) for r in rows}
        late_map = {r["course_code"]: int(r["late_count"] or 0) for r in rows}

    result: List[Tuple[str, int, int, int, int]] = []
    for r in total_rows:
        code = r["course_code"]
        total = int(r["total_students"] or 0)
        present = int(pres_map.get(code, 0))
        late = int(late_map.get(code, 0))
        absent = max(total - present - late, 0)
        result.append((code, present, absent, late, total))

    return result


def get_low_attendance_courses(for_date: date | None = None, threshold: float = 75.0) -> List[Tuple[str, float]]:
    """Return courses whose present rate falls below *threshold* percent."""

    breakdown = get_attendance_breakdown_per_course(for_date)
    low: List[Tuple[str, float]] = []
    for course_code, present, absent, late, total in breakdown:
        total = int(total or 0)
        if total <= 0:
            continue
        present_rate = (int(present or 0) / float(total)) * 100.0
        if present_rate < threshold:
            low.append((course_code, round(present_rate, 1)))
    return low
