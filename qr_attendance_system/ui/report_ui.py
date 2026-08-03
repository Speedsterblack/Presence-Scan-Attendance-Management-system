import tkinter as tk
from tkinter import ttk, messagebox
from datetime import date, datetime, timedelta

from database import attendance_db  # changed
from config import settings as app_settings
from ui.assets_utils import apply_background_image, get_logo_image
from ui import styles as ui_styles

class ReportUI:
    def __init__(self, root, parent, course_code):
        self.root = root
        self.parent = parent
        self.course_code = course_code

        # Track the date the lecturer is viewing; defaults to today.
        self._current_date: date = date.today()

        self.root.title(f"Attendance Report - {course_code}")
        self.root.protocol("WM_DELETE_WINDOW", self.go_back)

        # Apply theme for a consistent look with the rest of the app
        theme = app_settings.get_theme()
        bg = theme["bg_color"]
        fg = theme["text_color"]
        primary = theme["primary_color"]
        self.root.configure(bg=bg)

        # Subtle centered background image behind content
        self._bg_label = apply_background_image(self.root, (520, 520))

        # Small header logo
        self._logo_image = get_logo_image((64, 64), master=root)
        if self._logo_image is not None:
            tk.Label(root, image=self._logo_image, bg=bg, borderwidth=0).pack(pady=(8, 0))

        title = tk.Label(
            root,
            text=f"Attendance Report ({course_code})",
            font=ui_styles.SUBTITLE_FONT,
            bg=bg,
            fg=fg,
        )
        title.pack(pady=10)

        # Date filter row
        filter_frame = tk.Frame(root, bg=bg)
        filter_frame.pack(fill="x", padx=10, pady=(0, 6))
        tk.Label(filter_frame, text="Date (YYYY-MM-DD):", bg=bg, fg=fg).pack(side="left")
        self._date_var = tk.StringVar(master=root, value=self._current_date.strftime("%Y-%m-%d"))
        date_entry = tk.Entry(filter_frame, textvariable=self._date_var, width=12)
        date_entry.pack(side="left", padx=(4, 8))
        date_entry.bind("<Return>", self._on_date_entry_change)

        tk.Button(
            filter_frame,
            text="Today",
            width=8,
            font=ui_styles.BUTTON_FONT,
            command=self._on_today_clicked,
            **ui_styles.SECONDARY_BUTTON,
        ).pack(side="left", padx=(0, 6))
        tk.Button(
            filter_frame,
            text="◀",
            width=3,
            font=ui_styles.BUTTON_FONT,
            command=lambda: self._shift_date(-1),
            **ui_styles.SECONDARY_BUTTON,
        ).pack(side="left", padx=(0, 4))
        tk.Button(
            filter_frame,
            text="▶",
            width=3,
            font=ui_styles.BUTTON_FONT,
            command=lambda: self._shift_date(1),
            **ui_styles.SECONDARY_BUTTON,
        ).pack(side="left")

        # Container for student list (left) and summary chart (right)
        content = tk.Frame(root, bg=bg)
        content.pack(fill="both", expand=True, padx=10, pady=10)

        left = tk.Frame(content, bg=bg)
        left.pack(side="left", fill="both", expand=True)

        right = tk.Frame(content, bg=bg)
        right.pack(side="left", fill="both", expand=True, padx=(10, 0))

        # Treeview of students and their attendance status
        columns = ("student_id", "name", "status")
        self.tree = ttk.Treeview(left, columns=columns, show="headings", height=12)
        self.tree.heading("student_id", text="Student ID")
        self.tree.heading("name", text="Student Name")
        self.tree.heading("status", text="Status")
        self.tree.column("student_id", width=120, anchor="w")
        self.tree.column("name", width=260, anchor="w")
        self.tree.column("status", width=90, anchor="center")
        self.tree.pack(side="left", fill="both", expand=True)

        scrollbar = ttk.Scrollbar(left, orient="vertical", command=self.tree.yview)
        scrollbar.pack(side="right", fill="y")
        self.tree.configure(yscrollcommand=scrollbar.set)

        # Simple per-course attendance chart (Present vs Absent)
        tk.Label(
            right,
            text="Attendance Summary",
            font=("Arial", 12, "bold"),
            bg=bg,
            fg=fg,
        ).pack(anchor="w")
        self.chart = tk.Canvas(right, bg="#ffffff", height=260, highlightthickness=0)
        self.chart.pack(fill="both", expand=True, pady=(4, 0))

        # Resolve function in a Pylance-safe way and cache it
        get_by_course = getattr(attendance_db, "get_attendance_by_course", None)

        # If `attendance_db` is a module that contains an object named `attendance_db`
        if get_by_course is None:
            db_obj = getattr(attendance_db, "attendance_db", None)
            get_by_course = getattr(db_obj, "get_attendance_by_course", None)

        if get_by_course is None:
            raise AttributeError(
                "No 'get_attendance_by_course' found in database.attendance_db"
            )

        self._get_by_course = get_by_course
        self._theme_bg = bg
        self._theme_fg = fg

        # initial load
        self._refresh()

        # Bottom button bar
        btn_frame = tk.Frame(self.root, bg=bg)
        btn_frame.pack(fill="x", padx=10, pady=(0, 10))
        back_btn = tk.Button(
            btn_frame,
            text="Back",
            width=10,
            font=ui_styles.BUTTON_FONT,
            command=self.go_back,
            **ui_styles.PRIMARY_BUTTON,
        )
        back_btn.pack(side="right")

        # Enlarge the report window to a comfortable size so
        # lists are readable without manual resizing.
        # Maximize report window on startup
        self.root.update_idletasks()
        self.root.state('zoomed')
        self.root.minsize(1000, 650)

    def _set_current_date(self, new_date: date) -> None:
        self._current_date = new_date
        self._date_var.set(self._current_date.strftime("%Y-%m-%d"))
        self._refresh()

    def _shift_date(self, days: int) -> None:
        if not days:
            return
        today = date.today()
        candidate = self._current_date + timedelta(days=days)
        if candidate > today:
            return
        self._set_current_date(candidate)

    def _on_today_clicked(self) -> None:
        self._set_current_date(date.today())

    def _on_date_entry_change(self, event=None) -> None:
        raw = (self._date_var.get() or "").strip()
        try:
            parsed = datetime.strptime(raw, "%Y-%m-%d").date()
        except Exception:
            messagebox.showerror("Invalid date", "Please enter a valid date in YYYY-MM-DD format.")
            self._date_var.set(self._current_date.strftime("%Y-%m-%d"))
            return

        today = date.today()
        if parsed > today:
            messagebox.showerror("Invalid date", "You can only select today or previous dates.")
            self._date_var.set(self._current_date.strftime("%Y-%m-%d"))
            return

        self._set_current_date(parsed)

    def _refresh(self) -> None:
        # clear existing rows
        for iid in self.tree.get_children():
            self.tree.delete(iid)

        try:
            records = self._get_by_course(self.course_code, self._current_date)
        except TypeError:
            # fallback if older signature without date is present
            records = self._get_by_course(self.course_code)

        present_count = 0
        late_count = 0
        total_count = 0

        for student_id, student_name, course, status in records:
            self.tree.insert("", tk.END, values=(student_id, student_name, status))
            total_count += 1
            if status == "Present":
                present_count += 1
            elif status == "Late":
                late_count += 1

        self._draw_chart(present_count + late_count, total_count, self._theme_bg, self._theme_fg)

    def _draw_chart(self, present: int, total: int, bg: str, fg: str) -> None:
        """Draw a simple Present vs Absent bar for this course."""

        self.chart.delete("all")

        if total <= 0:
            self.chart.create_text(
                10,
                20,
                anchor="nw",
                text="No attendance records for this course.",
                fill="#2c3e50",
            )
            return

        absent = max(total - present, 0)
        present_ratio = present / float(total)
        absent_ratio = absent / float(total)

        w = max(260, self.chart.winfo_width() or 260)
        h = max(200, self.chart.winfo_height() or 200)

        padding_x = 80
        padding_top = 30
        padding_bottom = 40

        bar_area_height = max(80, h - padding_top - padding_bottom)

        # Single stacked bar centred horizontally
        bar_width = 80
        cx = w / 2.0
        x0 = cx - bar_width / 2.0
        x1 = cx + bar_width / 2.0

        # grid and labels
        for pct in (0, 25, 50, 75, 100):
            y = padding_top + bar_area_height * (1 - pct / 100.0)
            self.chart.create_line(
                padding_x - 4,
                y,
                w - padding_x + 4,
                y,
                fill="#eeeeee",
            )
            self.chart.create_text(
                padding_x - 8,
                y,
                anchor="e",
                text=f"{pct}%",
                fill="#2c3e50",
            )

        y_bottom = padding_top + bar_area_height

        # Present segment (green)
        present_h = bar_area_height * present_ratio
        y0 = y_bottom - present_h
        if present_h > 0:
            self.chart.create_rectangle(x0, y0, x1, y_bottom, fill="#0EB316", outline="")

        # Absent segment (red) above present
        absent_h = bar_area_height * absent_ratio
        y1 = y0
        y0_abs = y1 - absent_h
        if absent_h > 0:
            self.chart.create_rectangle(x0, y0_abs, x1, y1, fill="#e42727", outline="")

        # Legend below bar
        legend_y = padding_top + bar_area_height + 10
        legend_x = cx - 80
        self.chart.create_rectangle(legend_x, legend_y, legend_x + 14, legend_y + 14, fill="#0EB316", outline="")
        self.chart.create_text(legend_x + 20, legend_y + 7, anchor="w", text="Present", fill="#2c3e50")
        legend_x += 90
        self.chart.create_rectangle(legend_x, legend_y, legend_x + 14, legend_y + 14, fill="#e42727", outline="")
        self.chart.create_text(legend_x + 20, legend_y + 7, anchor="w", text="Absent", fill="#2c3e50")

    def go_back(self):
        self.root.destroy()
        try:
            self.parent.deiconify()
            try:
                self.parent.state("zoomed")
            except Exception:
                pass
        except Exception:
            pass
