from __future__ import annotations

import os
import threading
from typing import Any

import sqlite3

from database import db_config


SYNC_INTERVAL_SECONDS = float(os.getenv("SYNC_INTERVAL_SECONDS", "5"))
_stop_event = threading.Event()
_sync_thread: threading.Thread | None = None

# Parent tables come before child tables so PostgreSQL foreign keys remain valid.
TABLES: tuple[tuple[str, str, tuple[str, ...]], ...] = (
    # PostgreSQL folds the unquoted schema table name University to lowercase.
    ("University", "university", ("university_id",)),
    ("departments", "departments", ("department_id",)),
    ("semesters", "semesters", ("semester_id",)),
    ("hods", "hods", ("hod_id",)),
    ("lecturers", "lecturers", ("lecturer_id",)),
    ("students", "students", ("student_id",)),
    ("courses", "courses", ("course_id",)),
    ("course_registrations", "course_registrations", ("student_id", "course_id", "semester_id")),
    ("timetable", "timetable", ("timetable_id",)),
    ("attendance", "attendance", ("attendance_id",)),
    ("special_days", "special_days", ("special_day_id",)),
    ("audit_log", "audit_log", ("audit_id",)),
)


def _local_connection() -> sqlite3.Connection:
    connection = sqlite3.connect(db_config.DB_PATH)
    connection.row_factory = sqlite3.Row
    return connection


def _pull_remote_rows(
    local: sqlite3.Connection,
    remote_cursor: Any,
) -> int:
    """Import remote rows that are absent locally without blocking the app."""

    imported = 0
    for local_table, remote_table, primary_keys in TABLES:
        remote_cursor.execute(f'SELECT * FROM "{remote_table}"')
        remote_rows = remote_cursor.fetchall()
        for row in remote_rows:
            columns = list(row.keys())
            key_values = tuple(row[key] for key in primary_keys)
            where_sql = " AND ".join(f'"{key}" = ?' for key in primary_keys)
            exists = local.execute(
                f'SELECT 1 FROM "{local_table}" WHERE {where_sql} LIMIT 1',
                key_values,
            ).fetchone()
            if exists:
                continue
            column_sql = ", ".join(f'"{column}"' for column in columns)
            placeholders = ", ".join("?" for _ in columns)
            local.execute(
                f'INSERT OR IGNORE INTO "{local_table}" ({column_sql}) VALUES ({placeholders})',
                tuple(row[column] for column in columns),
            )
            imported += 1
    local.commit()
    return imported


def sync_once() -> int:
    """Mirror local rows to PostgreSQL; failures are retried next cycle."""

    if not (db_config.DATABASE_URL or db_config._has_database_parameters()):
        return 0
    if db_config.psycopg2 is None or db_config.RealDictCursor is None:
        return 0

    local = _local_connection()
    remote = None
    synced_rows = 0
    try:
        remote_kwargs: dict[str, Any] = {"cursor_factory": db_config.RealDictCursor}
        if db_config.DATABASE_URL:
            remote = db_config.psycopg2.connect(db_config.DATABASE_URL, **remote_kwargs)
        else:
            remote = db_config.psycopg2.connect(
                **db_config.DATABASE_PARAMETERS,
                sslmode=os.getenv("DB_SSLMODE", "require"),
                **remote_kwargs,
            )

        remote_cursor = remote.cursor()
        synced_rows = _pull_remote_rows(local, remote_cursor)
        for local_table, remote_table, primary_keys in TABLES:
            rows = local.execute(f'SELECT * FROM "{local_table}"').fetchall()
            if not rows:
                continue
            columns = rows[0].keys()
            column_sql = ", ".join(f'"{column}"' for column in columns)
            placeholders = ", ".join(["%s"] * len(columns))
            conflict_sql = ", ".join(f'"{key}"' for key in primary_keys)
            update_columns = [column for column in columns if column not in primary_keys]
            if update_columns:
                update_sql = ", ".join(
                    f'"{column}" = EXCLUDED."{column}"' for column in update_columns
                )
                conflict_action = f"DO UPDATE SET {update_sql}"
            else:
                conflict_action = "DO NOTHING"
            statement = (
                f'INSERT INTO "{remote_table}" ({column_sql}) VALUES ({placeholders}) '
                f"ON CONFLICT ({conflict_sql}) {conflict_action}"
            )
            for row in rows:
                remote_cursor.execute(statement, tuple(row[column] for column in columns))
                synced_rows += 1
        remote.commit()
        remote_cursor.close()
        return synced_rows
    finally:
        local.close()
        if remote is not None:
            remote.close()


def _worker() -> None:
    try:
        sync_once()
    except Exception:
        pass
    while not _stop_event.wait(SYNC_INTERVAL_SECONDS):
        try:
            sync_once()
        except Exception:
            # Network outages must never affect the local application.
            continue


def start() -> None:
    global _sync_thread
    if _sync_thread is not None and _sync_thread.is_alive():
        return
    _stop_event.clear()
    _sync_thread = threading.Thread(target=_worker, name="supabase-passive-sync", daemon=True)
    _sync_thread.start()


def stop() -> None:
    _stop_event.set()