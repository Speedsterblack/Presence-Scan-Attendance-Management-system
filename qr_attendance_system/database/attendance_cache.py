from __future__ import annotations

import os
import sqlite3
from datetime import date, datetime, time, timedelta
from pathlib import Path
from typing import Any, Optional


CACHE_PATH = Path(
    os.getenv("ATTENDANCE_CACHE_PATH")
    or Path(__file__).with_name("attendance_cache.db")
)
CACHE_DAYS = int(os.getenv("ATTENDANCE_CACHE_DAYS", "7"))


def _connect() -> sqlite3.Connection:
    CACHE_PATH.parent.mkdir(parents=True, exist_ok=True)
    connection = sqlite3.connect(CACHE_PATH)
    connection.row_factory = sqlite3.Row
    connection.execute(
        """
        CREATE TABLE IF NOT EXISTS cached_attendance (
            cache_id INTEGER PRIMARY KEY AUTOINCREMENT,
            timetable_id INTEGER NOT NULL,
            student_id TEXT NOT NULL,
            semester_id INTEGER NOT NULL,
            attendance_date DATE NOT NULL,
            status TEXT NOT NULL,
            synced INTEGER NOT NULL DEFAULT 0,
            created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
            synced_at TIMESTAMP,
            UNIQUE (timetable_id, student_id, semester_id, attendance_date)
        )
        """
    )
    connection.execute(
        """
        CREATE TABLE IF NOT EXISTS cached_courses (
            course_id INTEGER PRIMARY KEY,
            course_code TEXT NOT NULL UNIQUE,
            department_id INTEGER,
            grace_minutes INTEGER NOT NULL DEFAULT 0
        )
        """
    )
    connection.execute(
        """
        CREATE TABLE IF NOT EXISTS cached_timetable (
            timetable_id INTEGER PRIMARY KEY,
            course_id INTEGER NOT NULL,
            day_of_week TEXT NOT NULL,
            start_time TEXT NOT NULL,
            end_time TEXT NOT NULL
        )
        """
    )
    connection.execute(
        "CREATE TABLE IF NOT EXISTS cached_semester (semester_id INTEGER PRIMARY KEY, status TEXT NOT NULL)"
    )
    connection.commit()
    return connection


def refresh_reference_data() -> None:
    """Refresh the local course and timetable snapshot while online."""

    from database.db_config import get_cursor, is_postgres

    if not is_postgres():
        return

    with get_cursor(commit=False) as cursor:
        cursor.execute("SELECT course_id, course_code, department_id, grace_minutes FROM courses")
        courses = cursor.fetchall()
        cursor.execute(
            "SELECT timetable_id, course_id, day_of_week, start_time, end_time FROM timetable"
        )
        timetable = cursor.fetchall()
        cursor.execute("SELECT semester_id, status FROM semesters WHERE status = 'active' LIMIT 1")
        semester = cursor.fetchone()

    connection = _connect()
    try:
        connection.execute("DELETE FROM cached_timetable")
        connection.execute("DELETE FROM cached_courses")
        connection.execute("DELETE FROM cached_semester")
        connection.executemany(
            "INSERT INTO cached_courses (course_id, course_code, department_id, grace_minutes) VALUES (?, ?, ?, ?)",
            [
                (row["course_id"], row["course_code"], row.get("department_id"), row.get("grace_minutes", 0))
                for row in courses
            ],
        )
        if semester:
            connection.execute(
                "INSERT INTO cached_semester (semester_id, status) VALUES (?, ?)",
                (semester["semester_id"], semester["status"]),
            )
        connection.executemany(
            "INSERT INTO cached_timetable (timetable_id, course_id, day_of_week, start_time, end_time) VALUES (?, ?, ?, ?, ?)",
            [
                (row["timetable_id"], row["course_id"], row["day_of_week"], str(row["start_time"]), str(row["end_time"]))
                for row in timetable
            ],
        )
        connection.commit()
    finally:
        connection.close()


