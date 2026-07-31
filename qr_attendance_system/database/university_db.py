from typing import List, Optional, Tuple

from database.db_config import get_cursor


# University table from db_init.py:
# university_id SERIAL PRIMARY KEY,
# university_name VARCHAR(150) NOT NULL UNIQUE
# university_code VARCHAR(20) UNIQUE  -- optional human-readable ID


DEFAULT_UNIVERSITY_ID = 1


def get_single_university_id() -> int:
    """Return the university id used by this single-school database."""
    with get_cursor() as cursor:
        cursor.execute(
            "SELECT university_id FROM University ORDER BY university_id LIMIT 1"
        )
        row = cursor.fetchone()
        if row:
            return int(row["university_id"])

        cursor.execute(
            "INSERT INTO University (university_id, university_code, university_name) "
            "VALUES (%s, %s, %s) "
            "ON CONFLICT (university_id) DO UPDATE "
            "SET university_code = EXCLUDED.university_code, university_name = EXCLUDED.university_name",
            (DEFAULT_UNIVERSITY_ID, "SCH001", "Default University"),
        )

    return DEFAULT_UNIVERSITY_ID


def add_university(code: str, name: str) -> None:
    """Create/update the single university for this database."""
    university_id = get_single_university_id()
    with get_cursor() as cursor:
        cursor.execute(
            "UPDATE University SET university_code = %s, university_name = %s "
            "WHERE university_id = %s",
            (code, name, university_id),
        )


def get_all_University() -> List[Tuple[int, str | None, str]]:
    """Return a single-item list for the one university in this database."""
    university_id = get_single_university_id()
    with get_cursor(commit=False) as cursor:
        cursor.execute(
            "SELECT university_id, university_code, university_name "
            "FROM University WHERE university_id = %s",
            (university_id,),
        )
        rows = cursor.fetchall()

    return [
        (r["university_id"], r.get("university_code"), r["university_name"])
        for r in rows
    ]


def get_university(university_id: int) -> Optional[Tuple[int, str | None, str]]:
    effective_id = get_single_university_id()
    with get_cursor(commit=False) as cursor:
        cursor.execute(
            "SELECT university_id, university_code, university_name "
            "FROM University WHERE university_id = %s",
            (effective_id,),
        )
        r = cursor.fetchone()

    if not r:
        return None

    return (r["university_id"], r.get("university_code"), r["university_name"])


def update_university(university_id: int, code: str, name: str) -> None:
    effective_id = get_single_university_id()
    with get_cursor() as cursor:
        cursor.execute(
            "UPDATE University SET university_code = %s, university_name = %s WHERE university_id = %s",
            (code, name, effective_id),
        )


def delete_university(university_id: int) -> None:
    raise ValueError("Single-school mode: deleting the only university is not allowed")
