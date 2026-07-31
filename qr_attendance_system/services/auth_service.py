from typing import Optional, Tuple

from database.hod_db import authenticate_hod, update_password as update_hod_password
from database.lecturer_db import (
  authenticate_user as authenticate_lecturer,
  update_password as update_lecturer_password,
)


def authenticate_user(
  user_id: str,
  password: str,
  role: Optional[str] = None,
) -> Optional[Tuple[str, str, str]]:
  """Authenticate a user for the requested role.

  If ``role`` is provided, only the corresponding table is checked:

  - ``"admin"``   -> HODs table
  - ``"lecturer"`` -> lecturers table

  If ``role`` is None or unrecognised, the legacy behaviour is used:
  check HODs first (admin), then lecturers.

  Returns a tuple ``(id, name, role)`` suitable for utils.session.login.
  """

  role = (role or "").lower().strip() or None

  if role == "admin":
    return authenticate_hod(user_id, password)

  if role == "lecturer":
    return authenticate_lecturer(user_id, password)

  # Fallback: legacy behaviour (admin first, then lecturer)
  hod_user = authenticate_hod(user_id, password)
  if hod_user:
    return hod_user

  return authenticate_lecturer(user_id, password)


def change_password(user_id: str, role: Optional[str], new_password: str) -> None:
  """Change the password for the given user and role.

  Admin users (HODs) are updated via the hods table; lecturers via the
  lecturers table. If role is unknown, we fall back to the lecturer table.
  """

  role_norm = (role or "").lower().strip()

  if role_norm == "admin":
    update_hod_password(user_id, new_password)
  elif role_norm == "lecturer":
    update_lecturer_password(user_id, new_password)
  else:
    # fallback: treat as lecturer
    update_lecturer_password(user_id, new_password)

