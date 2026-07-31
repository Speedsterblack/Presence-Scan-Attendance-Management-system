from typing import List, Optional, Sequence, Tuple

import re

from database.course_db import (
    add_course as db_add_course,
    update_course as db_update_course,
    delete_course as db_delete_course,
    get_course as db_get_course,
)
from database.timetable_db import (
    add_timetable as db_add_timetable,
    delete_timetable_for_course as db_delete_timetable_for_course,
    get_timetable_for_course as db_get_timetable_for_course,
)
from database.hod_db import get_hod_department
from utils import session


_TIME_RE = re.compile(r"^([01]\d|2[0-3]):[0-5]\d$")


def _clean_time(t: str) -> str:
    """Normalise a time string to HH:MM.

    Accepts either "HH:MM" or "HH:MM:SS" (as often returned by
    PostgreSQL TIME columns) and trims any seconds component before
    validation. Whitespace is also stripped.
    """

    t = (t or "").strip()
    # If the time has seconds (HH:MM:SS), drop the seconds part.
    if t.count(":") == 2:
        hh, mm, _ss = t.split(":", 2)
        t = f"{hh}:{mm}"
    return t


def _normalise_timetable_entries(
    raw_entries: Sequence[Tuple[str, str, str]]
) -> List[Tuple[str, str, str]]:
    """Validate and normalise timetable entries.

    raw_entries is an iterable of (day, start, end) where start/end are
    expected to be HH:MM in 24h format.

    Raises ValueError with a user-friendly message on any problem.
    """

    entries: List[Tuple[str, str, str]] = []
    for day, start, end in raw_entries:
        s = _clean_time(start)
        e = _clean_time(end)
        if not s or not e:
            raise ValueError(f"Start/end times required for {day}")
        if not _TIME_RE.match(s) or not _TIME_RE.match(e):
            raise ValueError(
                f"Invalid time format for {day}. Use HH:MM (24h)"
            )
        entries.append((day, s, e))
    if not entries:
        raise ValueError("Select at least one day")
    return entries


def _to_minutes(t: str) -> int:
    hh, mm = t.split(":", 1)
    return int(hh) * 60 + int(mm)


def compute_total_weekly_minutes(
    entries: Sequence[Tuple[str, str, str]]
) -> int:
    """Return total duration in minutes for all timetable entries.

    Ensures each end is strictly after its start.
    """

    total = 0
    for _day, s, e in entries:
        start_m = _to_minutes(s)
        end_m = _to_minutes(e)
        if end_m <= start_m:
            raise ValueError("End time must be after start time for all days")
        total += end_m - start_m
    return total


def validate_credit_hours_against_timetable(
    credit_hours: int,
    entries: Sequence[Tuple[str, str, str]],
) -> None:
    """Validate credit hours and timetable time ranges.

    Credit hours must be positive. Timetable slots must have end times
    strictly after start times. There is intentionally no requirement
    that weekly timetable duration equals credit hours.
    """

    if credit_hours <= 0:
        raise ValueError("Credit hours must be a positive integer")

    compute_total_weekly_minutes(entries)


def get_current_admin_department_id() -> Optional[int]:
    """Return department_id for the currently logged-in admin, if any."""

    user = getattr(session, "current_user", None)
    if not isinstance(user, dict):
        return None
    if user.get("role") != "admin":
        return None
    admin_id = user.get("id")
    if not admin_id:
        return None
    try:
        return get_hod_department(str(admin_id))
    except Exception:
        return None


