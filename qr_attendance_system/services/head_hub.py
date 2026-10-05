"""Local-network hub hosted by the Head of University application."""

from __future__ import annotations

import json
import secrets
import sqlite3
import ssl
import threading
from datetime import date, datetime, time
from pathlib import Path
from typing import Any

from flask import Flask, jsonify, request

from database import db_config
from services.mobile_scanner import get_local_ip


HUB_PORT = 8765
_HUB_THREAD: threading.Thread | None = None
_HUB_RUNNING = False

# Master data is owned by the Head application and pulled by lecturer clients.
HUB_TABLES = (
    "University",
    "departments",
    "semesters",
    "hods",
    "lecturers",
    "students",
    "courses",
    "course_registrations",
    "timetable",
    "special_days",
)


def _token_path() -> Path:
    return Path(db_config.DB_PATH).parent / "head_hub_token.txt"


def get_hub_token() -> str:
    path = _token_path()
    try:
        if path.exists():
            token = path.read_text(encoding="utf-8").strip()
            if token:
                return token
        token = secrets.token_urlsafe(32)
        path.write_text(token, encoding="utf-8")
        return token
    except OSError:
        return ""


def _certificate_paths() -> tuple[Path, Path] | None:
    base = Path(__file__).resolve().parent.parent
    cert_file = base / "cert.pem"
    key_file = base / "key.pem"
    if cert_file.exists() and key_file.exists():
        return cert_file, key_file
    return None


def _json_value(value: Any) -> Any:
    if isinstance(value, (date, datetime, time)):
        return value.isoformat()
    return value


def _snapshot() -> dict[str, list[dict[str, Any]]]:
    connection = sqlite3.connect(db_config.DB_PATH)
    connection.row_factory = sqlite3.Row
    try:
        result: dict[str, list[dict[str, Any]]] = {}
        for table in HUB_TABLES:
            rows = connection.execute(f'SELECT * FROM "{table}"').fetchall()
            result[table] = [
                {key: _json_value(row[key]) for key in row.keys()}
                for row in rows
            ]
        return result
    finally:
        connection.close()


def start_head_hub_server(port: int = HUB_PORT) -> str:
    """Start the Head application LAN hub and return its local URL."""

    global _HUB_THREAD, _HUB_RUNNING
    if _HUB_RUNNING:
        return get_head_hub_url(port)

    app = Flask("presence_scan_head_hub")

    @app.before_request
    def require_pairing_token() -> Any:
        if request.path == "/api/health":
            return None
        expected = get_hub_token()
        received = request.headers.get("Authorization", "")
        if not expected or received != f"Bearer {expected}":
            return jsonify({"error": "Hub authentication required"}), 401
        return None

    @app.get("/api/health")
    def health() -> Any:
        return jsonify({"service": "presence-scan-head", "status": "ok"})

    @app.get("/api/snapshot")
    def snapshot() -> Any:
        try:
            return jsonify({"tables": _snapshot()})
        except Exception as error:
            return jsonify({"error": str(error)}), 500

    @app.post("/api/attendance")
    def attendance() -> Any:
        payload = request.get_json(silent=True) or {}
        rows = payload.get("rows", [])
        if not isinstance(rows, list):
            return jsonify({"error": "rows must be a list"}), 400

        connection = sqlite3.connect(db_config.DB_PATH)
        try:
            inserted = 0
            for row in rows:
                if not isinstance(row, dict):
                    continue
                columns = [
                    "attendance_id",
                    "timetable_id",
                    "student_id",
                    "semester_id",
                    "attendance_date",
                    "status",
                ]
                if any(column not in row for column in columns):
                    continue
                cursor = connection.execute(
                    'INSERT OR IGNORE INTO "attendance" '
                    '(attendance_id, timetable_id, student_id, semester_id, attendance_date, status) '
                    'VALUES (?, ?, ?, ?, ?, ?)',
                    tuple(row[column] for column in columns),
                )
                inserted += cursor.rowcount
            connection.commit()
            return jsonify({"inserted": inserted})
        finally:
            connection.close()

    def run() -> None:
        certificate = _certificate_paths()
        ssl_context = None
        if certificate:
            ssl_context = certificate
        app.run(
            host="0.0.0.0",
            port=port,
            debug=False,
            use_reloader=False,
            ssl_context=ssl_context,
        )

    _HUB_THREAD = threading.Thread(target=run, name="presence-scan-head-hub", daemon=True)
    _HUB_THREAD.start()
    _HUB_RUNNING = True
    return f"http://{get_local_ip()}:{port}"


def get_head_hub_url(port: int = HUB_PORT) -> str:
    scheme = "https" if _certificate_paths() else "http"
    return f"{scheme}://{get_local_ip()}:{port}"
