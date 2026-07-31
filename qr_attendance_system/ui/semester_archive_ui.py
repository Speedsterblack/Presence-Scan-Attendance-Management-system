from __future__ import annotations

import csv
import tkinter as tk
from tkinter import ttk, messagebox, filedialog
from typing import Any, Optional

from database.db_config import get_cursor
from database import semester_db
from config import settings as app_settings
from ui.assets_utils import apply_background_image, get_logo_image
from ui import styles as ui_styles


class SemesterArchiveUI:
    """Read-only view for past semesters and their summary counts."""

    def __init__(self, root: Any, parent: Optional[Any] = None) -> None:
        self.root = root
        self.parent = parent
        self.root.title("Semester Archive")
        self.root.protocol("WM_DELETE_WINDOW", self._on_close)

        theme = app_settings.get_theme()
        bg = theme["bg_color"]
        fg = theme["text_color"]
        self.root.configure(bg=bg)

        self._bg_label = apply_background_image(self.root, (520, 520))
        self._logo_image = get_logo_image((64, 64))
        if self._logo_image is not None:
            tk.Label(self.root, image=self._logo_image, bg=bg, borderwidth=0).pack(pady=(8, 0))

        tk.Label(
            self.root,
            text="Semester Archive",
            font=ui_styles.SUBTITLE_FONT,
            bg=bg,
            fg=fg,
        ).pack(pady=(8, 4))

        top = tk.Frame(self.root, bg=bg)
        top.pack(fill="x", padx=10, pady=(0, 8))

        tk.Label(top, text="Select semester:", bg=bg, fg=fg).pack(side="left")
        self.semester_var = tk.StringVar()
        self.semester_menu = ttk.Combobox(top, textvariable=self.semester_var, state="readonly", width=42)
        self.semester_menu.pack(side="left", padx=(6, 0))
        self.semester_menu.bind("<<ComboboxSelected>>", lambda _e: self._refresh())

        tk.Button(
            top,
            text="Refresh",
            command=self._load_semesters,
            font=ui_styles.BUTTON_FONT,
            **ui_styles.SECONDARY_BUTTON,
        ).pack(side="right")

        tk.Button(
            top,
            text="Export CSV",
            command=self._export_selected,
            font=ui_styles.BUTTON_FONT,
            **ui_styles.PRIMARY_BUTTON,
        ).pack(side="right", padx=(0, 8))

        content = tk.Frame(self.root, bg=bg)
        content.pack(fill="both", expand=True, padx=10, pady=10)

        columns = ("semester", "status", "start", "end", "registrations", "attendance", "present", "late")
        self.tree = ttk.Treeview(content, columns=columns, show="headings", height=12)
        headings = {
            "semester": "Semester",
            "status": "Status",
            "start": "Start Date",
            "end": "End Date",
            "registrations": "Registrations",
            "attendance": "Attendance Rows",
            "present": "Present",
            "late": "Late",
        }
        widths = {
            "semester": 180,
            "status": 90,
            "start": 100,
            "end": 100,
            "registrations": 110,
            "attendance": 120,
            "present": 80,
            "late": 80,
        }
        for key in columns:
            self.tree.heading(key, text=headings[key])
            self.tree.column(key, width=widths[key], anchor="w")
        self.tree.pack(side="left", fill="both", expand=True)

        vs = ttk.Scrollbar(content, orient="vertical", command=self.tree.yview)
        vs.pack(side="right", fill="y")
        self.tree.configure(yscrollcommand=vs.set)

        bottom = tk.Frame(self.root, bg=bg)
        bottom.pack(fill="x", padx=10, pady=(0, 10))

        tk.Button(
            bottom,
            text="Close",
            width=10,
            command=self._on_close,
            font=ui_styles.BUTTON_FONT,
            **ui_styles.MUTED_BUTTON,
        ).pack(side="right")

        self.root.update_idletasks()
        self.root.state("zoomed")
        self.root.minsize(1000, 650)

        self._semester_rows: list[dict[str, Any]] = []
        self._load_semesters()

    def _load_semesters(self) -> None:
        try:
            rows = semester_db.list_semesters(limit=50)
        except Exception as e:
            messagebox.showerror("Error", f"Could not load semesters:\n{e}")
            return

        self._semester_rows = rows
        labels = []
        for row in rows:
            name = str(row.get("semester_name") or "Semester")
            status = str(row.get("status") or "")
            start_date = row.get("start_date")
            label = f"{name} ({status})"
            if start_date:
                label += f" - {start_date}"
            labels.append(label)

        self.semester_menu["values"] = labels
        if labels and not self.semester_var.get():
            self.semester_var.set(labels[0])
        elif labels and self.semester_var.get() not in labels:
            self.semester_var.set(labels[0])

        self._refresh()

    def _selected_semester(self) -> Optional[dict[str, Any]]:
        current = self.semester_var.get().strip()
        if not current or not self._semester_rows:
            return None
        for row in self._semester_rows:
            name = str(row.get("semester_name") or "Semester")
            status = str(row.get("status") or "")
            start_date = row.get("start_date")
            label = f"{name} ({status})"
            if start_date:
                label += f" - {start_date}"
            if label == current:
                return row
        return self._semester_rows[0]

    def _refresh(self) -> None:
        for iid in self.tree.get_children():
            self.tree.delete(iid)

        semester = self._selected_semester()
        if not semester:
            return

        semester_id = int(semester["semester_id"])
        with get_cursor(commit=False) as cursor:
            cursor.execute(
                "SELECT COUNT(*) AS total FROM course_registrations WHERE semester_id = %s",
                (semester_id,),
            )
            registrations = int((cursor.fetchone() or {}).get("total") or 0)

            cursor.execute(
                "SELECT COUNT(*) AS total FROM attendance WHERE semester_id = %s",
                (semester_id,),
            )
            attendance_rows = int((cursor.fetchone() or {}).get("total") or 0)

            cursor.execute(
                "SELECT COUNT(*) AS total FROM attendance WHERE semester_id = %s AND status = 'Present'",
                (semester_id,),
            )
            present_count = int((cursor.fetchone() or {}).get("total") or 0)

            cursor.execute(
                "SELECT COUNT(*) AS total FROM attendance WHERE semester_id = %s AND status = 'Late'",
                (semester_id,),
            )
            late_count = int((cursor.fetchone() or {}).get("total") or 0)

        self.tree.insert(
            "",
            tk.END,
            values=(
                semester.get("semester_name") or "",
                str(semester.get("status") or ""),
                semester.get("start_date") or "",
                semester.get("end_date") or "",
                registrations,
                attendance_rows,
                present_count,
                late_count,
            ),
        )

    def _export_selected(self) -> None:
        semester = self._selected_semester()
        if not semester:
            messagebox.showerror("Error", "Select a semester first.")
            return

        semester_id = int(semester["semester_id"])
        default_dir = app_settings.get_export_directory()
        file_path = filedialog.asksaveasfilename(
            title="Export semester archive",
            initialdir=default_dir,
            defaultextension=".csv",
            filetypes=[("CSV files", "*.csv")],
            initialfile=f"semester_{semester_id}_archive.csv",
        )
        if not file_path:
            return

        try:
            with get_cursor(commit=False) as cursor:
                cursor.execute(
                    "SELECT c.course_code, COUNT(*) AS registrations FROM course_registrations cr "
                    "JOIN courses c ON c.course_id = cr.course_id WHERE cr.semester_id = %s GROUP BY c.course_code ORDER BY c.course_code",
                    (semester_id,),
                )
                reg_rows = cursor.fetchall()
                cursor.execute(
                    "SELECT c.course_code, COUNT(*) AS attendance_rows FROM attendance a "
                    "JOIN timetable t ON t.timetable_id = a.timetable_id "
                    "JOIN courses c ON c.course_id = t.course_id WHERE a.semester_id = %s GROUP BY c.course_code ORDER BY c.course_code",
                    (semester_id,),
                )
                att_rows = {row["course_code"]: row["attendance_rows"] for row in cursor.fetchall()}

            with open(file_path, "w", newline="", encoding="utf-8") as f:
                writer = csv.writer(f)
                writer.writerow(["Semester Archive Report"])
                writer.writerow(["Semester", semester.get("semester_name") or ""])
                writer.writerow(["Status", semester.get("status") or ""])
                writer.writerow(["Start Date", semester.get("start_date") or ""])
                writer.writerow(["End Date", semester.get("end_date") or ""])
                writer.writerow([])
                writer.writerow(["Course", "Registrations", "Attendance Rows"])
                for row in reg_rows:
                    code = row["course_code"]
                    writer.writerow([code, int(row["registrations"] or 0), int(att_rows.get(code, 0) or 0)])

            messagebox.showinfo("Export", f"Semester archive exported to:\n{file_path}")
        except Exception as e:
            messagebox.showerror("Error", f"Could not export semester archive:\n{e}")

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
