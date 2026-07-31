from typing import Any, List, Optional, Tuple

from database.db_config import get_cursor
from database.hod_db import get_hod_department
from utils.security import hash_password, is_hashed_password, verify_password
from utils import session


_USER_COLUMN: Optional[str] = None
_NAME_COLUMN: Optional[str] = None
_HAS_DEPARTMENT_FK: bool = False


def _norm_user_id(value: object) -> str:
    return str(value or "").strip()


def _init_schema_metadata() -> None:
    global _USER_COLUMN, _NAME_COLUMN, _HAS_DEPARTMENT_FK
    if _USER_COLUMN is not None and _NAME_COLUMN is not None:
        return

    with get_cursor() as cursor:
        cursor.execute(
            """
            SELECT column_name
            FROM information_schema.columns
            WHERE table_name = 'lecturers'
            """
        )
        columns = {row["column_name"] for row in cursor.fetchall()}

        user_column = "username" if "username" in columns else "lecturer_id" if "lecturer_id" in columns else None
        name_column = "full_name" if "full_name" in columns else "lecturer_name" if "lecturer_name" in columns else None

        _HAS_DEPARTMENT_FK = "department_id" in columns

        if "role" not in columns:
            cursor.execute("ALTER TABLE lecturers ADD COLUMN role VARCHAR(20) DEFAULT 'lecturer'")

    _USER_COLUMN = user_column or "lecturer_id"
    _NAME_COLUMN = name_column or "lecturer_name"





def get_all_lecturers() -> List[Tuple[str, str, str]]:
    _init_schema_metadata()

    dept_filter = None
    try:
        user = getattr(session, "current_user", None)
        if isinstance(user, dict) and str(user.get("role", "")).lower() == "admin":
            hod_id = _norm_user_id(user.get("id", ""))
            if hod_id:
                dept_filter = get_hod_department(hod_id)
    except Exception:
        dept_filter = None

    query = f"""
        SELECT {_USER_COLUMN} AS username,
               {_NAME_COLUMN} AS full_name,
               COALESCE(role, 'lecturer') AS role
        FROM lecturers
    """
    params: List[Any] = []
    if dept_filter is not None and _HAS_DEPARTMENT_FK:
        query += " WHERE department_id = %s"
        params.append(dept_filter)
    query += f" ORDER BY {_USER_COLUMN}"

    with get_cursor(commit=False) as cursor:
        cursor.execute(query, tuple(params))
        rows = cursor.fetchall()

    return [
        (row["username"], row["full_name"], row["role"])
        for row in rows
    ]


def add_lecturer(username: str, full_name: str, password: str, role: str = "lecturer", department_id: Optional[int] = None) -> None:
    _init_schema_metadata()

    username = _norm_user_id(username)
    password_hash = hash_password(password)

    effective_role = role or "lecturer"

    columns = [_USER_COLUMN, _NAME_COLUMN, "password", "role"]
    # use a loosely-typed list so inserting an int department_id doesn't upset type checkers
    values: List[Any] = [username, full_name, password_hash, effective_role]

    if _HAS_DEPARTMENT_FK:
        if department_id is None:
            raise ValueError("Department ID is required when adding a lecturer")
        columns.insert(2, "department_id")
        values.insert(2, department_id)

    placeholders = ", ".join(["%s"] * len(columns))
    column_list = ", ".join(columns)

    update_parts = [
        f"{_NAME_COLUMN} = EXCLUDED.{_NAME_COLUMN}",
        "password = EXCLUDED.password",
        "role = EXCLUDED.role",
    ]
    if _HAS_DEPARTMENT_FK:
        update_parts.append("department_id = EXCLUDED.department_id")

    on_conflict_set = ", ".join(update_parts)

    query = f"""
        INSERT INTO lecturers ({column_list})
        VALUES ({placeholders})
        ON CONFLICT ({_USER_COLUMN})
        DO UPDATE SET {on_conflict_set}
    """

    with get_cursor() as cursor:
        cursor.execute(query, tuple(values))


def update_lecturer_profile(username: str, full_name: str, role: str = "lecturer") -> None:
    _init_schema_metadata()

    username = _norm_user_id(username)
    full_name = (full_name or "").strip()
    effective_role = (role or "lecturer").strip() or "lecturer"

    if not username or not full_name:
        raise ValueError("Lecturer ID and name are required")

    query = f"UPDATE lecturers SET {_NAME_COLUMN} = %s, role = %s WHERE {_USER_COLUMN} = %s"

    with get_cursor() as cursor:
        cursor.execute(query, (full_name, effective_role, username))


def update_password(username: str, new_password: str) -> None:
    _init_schema_metadata()

    username = _norm_user_id(username)
    password_hash = hash_password(new_password)

    query = f"UPDATE lecturers SET password = %s WHERE {_USER_COLUMN} = %s"

    with get_cursor() as cursor:
        cursor.execute(query, (password_hash, username))


def delete_lecturer(username: str) -> None:
    _init_schema_metadata()

    username = _norm_user_id(username)

    query = f"DELETE FROM lecturers WHERE {_USER_COLUMN} = %s"

    with get_cursor() as cursor:
        cursor.execute(query, (username,))


def authenticate_user(user_id: str, password: str) -> Optional[Tuple[str, str, str]]:
    _init_schema_metadata()

    user_id = _norm_user_id(user_id)

    query = f"""
        SELECT {_USER_COLUMN} AS username,
               {_NAME_COLUMN} AS full_name,
               password,
               COALESCE(role, 'lecturer') AS role
        FROM lecturers
        WHERE {_USER_COLUMN} = %s
    """

    with get_cursor(commit=False) as cursor:
        cursor.execute(query, (user_id,))
        row = cursor.fetchone()

    if not row:
        return None

    stored_password = str(row.get("password") or "")
    if not verify_password(password, stored_password):
        return None

    # Migrate legacy plaintext password rows to hashed form on successful login.
    if not is_hashed_password(stored_password):
        try:
            update_password(user_id, password)
        except Exception:
            pass

    return (row["username"], row["full_name"], row["role"])


def get_lecturer_courses(lecturer_id: str) -> List[str]:
    """Return a list of course codes assigned to the given lecturer.

    This is used by the QR scanner to verify that the currently
    logged-in lecturer is actually assigned to the course that is
    in session before allowing attendance to be recorded.

    The ``lecturer_id`` here is the same identifier used when
    creating or assigning courses (``courses.lecturer_id``).
    """

    lecturer_id = (lecturer_id or "").strip()
    if not lecturer_id:
        return []

    with get_cursor(commit=False) as cursor:
        cursor.execute(
            "SELECT course_code FROM courses WHERE lecturer_id = %s ORDER BY course_code",
            (lecturer_id,),
        )
        rows = cursor.fetchall()

    return [str(r["course_code"]) for r in rows]
