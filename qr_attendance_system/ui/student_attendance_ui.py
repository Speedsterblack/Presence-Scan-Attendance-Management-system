from __future__ import annotations

import tkinter as tk
from tkinter import ttk, messagebox

from database import student_attendance_db
from ui.assets_utils import apply_background_image, get_logo_image
from ui import styles as ui_styles
from config import settings as app_settings


class StudentAttendanceUI:
    def __init__(self, root: tk.Toplevel, parent: tk.Tk) -> None:
        self.root = root
        self.parent = parent
        self.root.title("Student Attendance Lookup")
        self.root.protocol("WM_DELETE_WINDOW", self._on_close)

        theme = app_settings.get_theme()
        self.bg = theme["bg_color"]
        self.fg = theme["text_color"]
        self.root.configure(bg=self.bg)

        self._bg_label = apply_background_image(root, (520, 520))
        self._logo_image = get_logo_image((72, 72), master=root)
        if self._logo_image is not None:
            tk.Label(root, image=self._logo_image, bg=self.bg, borderwidth=0).pack(pady=(8, 0))

        tk.Label(
            root,
            text="Student Attendance Lookup",
            font=ui_styles.SUBTITLE_FONT,
            bg=self.bg,
            fg=self.fg,
        ).pack(pady=(6, 4))

        tk.Label(
            root,
            text="Search by student name or ID, then select a student to view attendance per course.",
            font=("Arial", 9),
            bg=self.bg,
            fg=self.fg,
        ).pack(pady=(0, 8))

        top = tk.Frame(root, bg=self.bg)
        top.pack(fill="x", padx=10, pady=(0, 8))

        tk.Label(top, text="Search:", bg=self.bg, fg=self.fg).pack(side="left")
        self.search_var = tk.StringVar(master=root)
        self.search_entry = tk.Entry(top, textvariable=self.search_var, width=30)
        self.search_entry.pack(side="left", padx=(4, 6))
        self.search_entry.bind("<Return>", self._on_search)

        tk.Button(
            top,
            text="Search",
            width=10,
            font=ui_styles.BUTTON_FONT,
            command=self._on_search,
            **ui_styles.PRIMARY_BUTTON,
        ).pack(side="left", padx=(0, 6))

        content = tk.Frame(root, bg=self.bg)
        content.pack(fill="both", expand=True, padx=10, pady=8)

        # Left column: stacked tables
        left_column = tk.Frame(content, bg=self.bg)
        left_column.pack(side="left", fill="both", expand=True, padx=(0, 10))

        top_section = tk.Frame(left_column, bg=self.bg)
        top_section.pack(fill="both", expand=True, pady=(0, 10))

        bottom_section = tk.Frame(left_column, bg=self.bg)
        bottom_section.pack(fill="both", expand=True)

        # Top: Matching Students table
        tk.Label(top_section, text="Matching Students", font=("Arial", 12, "bold"), bg=self.bg, fg=self.fg).pack(anchor="w")
        self.results_tree = ttk.Treeview(
            top_section,
            columns=("student_id", "name", "Department", "level"),
            show="headings",
            height=12,
        )
        for col, text, width in (
            ("student_id", "Student ID", 100),
            ("name", "Name", 160),
            ("Department", "Department", 120),
            ("level", "Level", 70),
        ):
            self.results_tree.heading(col, text=text)
            self.results_tree.column(col, width=width, anchor="w")
        self.results_tree.pack(side="left", fill="both", expand=True)
        self.results_tree.bind("<<TreeviewSelect>>", self._on_result_select)

        results_scroll = ttk.Scrollbar(top_section, orient="vertical", command=self.results_tree.yview)
        results_scroll.pack(side="right", fill="y")
        self.results_tree.configure(yscrollcommand=results_scroll.set)

        # Bottom: Per-course attendance table
        tk.Label(bottom_section, text="Per-course attendance", font=("Arial", 12, "bold"), bg=self.bg, fg=self.fg).pack(anchor="w")
        self.summary_tree = ttk.Treeview(
            bottom_section,
            columns=("course", "title", "present", "late", "absent", "sessions", "expected"),
            show="headings",
            height=12,
        )
        headings = {
            "course": "Course",
            "title": "Title",
            "present": "Present",
            "late": "Late",
            "absent": "Absent",
            "sessions": "Observed",
            "expected": "Expected",
        }
        widths = {"course": 70, "title": 140, "present": 60, "late": 50, "absent": 60, "sessions": 65, "expected": 65}
        for col in self.summary_tree["columns"]:
            self.summary_tree.heading(col, text=headings[col])
            self.summary_tree.column(col, width=widths[col], anchor="center" if col != "title" else "w")
        self.summary_tree.pack(side="left", fill="both", expand=True)

        summary_scroll = ttk.Scrollbar(bottom_section, orient="vertical", command=self.summary_tree.yview)
        summary_scroll.pack(side="right", fill="y")
        self.summary_tree.configure(yscrollcommand=summary_scroll.set)

        # Right column: Graph
        right = tk.Frame(content, bg=self.bg)
        right.pack(side="left", fill="both", expand=True)

        tk.Label(right, text="Attendance graph", font=("Arial", 12, "bold"), bg=self.bg, fg=self.fg).pack(anchor="w")
        self.graph_canvas = tk.Canvas(right, width=380, height=420, bg="white", highlightthickness=1, highlightbackground="#cccccc")
        self.graph_canvas.pack(fill="both", expand=True, pady=(4, 0))
        self._draw_empty_graph("Select a student to display attendance trends.")

        bottom = tk.Frame(root, bg=self.bg)
        bottom.pack(fill="x", padx=10, pady=(0, 10))

        tk.Button(
            bottom,
            text="Close",
            width=10,
            font=ui_styles.BUTTON_FONT,
            command=self._on_close,
            **ui_styles.MUTED_BUTTON,
        ).pack(side="right")

        self.search_entry.focus_set()
        self._results: list[tuple[str, str, str, str]] = []
        self._all_students: list[tuple[str, str, str, str]] = []
        self._load_all_students()
        # Maximize student attendance window on startup
        self.root.update_idletasks()
        self.root.state('zoomed')
        self.root.minsize(1000, 650)

    def _load_all_students(self) -> None:
        try:
            rows = student_attendance_db.get_visible_students()
        except Exception as exc:
            messagebox.showerror("Error", f"Could not load students:\n{exc}")
            rows = []

        self._all_students = rows
        self._reload_results(rows)

    def _reload_results(self, rows: list[tuple[str, str, str, str]]) -> None:
        self._results = rows
        for iid in self.results_tree.get_children():
            self.results_tree.delete(iid)
        for row in rows:
            self.results_tree.insert("", "end", values=row)
        if not rows:
            self._clear_summary()

    def _clear_summary(self) -> None:
        for iid in self.summary_tree.get_children():
            self.summary_tree.delete(iid)

    def _draw_empty_graph(self, message: str) -> None:
        self.graph_canvas.delete("all")
        self.graph_canvas.create_text(
            230,
            200,
            text=message,
            fill="#666666",
            font=("Arial", 11, "italic"),
            width=380,
            justify="center",
        )

    def _draw_attendance_graph(self, rows: list[tuple[str, str, int, int, int, int, int]]) -> None:
        self.graph_canvas.delete("all")

        if not rows:
            self._draw_empty_graph("No attendance data to plot.")
            return

        width = max(self.graph_canvas.winfo_width(), 500)
        height = max(self.graph_canvas.winfo_height(), 380)
        left_pad = 48
        top_pad = 30
        right_pad = 48
        bottom_pad = 70
        bar_area_height = max(100, height - top_pad - bottom_pad)
        bar_area_width = max(100, width - 2 * left_pad)

        # Percentage grid like the admin dashboard
        for pct in (0, 25, 50, 75, 100):
            y = top_pad + bar_area_height * (1 - pct / 100.0)
            self.graph_canvas.create_line(left_pad - 2, y, width - right_pad, y, fill="#eeeeee")
            self.graph_canvas.create_text(left_pad - 6, y, anchor="e", text=f"{pct}%", fill="#333333", font=("Arial", 8))

        n = max(1, min(len(rows), 12))
        slot_width = bar_area_width / float(n)
        if n == 1:
            cluster_width = min(bar_area_width * 0.92, 260)
            single_bar_width = max(20, min((cluster_width - 24) / 3.0, 54))
            gap = max(8, (cluster_width - single_bar_width * 3) / 2)
        else:
            cluster_width = min(slot_width * 0.72, 110)
            single_bar_width = max(12, min(cluster_width / 4.0, 24))
            gap = max(6, (cluster_width - single_bar_width * 3) / 2)

        max_value = 1
        for _, _, present, late, absent, _, _ in rows[:n]:
            max_value = max(max_value, int(present or 0), int(late or 0), int(absent or 0))

        # Centered legend underneath the chart
        legend_item_width = 110
        legend_total_width = legend_item_width * 3
        legend_start_x = left_pad + max(0, (bar_area_width - legend_total_width) / 2)
        legend_y = height - 18
        legend_items = [("Present", "#0EB316"), ("Late", "#cccf09"), ("Absent", "#e42727")]
        legend_x = legend_start_x
        for label, color in legend_items:
            self.graph_canvas.create_rectangle(legend_x, legend_y - 8, legend_x + 12, legend_y + 4, fill=color, outline=color)
            self.graph_canvas.create_text(legend_x + 18, legend_y - 2, text=label, anchor="w", fill="#333333", font=("Arial", 9))
            legend_x += legend_item_width

        for i, (course, title, present, late, absent, sessions, expected) in enumerate(rows[:12]):
            present = max(int(present or 0), 0)
            late = max(int(late or 0), 0)
            absent = max(int(absent or 0), 0)

            if n == 1:
                cx = left_pad + cluster_width / 2
            else:
                cx = left_pad + cluster_width / 2 + i * slot_width

            base_x = cx - cluster_width / 2
            y_bottom = top_pad + bar_area_height

            metrics = [
                ("Present", present, "#0EB316", base_x),
                ("Late", late, "#cccf09", base_x + single_bar_width + gap),
                ("Absent", absent, "#e42727", base_x + (single_bar_width + gap) * 2),
            ]

            for label, value, color, x0 in metrics:
                x1 = x0 + single_bar_width
                bar_h = bar_area_height * (value / float(max_value)) if max_value > 0 else 0
                y0 = y_bottom - bar_h
                if bar_h > 0:
                    self.graph_canvas.create_rectangle(x0, y0, x1, y_bottom, fill=color, outline="")
                value_y = y0 - 8 if bar_h > 0 else y_bottom - 8
                self.graph_canvas.create_text(x0 + single_bar_width / 2, value_y, text=str(value), fill="#333333", font=("Arial", 8))

            # Course label under the grouped cluster, like the dashboard labels
            label_y = top_pad + bar_area_height + 12
            self.graph_canvas.create_text(cx, label_y, anchor="n", text=str(course), fill="#222222", font=("Arial", 9, "bold"))
            self.graph_canvas.create_text(cx, label_y + 14, anchor="n", text=str(title)[:22], fill="#666666", font=("Arial", 8), width=cluster_width + 12)

            # Observed/expected note above the cluster
            self.graph_canvas.create_text(cx, top_pad - 4, text=f"{sessions}/{expected}", anchor="s", fill="#333333", font=("Arial", 8))

        # baseline under the bars for visual separation
        self.graph_canvas.create_line(left_pad, top_pad + bar_area_height, width - right_pad, top_pad + bar_area_height, fill="#dddddd")

    def _on_search(self, event=None) -> None:
        query = self.search_var.get().strip()
        if not self._all_students:
            self._load_all_students()
            if not self._all_students:
                return

        if not query:
            self._reload_results(self._all_students)
            return

        q = query.lower()
        rows = [
            row for row in self._all_students
            if q in str(row[0]).lower() or q in str(row[1]).lower()
        ]

        self._reload_results(rows)
        if len(rows) == 1:
            first = self.results_tree.get_children()[0]
            self.results_tree.selection_set(first)
            self.results_tree.focus(first)
            self._load_selected_student()

    def _on_result_select(self, event=None) -> None:
        sel = self.results_tree.selection()
        if not sel:
            return
        self._load_selected_student()

    def _load_selected_student(self, event=None) -> None:
        sel = self.results_tree.selection()
        if not sel:
            messagebox.showinfo("Select student", "Please select a student from the list.")
            return

        values = self.results_tree.item(sel[0], "values")
        if not values:
            return

        student_id, student_name, Department, level = values
        try:
            rows = student_attendance_db.get_student_course_summary(str(student_id))
        except Exception as exc:
            messagebox.showerror("Error", f"Could not load attendance summary:\n{exc}")
            return

        self._clear_summary()
        for course, title, present, late, absent, sessions, expected in rows:
            self.summary_tree.insert(
                "",
                "end",
                values=(course, title, present, late, absent, sessions, expected),
            )

        self._draw_attendance_graph(rows)

        if not rows:
            self.summary_tree.insert("", "end", values=("-", "No registered courses found", 0, 0, 0, 0, 0))
            self._draw_empty_graph("No registered courses found for this student.")

    def _on_close(self) -> None:
        try:
            self.root.destroy()
        finally:
            try:
                if self.parent is not None:
                    try:
                        self.parent.deiconify()
                        try:
                            self.parent.state("zoomed")
                        except Exception:
                            pass
                    except Exception:
                        pass
            except Exception:
                pass
