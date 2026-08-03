from __future__ import annotations

from datetime import datetime
from typing import Any, Optional

from database.db_config import get_cursor


def ensure_audit_table() -> None:
    """Best-effort creation of the audit log table."""

    with get_cursor() as cursor:
        cursor.execute(
            "CREATE TABLE IF NOT EXISTS audit_log ("
            "audit_id INTEGER PRIMARY KEY AUTOINCREMENT, "
            "actor_id TEXT, "
            "actor_role TEXT, "
            "action TEXT NOT NULL, "
            "details TEXT, "
            "created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP"
            ")"
        )


def log_action(action: str, actor_id: str | None = None, actor_role: str | None = None, details: str | None = None) -> None:
    """Record an administrative action in the audit log."""

    try:
        ensure_audit_table()
        with get_cursor() as cursor:
            cursor.execute(
                "INSERT INTO audit_log (actor_id, actor_role, action, details) VALUES (%s, %s, %s, %s)",
                (actor_id, actor_role, action, details),
            )
    except Exception:
        # Audit logging must never block the primary workflow.
        pass


def list_audit_logs(limit: int = 100) -> list[dict[str, Any]]:
    """Return the newest audit records first."""

    with get_cursor(commit=False) as cursor:
        cursor.execute(
            "SELECT audit_id, actor_id, actor_role, action, details, created_at "
            "FROM audit_log ORDER BY created_at DESC, audit_id DESC LIMIT %s",
            (limit,),
        )
        rows = cursor.fetchall()

    result: list[dict[str, Any]] = []
    for row in rows:
        result.append(dict(row) if isinstance(row, dict) else dict(row or {}))
    return result