def get_offline_session(course_code: str, day_name: str, current_time: time) -> Optional[dict[str, Any]]:
    """Return cached course/session data for an offline attendance scan."""

    connection = _connect()
    try:
        course = connection.execute(
            "SELECT * FROM cached_courses WHERE course_code = ?",
            (course_code,),
        ).fetchone()
        if course is None:
            return None

        rows = connection.execute(
            """
            SELECT * FROM cached_timetable
            WHERE course_id = ? AND day_of_week = ?
            ORDER BY start_time
            """,
            (course["course_id"], day_name),
        ).fetchall()
    finally:
        connection.close()

    for row in rows:
        start = time.fromisoformat(row["start_time"][:8])
        end = time.fromisoformat(row["end_time"][:8])
        if start <= current_time <= end:
            return {
                "course_id": course["course_id"],
                "department_id": course["department_id"],
                "grace_minutes": course["grace_minutes"],
                "timetable_id": row["timetable_id"],
                "start_time": start,
                "end_time": end,
            }
    return None


def get_cached_semester_id() -> Optional[int]:
    connection = _connect()
    try:
        row = connection.execute(
            "SELECT semester_id FROM cached_semester WHERE status = 'active' LIMIT 1"
        ).fetchone()
        return int(row["semester_id"]) if row else None
    finally:
        connection.close()


def has_attendance(timetable_id: int, student_id: str, semester_id: int, attendance_date: date) -> bool:
    connection = _connect()
    try:
        row = connection.execute(
            """
            SELECT 1 FROM cached_attendance
            WHERE timetable_id = ? AND student_id = ? AND semester_id = ? AND attendance_date = ?
            """,
            (timetable_id, student_id, semester_id, attendance_date),
        ).fetchone()
        return row is not None
    finally:
        connection.close()


def store_attendance(
    timetable_id: int,
    student_id: str,
    semester_id: int,
    attendance_date: date,
    status: str,
    *,
    synced: bool,
) -> None:
    """Store a local attendance copy or an unsynced attendance queue item."""

    connection = _connect()
    try:
        connection.execute(
            """
            INSERT INTO cached_attendance
                (timetable_id, student_id, semester_id, attendance_date, status, synced, synced_at)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT (timetable_id, student_id, semester_id, attendance_date)
            DO UPDATE SET status = excluded.status,
                          synced = excluded.synced,
                          synced_at = excluded.synced_at
            """,
            (
                timetable_id,
                student_id,
                semester_id,
                attendance_date,
                status,
                int(synced),
                datetime.now() if synced else None,
            ),
        )
        connection.commit()
    finally:
        connection.close()


def sync_pending() -> int:
    """Retry queued attendance rows against the configured remote database."""

    from database.db_config import is_postgres, get_cursor

    if not is_postgres():
        return 0

    connection = _connect()
    rows = connection.execute(
        "SELECT * FROM cached_attendance WHERE synced = 0 ORDER BY cache_id"
    ).fetchall()
    connection.close()

    synced_count = 0
    for row in rows:
        try:
            with get_cursor() as cursor:
                cursor.execute(
                    """
                    INSERT INTO attendance
                        (timetable_id, student_id, semester_id, status, attendance_date)
                    VALUES (%s, %s, %s, %s, %s)
                    ON CONFLICT (timetable_id, student_id, attendance_date, semester_id)
                    DO NOTHING
                    """,
                    (
                        row["timetable_id"],
                        row["student_id"],
                        row["semester_id"],
                        row["status"],
                        row["attendance_date"],
                    ),
                )
            mark_synced(int(row["cache_id"]))
            synced_count += 1
        except Exception:
            continue
    return synced_count


def mark_synced(cache_id: int) -> None:
    connection = _connect()
    try:
        connection.execute(
            "UPDATE cached_attendance SET synced = 1, synced_at = ? WHERE cache_id = ?",
            (datetime.now(), cache_id),
        )
        connection.commit()
    finally:
        connection.close()


def purge_expired() -> int:
    """Delete only synced local rows older than the configured retention period."""

    cutoff = datetime.now() - timedelta(days=CACHE_DAYS)
    connection = _connect()
    try:
        result = connection.execute(
            "DELETE FROM cached_attendance WHERE synced = 1 AND synced_at < ?",
            (cutoff,),
        )
        connection.commit()
        return result.rowcount
    finally:
        connection.close()


def maintain() -> tuple[int, int]:
    """Retry pending rows and remove expired synced cache rows."""

    try:
        refresh_reference_data()
    except Exception:
        pass
    synced = sync_pending()
    removed = purge_expired()
    return synced, removed