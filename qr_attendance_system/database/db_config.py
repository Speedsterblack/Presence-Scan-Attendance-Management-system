import os
from typing import Optional

from psycopg2.pool import SimpleConnectionPool
import psycopg2.extras


DB_MIN_CONN = int(os.getenv("DB_MIN_CONN", "1"))
DB_MAX_CONN = int(os.getenv("DB_MAX_CONN", "5"))
# Default DSN can be overridden via the DATABASE_URL environment variable.
DB_DSN = os.getenv(
    "DATABASE_URL",
    "postgresql://postgres:Speedster@localhost:5432/Presence_Scan",
)

_pool: Optional[SimpleConnectionPool] = None


def init_db_pool(dsn: Optional[str] = None) -> None:
    """Initialise a global connection pool if not already created."""
    global _pool
    if _pool is not None:
        return
    dsn = dsn or DB_DSN
    if not dsn:
        raise RuntimeError("DATABASE_URL not set")
    _pool = SimpleConnectionPool(DB_MIN_CONN, DB_MAX_CONN, dsn)


def get_connection():
    """Get a connection from the pool, creating the pool on first use."""
    global _pool
    if _pool is None:
        init_db_pool()
    assert _pool is not None
    return _pool.getconn()


def release_connection(conn) -> None:
    """Return a connection to the pool."""
    global _pool
    if _pool is not None and conn is not None:
        _pool.putconn(conn)


def close_pool() -> None:
    """Close all connections in the pool (for one-off scripts)."""
    global _pool
    if _pool is not None:
        _pool.closeall()
        _pool = None

class _CursorContext:
    """Context manager that yields a RealDictCursor.

    This explicit class makes type checkers (like Pylance) recognize that the
    result of get_cursor() implements the ContextManager protocol, avoiding
    generator-with warnings while preserving the original behaviour.
    """

    def __init__(self, commit: bool = True):
        self._commit = commit
        self._conn = None
        self._cur = None

    def __enter__(self):
        self._conn = get_connection()
        self._cur = self._conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
        return self._cur

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
                    release_connection(self._conn)


def get_cursor(commit: bool = True) -> _CursorContext:
    """Return a context manager that yields a RealDictCursor.

    Usage remains::

        with get_cursor() as cursor:
            cursor.execute(...)
    """

    return _CursorContext(commit)

