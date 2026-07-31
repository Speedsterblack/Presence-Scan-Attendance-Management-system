from __future__ import annotations

from typing import Any, Optional

from database.db_config import get_cursor
from database.semester_db import get_active_semester_id, get_active_semester, ensure_active_semester
from database.audit_db import log_action
from utils import session


def get_latest_closed_semester() -> Optional[dict[str, Any]]:
    """Return the most recent closed semester."""

    with get_cursor(commit=False) as cursor:
        cursor.execute(
            "SELECT semester_id, semester_name, start_date, end_date, status, created_at, closed_at "
            "FROM semesters WHERE status = 'closed' "
            "ORDER BY COALESCE(end_date, start_date) DESC, semester_id DESC LIMIT 1"
        )
        row = cursor.fetchone()
    return dict(row) if row else None


def copy_latest_closed_semester_registrations_to_active() -> int:
    """Copy all course registrations from the latest closed semester into the active semester.

    Returns the number of rows inserted.
    """

    active_semester_id = get_active_semester_id(create_if_missing=True)
    if active_semester_id is None:
        active_semester_id = int(ensure_active_semester()["semester_id"])

    previous = get_latest_closed_semester()
    if not previous:
        return 0

    source_semester_id = int(previous["semester_id"])
    if source_semester_id == active_semester_id:
        return 0

    inserted = 0
    with get_cursor() as cursor:
        cursor.execute(
            "INSERT INTO course_registrations (student_id, course_id, semester_id) "
            "SELECT student_id, course_id, %s FROM course_registrations "
            "WHERE semester_id = %s "
            "ON CONFLICT (student_id, course_id, semester_id) DO NOTHING",
            (active_semester_id, source_semester_id),
        )
        inserted = cursor.rowcount or 0

    try:
        user = getattr(session, "current_user", None)
    except Exception:
        user = None
    actor_id = user.get("id") if isinstance(user, dict) else None
    actor_role = user.get("role") if isinstance(user, dict) else None
    log_action(
        "copy_previous_semester_registrations",
        actor_id=str(actor_id) if actor_id else None,
        actor_role=str(actor_role) if actor_role else None,
        details=f"Copied registrations from semester {source_semester_id} to active semester {active_semester_id}.",
    )
    return int(inserted)


def copy_previous_semester_registrations_to_active() -> int:
    """Alias used by the UI."""

    return copy_latest_closed_semester_registrations_to_active()
