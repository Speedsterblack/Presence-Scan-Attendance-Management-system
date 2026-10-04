"""Pull master data from the Head of University over the local LAN."""

from __future__ import annotations

import json
import sqlite3
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


def _head_url() -> str:
    return app_settings.get_head_url().rstrip("/")


def pull_from_head() -> int:
    """Pull missing master rows from the configured Head hub.

    Returns the number of rows added. A missing or unavailable hub is treated
    as an offline condition so the lecturer can still use local data.
    """

    base_url = _head_url()
    if not base_url:
        return 0

    request = Request(f"{base_url}/api/snapshot", headers={"Accept": "application/json"})
    with urlopen(request, timeout=5) as response:
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
        headers={"Content-Type": "application/json", "Accept": "application/json"},
        method="POST",
    )
    with urlopen(request, timeout=5) as response:
        payload: dict[str, Any] = json.loads(response.read().decode("utf-8"))
    return int(payload.get("inserted", 0))
