from typing import List, Tuple

from datetime import datetime, timedelta, date

from database.db_config import get_cursor
from database.semester_db import get_active_semester_id, ensure_active_semester
from database import special_days_db
from database import attendance_cache


# attendance table from db_init.py:
# attendance_id SERIAL PRIMARY KEY,
# timetable_id INT NOT NULL,
# student_id VARCHAR(20) NOT NULL,
# status VARCHAR(10) CHECK (status IN ('Present', 'Absent')) NOT NULL,
# UNIQUE (timetable_id, student_id)

def get_attendance_by_course(course_code: str, for_date: date | None = None) -> List[Tuple[str, str, str, str]]:
    """Return registered students and their attendance status for a course.

    Students without a record for the given date are returned as ``Absent``.
    """

    if for_date is None:
        for_date = date.today()

    try:
        semester_id = get_active_semester_id(create_if_missing=True)
        if semester_id is None:
            semester_id = int(ensure_active_semester()["semester_id"])
    except Exception:
        semester_id = attendance_cache.get_cached_semester_id()
        if semester_id is None:
            return []

    with get_cursor(commit=False) as cursor:
        cursor.execute(
            "SELECT s.student_id, s.student_name, c.course_code,\n"
            "       CASE MAX(CASE WHEN a.status = 'Present' THEN 2\n"
            "                     WHEN a.status = 'Late' THEN 1\n"
            "                     ELSE 0 END)\n"
            "         WHEN 2 THEN 'Present'\n"
            "         WHEN 1 THEN 'Late'\n"
            "         ELSE 'Absent' END AS status\n"
            "FROM course_registrations cr\n"
            "JOIN students s ON cr.student_id = s.student_id\n"
            "JOIN courses c ON cr.course_id = c.course_id\n"
            "LEFT JOIN attendance a\n"
            "  ON a.student_id = s.student_id\n"
            " AND a.attendance_date = %s\n"
            " AND a.semester_id = %s\n"
            " AND EXISTS (\n"
            "     SELECT 1 FROM timetable t\n"
            "     WHERE t.timetable_id = a.timetable_id\n"
            "       AND t.course_id = c.course_id\n"
            " )\n"
            "WHERE c.course_code = %s\n"
            "  AND cr.semester_id = %s\n"
            "GROUP BY s.student_id, s.student_name, c.course_code\n"
            "ORDER BY s.student_id",
            (for_date, semester_id, course_code, semester_id),
        )
        rows = cursor.fetchall()

    return [
        (r["student_id"], r["student_name"], r["course_code"], r["status"]) for r in rows
    ]