def create_course_with_timetable(
    course_code: str,
    course_name: str,
    lecturer_id: str,
    credit_hours: int,
    grace_minutes: int,
    raw_day_entries: Sequence[Tuple[str, str, str]],
) -> None:
    """Create a course and its timetable enforcing business rules.

    - Validates presence of core fields
    - Validates timetable times and format
    - Ensures credit hours are positive
    - Binds the course to the current admin's department when available
    """

    course_code = (course_code or "").strip()
    course_name = (course_name or "").strip()
    lecturer_id = (lecturer_id or "").strip()

    if not all([course_code, course_name, lecturer_id]):
        raise ValueError("All fields are required")

    if grace_minutes < 0:
        raise ValueError("Grace period must be zero or positive minutes")

    entries = _normalise_timetable_entries(raw_day_entries)
    validate_credit_hours_against_timetable(credit_hours, entries)

    department_id = get_current_admin_department_id()

    # Persist course and timetable in a single logical operation.
    # If the course already exists, treat this as an update so that
    # reusing the same course code from the main form replaces
    # previous details and timetable instead of accumulating rows.
    existing = db_get_course(course_code)
    if existing is None:
        db_add_course(
            course_code,
            course_name,
            None,
            credit_hours,
            lecturer_id,
            grace_minutes,
            department_id,
        )
    else:
        db_update_course(
            course_code,
            course_name,
            None,
            credit_hours,
            lecturer_id,
            grace_minutes,
        )

    # Always replace the timetable fully for this course code.
    db_delete_timetable_for_course(course_code)
    for day, start, end in entries:
        db_add_timetable(course_code, day, start, end)


def update_course_with_timetable(
    course_code: str,
    course_name: str,
    lecturer_id: str,
    credit_hours: int,
    grace_minutes: Optional[int],
    raw_day_entries: Sequence[Tuple[str, str, str]],
) -> None:
    """Update a course and completely replace its timetable.

    Applies the same validations as creation. If ``grace_minutes`` is None,
    the previous value is preserved by database.course_db.update_course.
    """

    course_code = (course_code or "").strip()
    course_name = (course_name or "").strip()
    lecturer_id = (lecturer_id or "").strip()

    if not all([course_code, course_name, lecturer_id]):
        raise ValueError("All fields are required")

    if grace_minutes is not None and grace_minutes < 0:
        raise ValueError("Grace period must be zero or positive minutes")

    entries = _normalise_timetable_entries(raw_day_entries)
    validate_credit_hours_against_timetable(credit_hours, entries)

    # Update course core data
    db_update_course(
        course_code,
        course_name,
        None,
        credit_hours,
        lecturer_id,
        grace_minutes,
    )

    # Replace timetable fully
    db_delete_timetable_for_course(course_code)
    for day, start, end in entries:
        db_add_timetable(course_code, day, start, end)


def remove_course(course_code: str) -> None:
    """Delete a course by code.

    Thin service wrapper so UI code does not talk directly to
    database.course_db. Does *not* modify timetable entries; those
    are managed separately (and may be cascaded by the database).
    """

    course_code = (course_code or "").strip()
    if not course_code:
        raise ValueError("Course code is required")
    db_delete_course(course_code)


def clear_timetable_for_course(course_code: str) -> List[Tuple[str, str, str]]:
    """Clear timetable entries for a course and return previous rows.

    Returns a list of (day, start, end) tuples that can be used by
    the caller to implement an undo feature.
    """

    course_code = (course_code or "").strip()
    if not course_code:
        raise ValueError("Course code is required")

    prev_rows = list(db_get_timetable_for_course(course_code))
    db_delete_timetable_for_course(course_code)
    return [(r[0], r[1], r[2]) for r in prev_rows]


def restore_timetable_for_course(
    course_code: str,
    entries: Sequence[Tuple[str, str, str]],
) -> None:
    """Restore timetable entries for a course from (day, start, end)."""

    course_code = (course_code or "").strip()
    if not course_code:
        raise ValueError("Course code is required")

    for day, start, end in entries:
        db_add_timetable(course_code, day, start, end)


def assign_lecturer_to_course(course_code: str, lecturer_id: str) -> None:
    """Assign a lecturer to a course while preserving other fields.

    This reads the existing course so that credit hours and grace
    minutes are not accidentally reset when only the lecturer
    changes.
    """

    course_code = (course_code or "").strip()
    lecturer_id = (lecturer_id or "").strip()
    if not course_code or not lecturer_id:
        raise ValueError("Course code and lecturer ID are required")

    row = db_get_course(course_code)
    if not row:
        raise ValueError("Course not found")

    title = row[1]
    credit_hours = row[4]
    grace_minutes = row[5]

    db_update_course(course_code, title, None, credit_hours, lecturer_id, grace_minutes)
