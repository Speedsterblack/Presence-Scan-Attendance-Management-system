import tkinter as tk
from tkinter import ttk, messagebox
import csv
import os
from datetime import datetime, date, timedelta

from database import analytics_db
from utils import session
from ui.course_ui import CourseUI
from ui.manage_lecturers_ui import ManageLecturersUI
from ui.student_ui import StudentUI
from config import settings as app_settings
from ui.assets_utils import get_logo_image, apply_background_image
from ui import styles as ui_styles

_THEME = app_settings.get_theme()
BG_COLOR = _THEME["bg_color"]
PRIMARY = _THEME["primary_color"]
TEXT = _THEME["text_color"]

# Dedicated background for the chart area; always white so
# the graph stands out clearly regardless of theme.
CHART_BG = "#ffffff"
# Use a dark, high-contrast text color for anything drawn
# on top of the white chart background so labels remain
# readable even when the overall app theme is dark.
CHART_TEXT = "#2c3e50"


def attendance_count_per_course():
    """Get attendance count per course from database."""
    fn = getattr(analytics_db, "get_attendance_count_per_course", None)
    if callable(fn):
        return fn()

    # fallback for alternate naming
    fn = getattr(analytics_db, "attendance_count_per_course", None)
    if callable(fn):
        return fn()

    raise AttributeError(
        "analytics_db has no callable 'get_attendance_count_per_course' "
        "or 'attendance_count_per_course'"
    )


def late_count_per_course():
    """Get late arrival count per course from database."""
    fn = getattr(analytics_db, "get_late_count_per_course", None)
    if callable(fn):
        return fn()

    # fallback for alternate naming
    fn = getattr(analytics_db, "late_count_per_course", None)
    if callable(fn):
        return fn()

    raise AttributeError(
        "analytics_db has no callable 'get_late_count_per_course' "
        "or 'late_count_per_course'"
    )


def attendance_breakdown_per_course(target_date: date | None = None):
    """Get per-course (present, absent, late, total) breakdown for a date."""

    fn = getattr(analytics_db, "get_attendance_breakdown_per_course", None)
    if callable(fn):
        return fn(target_date)

    raise AttributeError(
        "analytics_db has no callable 'get_attendance_breakdown_per_course'"
    )


