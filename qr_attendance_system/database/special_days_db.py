from __future__ import annotations

from datetime import date
from typing import List, Tuple, Optional

from database.db_config import get_cursor, is_postgres
from database.hod_db import get_hod_department
from utils import session


_SCHEMA_READY = False


def ensure_special_days_schema() -> None:
    """Upgrade legacy special_days tables to the department-aware schema."""

    global _SCHEMA_READY
    if _SCHEMA_READY:
        return

    with get_cursor() as cursor:
        if is_postgres():
            cursor.execute(
                "SELECT column_name AS name FROM information_schema.columns "
                "WHERE table_schema = current_schema() AND table_name = 'special_days'"
            )
        else:
            cursor.execute("PRAGMA table_info(special_days)")
        columns = {row["name"] for row in cursor.fetchall()}

        legacy_shared_schema = "department_id" not in columns
        if legacy_shared_schema:
            cursor.execute(
                "ALTER TABLE special_days ADD COLUMN department_id INTEGER"
            )
            cursor.execute("UPDATE special_days SET department_id = 1 WHERE department_id IS NULL")

            cursor.execute("SELECT department_id FROM departments ORDER BY department_id")
            department_ids = [int(row["department_id"]) for row in cursor.fetchall()]
            if department_ids:
                cursor.execute(
                    "SELECT day, label, is_no_school FROM special_days WHERE department_id = 1"
                )
                legacy_rows = cursor.fetchall()
                for dept_id in department_ids:
                    if dept_id == 1:
                        continue
                    for row in legacy_rows:
                        cursor.execute(
                            "INSERT INTO special_days (department_id, day, label, is_no_school) "
                            "SELECT %s, %s, %s, %s "
                            "WHERE NOT EXISTS ("
                            "  SELECT 1 FROM special_days existing "
                            "  WHERE existing.department_id = %s AND existing.day = %s"
                            ")",
                            (
                                dept_id,
                                row["day"],
                                row.get("label", ""),
                                bool(row["is_no_school"]),
                                dept_id,
                                row["day"],
                            ),
                        )

        cursor.execute(
            "CREATE UNIQUE INDEX IF NOT EXISTS idx_special_days_department_day "
            "ON special_days(department_id, day)"
        )

    _SCHEMA_READY = True


def get_current_department_id() -> Optional[int]:
    """Return the logged-in admin's department id, if available."""

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


def _resolve_department_id(department_id: Optional[int] = None) -> Optional[int]:
    if department_id is not None:
        try:
            return int(department_id)
        except Exception:
            return None
    return get_current_department_id()


def list_special_days(department_id: Optional[int] = None) -> List[Tuple[date, str, bool]]:
    """Return all special days as (day, label, is_no_school).

    Results are ordered by day ascending.
    """

    ensure_special_days_schema()

    dept_id = _resolve_department_id(department_id)
    if dept_id is None:
        return []

    with get_cursor(commit=False) as cursor:
        cursor.execute(
            "SELECT day, COALESCE(label, '') AS label, is_no_school "
            "FROM special_days WHERE department_id = %s ORDER BY day ASC",
            (dept_id,),
        )
        rows = cursor.fetchall()

    return [
        (r["day"], r["label"], bool(r["is_no_school"])) for r in rows
    ]


def add_special_day(
    day: date,
    label: str = "",
    is_no_school: bool = True,
    department_id: Optional[int] = None,
) -> None:
    """Insert or update a special day definition.

    If the day already exists, its label and flag are updated.
    """

    ensure_special_days_schema()

    dept_id = _resolve_department_id(department_id)
    if dept_id is None:
        raise ValueError("Department ID is required for special day updates")

    with get_cursor() as cursor:
        cursor.execute(
            """
            INSERT INTO special_days (department_id, day, label, is_no_school)
            VALUES (%s, %s, %s, %s)
            ON CONFLICT (department_id, day)
            DO UPDATE SET label = EXCLUDED.label,
                          is_no_school = EXCLUDED.is_no_school
            """,
            (dept_id, day, label, is_no_school),
        )


def delete_special_day(day: date, department_id: Optional[int] = None) -> None:
    """Remove a special day definition for the given date."""

    ensure_special_days_schema()

    dept_id = _resolve_department_id(department_id)
    if dept_id is None:
        raise ValueError("Department ID is required for special day deletion")

    with get_cursor() as cursor:
        cursor.execute(
            "DELETE FROM special_days WHERE department_id = %s AND day = %s",
            (dept_id, day),
        )


def get_special_day(day: date, department_id: Optional[int] = None) -> Optional[Tuple[date, str, bool]]:
    """Return (day, label, is_no_school) for a given date, if any."""

    ensure_special_days_schema()

    dept_id = _resolve_department_id(department_id)
    if dept_id is None:
        return None

    with get_cursor(commit=False) as cursor:
        cursor.execute(
            "SELECT day, COALESCE(label, '') AS label, is_no_school "
            "FROM special_days WHERE department_id = %s AND day = %s",
            (dept_id, day),
        )
        row = cursor.fetchone()

    if not row:
        return None

    return row["day"], row["label"], bool(row["is_no_school"])


def is_no_school_day(day: date, department_id: Optional[int] = None) -> bool:
    """Return True if the given date is marked as a no-school day."""

    info = get_special_day(day, department_id=department_id)
    if not info:
        return False
    _, _, is_no_school = info
    return bool(is_no_school)
