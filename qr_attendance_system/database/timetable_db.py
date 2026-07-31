from typing import Any, Dict, List, Optional, Tuple

from datetime import datetime

from database.db_config import get_cursor


# timetable table from db_init.py:
# timetable_id SERIAL PRIMARY KEY,
# course_id INT NOT NULL,
# day_of_week VARCHAR(20) NOT NULL,
# start_time TIME NOT NULL,
# end_time TIME NOT NULL


def add_timetable(course_code: str, day: str, start_time: str, end_time: str) -> None:
    """Add a timetable entry for a course using its course_code."""
    with get_cursor() as cursor:
        cursor.execute("SELECT course_id FROM courses WHERE course_code = %s", (course_code,))
        row = cursor.fetchone()
        if not row:
            raise ValueError(f"No course found with code {course_code}")
        course_id = row["course_id"]

        cursor.execute(
            "INSERT INTO timetable (course_id, day_of_week, start_time, end_time) VALUES (%s, %s, %s, %s)",
            (course_id, day, start_time, end_time),
        )


def get_timetable_for_course(course_code: str) -> List[Tuple[str, str, str]]:
    """Return list of (day_of_week, start_time, end_time) for a course code."""
    with get_cursor(commit=False) as cursor:
        cursor.execute("SELECT course_id FROM courses WHERE course_code = %s", (course_code,))
        row = cursor.fetchone()
        if not row:
            return []
        course_id = row["course_id"]

        cursor.execute(
            "SELECT day_of_week, start_time, end_time FROM timetable WHERE course_id = %s ORDER BY timetable_id",
            (course_id,),
        )
        rows = cursor.fetchall()

    return [(r["day_of_week"], str(r["start_time"]), str(r["end_time"])) for r in rows]


def delete_timetable_for_course(course_code: str) -> None:
    with get_cursor() as cursor:
        cursor.execute("SELECT course_id FROM courses WHERE course_code = %s", (course_code,))
        row = cursor.fetchone()
        if not row:
            return
        course_id = row["course_id"]
        cursor.execute("DELETE FROM timetable WHERE course_id = %s", (course_id,))


def get_current_course() -> Optional[Dict[str, Any]]:
    """Return the current course in session based on day/time, if any.

    The result is a dict compatible with what ScanQRUI expects, containing at
    least: course_code, course_name, lecturer_id, lecturer_name, start_time,
    end_time and timetable_id.
    """

    now = datetime.now()
    # timetable uses short day names like "Mon", "Tue", ...
    day_names = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]
    day_name = day_names[now.weekday()]

    with get_cursor(commit=False) as cursor:
        cursor.execute(
            """
            SELECT t.timetable_id,
                   c.course_code,
                   c.course_title,
                   c.lecturer_id,
                   l.lecturer_name,
                   t.start_time,
                   t.end_time
            FROM timetable t
            JOIN courses c ON t.course_id = c.course_id
            LEFT JOIN lecturers l ON c.lecturer_id = l.lecturer_id
            WHERE t.day_of_week = %s
              AND t.start_time <= %s
              AND t.end_time >= %s
            ORDER BY t.start_time
            LIMIT 1
            """,
            (day_name, now.time(), now.time()),
        )
        row = cursor.fetchone()

    if not row:
        return None

    return {
        "timetable_id": row["timetable_id"],
        "course_code": row["course_code"],
        "course_name": row["course_title"],
        "lecturer_id": row["lecturer_id"],
        "lecturer_name": row.get("lecturer_name") if isinstance(row, dict) else None,
        "start_time": row["start_time"],
        "end_time": row["end_time"],
    }
