from __future__ import annotations

from typing import Any

from database.db_config import get_cursor


def get_student_transcript(student_id: str) -> list[dict[str, Any]]:
    """Return semester/course history for a student across all semesters."""

    with get_cursor(commit=False) as cursor:
        cursor.execute(
            "SELECT sem.semester_id, sem.semester_name, sem.status AS semester_status, "
            "       c.course_code, c.course_title, "
            "       COUNT(DISTINCT a.attendance_date) FILTER (WHERE a.status = 'Present') AS present_count, "
            "       COUNT(DISTINCT a.attendance_date) FILTER (WHERE a.status = 'Late') AS late_count, "
            "       COUNT(DISTINCT a.attendance_date) AS attendance_count "
            "FROM course_registrations cr "
            "JOIN semesters sem ON sem.semester_id = cr.semester_id "
            "JOIN courses c ON c.course_id = cr.course_id "
            "LEFT JOIN attendance a ON a.student_id = cr.student_id "
            "  AND a.semester_id = cr.semester_id "
            "  AND a.timetable_id IN (SELECT t.timetable_id FROM timetable t WHERE t.course_id = c.course_id) "
            "WHERE cr.student_id = %s "
            "GROUP BY sem.semester_id, sem.semester_name, sem.status, c.course_code, c.course_title "
            "ORDER BY sem.start_date DESC, c.course_code ASC",
            (student_id,),
        )
        rows = cursor.fetchall()

    return [dict(row) if isinstance(row, dict) else dict(row or {}) for row in rows]
