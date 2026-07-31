import tkinter as tk
from tkinter import messagebox
from ui.student_ui import StudentUI
from ui.course_ui import CourseUI
from ui.report_ui import ReportUI
from ui.course_registration_ui import CourseRegistrationUI
from utils import session
from database.course_db import get_all_courses
from database.db_config import get_cursor
from config import settings as app_settings
from ui.assets_utils import get_logo_image, apply_background_image
from ui import styles as ui_styles
from services.mobile_scanner import start_mobile_scanner_server, get_local_ip

_THEME = app_settings.get_theme()
BG_COLOR = _THEME["bg_color"]
PRIMARY = _THEME["primary_color"]
TEXT = _THEME["text_color"]


class DashboardUI:
    def __init__(self, root):
        self.root = root
        self.root.title("Dashboard")
        self.root.configure(bg=BG_COLOR)

        # Shared background image (background.png) behind all content
        self._bg_label = apply_background_image(self.root, (520, 520))

        # Container frame to keep content centred on large screens
        self.main_frame = tk.Frame(self.root, bg=BG_COLOR)
        self.main_frame.pack(expand=True)

        # Window icon and header logo
        self._icon_image = get_logo_image((64, 64))
        if self._icon_image is not None:
            try:
                self.root.iconphoto(False, self._icon_image)
            except Exception:
                pass

        self._logo_image = get_logo_image((80, 80))
        if self._logo_image is not None:
            tk.Label(self.main_frame, image=self._logo_image, bg=BG_COLOR, borderwidth=0).pack(pady=(10, 0))

        tk.Label(
            self.main_frame,
            text="Attendance Management System",
            font=("Arial", 20, "bold"),
            fg=TEXT,
            bg=BG_COLOR
        ).pack(pady=10)

        # ===== ROLE-BASED BUTTONS =====
        role = session.current_user.get("role") if session.current_user else None

        if role == "admin":
            self.create_button("Scan QR Code", self.open_scan)
            self.create_button("Manage Students", self.open_student)
            self.create_button("Manage Courses", self.open_courses)
            self.create_button("View Reports", self.open_reports)
            self.create_button("Settings", self.open_settings)

        elif role == "lecturer":
            # Lecturers can scan attendance and view their reports.
            self.create_button("Scan Attendance", self.open_scan)
            self.create_button("Register Students to Course", self.open_course_registration)
            self.create_button("Student Attendance", self.open_student_attendance)
            self.create_button("My Reports", self.open_reports)
            self.create_button("Settings", self.open_settings)

        self.create_button("Logout", self.logout)

        # Maximize dashboard on startup
        self.root.update_idletasks()
        self.root.state('zoomed')
        self.root.minsize(1000, 600)

    # ================= HELPERS =================

    def create_button(self, text, command):
        tk.Button(
            self.main_frame,
            text=text,
            width=30,
            font=ui_styles.BUTTON_FONT,
            command=command,
            **ui_styles.PRIMARY_BUTTON,
        ).pack(pady=10)

    def _apply_parent_state(self, child: tk.Toplevel) -> None:
        """If the dashboard is maximized, maximize the child window too."""
        try:
            if self.root.state() == "zoomed":
                child.state("zoomed")
        except Exception:
            pass

    # ================= NAVIGATION =================

    def open_scan(self):
        from ui.scan_qr_ui import ScanQRUI
        # Hide the dashboard while the scanner window is open
        try:
            was_zoomed = self.root.state() == "zoomed"
        except Exception:
            was_zoomed = False
        self.root.withdraw()
        window = tk.Toplevel(self.root)
        ScanQRUI(window, parent=self.root)
        try:
            window.state("zoomed")
        except Exception:
            pass

    def open_student(self):
        try:
            was_zoomed = self.root.state() == "zoomed"
        except Exception:
            was_zoomed = False
        self.root.withdraw()
        window = tk.Toplevel(self.root)
        StudentUI(window, parent=self.root)
        try:
            window.state("zoomed")
        except Exception:
            pass

    def open_course_registration(self):
        try:
            was_zoomed = self.root.state() == "zoomed"
        except Exception:
            was_zoomed = False

        self.root.withdraw()
        window = tk.Toplevel(self.root)
        CourseRegistrationUI(window, parent=self.root)
        try:
            window.state("zoomed")
        except Exception:
            pass

    def open_student_attendance(self):
        from ui.student_attendance_ui import StudentAttendanceUI

        try:
            was_zoomed = self.root.state() == "zoomed"
        except Exception:
            was_zoomed = False

        self.root.withdraw()
        window = tk.Toplevel(self.root)
        StudentAttendanceUI(window, parent=self.root)
        try:
            window.state("zoomed")
        except Exception:
            pass

    def open_mobile_scanner(self):
        """Open mobile scanner dialog showing QR code for phone access.
        
        Automatically detects lecturer's courses and passes the course code
        to the mobile scanner, so users don't need to enter it manually.
        """
        try:
            # Get the current lecturer's ID from session
            user = getattr(session, "current_user", None)
            if not isinstance(user, dict):
                messagebox.showerror("Mobile Scanner Error", "No active session")
                return
            
            lecturer_id = str(user.get("id", "")).strip()
            if not lecturer_id:
                messagebox.showerror("Mobile Scanner Error", "Cannot determine lecturer ID")
                return
            
            # Query lecturer's courses
            lecturer_courses = []
            with get_cursor(commit=False) as cursor:
                cursor.execute(
                    "SELECT course_code FROM courses WHERE lecturer_id = %s ORDER BY course_code",
                    (lecturer_id,)
                )
                rows = cursor.fetchall()
                lecturer_courses = [r["course_code"] for r in rows]
            
            if not lecturer_courses:
                messagebox.showerror(
                    "Mobile Scanner Error",
                    "No courses assigned to your account."
                )
                return
            
            # Choose which course to scan for
            if len(lecturer_courses) == 1:
                course_code = lecturer_courses[0]
            else:
                # Multiple courses: let lecturer choose
                from tkinter import simpledialog
                course_code = simpledialog.askstring(
                    "Select Course",
                    f"You teach {len(lecturer_courses)} courses. Which course to scan for?\n\n" +
                    "\n".join(f"{i+1}. {c}" for i, c in enumerate(lecturer_courses)),
                    parent=self.root
                )
                if not course_code:
                    return  # User cancelled
                
                # Validate selection
                if course_code not in lecturer_courses:
                    # Check if they entered a number
                    try:
                        idx = int(course_code) - 1
                        if 0 <= idx < len(lecturer_courses):
                            course_code = lecturer_courses[idx]
                        else:
                            messagebox.showerror("Invalid Selection", f"Please select 1-{len(lecturer_courses)}")
                            return
                    except ValueError:
                        if course_code not in lecturer_courses:
                            messagebox.showerror(
                                "Invalid Selection",
                                f"Course '{course_code}' not found. Please select from your courses."
                            )
                            return
            
            # Start the mobile scanner server with course code
            url = start_mobile_scanner_server(course_code=course_code)
            
            # Generate QR code for the URL (url already includes https://)
            import qrcode
            qr = qrcode.QRCode(version=1, box_size=10, border=5)
            qr.add_data(url)
            qr.make(fit=True)
            pil_image = qr.make_image(fill_color="black", back_color="white")
            
            # Convert PIL image to PhotoImage
            from PIL import ImageTk
            photo = ImageTk.PhotoImage(pil_image)
            
            # Create dialog window
            dialog = tk.Toplevel(self.root)
            dialog.title("Mobile Scanner")
            dialog.geometry("500x600")
            dialog.lift()
            dialog.focus()
            dialog.attributes('-topmost', True)
            
            tk.Label(
                dialog,
                text="Scan with your phone camera",
                font=("Arial", 14, "bold"),
                bg="white"
            ).pack(pady=10)
            
            tk.Label(
                dialog,
                text=f"Course: {course_code}",
                font=("Arial", 12, "bold"),
                bg="white",
                fg="#1e90ff"
            ).pack(pady=5)
            
            tk.Label(
                dialog,
                text=f"Or visit: {url}",
                font=("Arial", 11),
                bg="white",
                fg="#666"
            ).pack(pady=5)
            
            qr_label = tk.Label(dialog, image=photo, bg="white")
            dialog._qr_photo = photo  # type: ignore # Keep a reference on dialog to prevent garbage collection
            qr_label.pack(pady=20)
            
            tk.Label(
                dialog,
                text="Mobile scanner is now active.\nClose this window to stop.",
                font=("Arial", 10),
                bg="white",
                fg="#999",
                justify="center"
            ).pack(pady=10)
            
            def on_close():
                dialog.destroy()
            
            dialog.protocol("WM_DELETE_WINDOW", on_close)
            messagebox.showinfo(
                "Mobile Scanner Started",
                f"Scanning for: {course_code}\n\nOpen this URL on your phone:\n{url}\n\nOr scan the QR code above"
            )
            dialog.attributes('-topmost', False)  # Allow other windows to come to front now
            
        except Exception as e:
            messagebox.showerror("Mobile Scanner Error", f"Could not start mobile scanner:\n{e}")


    def open_courses(self):
        try:
            was_zoomed = self.root.state() == "zoomed"
        except Exception:
            was_zoomed = False
        self.root.withdraw()
        window = tk.Toplevel(self.root)
        CourseUI(window, parent=self.root)
        try:
            window.state("zoomed")
        except Exception:
            pass

    def open_reports(self):
        courses = get_all_courses()
        # If a lecturer is logged in, only consider their own courses.
        try:
            user = session.current_user
        except Exception:
            user = None
        role = user.get("role") if isinstance(user, dict) else None
        if role == "lecturer" and isinstance(user, dict):
            lecturer_id = str(user.get("id", ""))
            courses = [c for c in courses if str(c[3]) == lecturer_id]

        if not courses:
            messagebox.showinfo("Reports", "No courses available for your account.")
            return

        # If there's exactly one course for this lecturer, open its report directly
        if role == "lecturer" and len(courses) == 1:
            course_code = courses[0][0]
            try:
                was_zoomed = self.root.state() == "zoomed"
            except Exception:
                was_zoomed = False
            report_win = tk.Toplevel(self.root)
            ReportUI(report_win, parent=self.root, course_code=course_code)
            self.root.withdraw()
            try:
                report_win.state("zoomed")
            except Exception:
                pass
            return

        # Otherwise fall back to the course selection dialog (useful for admins
        # or lecturers with multiple courses).
        try:
            was_zoomed = self.root.state() == "zoomed"
        except Exception:
            was_zoomed = False
        window = tk.Toplevel(self.root)
        window.title("Select Course")
        window.geometry("300x200")
        try:
            window.state("zoomed")
        except Exception:
            pass

        tk.Label(window, text="Select Course").pack(pady=10)

        # get_all_courses returns tuples:
        # (course_code, title, department_id, lecturer_id, credit_hours, grace_minutes)
        course_codes = [c[0] for c in courses]

        course_var = tk.StringVar(value=course_codes[0])
        tk.OptionMenu(window, course_var, *course_codes).pack()

        def open_selected():
            course = course_var.get()  # this is the selected course_code string
            try:
                window_was_zoomed = window.state() == "zoomed"
            except Exception:
                window_was_zoomed = False
            window.destroy()
            report_win = tk.Toplevel(self.root)
            ReportUI(report_win, parent=self.root, course_code=course)
            self.root.withdraw()
            try:
                report_win.state("zoomed")
            except Exception:
                pass

        tk.Button(window, text="Open Report", command=open_selected).pack(pady=15)

    def open_settings(self):
        from ui.settings_ui import SettingsUI
        try:
            was_zoomed = self.root.state() == "zoomed"
        except Exception:
            was_zoomed = False

        self.root.withdraw()
        win = tk.Toplevel(self.root)
        SettingsUI(win, parent=self.root)
        try:
            win.state("zoomed")
        except Exception:
            pass

    def logout(self):
        # Confirm logout with the user; allow Cancel to abort
        if not messagebox.askokcancel('Confirm Logout', 'Are you sure you want to log out?'):
            return

        try:
            was_zoomed = self.root.state() == "zoomed"
        except Exception:
            was_zoomed = False

        # clear session
        try:
            session.logout()
        except Exception:
            pass

        # close current window and show login UI
        try:
            self.root.destroy()
        except Exception:
            pass

        # Launch login screen in a fresh root (mirrors LoginUI behavior)
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
            # if launching login UI fails, exit silently
            pass
