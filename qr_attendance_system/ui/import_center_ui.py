from __future__ import annotations

import csv
import tkinter as tk
from tkinter import filedialog, messagebox
from typing import Any, Optional

from config import settings as app_settings
from database.course_registration_db import register_student_to_course
from database.hod_db import get_hod_department
from database.lecturer_db import add_lecturer, get_all_lecturers
from database.student_db import add_student
from services.course_service import create_course_with_timetable
from ui.assets_utils import apply_background_image, get_logo_image
from ui import styles as ui_styles
from utils import session


class ImportCenterUI:
    """Admin screen for importing CSV data templates."""

    def __init__(self, root: Any, parent: Optional[Any] = None) -> None:
        self.root = root
        self.parent = parent
        self.root.title("Import Center")
        self.root.protocol("WM_DELETE_WINDOW", self._on_close)

        theme = app_settings.get_theme()
        bg = theme["bg_color"]
        fg = theme["text_color"]
        self.root.configure(bg=bg)

        self._bg_label = apply_background_image(self.root, (520, 520))
        self._logo_image = get_logo_image((72, 72), master=self.root)
        if self._logo_image is not None:
            tk.Label(self.root, image=self._logo_image, bg=bg, borderwidth=0).pack(pady=(10, 0))

        tk.Label(
            self.root,
            text="CSV Import Center",
            font=("Arial", 18, "bold"),
            bg=bg,
            fg=fg,
        ).pack(pady=(12, 8))

        tk.Label(
            self.root,
            text=(
                "Import lecturers before courses so lecturer IDs satisfy course references.\n"
                "Imports skip invalid rows and show a summary at the end."
            ),
            bg=bg,
            fg=fg,
            font=("Arial", 10),
            justify="center",
        ).pack(pady=(0, 10))

        body = tk.Frame(self.root, bg=bg)
        body.pack(fill="both", expand=True, padx=16, pady=8)

        tk.Button(
            body,
            text="Import Students CSV",
            command=self._import_students,
            width=24,
            font=ui_styles.BUTTON_FONT,
            **ui_styles.PRIMARY_BUTTON,
        ).pack(pady=6)

        tk.Button(
            body,
            text="Import Lecturers CSV",
            command=self._import_lecturers,
            width=24,
            font=ui_styles.BUTTON_FONT,
            **ui_styles.SECONDARY_BUTTON,
        ).pack(pady=6)

        tk.Button(
            body,
            text="Import Courses CSV",
            command=self._import_courses,
            width=24,
            font=ui_styles.BUTTON_FONT,
            **ui_styles.SECONDARY_BUTTON,
        ).pack(pady=6)

        tk.Button(
            body,
            text="Import Registrations CSV",
            command=self._import_registrations,
            width=24,
            font=ui_styles.BUTTON_FONT,
            **ui_styles.SECONDARY_BUTTON,
        ).pack(pady=6)

        tk.Button(
            body,
            text="Close",
            command=self._on_close,
            width=24,
            font=ui_styles.BUTTON_FONT,
            **ui_styles.MUTED_BUTTON,
        ).pack(pady=(18, 0))

        self.root.update_idletasks()
        self.root.state("zoomed")
        self.root.minsize(900, 600)

    def _select_csv(self, title: str) -> str:
        return filedialog.askopenfilename(
            title=title,
            filetypes=[("CSV files", "*.csv"), ("All files", "*.*")],
        )

    def _admin_department_id(self) -> Optional[int]:
        try:
            user = session.current_user
        except Exception:
            user = None
        if not isinstance(user, dict):
            return None
        if str(user.get("role", "")).lower() != "admin":
            return None
        admin_id = str(user.get("id", "")).strip()
        if not admin_id:
            return None
        try:
            dept_id = get_hod_department(admin_id)
            return int(dept_id) if dept_id is not None else None
        except Exception:
            return None

    def _import_students(self) -> None:
        path = self._select_csv("Select students CSV")
        if not path:
            return

        success = 0
        failures: list[str] = []
        try:
            with open(path, newline="", encoding="utf-8") as f:
                reader = csv.DictReader(f)
                for idx, row in enumerate(reader, start=2):
                    sid = str(row.get("student_id") or "").strip()
                    name = str(row.get("student_name") or "").strip()
                    Department = str(row.get("Department") or "").strip()
                    level = str(row.get("level") or "").strip()
                    if not sid or not name:
                        failures.append(f"row {idx}: missing student_id/student_name")
                        continue
                    try:
                        add_student(sid, name, Department, level)
                        success += 1
                    except Exception as exc:
                        failures.append(f"row {idx}: {exc}")
        except Exception as exc:
            messagebox.showerror("Import Error", f"Could not read file:\n{exc}")
            return

        self._show_summary("Students import", success, failures)

    def _import_lecturers(self) -> None:
        dept_id = self._admin_department_id()
        if dept_id is None:
            messagebox.showerror("Import Error", "Could not determine your admin department.")
            return

        path = self._select_csv("Select lecturers CSV")
        if not path:
            return

        success = 0
        failures: list[str] = []
        try:
            with open(path, newline="", encoding="utf-8") as f:
                reader = csv.DictReader(f)
                for idx, row in enumerate(reader, start=2):
                    lecturer_id = str(row.get("lecturer_id") or row.get("Lecturer_ID") or "").strip()
                    lecturer_name = str(row.get("lecturer_name") or row.get("full_name") or "").strip()
                    password = str(row.get("password") or "").strip()
                    role = str(row.get("role") or "lecturer").strip() or "lecturer"
                    if not lecturer_id or not lecturer_name or not password:
                        failures.append(f"row {idx}: missing lecturer_id/lecturer_name/password")
                        continue
                    try:
                        add_lecturer(lecturer_id, lecturer_name, password, role, department_id=dept_id)
                        success += 1
                    except Exception as exc:
                        failures.append(f"row {idx}: {exc}")
        except Exception as exc:
            messagebox.showerror("Import Error", f"Could not read file:\n{exc}")
            return

        self._show_summary("Lecturers import", success, failures)

    def _import_courses(self) -> None:
        dept_id = self._admin_department_id()
        if dept_id is None:
            messagebox.showerror("Import Error", "Could not determine your admin department.")
            return

        path = self._select_csv("Select courses CSV")
        if not path:
            return

        success = 0
        failures: list[str] = []
        lecturer_ids = {str(row[0]).strip() for row in get_all_lecturers()}
        try:
            with open(path, newline="", encoding="utf-8") as f:
                reader = csv.DictReader(f)
                for idx, row in enumerate(reader, start=2):
                    course_code = str(row.get("course_code") or "").strip()
                    course_title = str(row.get("course_title") or row.get("course_name") or "").strip()
                    lecturer_id = str(row.get("lecturer_id") or "").strip()
                    credit_hours_text = str(row.get("credit_hours") or "0").strip()
                    grace_text = str(row.get("grace_minutes") or "0").strip()
                    day = str(row.get("day_of_week") or row.get("day") or "").strip()
                    start_time = str(row.get("start_time") or "").strip()
                    end_time = str(row.get("end_time") or "").strip()

                    if not course_code or not course_title or not lecturer_id:
                        failures.append(f"row {idx}: missing course_code/course_title/lecturer_id")
                        continue
                    if lecturer_id not in lecturer_ids:
                        failures.append(f"row {idx}: lecturer ID {lecturer_id} was not found; import lecturers first")
                        continue
                    if any((day, start_time, end_time)) and not all((day, start_time, end_time)):
                        failures.append(f"row {idx}: day_of_week, start_time, and end_time must be supplied together")
                        continue

                    try:
                        credit_hours = int(credit_hours_text or "0")
                        grace_minutes = int(grace_text or "0")
                        if credit_hours < 0 or grace_minutes < 0:
                            raise ValueError("negative values are not allowed")
                    except Exception:
                        failures.append(f"row {idx}: invalid credit_hours or grace_minutes")
                        continue

                    try:
                        create_course_with_timetable(
                            course_code,
                            course_title,
                            lecturer_id,
                            credit_hours,
                            grace_minutes,
                            [(day, start_time, end_time)],
                        )
                        success += 1
                    except Exception as exc:
                        failures.append(f"row {idx}: {exc}")
        except Exception as exc:
            messagebox.showerror("Import Error", f"Could not read file:\n{exc}")
            return

        self._show_summary("Courses import", success, failures)

    def _import_registrations(self) -> None:
        path = self._select_csv("Select registrations CSV")
        if not path:
            return

        success = 0
        failures: list[str] = []
        try:
            with open(path, newline="", encoding="utf-8") as f:
                reader = csv.DictReader(f)
                for idx, row in enumerate(reader, start=2):
                    sid = str(row.get("student_id") or "").strip()
                    course_code = str(row.get("course_code") or "").strip()
                    if not sid or not course_code:
                        failures.append(f"row {idx}: missing student_id/course_code")
                        continue
                    try:
                        register_student_to_course(sid, course_code)
                        success += 1
                    except Exception as exc:
                        failures.append(f"row {idx}: {exc}")
        except Exception as exc:
            messagebox.showerror("Import Error", f"Could not read file:\n{exc}")
            return

        self._show_summary("Registrations import", success, failures)

    def _show_summary(self, title: str, success: int, failures: list[str]) -> None:
        if failures:
            top = "\n".join(failures[:8])
            messagebox.showinfo(title, f"Imported: {success}\nFailures: {len(failures)}\n\nTop issues:\n{top}")
        else:
            messagebox.showinfo(title, f"Imported: {success}\nFailures: 0")

    def _on_close(self) -> None:
        try:
            self.root.destroy()
        finally:
            if self.parent is not None:
                try:
                    self.parent.deiconify()
                    try:
                        self.parent.state("zoomed")
                    except Exception:
                        pass
                except Exception:
                    pass