class AdminDashboardUI:
    def __init__(self, root):
        self.root = root
        root.title("Admin Dashboard")
        root.configure(bg=BG_COLOR)

        # Subtle centered background image behind content
        self._bg_label = apply_background_image(root, (520, 520))

        self._icon_image = get_logo_image((64, 64), master=root)
        if self._icon_image is not None:
            try:
                root.iconphoto(False, self._icon_image)
            except Exception:
                pass

        self._logo_image = get_logo_image((140, 140), master=root)
        if self._logo_image is not None:
            logo_lbl = tk.Label(root, image=self._logo_image, bg=BG_COLOR, borderwidth=0)
            setattr(logo_lbl, "image", self._logo_image)
            logo_lbl.pack(pady=(8, 0))

        tk.Label(
            root,
            text="Admin Analytics Dashboard",
            font=ui_styles.SUBTITLE_FONT,
            bg=BG_COLOR,
            fg=TEXT,
        ).pack(pady=4)

        # Track the currently selected date for analytics
        self._current_date: date = date.today()

        # Top controls
        btn_frame = tk.Frame(root, bg=BG_COLOR)
        btn_frame.pack(fill='x', padx=8, pady=6)

        tk.Button(
            btn_frame,
            text="Manage Courses",
            width=16,
            font=ui_styles.BUTTON_FONT,
            command=self.open_course_ui,
            **ui_styles.PRIMARY_BUTTON,
        ).pack(side="left", padx=6)
        tk.Button(
            btn_frame,
            text="Manage Students",
            width=16,
            font=ui_styles.BUTTON_FONT,
            command=self.open_student_ui,
            **ui_styles.PRIMARY_BUTTON,
        ).pack(side="left", padx=6)
        tk.Button(
            btn_frame,
            text="Manage Lecturers",
            width=16,
            font=ui_styles.BUTTON_FONT,
            command=self.open_lecturer_ui,
            **ui_styles.PRIMARY_BUTTON,
        ).pack(side="left", padx=6)
        tk.Button(
            btn_frame,
            text="Student Attendance",
            width=16,
            font=ui_styles.BUTTON_FONT,
            command=self.open_student_attendance,
            **ui_styles.SECONDARY_BUTTON,
        ).pack(side="left", padx=6)
        tk.Button(
            btn_frame,
            text="Special Days",
            width=14,
            font=ui_styles.BUTTON_FONT,
            command=self.open_special_days,
            **ui_styles.SECONDARY_BUTTON,
        ).pack(side="left", padx=6)
        tk.Button(
            btn_frame,
            text="Account",
            width=10,
            font=ui_styles.BUTTON_FONT,
            command=self.open_account,
            **ui_styles.SECONDARY_BUTTON,
        ).pack(side='left', padx=6)
        tk.Button(
            btn_frame,
            text="Settings",
            width=10,
            font=ui_styles.BUTTON_FONT,
            command=self.open_settings,
            **ui_styles.SECONDARY_BUTTON,
        ).pack(side='left', padx=6)
        tk.Button(
            btn_frame,
            text="Export CSV",
            width=10,
            font=ui_styles.BUTTON_FONT,
            command=self.export_csv,
            **ui_styles.SECONDARY_BUTTON,
        ).pack(side="left", padx=6)
        tk.Button(
            btn_frame,
            text="Logout",
            width=10,
            font=ui_styles.BUTTON_FONT,
            command=self.logout,
            **ui_styles.DANGER_BUTTON,
        ).pack(side="right", padx=6)

        # Date filter controls so admins can browse previous days
        filter_frame = tk.Frame(root, bg=BG_COLOR)
        filter_frame.pack(fill='x', padx=8, pady=(0, 4))
        tk.Label(filter_frame, text="Date (YYYY-MM-DD):", bg=BG_COLOR, fg=TEXT).pack(side="left")
        self._date_var = tk.StringVar(master=root, value=self._current_date.strftime("%Y-%m-%d"))
        date_entry = tk.Entry(filter_frame, textvariable=self._date_var, width=12)
        date_entry.pack(side="left", padx=(4, 8))
        date_entry.bind("<Return>", self._on_date_entry_change)


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
            text="Today",
            width=8,
            font=ui_styles.BUTTON_FONT,
            command=self._on_today_clicked,
            **ui_styles.SECONDARY_BUTTON,
        ).pack(side="left", padx=(0, 6))

        tk.Button(
            filter_frame,
            text="▶",
            width=3,
            font=ui_styles.BUTTON_FONT,
            command=lambda: self._shift_date(1),
            **ui_styles.SECONDARY_BUTTON,
        ).pack(side="left")

        # Main content frames
        content = tk.Frame(root, bg=BG_COLOR)
        content.pack(fill='both', expand=True, padx=8, pady=6)

        # Left: Summary treeview for attendance breakdown (fixed width)
        left = tk.Frame(content, bg=BG_COLOR)
        # Keep this panel from stretching horizontally so the
        # chart on the right can occupy more space.
        left.pack(side='left', fill='y', expand=False, padx=(0,8))

        tk.Label(left, text="Attendance Summary per Course", font=("Arial", 12, "bold"), bg=BG_COLOR, fg=TEXT).pack(anchor='w')
        self.summary_tree = ttk.Treeview(
            left,
            columns=("course", "present", "late", "absent"),
            show='headings',
            height=12,
        )
        self.summary_tree.heading('course', text='Course', anchor='w')
        self.summary_tree.heading('present', text='Present', anchor='center')
        self.summary_tree.heading('late', text='Late', anchor='center')
        self.summary_tree.heading('absent', text='Absent', anchor='center')
        self.summary_tree.column('course', width=200)
        self.summary_tree.column('present', width=80, anchor='center')
        self.summary_tree.column('late', width=80, anchor='center')
        self.summary_tree.column('absent', width=80, anchor='center')
        self.summary_tree.pack(fill='x', expand=False, pady=(4,10))

        # Right: enlarged bar chart canvas
        right = tk.Frame(content, bg=BG_COLOR)
        right.pack(side='left', fill='both', expand=True)
        tk.Label(right, text="Attendance Chart", font=("Arial", 12, "bold"), bg=BG_COLOR, fg=TEXT).pack(anchor='w')
        # Give the chart a larger default height; it will also
        # grow horizontally with the window. Use a dedicated
        # chart background so the graph stands out as its own
        # panel.
        self.chart = tk.Canvas(right, bg=CHART_BG, height=380, highlightthickness=0)
        self.chart.pack(fill='both', expand=True, pady=(4,10))
        # Redraw the chart whenever the canvas is resized so
        # elements like the legend stay anchored in the actual
        # top-right corner of the current chart area.
        self.chart.bind("<Configure>", self._on_chart_resize)

        # status line
        self.status = tk.Label(root, text="", anchor='w', bg=BG_COLOR, fg=TEXT)
        self.status.pack(fill='x', padx=8, pady=(0,6))

        self.notify_label = tk.Label(root, text="", anchor='w', bg=BG_COLOR, fg=TEXT, font=('Arial', 10, 'bold'))
        self.notify_label.pack(fill='x', padx=8, pady=(0,6))

        # Ensure the admin dashboard opens at a comfortable, large size
        # similar to a full application window.
        # Maximize admin dashboard on startup
        root.update_idletasks()
        root.state('zoomed')
        root.minsize(1100, 700)

        self._auto_id = None
        self._last_breakdown = []
        self._account_win = None

        # initial load
        self.refresh_data()

        # start periodic auto-refresh if enabled in settings so
        # the dashboard data stays up to date without manual
        # interaction
        try:
            if app_settings.get_admin_auto_refresh_enabled():
                self._start_auto()
        except Exception:
            pass

    def _apply_parent_state(self, child: tk.Toplevel) -> None:
        """If the admin dashboard is maximized, maximize the child window too."""
        try:
            if self.root.state() == "zoomed":
                child.state("zoomed")
        except Exception:
            pass

    def _set_current_date(self, new_date: date) -> None:
        """Update the active analytics date and refresh the view."""
        try:
            self._current_date = new_date
            self._date_var.set(self._current_date.strftime("%Y-%m-%d"))
        except Exception:
            pass
        self.refresh_data()

    def _shift_date(self, days: int) -> None:
        # Arrow navigation should only move between today and
        # previous days that actually have scheduled classes.
        if not days:
            return

        today = date.today()

        # Start from the next candidate day in the requested
        # direction, but never beyond today.
        if days > 0:
            # moving forward towards today
            candidate = self._current_date + timedelta(days=1)
            if candidate > today:
                # do not go into the future
                return
            step = 1
        else:
            # moving backwards in time
            candidate = self._current_date - timedelta(days=1)
            step = -1

        # Walk until we find a day that has classes scheduled,
        # or until we run out of reasonable history.
        tries = 0
        max_tries = 365  # one academic year of history
        while tries < max_tries:
            # never move past today into the future
            if candidate > today:
                break

            try:
                has_classes = analytics_db.has_classes_on(candidate)
            except Exception:
                has_classes = False

            if has_classes:
                self._set_current_date(candidate)
                return

            candidate = candidate + timedelta(days=step)
            tries += 1

        # If we got here, we didn't find another day with classes.
        if step < 0:
            messagebox.showinfo("No earlier classes", "No earlier days with scheduled classes were found.")
        else:
            messagebox.showinfo("No later classes", "There are no later days with scheduled classes.")

    def _on_today_clicked(self) -> None:
        self._set_current_date(date.today())

    def _on_date_entry_change(self, event=None) -> None:
        raw = (self._date_var.get() or "").strip()
        try:
            parsed = datetime.strptime(raw, "%Y-%m-%d").date()
        except Exception:
            messagebox.showerror("Invalid date", "Please enter a valid date in YYYY-MM-DD format.")
            # reset to current known-good value
            self._date_var.set(self._current_date.strftime("%Y-%m-%d"))
            return

        # Do not allow selecting dates in the future via the
        # filter; typed dates can still be days without classes.
        today = date.today()
        if parsed > today:
            messagebox.showerror("Invalid date", "You can only select today or previous dates.")
            self._date_var.set(self._current_date.strftime("%Y-%m-%d"))
            return
        self._set_current_date(parsed)

    def open_account(self):
        try:
            user = session.current_user
        except Exception:
            user = None

        if not user:
            messagebox.showerror('Error', 'No user session found')
            return

        # If an account window is already open, just focus it
        if self._account_win is not None and self._account_win.winfo_exists():
            try:
                self._account_win.lift()
                self._account_win.focus_force()
            except Exception:
                pass
            return

        win = tk.Toplevel(self.root)
        win.title('Account')
        win.geometry('360x220')
        self._account_win = win

        def _on_close():
            try:
                win.destroy()
            except Exception:
                pass
            self._account_win = None

        win.protocol("WM_DELETE_WINDOW", _on_close)

        tk.Label(win, text='Account Details', font=('Arial', 12, 'bold')).pack(pady=8)
        tk.Label(win, text=f"User: {user.get('id')}").pack(anchor='w', padx=12)
        tk.Label(win, text=f"Name: {user.get('name')}").pack(anchor='w', padx=12)
        tk.Label(win, text=f"Role: {user.get('role')}").pack(anchor='w', padx=12)

        # Only admins should see reset password for other accounts, but admin can reset their own password here
        tk.Button(win, text='Reset Password', bg='#1e90ff', fg='white', command=lambda: self._open_reset_password(win, user.get('id'))).pack(pady=12)
        tk.Button(win, text='Close', command=_on_close).pack()

    def _open_reset_password(self, parent, user_id):
        win = tk.Toplevel(parent)
        win.title('Reset Password')
        win.geometry('360x180')

        tk.Label(win, text=f'Reset password for {user_id}', font=('Arial', 11)).pack(pady=8)
        tk.Label(win, text='New password:').pack(anchor='w', padx=12)
        p1 = tk.Entry(win, show='*')
        p1.pack(fill='x', padx=12)
        tk.Label(win, text='Confirm password:').pack(anchor='w', padx=12, pady=(8,0))
        p2 = tk.Entry(win, show='*')
        p2.pack(fill='x', padx=12)

        def do_reset():
            np = p1.get().strip()
            c = p2.get().strip()
            if not np:
                messagebox.showerror('Error', 'Password cannot be empty')
                return
            if np != c:
                messagebox.showerror('Error', 'Passwords do not match')
                return
            try:
                from database.lecturer_db import update_password
                update_password(user_id, np)
                messagebox.showinfo('Success', 'Password updated')
                win.destroy()
                parent.destroy()
            except Exception as e:
                messagebox.showerror('Error', f'Could not update password:\n{e}')

        tk.Button(win, text='Update Password', bg='#1e90ff', fg='white', command=do_reset).pack(pady=12)
        tk.Button(win, text='Cancel', command=win.destroy).pack()

    def refresh_data(self):
        try:
            target_date = getattr(self, "_current_date", date.today())

            # clear summary tree
            for iid in self.summary_tree.get_children():
                self.summary_tree.delete(iid)

            # attendance breakdown per course (only courses scheduled
            # for today are included by the analytics helper)
            breakdown = attendance_breakdown_per_course(target_date)
            if not isinstance(breakdown, (list, tuple)):
                breakdown = []

            # remember last data so we can redraw cleanly on
            # canvas resize events
            self._last_breakdown = breakdown

            if not breakdown:
                # Differentiate between days with scheduled classes
                # that simply have no scans yet vs. days where no
                # timetable entries exist (weekends or unscheduled).
                try:
                    has_classes = analytics_db.has_classes_on(target_date)
                except Exception:
                    has_classes = False

                if has_classes:
                    self.status.config(text=f"No attendance recorded yet for classes on {target_date:%Y-%m-%d}.")
                else:
                    self.status.config(text=f"No classes scheduled on {target_date:%Y-%m-%d}.")
            else:
                # summary tree shows present, late and absent counts
                for course, present, absent, late, total in breakdown:
                    self.summary_tree.insert('', 'end', values=(course, present, late, absent))
                self.status.config(text=f"Loaded {len(breakdown)} courses for {target_date:%Y-%m-%d}")

            self._refresh_notifications(target_date)

            # draw stacked chart from breakdown rows
            self._draw_chart(breakdown)
        except Exception as e:
            self.status.config(text=f"Error loading analytics: {e}")
            try:
                self.notify_label.config(text="")
            except Exception:
                pass

    def _refresh_notifications(self, target_date: date) -> None:
        try:
            low = analytics_db.get_low_attendance_courses(target_date, threshold=75.0)
        except Exception:
            low = []

        if not low:
            text = "Notifications: no low-attendance alerts for this date."
        else:
            top = ", ".join(f"{code} ({rate}%)" for code, rate in low[:3])
            more = f" and {len(low) - 3} more" if len(low) > 3 else ""
            text = f"Notifications: low attendance in {top}{more}."

        try:
            self.notify_label.config(text=text)
        except Exception:
            pass

    def open_course_ui(self):
        try:
            was_zoomed = self.root.state() == "zoomed"
        except Exception:
            was_zoomed = False

        self.root.withdraw()
        top = tk.Toplevel(self.root)
        try:
            top.state('zoomed')
        except Exception:
            pass
        CourseUI(top, self.root)

        

    def open_student_ui(self):
        try:
            was_zoomed = self.root.state() == "zoomed"
        except Exception:
            was_zoomed = False

        self.root.withdraw()
        top = tk.Toplevel(self.root)
        try:
            top.state('zoomed')
        except Exception:
            pass
        StudentUI(top, self.root)

        

    def open_lecturer_ui(self):
        try:
            was_zoomed = self.root.state() == "zoomed"
        except Exception:
            was_zoomed = False

        self.root.withdraw()
        top = tk.Toplevel(self.root)
        try:
            top.state('zoomed')
        except Exception:
            pass
        ManageLecturersUI(top, self.root)

        

    def open_special_days(self):
        from ui.special_days_ui import SpecialDaysUI

        try:
            was_zoomed = self.root.state() == "zoomed"
        except Exception:
            was_zoomed = False

        self.root.withdraw()
        top = tk.Toplevel(self.root)
        try:
            top.state('zoomed')
        except Exception:
            pass
        SpecialDaysUI(top, self.root)

        

    def open_student_attendance(self):
        from ui.student_attendance_ui import StudentAttendanceUI

        try:
            was_zoomed = self.root.state() == "zoomed"
        except Exception:
            was_zoomed = False

        self.root.withdraw()
        top = tk.Toplevel(self.root)
        try:
            top.state('zoomed')
        except Exception:
            pass
        StudentAttendanceUI(top, self.root)

        

    def open_settings(self):
        from ui.settings_ui import SettingsUI

        try:
            was_zoomed = self.root.state() == "zoomed"
        except Exception:
            was_zoomed = False

        self.root.withdraw()
        top = tk.Toplevel(self.root)
        try:
            top.state('zoomed')
        except Exception:
            pass
        SettingsUI(top, self.root)

        

    def _on_chart_resize(self, event):
        """Redraw the chart using the current canvas size.

        This keeps the stacked bars and legend properly
        aligned with the right and top edges when the
        window is resized.
        """
        try:
            breakdown = getattr(self, "_last_breakdown", []) or []
            self._draw_chart(breakdown)
        except Exception:
            pass

    def _draw_chart(self, breakdown_rows):
        """Render a simple *percentage* stacked column chart.

        Each course is shown as a 100% bar split into
        present vs absent vs late attendance, based on the
        total number of students registered for that course.

        ``breakdown_rows`` is a list of
        (course_code, present, absent, late, total).
        """

        # rows: list of (course, present, absent, late, total)
        self.chart.delete('all')
        # keep canvas background in sync with the dedicated
        # chart panel color
        try:
            self.chart.configure(bg=CHART_BG)
        except Exception:
            pass
        if not breakdown_rows:
            self.chart.create_text(10, 20, anchor='nw', text='No data to chart', fill=CHART_TEXT)
            return

        # horizontal padding around the bar area; keep small so
        # the bars sit close to the y-axis labels, but large
        # enough that the left-most "100%" label is not clipped
        # by the canvas edge
        padding_x = 48
        padding_top = 30
        # extra bottom padding to accommodate course labels
        # and the legend underneath them
        padding_bottom = 70

        w = max(300, self.chart.winfo_width() or 500)
        h = max(260, self.chart.winfo_height() or 320)

        # available drawing area for bars
        bar_area_height = max(100, h - padding_top - padding_bottom)
        bar_area_width = max(100, w - 2 * padding_x)

        n = max(1, len(breakdown_rows))
        slot_width = bar_area_width / float(n)
        # Keep bars visually slim even when there are only
        # one or two courses by capping the maximum width.
        bar_width = min(slot_width * 0.6, 80)

        # y-axis percentage grid (0, 25, 50, 75, 100)
        for pct in (0, 25, 50, 75, 100):
            y = padding_top + bar_area_height * (1 - pct / 100.0)
            # draw a light grid line across the bar area and
            # label percentages just to the left of the bars
            self.chart.create_line(padding_x - 2, y, w - padding_x, y, fill='#eeeeee')
            self.chart.create_text(padding_x - 6, y, anchor='e', text=f"{pct}%", fill=CHART_TEXT)

        # draw one stacked vertical bar per course, starting close
        # to the y-axis so the first column appears near the labels
        for i, (course, present, absent, late, total) in enumerate(breakdown_rows):
            total = max(int(total or 0), 0)
            present = max(int(present or 0), 0)
            late = max(int(late or 0), 0)
            absent = max(int(absent or 0), 0)

            if total <= 0:
                present_ratio = late_ratio = absent_ratio = 0.0
            else:
                present_ratio = min(max(present / float(total), 0.0), 1.0)
                late_ratio = min(max(late / float(total), 0.0), 1.0)
                absent_ratio = min(max(absent / float(total), 0.0), 1.0)

            # base x so first bar is close to the y-axis; subsequent
            # bars are spaced evenly to the right.
            if n == 1:
                cx = padding_x + bar_width / 2 + 6
            else:
                cx = padding_x + bar_width / 2 + 6 + i * (slot_width)
            x0 = cx - bar_width / 2
            x1 = cx + bar_width / 2

            # present segment (bottom)
            on_h = bar_area_height * present_ratio
            y1 = padding_top + bar_area_height
            y0 = y1 - on_h
            if on_h > 0:
                self.chart.create_rectangle(x0, y0, x1, y1, fill="#0EB316", outline='')

            # late segment (middle)
            late_h = bar_area_height * late_ratio
            y2 = y0
            y0_late = y2 - late_h
            if late_h > 0:
                self.chart.create_rectangle(x0, y0_late, x1, y2, fill="#cccf09", outline='')

            # absent segment (top)
            abs_h = bar_area_height * absent_ratio
            y3 = y0_late
            y0_abs = y3 - abs_h
            if abs_h > 0:
                self.chart.create_rectangle(x0, y0_abs, x1, y3, fill="#e42727", outline='')

            # course label under the bar (above the legend)
            label_y = h - padding_bottom + 10
            self.chart.create_text(cx, label_y, anchor='n', text=str(course), fill=CHART_TEXT)

        # legend centered underneath the course labels so it
        # appears clearly lower than the course names but still
        # within the white chart area.
        legend_item_width = 110  # approx width of one "color + text" pair
        legend_total_width = legend_item_width * 3
        legend_start_x = padding_x + max(0, (bar_area_width - legend_total_width) / 2)
        legend_y = (h - padding_bottom + 10) + 24

        legend_x = legend_start_x
        self.chart.create_rectangle(legend_x, legend_y, legend_x + 14, legend_y + 14, fill='#0EB316', outline='')
        self.chart.create_text(legend_x + 20, legend_y + 7, anchor='w', text='Present', fill=CHART_TEXT)
        legend_x += legend_item_width
        self.chart.create_rectangle(legend_x, legend_y, legend_x + 14, legend_y + 14, fill='#cccf09', outline='')
        self.chart.create_text(legend_x + 20, legend_y + 7, anchor='w', text='Late', fill=CHART_TEXT)
        legend_x += legend_item_width
        self.chart.create_rectangle(legend_x, legend_y, legend_x + 14, legend_y + 14, fill='#e42727', outline='')
        self.chart.create_text(legend_x + 20, legend_y + 7, anchor='w', text='Absent', fill=CHART_TEXT)

    def export_csv(self):
        try:
            target_date = getattr(self, "_current_date", date.today())
            breakdown = attendance_breakdown_per_course(target_date)
            if not isinstance(breakdown, (list, tuple)):
                breakdown = []
            
            out_dir = os.path.join(os.getcwd(), 'reports')
            os.makedirs(out_dir, exist_ok=True)
            fname = os.path.join(out_dir, f'attendance_summary_{target_date.strftime("%Y%m%d")}_{datetime.now().strftime("%H%M%S")}.csv')
            with open(fname, 'w', newline='') as f:
                writer = csv.writer(f)
                writer.writerow(['Course', 'Present Count', 'Absent Count', 'Late Count', 'Total Registered'])
                for course, present, absent, late, total in breakdown:
                    writer.writerow([course, present, absent, late, total])
            messagebox.showinfo('Exported', f'Attendance summary exported to {fname}')
        except Exception as e:
            messagebox.showerror('Error', f'Failed to export CSV: {e}')

    def logout(self):
        if not messagebox.askokcancel('Confirm Logout', 'Are you sure you want to log out?'):
            return

        try:
            was_zoomed = self.root.state() == "zoomed"
        except Exception:
            was_zoomed = False

        try:
            self._stop_auto()
        except Exception:
            pass
        try:
            session.logout()
        except Exception:
            pass
        try:
            self.root.destroy()
        except Exception:
            pass
        try:
            from ui.login_ui import LoginUI
            new_root = tk.Tk()
            LoginUI(new_root)
            try:
                new_root.state("zoomed")
            except Exception:
                pass
            new_root.mainloop()
        except Exception:
            pass

    def _start_auto(self):
        # use the configured interval (seconds) from settings
        try:
            interval = app_settings.get_admin_auto_refresh_interval()
        except Exception:
            interval = 30
        self._stop_auto()
        self._auto_id = self.root.after(interval * 1000, self._auto_tick)
        self.status.config(text=f'Auto-refresh every {interval}s enabled')
        # persist setting
        try:
            app_settings.update_settings_for_current_role({
                "admin": {
                    "auto_refresh_enabled": True,
                    "auto_refresh_interval_seconds": interval,
                }
            })
        except Exception:
            pass

    def _stop_auto(self):
        if self._auto_id:
            try:
                self.root.after_cancel(self._auto_id)
            except Exception:
                pass
            self._auto_id = None
            self.status.config(text='Auto-refresh stopped')
            try:
                app_settings.update_settings_for_current_role({
                    "admin": {
                        "auto_refresh_enabled": False,
                    }
                })
            except Exception:
                pass

    def _auto_tick(self):
        self.refresh_data()
        try:
            interval = app_settings.get_admin_auto_refresh_interval()
        except Exception:
            interval = 30
        self._auto_id = self.root.after(interval * 1000, self._auto_tick)
