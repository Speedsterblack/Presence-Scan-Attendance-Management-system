"""Local-network hub hosted by the Head of University application."""

from __future__ import annotations

import json
import sqlite3
import threading
from datetime import date, datetime, time
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
        return f"http://{get_local_ip()}:{port}"

    app = Flask("presence_scan_head_hub")

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
        app.run(host="0.0.0.0", port=port, debug=False, use_reloader=False)

    _HUB_THREAD = threading.Thread(target=run, name="presence-scan-head-hub", daemon=True)
    _HUB_THREAD.start()
    _HUB_RUNNING = True
    return f"http://{get_local_ip()}:{port}"


def get_head_hub_url(port: int = HUB_PORT) -> str:
    return f"http://{get_local_ip()}:{port}"
