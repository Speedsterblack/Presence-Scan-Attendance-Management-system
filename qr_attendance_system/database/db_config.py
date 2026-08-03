import os
import re
import sqlite3
from datetime import date, datetime, time
from pathlib import Path
from typing import Optional


DB_PATH = Path(
    os.getenv("DATABASE_PATH")
    or Path(__file__).with_name("presence_scan.db")
)


def _register_sqlite_adapters() -> None:
    sqlite3.register_adapter(date, lambda value: value.isoformat())
    sqlite3.register_adapter(datetime, lambda value: value.isoformat(sep=" "))
    sqlite3.register_adapter(time, lambda value: value.strftime("%H:%M:%S"))

    sqlite3.register_converter("DATE", lambda value: date.fromisoformat(value.decode()))
    sqlite3.register_converter(
        "TIMESTAMP",
        lambda value: datetime.fromisoformat(value.decode().replace("Z", "+00:00")),
    )
    sqlite3.register_converter(
        "TIME",
        lambda value: datetime.strptime(value.decode(), "%H:%M:%S").time(),
    )


_register_sqlite_adapters()


def init_db_pool(dsn: Optional[str] = None) -> None:
    """Prepare the local sqlite database file used by the app."""

    # ``dsn`` is accepted for compatibility with older launchers, but the app
    # now uses a local sqlite database by default.
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    if not DB_PATH.exists():
        DB_PATH.touch()


def _connect() -> sqlite3.Connection:
    init_db_pool()
    conn = sqlite3.connect(
        DB_PATH,
        detect_types=sqlite3.PARSE_DECLTYPES | sqlite3.PARSE_COLNAMES,
    )
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def get_connection():
    """Open a new connection to the local sqlite database."""

    return _connect()


def release_connection(conn) -> None:
    """Close a sqlite connection obtained from get_connection()."""

    if conn is not None:
        conn.close()


def close_pool() -> None:
    """Compatibility no-op for the old pooled connection API."""

    return None


class _SQLiteRow(dict):
    def __getitem__(self, key):
        if isinstance(key, int):
            return list(self.values())[key]
        return super().__getitem__(key)


def _convert_placeholders(sql: str) -> str:
    return re.sub(r"%s", "?", sql)


class SQLiteCursorContext:
    """Context manager that yields a sqlite cursor with dict-like rows."""

    def __init__(self, commit: bool = True):
        self._commit = commit
        self._conn = None
        self._cur = None

    def __enter__(self):
        self._conn = _connect()
        self._cur = self._conn.cursor()
        return self

    def __exit__(self, exc_type, exc, tb):
        try:
            if self._conn is not None:
                if exc_type is None and self._commit:
                    self._conn.commit()
                else:
                    self._conn.rollback()
        finally:
            try:
                if self._cur is not None:
                    self._cur.close()
            finally:
                if self._conn is not None:
                    self._conn.close()

    def execute(self, sql, params=()):
        assert self._cur is not None
        return self._cur.execute(_convert_placeholders(sql), params)

    def executemany(self, sql, seq_of_params):
        assert self._cur is not None
        return self._cur.executemany(_convert_placeholders(sql), seq_of_params)

    def fetchone(self):
        assert self._cur is not None
        row = self._cur.fetchone()
        return _SQLiteRow(dict(row)) if row is not None else None

    def fetchall(self):
        assert self._cur is not None
        return [_SQLiteRow(dict(row)) for row in self._cur.fetchall()]

    @property
    def lastrowid(self):
        assert self._cur is not None
        return self._cur.lastrowid

    def close(self) -> None:
        if self._cur is not None:
            self._cur.close()

def get_cursor(commit: bool = True) -> SQLiteCursorContext:
    """Return a context manager that yields a sqlite cursor.

    Usage remains::

        with get_cursor() as cursor:
            cursor.execute(...)
    """

    return SQLiteCursorContext(commit)

