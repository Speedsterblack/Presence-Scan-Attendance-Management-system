"""Pull master data from the Head of University over the local LAN."""

from __future__ import annotations

import json
import sqlite3
import ssl
from typing import Any
from urllib.request import Request, urlopen

from database import db_config
from config import settings as app_settings


SYNC_TABLES = (
    "University",
    "departments",
    "semesters",
    "hods",
    "lecturers",
    "students",
    "courses",
    "course_registrations",
    "timetable",
    "special_days",
)

SYNC_KEYS = {
    "University": ("university_id",),
    "departments": ("department_id",),
    "semesters": ("semester_id",),
    "hods": ("department_id",),
    "lecturers": ("lecturer_id",),
    "students": ("student_id",),
    "courses": ("course_id",),
    "course_registrations": ("student_id", "course_id", "semester_id"),
    "timetable": ("timetable_id",),
    "special_days": ("special_day_id",),
}


def _head_url() -> str:
    return app_settings.get_head_url().rstrip("/")


def _head_headers() -> dict[str, str]:
    token = app_settings.get_head_token()
    return {"Accept": "application/json", "Authorization": f"Bearer {token}"}


def _open(request: Request):
    if request.full_url.startswith("https://"):
        return urlopen(request, timeout=5, context=ssl._create_unverified_context())
    return urlopen(request, timeout=5)


def pull_from_head() -> int:
    """Pull missing master rows from the configured Head hub.

    Returns the number of rows added. A missing or unavailable hub is treated
    as an offline condition so the lecturer can still use local data.
    """

    base_url = _head_url()
    if not base_url:
        return 0

    request = Request(f"{base_url}/api/snapshot", headers=_head_headers())
    with _open(request) as response:
        payload: dict[str, Any] = json.loads(response.read().decode("utf-8"))

    tables = payload.get("tables")
    if not isinstance(tables, dict):
        raise RuntimeError("Head hub returned an invalid snapshot")

    connection = sqlite3.connect(db_config.DB_PATH)
    added = 0
    try:
        connection.execute("PRAGMA foreign_keys = ON")
        for table in SYNC_TABLES:
            rows = tables.get(table, [])
            if not isinstance(rows, list):
                continue
            for row in rows:
                if not isinstance(row, dict) or not row:
                    continue
                columns = list(row)
                column_sql = ", ".join(f'"{column}"' for column in columns)
                placeholders = ", ".join("?" for _ in columns)
                keys = SYNC_KEYS[table]
                update_columns = [column for column in columns if column not in keys]
                where_sql = " AND ".join(f'"{key}" = ?' for key in keys)
                if update_columns:
                    update_sql = ", ".join(f'"{column}" = ?' for column in update_columns)
                    cursor = connection.execute(
                        f'UPDATE "{table}" SET {update_sql} WHERE {where_sql}',
                        tuple(row[column] for column in update_columns)
                        + tuple(row[key] for key in keys),
                    )
                    if cursor.rowcount:
                        continue
                cursor = connection.execute(
                    f'INSERT OR IGNORE INTO "{table}" ({column_sql}) VALUES ({placeholders})',
                    tuple(row[column] for column in columns),
                )
                added += cursor.rowcount
        connection.commit()
        return added
    finally:
        connection.close()


def push_local_attendance() -> int:
    """Upload local attendance rows to the Head hub over the LAN."""

    base_url = _head_url()
    if not base_url:
        return 0

    connection = sqlite3.connect(db_config.DB_PATH)
    connection.row_factory = sqlite3.Row
    try:
        rows = [dict(row) for row in connection.execute('SELECT * FROM "attendance"')]
    finally:
        connection.close()

    encoded_rows = json.dumps(
        {"rows": [{key: str(value) if value is not None else None for key, value in row.items()} for row in rows]}
    ).encode("utf-8")
    request = Request(
        f"{base_url}/api/attendance",
        data=encoded_rows,
        headers={
            **_head_headers(),
            "Content-Type": "application/json",
        },
        method="POST",
    )
    with _open(request) as response:
        payload: dict[str, Any] = json.loads(response.read().decode("utf-8"))
    return int(payload.get("inserted", 0))