def mark_attendance(student_id: str, course_code: str):
    """Mark a student as present for the current session of a course.

    Returns either True on success, or ``(False, message)`` on failure.
    When a scan happens after the grace period but before the session ends,
    the record is stored as ``Late`` and the function returns ``(True, 'Late')``.
    """

    now = datetime.now()
    today = now.date()
    try:
        semester_id = get_active_semester_id(create_if_missing=True)
        if semester_id is None:
            semester_id = int(ensure_active_semester()["semester_id"])
    except Exception:
        semester_id = attendance_cache.get_cached_semester_id()
        if semester_id is None:
            return False, "The database is unavailable and no active semester is cached locally."

    # Block attendance entirely on no-school special days (for
    # example, holidays or institutional events). This keeps the
    # database free of records for days where the school is fully
    # closed.
    day_names = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]
    day_name = day_names[now.weekday()]

    offline_session = None
    try:
        with get_cursor() as cursor:
            cursor.execute(
                "SELECT course_id, grace_minutes, department_id FROM courses WHERE course_code = %s",
                (course_code,),
            )
            row = cursor.fetchone()
        if not row:
            raise ValueError(f"No course found with code {course_code}")
        course_id = row["course_id"]
        grace_minutes = int(row.get("grace_minutes", 0)) if hasattr(row, "get") else int(row[1])
        course_department_id = row.get("department_id") if hasattr(row, "get") else None
    except Exception:
        offline_session = attendance_cache.get_offline_session(course_code, day_names[now.weekday()], now.time())
        if offline_session is None:
            return False, "The database is unavailable and this course is not cached locally."
        course_id = offline_session["course_id"]
        grace_minutes = int(offline_session["grace_minutes"] or 0)
        course_department_id = offline_session["department_id"]

    # Block attendance entirely on no-school special days for the
    # course's department.
    try:
        if course_department_id is not None and special_days_db.is_no_school_day(today, int(course_department_id)):
            return False, "No class is active right now because today is a no-school day for this department."
    except Exception:
        # If anything goes wrong while checking special days,
        # fall back to normal behaviour instead of crashing.
        pass

    if offline_session is not None:
        timetable_id = offline_session["timetable_id"]
        start_time = offline_session["start_time"]
        end_time = offline_session["end_time"]
        if attendance_cache.has_attendance(timetable_id, student_id, semester_id, today):
            remaining = max(timedelta(0), datetime.combine(today, end_time) - now)
            return False, f"Attendance already recorded for this session. {remaining} remaining in class."
        start_dt = datetime.combine(today, start_time)
        end_dt = datetime.combine(today, end_time)
        cutoff_dt = min(end_dt, start_dt + timedelta(minutes=grace_minutes))
        status = "Late" if now > cutoff_dt else "Present"
        attendance_cache.store_attendance(
            timetable_id, student_id, semester_id, today, status, synced=False
        )
        return True, "Attendance saved locally and will sync when the connection returns."

    with get_cursor() as cursor:
        # find the timetable entry for this course that is currently in session
        cursor.execute(
            """
            SELECT timetable_id, start_time, end_time
            FROM timetable
            WHERE course_id = %s
              AND day_of_week = %s
              AND start_time <= %s
              AND end_time >= %s
            ORDER BY start_time
            LIMIT 1
            """,
            (course_id, day_name, now.time(), now.time()),
        )
        trow = cursor.fetchone()
        if not trow:
            # no active timetable slot; treat as failure
            return False, "No class is active for this course right now."

        timetable_id = trow["timetable_id"]
        start_time = trow["start_time"]
        end_time = trow["end_time"]

        # apply grace period: allow attendance only up to start_time + grace_minutes
        start_dt = datetime.combine(now.date(), start_time)
        end_dt = datetime.combine(now.date(), end_time)
        cutoff_dt = min(end_dt, start_dt + timedelta(minutes=grace_minutes))
        if now > end_dt:
            # too late for this slot
            return False, "This class session has already ended."

        status = "Late" if now > cutoff_dt else "Present"

        # check if already marked
        cursor.execute(
            "SELECT attendance_id FROM attendance\n"
            " WHERE timetable_id = %s\n"
            "   AND student_id = %s\n"
            "   AND attendance_date = CURRENT_DATE\n"
            "   AND semester_id = %s",
            (timetable_id, student_id, semester_id),
        )
        already = cursor.fetchone()
        if already:
            # compute remaining time until the end of the slot for UI messaging
            end_dt = datetime.combine(now.date(), end_time)
            remaining = max(timedelta(0), end_dt - now)
            return False, f"Attendance already recorded for this session. {remaining} remaining in class."

        # insert attendance as Present
        try:
            cursor.execute(
                "INSERT INTO attendance (timetable_id, student_id, semester_id, status, attendance_date)\n"
                "VALUES (%s, %s, %s, %s, CURRENT_DATE)",
                (timetable_id, student_id, semester_id, status),
            )
        except Exception:
            attendance_cache.store_attendance(
                timetable_id,
                student_id,
                semester_id,
                today,
                status,
                synced=False,
            )
            return True, "Attendance saved locally and will sync when the connection returns."

    attendance_cache.store_attendance(
        timetable_id,
        student_id,
        semester_id,
        today,
        status,
        synced=True,
    )

    # After inserting attendance, check whether the semester should be closed.
    try:
        # Import here to avoid circular imports at module import time
        from database.student_attendance_db import _count_observed_sessions
        from database.semester_db import get_active_semester, close_active_semester
        from config.settings import get_semester_weeks
        import math

        # sessions per week for this course
        with get_cursor(commit=False) as _c:
            _c.execute(
                """
                SELECT COUNT(*) AS sessions_per_week
                FROM timetable t
                JOIN courses c ON t.course_id = c.course_id
                WHERE c.course_code = %s
                """,
                (course_code,),
            )
            tw = _c.fetchone() or {}
            sessions_per_week = int(tw.get("sessions_per_week") or 0)

        # determine semester weeks: prefer explicit semester end_date when available
        sem = get_active_semester()
        if sem:
            start = sem.get("start_date")
            end = sem.get("end_date")
            if start and end:
                # compute inclusive number of weeks between start and end
                days = (end - start).days
                sem_weeks = max(0, math.ceil(days / 7.0))
            else:
                # fallback to configured semester weeks
                try:
                    sem_weeks = int(get_semester_weeks())
                except Exception:
                    sem_weeks = 15
        else:
            try:
                sem_weeks = int(get_semester_weeks())
            except Exception:
                sem_weeks = 15

        expected_total = sessions_per_week * max(0, sem_weeks)

        # count observed sessions for this course in this semester
        try:
            observed = _count_observed_sessions(course_code, course_department_id, int(semester_id))
        except Exception:
            observed = 0

        # If observed sessions equals the expected sessions for the semester,
        # close the active semester. Use strict equality per requirements.
        if expected_total > 0 and observed == expected_total:
            try:
                # record an audit entry for the auto-close then close semester
                try:
                    from database.audit_db import log_action
                    log_action("auto_close_semester", None, None,
                               f"Auto-closed semester after reaching expected sessions ({expected_total}) for course {course_code}.")
                except Exception:
                    pass

                close_active_semester()
            except Exception:
                # Do not let failure to close the semester break attendance marking.
                pass
    except Exception:
        # Best-effort: failures here should not prevent successful attendance marking.
        pass

    return (True, status) if status == "Late" else True
