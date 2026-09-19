from typing import List, Optional, Tuple

from database.db_config import get_cursor


# departments table from db_init.py:
# department_id SERIAL PRIMARY KEY,
# department_name VARCHAR(150) NOT NULL,
# university_id INT NOT NULL,
# department_code VARCHAR(20) UNIQUE  -- optional human-readable ID


def add_department(code: str, name: str, university_id: int) -> int:
    """Create a department under the selected university."""
    with get_cursor() as cursor:
        cursor.execute(
            "INSERT INTO departments (department_code, department_name, university_id) "
            "VALUES (%s, %s, %s) RETURNING department_id",
            (code, name, university_id),
        )
        row = cursor.fetchone()

    assert row is not None
    return int(row["department_id"])


def get_all_departments() -> List[Tuple[int, str | None, str, int]]:
    """Return all departments as (id, code, name, university_id)."""
    with get_cursor(commit=False) as cursor:
        cursor.execute(
            "SELECT department_id, department_code, department_name, university_id "
            "FROM departments ORDER BY department_name",
        )
        rows = cursor.fetchall()

    return [
        (
            r["department_id"],
            r.get("department_code"),
            r["department_name"],
            r["university_id"],
        )
        for r in rows
    ]


def get_department(department_id: int) -> Optional[Tuple[int, str | None, str, int]]:
    """Fetch a single department by its id."""
    with get_cursor(commit=False) as cursor:
        cursor.execute(
            "SELECT department_id, department_code, department_name, university_id "
            "FROM departments WHERE department_id = %s",
            (department_id,),
        )
        r = cursor.fetchone()

    if not r:
        return None

    return (
        r["department_id"],
        r.get("department_code"),
        r["department_name"],
        r["university_id"],
    )


def update_department(department_id: int, code: str, name: str, university_id: int) -> None:
    """Update an existing department and its university."""
    with get_cursor() as cursor:
        cursor.execute(
            "UPDATE departments SET department_code = %s, department_name = %s, university_id = %s "
            "WHERE department_id = %s",
            (code, name, university_id, department_id),
        )


def delete_department(department_id: int) -> None:
    """Delete a department by id.

    Note: because of the foreign key, this will fail if other records
    (like hods or courses) still reference the department.
    """
    with get_cursor() as cursor:
        cursor.execute("DELETE FROM departments WHERE department_id = %s", (department_id,))
