import os
import re
import sqlite3
import sys
from datetime import date, datetime, time
from pathlib import Path
from typing import Any, Optional, Protocol

try:
    import psycopg2
    from psycopg2.extras import RealDictCursor
except ImportError:
    psycopg2 = None
    RealDictCursor = None


def _default_database_path() -> Path:
    """Return a writable database path for the current application."""

    if getattr(sys, "frozen", False):
        app_data = os.getenv("LOCALAPPDATA") or os.getenv("APPDATA")
        if app_data:
            application_name = (
                "Presence Scan Developer"
                if Path(sys.executable).stem.lower().startswith("developer")
                else "Presence Scan"
            )
            return Path(app_data) / application_name / "data" / "presence_scan.db"
    return Path(__file__).with_name("presence_scan.db")


DB_PATH = Path(os.getenv("DATABASE_PATH") or _default_database_path())
DATABASE_URL = os.getenv("DATABASE_URL", "").strip()
# Local SQLite is the responsive working copy whenever remote credentials exist.
LOCAL_PRIMARY = os.getenv("LOCAL_PRIMARY", "1").strip().lower() in {"1", "true", "yes", "on"}
DATABASE_PARAMETERS = {
    "host": os.getenv("DB_HOST") or os.getenv("DATABASE_HOST"),
    "port": os.getenv("DB_PORT") or os.getenv("DATABASE_PORT", "5432"),
    "dbname": os.getenv("DB_NAME") or os.getenv("DATABASE_NAME"),
    "user": os.getenv("DB_USER") or os.getenv("DATABASE_USER"),
    "password": os.getenv("DB_PASSWORD") or os.getenv("DATABASE_PASSWORD"),
}


def _has_database_parameters() -> bool:
    return bool(
        DATABASE_PARAMETERS["host"]
        and DATABASE_PARAMETERS["dbname"]
        and DATABASE_PARAMETERS["user"]
        and DATABASE_PARAMETERS["password"]
    )


class DatabaseConnection(Protocol):
    """Common connection operations used by both database backends."""

    def cursor(self) -> Any: ...
    def commit(self) -> Any: ...
    def rollback(self) -> Any: ...
    def close(self) -> Any: ...


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
        lambda value: datetime.strptime(
            value.decode(), "%H:%M:%S" if value.decode().count(":") == 2 else "%H:%M"
        ).time(),
    )


_register_sqlite_adapters()


def init_db_pool(dsn: Optional[str] = None) -> None:
    """Prepare the configured database backend."""

    global DATABASE_URL
    if dsn:
        DATABASE_URL = dsn.strip()
    if (DATABASE_URL or _has_database_parameters()) and not LOCAL_PRIMARY:
        if psycopg2 is None:
            raise RuntimeError("DATABASE_URL is set but psycopg2-binary is not installed")
        return

    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    if not DB_PATH.exists():
        DB_PATH.touch()


def _connect() -> DatabaseConnection:
    init_db_pool()
    if DATABASE_URL and not LOCAL_PRIMARY:
        assert psycopg2 is not None
        assert RealDictCursor is not None
        return psycopg2.connect(DATABASE_URL, cursor_factory=RealDictCursor)
    if _has_database_parameters() and not LOCAL_PRIMARY:
        assert psycopg2 is not None
        assert RealDictCursor is not None
        return psycopg2.connect(
            **DATABASE_PARAMETERS,
            sslmode=os.getenv("DB_SSLMODE", "require"),
            cursor_factory=RealDictCursor,
        )

    conn = sqlite3.connect(
        DB_PATH,
        detect_types=sqlite3.PARSE_DECLTYPES | sqlite3.PARSE_COLNAMES,
    )
    conn.row_factory = sqlite3.Row
    if not is_postgres():
        conn.execute("PRAGMA foreign_keys = ON")
    return conn


def _connect_local() -> sqlite3.Connection:
    init_db_pool()
    conn = sqlite3.connect(
        DB_PATH,
        detect_types=sqlite3.PARSE_DECLTYPES | sqlite3.PARSE_COLNAMES,
    )
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def get_connection() -> DatabaseConnection:
    """Open a connection to PostgreSQL or the local SQLite fallback."""

    return _connect()


def release_connection(conn: DatabaseConnection) -> None:
    """Close a connection obtained from get_connection()."""

    if conn is not None:
        conn.close()


def close_pool() -> None:
    """Compatibility no-op for the old pooled connection API."""

    return None


def is_postgres() -> bool:
    return bool((DATABASE_URL or _has_database_parameters()) and not LOCAL_PRIMARY)


class _SQLiteRow(dict):
    def __getitem__(self, key):
        if isinstance(key, int):
            return list(self.values())[key]
        return super().__getitem__(key)


def _convert_placeholders(sql: str) -> str:
    return re.sub(r"%s", "?", sql)


class SQLiteCursorContext:
    """Context manager that yields a cursor with dict-like rows."""

    def __init__(self, commit: bool = True, local: bool = False):
        self._commit = commit
        self._local = local
        self._conn = None
        self._cur = None

    def __enter__(self):
        self._conn = _connect_local() if self._local else _connect()
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
        if is_postgres():
            return self._cur.execute(sql, params)
        return self._cur.execute(_convert_placeholders(sql), params)

    def executemany(self, sql, seq_of_params):
        assert self._cur is not None
        if is_postgres():
            return self._cur.executemany(sql, seq_of_params)
        return self._cur.executemany(_convert_placeholders(sql), seq_of_params)

    def fetchone(self):
        assert self._cur is not None
        row = self._cur.fetchone()
        if is_postgres():
            return row
        return _SQLiteRow(dict(row)) if row is not None else None

    def fetchall(self):
        assert self._cur is not None
        if is_postgres():
            return self._cur.fetchall()
        return [_SQLiteRow(dict(row)) for row in self._cur.fetchall()]

    @property
    def lastrowid(self):
        assert self._cur is not None
        if is_postgres():
            return None
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


def get_local_cursor(commit: bool = True) -> SQLiteCursorContext:
    """Return a cursor backed by the local SQLite database."""

    return SQLiteCursorContext(commit, local=True)

