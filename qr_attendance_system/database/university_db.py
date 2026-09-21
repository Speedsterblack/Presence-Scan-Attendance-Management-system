from typing import List, Optional, Tuple

from database.db_config import get_cursor


def _ensure_university_table() -> None:
    """Ensure the institution schema exists before university operations."""

    from database.db_init import create_tables

    with get_cursor(commit=False) as cursor:
        if hasattr(cursor, "execute"):
            try:
                cursor.execute("SELECT 1 FROM University LIMIT 1")
                return
            except Exception as error:
                if "no such table" not in str(error).lower() and "does not exist" not in str(error).lower():
                    raise
    create_tables()


# University table from db_init.py:
# university_id SERIAL PRIMARY KEY,
# university_name VARCHAR(150) NOT NULL UNIQUE
# university_code VARCHAR(20) UNIQUE  -- optional human-readable ID


def get_single_university_id() -> int:
    """Return the only registered university ID, without creating one."""
    _ensure_university_table()
    with get_cursor() as cursor:
        cursor.execute(
            "SELECT university_id FROM University ORDER BY university_id LIMIT 1"
        )
        row = cursor.fetchone()
        if row:
            return int(row["university_id"])

    raise ValueError("No university is registered. Complete institution setup first.")


def add_university(code: str, name: str) -> None:
    """Create a university, updating an existing row with the same code."""
    _ensure_university_table()
    with get_cursor() as cursor:
        cursor.execute(
            "INSERT INTO University (university_code, university_name) "
            "VALUES (%s, %s) "
            "ON CONFLICT (university_code) DO UPDATE "
            "SET university_name = EXCLUDED.university_name",
            (code, name),
        )


def get_all_University() -> List[Tuple[int, str | None, str]]:
    """Return every registered university."""
    _ensure_university_table()
    with get_cursor(commit=False) as cursor:
        cursor.execute(
            "SELECT university_id, university_code, university_name "
            "FROM University ORDER BY university_id",
        )
        rows = cursor.fetchall()

    return [
        (r["university_id"], r.get("university_code"), r["university_name"])
        for r in rows
    ]


def get_university(university_id: int) -> Optional[Tuple[int, str | None, str]]:
    _ensure_university_table()
    with get_cursor(commit=False) as cursor:
        cursor.execute(
            "SELECT university_id, university_code, university_name "
            "FROM University WHERE university_id = %s",
            (university_id,),
        )
        r = cursor.fetchone()

    if not r:
        return None

    return (r["university_id"], r.get("university_code"), r["university_name"])


def update_university(university_id: int, code: str, name: str) -> None:
    _ensure_university_table()
    with get_cursor() as cursor:
        cursor.execute(
            "UPDATE University SET university_code = %s, university_name = %s WHERE university_id = %s",
            (code, name, university_id),
        )


def delete_university(university_id: int) -> None:
    _ensure_university_table()
    with get_cursor() as cursor:
        cursor.execute("DELETE FROM University WHERE university_id = %s", (university_id,))
