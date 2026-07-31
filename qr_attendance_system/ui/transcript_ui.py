from __future__ import annotations

import tkinter as tk
from tkinter import ttk, messagebox
from typing import Any, Optional

from config import settings as app_settings
from database.transcript_db import get_student_transcript
from ui.assets_utils import apply_background_image, get_logo_image
from ui import styles as ui_styles


class TranscriptUI:
    """Simple transcript-style history viewer for a single student."""

    def __init__(self, root: Any, parent: Optional[Any] = None) -> None:
        self.root = root
        self.parent = parent
        self.root.title("Student Transcript History")
        self.root.protocol("WM_DELETE_WINDOW", self._on_close)

        theme = app_settings.get_theme()
        bg = theme["bg_color"]
        fg = theme["text_color"]
        self.root.configure(bg=bg)

        self._bg_label = apply_background_image(self.root, (520, 520))
        self._logo_image = get_logo_image((64, 64))
        if self._logo_image is not None:
            tk.Label(self.root, image=self._logo_image, bg=bg, borderwidth=0).pack(pady=(8, 0))

        tk.Label(self.root, text="Student Transcript History", font=ui_styles.SUBTITLE_FONT, bg=bg, fg=fg).pack(pady=(8, 4))

        top = tk.Frame(self.root, bg=bg)
        top.pack(fill="x", padx=10, pady=(0, 8))
        tk.Label(top, text="Student ID:", bg=bg, fg=fg).pack(side="left")
        self.student_var = tk.StringVar()
        tk.Entry(top, textvariable=self.student_var, width=24).pack(side="left", padx=6)
        tk.Button(top, text="Load", command=self._load, font=ui_styles.BUTTON_FONT, **ui_styles.PRIMARY_BUTTON).pack(side="left")

        content = tk.Frame(self.root, bg=bg)
        content.pack(fill="both", expand=True, padx=10, pady=10)

        cols = ("semester", "status", "course", "title", "present", "late", "attendance")
        self.tree = ttk.Treeview(content, columns=cols, show="headings", height=16)
        headings = {
            "semester": "Semester",
            "status": "Sem Status",
            "course": "Course",
            "title": "Title",
            "present": "Present",
            "late": "Late",
            "attendance": "Attendance Rows",
        }
        widths = {"semester": 150, "status": 90, "course": 80, "title": 180, "present": 70, "late": 60, "attendance": 110}
        for col in cols:
            self.tree.heading(col, text=headings[col])
            self.tree.column(col, width=widths[col], anchor="w")
        self.tree.pack(side="left", fill="both", expand=True)
        scrollbar = ttk.Scrollbar(content, orient="vertical", command=self.tree.yview)
        scrollbar.pack(side="right", fill="y")
        self.tree.configure(yscrollcommand=scrollbar.set)

        bottom = tk.Frame(self.root, bg=bg)
        bottom.pack(fill="x", padx=10, pady=(0, 10))
        tk.Button(bottom, text="Close", width=10, command=self._on_close, font=ui_styles.BUTTON_FONT, **ui_styles.MUTED_BUTTON).pack(side="right")

        self.root.update_idletasks()
        self.root.state("zoomed")
        self.root.minsize(1000, 650)

    def _load(self) -> None:
        student_id = self.student_var.get().strip()
        if not student_id:
            messagebox.showerror("Error", "Enter a student ID.")
            return

        try:
            rows = get_student_transcript(student_id)
        except Exception as exc:
            messagebox.showerror("Error", f"Could not load transcript:\n{exc}")
            return

        for iid in self.tree.get_children():
            self.tree.delete(iid)

        if not rows:
            self.tree.insert("", "end", values=("-", "-", "No records", "", 0, 0, 0))
            return

        for row in rows:
            self.tree.insert(
                "",
                "end",
                values=(
                    row.get("semester_name") or "",
                    row.get("semester_status") or "",
                    row.get("course_code") or "",
                    row.get("course_title") or "",
                    int(row.get("present_count") or 0),
                    int(row.get("late_count") or 0),
                    int(row.get("attendance_count") or 0),
                ),
            )

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
