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

BOOTSTRAP_TABLES: tuple[tuple[str, str, tuple[str, ...]], ...] = (
    ("University", "university", ("university_id",)),
    ("departments", "departments", ("department_id",)),
    ("hods", "hods", ("hod_id",)),
    ("lecturers", "lecturers", ("lecturer_id",)),
)


def _configured_university_code() -> str:
    return os.getenv("PRESENCE_SCAN_UNIVERSITY_CODE", "").strip()


def _sync_all_universities() -> bool:
    return os.getenv("PRESENCE_SCAN_ALL_UNIVERSITIES", "").strip().lower() in {
        "1", "true", "yes", "on"
    }


def _local_connection() -> sqlite3.Connection:
    connection = sqlite3.connect(db_config.DB_PATH)
    connection.row_factory = sqlite3.Row
    return connection


def _pull_remote_rows(
    local: sqlite3.Connection,
    remote_cursor: Any,
    tables: tuple[tuple[str, str, tuple[str, ...]], ...] = TABLES,
) -> int:
    """Import remote rows that are absent locally without blocking the app."""

    imported = 0
    for local_table, remote_table, primary_keys in tables:
        try:
            university_code = _configured_university_code()
            if local_table == "University" and not _sync_all_universities():
                if not university_code:
                    continue
                remote_cursor.execute(
                    'SELECT * FROM "university" WHERE university_code = %s',
                    (university_code,),
                )
            elif local_table == "departments" and not _sync_all_universities():
                if not university_code:
                    continue
                remote_cursor.execute(
                    'SELECT d.* FROM "departments" d '
                    'JOIN "university" u ON u.university_id = d.university_id '
                    'WHERE u.university_code = %s',
                    (university_code,),
                )
            elif local_table == "hods":
                if not university_code and not _sync_all_universities():
                    continue
                if _sync_all_universities():
                    remote_cursor.execute('SELECT * FROM "hods"')
                else:
                    remote_cursor.execute(
                        'SELECT h.* FROM "hods" h '
                        'JOIN "departments" d ON d.department_id = h.department_id '
                        'JOIN "university" u ON u.university_id = d.university_id '
                        'WHERE u.university_code = %s',
                        (university_code,),
                    )
            elif local_table == "lecturers":
                if not university_code and not _sync_all_universities():
                    continue
                if _sync_all_universities():
                    remote_cursor.execute('SELECT * FROM "lecturers"')
                else:
                    remote_cursor.execute(
                        'SELECT l.* FROM "lecturers" l '
                        'JOIN "departments" d ON d.department_id = l.department_id '
                        'JOIN "university" u ON u.university_id = d.university_id '
                        'WHERE u.university_code = %s',
                        (university_code,),
                    )
            else:
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
        except Exception:
            # A missing or incompatible table must not block other tables.
            remote_cursor.connection.rollback()
            continue
    local.commit()
    return imported


def _connect_remote() -> Any:
    remote_kwargs: dict[str, Any] = {"cursor_factory": db_config.RealDictCursor}
    if db_config.DATABASE_URL:
        return db_config.psycopg2.connect(db_config.DATABASE_URL, **remote_kwargs)
    return db_config.psycopg2.connect(
        **db_config.DATABASE_PARAMETERS,
        sslmode=os.getenv("DB_SSLMODE", "require"),
        **remote_kwargs,
    )


def sync_credentials_once() -> int:
    """Import remote credentials before the first login window is shown."""

    if not (db_config.DATABASE_URL or db_config._has_database_parameters()):
        return 0
    if db_config.psycopg2 is None or db_config.RealDictCursor is None:
        return 0

    local = _local_connection()
    remote = None
    remote_cursor = None
    try:
        remote = _connect_remote()
        remote_cursor = remote.cursor()
        imported = _pull_remote_rows(local, remote_cursor, BOOTSTRAP_TABLES)
        return imported
    finally:
        if remote_cursor is not None:
            remote_cursor.close()
        local.close()
        if remote is not None:
            remote.close()


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
        remote = _connect_remote()

        remote_cursor = remote.cursor()
        synced_rows = _pull_remote_rows(local, remote_cursor)
        for local_table, remote_table, primary_keys in TABLES:
            if local_table in {"hods", "lecturers"}:
                university_code = _configured_university_code()
                if not university_code and not _sync_all_universities():
                    continue
                if _sync_all_universities():
                    rows = local.execute(f'SELECT * FROM "{local_table}"').fetchall()
                else:
                    rows = local.execute(
                        f'SELECT source.* FROM "{local_table}" source '
                        'JOIN "departments" d ON d.department_id = source.department_id '
                        'JOIN "University" u ON u.university_id = d.university_id '
                        'WHERE u.university_code = ?',
                        (university_code,),
                    ).fetchall()
            else:
                rows = local.execute(f'SELECT * FROM "{local_table}"').fetchall()
            if not rows:
                continue
            columns = list(rows[0].keys())
            remote_columns = [
                "department" if local_table == "students" and column == "Department" else column
                for column in columns
            ]
            column_sql = ", ".join(f'"{column}"' for column in remote_columns)
            placeholders = ", ".join(["%s"] * len(columns))
            conflict_sql = ", ".join(f'"{key}"' for key in primary_keys)
            update_columns = [column for column in remote_columns if column not in primary_keys]
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