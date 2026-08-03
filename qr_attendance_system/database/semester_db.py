from __future__ import annotations

from datetime import date
from typing import Any, Optional

from database.db_config import get_cursor
from database.audit_db import log_action



def _row_to_dict(row: Any) -> dict[str, Any]:
    if isinstance(row, dict):
        return row
    return dict(row or {})


def get_active_semester() -> Optional[dict[str, Any]]:
    """Return the currently active semester row, if any."""

    with get_cursor(commit=False) as cursor:
        cursor.execute(
            "SELECT semester_id, semester_name, start_date, end_date, status, created_at, closed_at "
            "FROM semesters "
            "WHERE status = 'active' "
            "ORDER BY start_date DESC, semester_id DESC "
            "LIMIT 1"
        )
        row = cursor.fetchone()

    return _row_to_dict(row) if row else None


def ensure_active_semester(default_name: str = "Semester 1") -> dict[str, Any]:
    """Return the active semester, creating one if necessary."""

    semester = get_active_semester()
    if semester:
        return semester

    with get_cursor() as cursor:
        cursor.execute(
            "INSERT INTO semesters (semester_name, start_date, status) "
            "VALUES (%s, CURRENT_DATE, 'active') "
            "RETURNING semester_id, semester_name, start_date, end_date, status, created_at, closed_at",
            (default_name,),
        )
        row = cursor.fetchone()

    return _row_to_dict(row)


def get_active_semester_id(create_if_missing: bool = True) -> Optional[int]:
    """Return the active semester id, optionally creating one if needed."""

    semester = get_active_semester()
    if semester is None and create_if_missing:
        semester = ensure_active_semester()
    if not semester:
        return None
    return int(semester["semester_id"])


def get_active_semester_label(create_if_missing: bool = True) -> str:
    """Return a human-readable label for the active semester."""

    semester = get_active_semester()
    if semester is None and create_if_missing:
        semester = ensure_active_semester()
    if not semester:
        return "No active semester"

    name = str(semester.get("semester_name") or "Semester")
    start_date = semester.get("start_date")
    if start_date:
        return f"{name} ({start_date})"
    return name


def list_semesters(limit: int = 20) -> list[dict[str, Any]]:
    """Return recent semesters, newest first."""

    with get_cursor(commit=False) as cursor:
        cursor.execute(
            "SELECT semester_id, semester_name, start_date, end_date, status, created_at, closed_at "
            "FROM semesters "
            "ORDER BY start_date DESC, semester_id DESC "
            "LIMIT %s",
            (limit,),
        )
        rows = cursor.fetchall()

    return [_row_to_dict(row) for row in rows]


def close_active_semester(end_date: date | None = None) -> Optional[dict[str, Any]]:
    """Close the current active semester.

    Returns the updated semester row or None if nothing was active.
    """

    with get_cursor() as cursor:
        cursor.execute(
            "UPDATE semesters "
            "SET status = 'closed', end_date = COALESCE(%s, CURRENT_DATE), closed_at = CURRENT_TIMESTAMP "
            "WHERE semester_id = ("
            "    SELECT semester_id FROM semesters WHERE status = 'active' "
            "    ORDER BY start_date DESC, semester_id DESC LIMIT 1"
            ") "
            "RETURNING semester_id, semester_name, start_date, end_date, status, created_at, closed_at",
            (end_date,),
        )
        row = cursor.fetchone()

    if row:
        log_action(
            "close_semester",
            actor_id=None,
            actor_role=None,
            details=f"Closed semester {row['semester_name']} (ID {row['semester_id']}).",
        )

    return _row_to_dict(row) if row else None


def start_new_semester(semester_name: str, start_date: date | None = None) -> dict[str, Any]:
    """Close the active semester if present and create a new active one."""

    close_active_semester(end_date=start_date)
    return create_semester(semester_name, start_date=start_date, active=True)


def create_semester(
    semester_name: str,
    start_date: date | None = None,
    active: bool = True,
) -> dict[str, Any]:
    """Create a semester row and optionally make it the active one."""

    start_date = start_date or date.today()
    status = "active" if active else "closed"
    with get_cursor() as cursor:
        if active:
            cursor.execute(
                "UPDATE semesters SET status = 'closed', end_date = COALESCE(end_date, CURRENT_DATE), closed_at = COALESCE(closed_at, CURRENT_TIMESTAMP) "
                "WHERE status = 'active'"
            )
        cursor.execute(
            "INSERT INTO semesters (semester_name, start_date, status) "
            "VALUES (%s, %s, %s) "
            "RETURNING semester_id, semester_name, start_date, end_date, status, created_at, closed_at",
            (semester_name, start_date, status),
        )
        row = cursor.fetchone()

    if row and active:
        log_action(
            "start_new_semester",
            actor_id=None,
            actor_role=None,
            details=f"Started new active semester {row['semester_name']} (ID {row['semester_id']}).",
        )

    return _row_to_dict(row)


def close_and_start_next_semester(semester_name: str, start_date: date | None = None) -> dict[str, Any]:
    """Close the current semester and create a new active one."""

    close_active_semester(end_date=start_date)
    return create_semester(semester_name, start_date=start_date, active=True)
