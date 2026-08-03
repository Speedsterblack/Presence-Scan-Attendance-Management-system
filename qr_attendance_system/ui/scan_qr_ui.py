import tkinter as tk
from tkinter import messagebox
import cv2
import winsound
from PIL import Image, ImageTk
from datetime import datetime, timedelta
from typing import Any, Callable, Dict, Optional, Set, Union

from utils import session
from qr.qr_scanner import scan_qr_live
from config import settings as app_settings
from ui.assets_utils import apply_background_image, get_logo_image
from ui import styles as ui_styles
import database.student_db as student_db
import database.attendance_db as attendance_db
import database.timetable_db as timetable_db
import database.lecturer_db as lecturer_db
import database.course_registration_db as course_registration_db
from services.mobile_scanner import start_mobile_scanner_server, get_mobile_scanner_url
import database.course_db as course_db


class ScanQRUI:

    # Accept both Tk and Toplevel so this class can be used
    # as a child window without type-checker errors.
    def __init__(
        self,
        root: Union[tk.Tk, tk.Toplevel],
        parent: Optional[Union[tk.Tk, tk.Toplevel]] = None,
    ) -> None:
        self.root = root
        self.parent = parent
        self.root.title("Scan Student QR Code")

        theme = app_settings.get_theme()
        self.bg_color = theme["bg_color"]
        self.primary_color = theme["primary_color"]
        self.text_color = theme["text_color"]

        self.root.configure(bg=self.bg_color)

        # Subtle centered background image behind scanner UI
        self._bg_label = apply_background_image(self.root, (520, 520))

        # Small header logo above the scanner title
        self._logo_image = get_logo_image((72, 72), master=self.root)
        if self._logo_image is not None:
            tk.Label(self.root, image=self._logo_image, bg=self.bg_color, borderwidth=0).pack(pady=(10, 0))

        cv2.destroyAllWindows()

        # ===== STATE =====
        self.running: bool = True
        self.scanning_enabled: bool = False
        self.after_id: Optional[str] = None
        self.processing_scan: bool = False
        self.last_scan_time: Dict[str, datetime] = {}
        self.scan_cooldown: int = app_settings.get_scanner_cooldown()
        self.scanned_today: Set[str] = set()
        self.current_course: Optional[Dict[str, Any]] = None

        # keep image reference for tkinter (avoid assigning unknown attributes to Label)
        self._video_img: Optional[ImageTk.PhotoImage] = None

        # ===== CAMERA =====
        self.cap = cv2.VideoCapture(0, cv2.CAP_DSHOW)
        self.cap.set(cv2.CAP_PROP_FRAME_WIDTH, 840)
        self.cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 680)

        self.root.protocol("WM_DELETE_WINDOW", self.on_close)

        # ===== UI =====
        tk.Label(
            self.root,
            text="QR Code Scanner",
            font=("Arial", 20, "bold"),
            fg=self.text_color,
            bg=self.bg_color,
        ).pack(pady=10)

        # Brief hint so users understand why some scans may be rejected.
        self.info_label = tk.Label(
            self.root,
            text="Only students registered for the current course can be marked present.",
            font=("Arial", 9),
            fg=self.text_color,
            bg=self.bg_color,
        )
        self.info_label.pack(pady=(0, 4))

        self.class_label = tk.Label(
            self.root,
            text="No class in session",
            font=("Arial", 11, "bold"),
            fg=self.text_color,
            bg=self.bg_color,
        )
        self.class_label.pack()

        self.video_label = tk.Label(
            self.root,
            bg="black",
            width=840,
            height=680,
        )
        self.video_label.pack(pady=10)

        # Control buttons frame
        controls_frame = tk.Frame(self.root, bg=self.bg_color)
        controls_frame.pack(pady=10)

        self.start_button = tk.Button(
            controls_frame,
            text="Start Scanning",
            font=ui_styles.BUTTON_FONT,
            command=self.start_scanning,
            **ui_styles.PRIMARY_BUTTON,
        )
        self.start_button.pack(side="left", padx=5)

        self.stop_button = tk.Button(
            controls_frame,
            text="Stop Scanning",
            font=ui_styles.BUTTON_FONT,
            command=self.stop_scanning,
            **ui_styles.PRIMARY_BUTTON,
        )
        self.stop_button.pack(side="left", padx=5)
        self.stop_button.config(state="disabled")

        self.counter_label = tk.Label(
            self.root,
            text="Scanned Today: 0",
            font=("Arial", 10, "bold"),
            bg=self.bg_color,
            fg=self.text_color,
        )
        self.counter_label.place(x=10, y=10)

        self.notification = tk.Label(
            self.root,
            text="",
            font=("Arial", 10, "bold"),
            fg="white",
            padx=10,
            pady=5,
        )
        self.notification.place_forget()

        # Top-right Back button
        self.back_button = tk.Button(
            self.root,
            text="Back",
            width=10,
            font=ui_styles.BUTTON_FONT,
            command=self.on_close,
            **ui_styles.PRIMARY_BUTTON,
        )
        self.back_button.place(relx=1.0, x=-10, y=10, anchor="ne")

        # Mobile Scanner button (top-right, above Back)
        self.mobile_button = tk.Button(
            self.root,
            text="📱 Mobile Scanner",
            width=16,
            font=ui_styles.BUTTON_FONT,
            command=self.open_mobile_scanner,
            **ui_styles.PRIMARY_BUTTON,
        )
        self.mobile_button.place(relx=1.0, x=-10, y=50, anchor="ne")

        # Ensure the scanner window opens big enough for the
        # video preview and labels.
        self.root.update_idletasks()
        # Use the window's requested size with sensible minimums,
        # but avoid locking the user into a huge minimum when
        # resizing or maximizing.
        req_w = self.root.winfo_reqwidth()
        req_h = self.root.winfo_reqheight()
        win_w = max(req_w, 960)
        win_h = max(req_h, 600)
        self.root.geometry(f"{win_w}x{win_h}")
        # Allow some flexibility when restoring from maximized state.
        self.root.minsize(800, 500)

        self.update_frame()

    # ================= INTERNAL HELPERS =================

    def _resolve_callable(
        self,
        module_obj: Any,
        func_name: str,
        nested_obj_name: str
    ) -> Optional[Callable[..., Any]]:
        fn = getattr(module_obj, func_name, None)
        if callable(fn):
            return fn

        nested_obj = getattr(module_obj, nested_obj_name, None)
        fn = getattr(nested_obj, func_name, None)
        if callable(fn):
            return fn

        return None

    # ================= UI HELPERS =================

    def start_scanning(self) -> None:
        self.scanning_enabled = True
        self.start_button.config(state="disabled")
        self.stop_button.config(state="normal")
        self.show_notification("Scanning started", True)

    def stop_scanning(self) -> None:
        self.scanning_enabled = False
        self.start_button.config(state="normal")
        self.stop_button.config(state="disabled")
        self.show_notification("Scanning stopped", True)

    def open_mobile_scanner(self) -> None:
        """Open the mobile scanner on the current device's local network."""
        try:
            course_code = ""
            # Try to auto-detect lecturer's course
            try:
                cursor = None
                from database.db_config import get_connection
                conn = get_connection()
                if conn:
                    cursor = conn.cursor()
                    lecturer_id = None
                    if isinstance(session.current_user, dict):
                        lecturer_id = session.current_user.get("id")
                    
                    if lecturer_id and cursor:
                        cursor.execute(
                            "SELECT DISTINCT c.course_code FROM courses c "
                            "WHERE c.lecturer_id = %s LIMIT 1",
                            (lecturer_id,)
                        )
                        row = cursor.fetchone()
                        if row:
                            course_code = row[0]
                    
                    if cursor:
                        cursor.close()
                    if conn:
                        conn.close()
            except Exception as e:
                print(f"Auto-detect course failed: {e}")
            
            # Start Flask server with auto-detected course
            url = start_mobile_scanner_server(course_code=course_code)
            
            if url:
                self._show_qr_code_dialog(url)
                self.show_notification("Mobile scanner ready", True)
            else:
                messagebox.showerror("Error", "Failed to start mobile scanner", parent=self.root)
        except Exception as e:
            messagebox.showerror("Error", f"Mobile scanner error: {str(e)}", parent=self.root)

    def _show_qr_code_dialog(self, url: str) -> None:
        """Display a dialog with the QR code and URL for the mobile scanner."""
        try:
            import qrcode as qr_lib
            
            # Generate QR code
            qr = qr_lib.QRCode(version=1, box_size=10, border=5)
            qr.add_data(url)
            qr.make(fit=True)
            pil_img = qr.make_image(fill_color="black", back_color="white")
            
            # Convert to PhotoImage for Tkinter
            qr_photo = ImageTk.PhotoImage(pil_img, master=self.root)
            
            # Create dialog window
            dialog = tk.Toplevel(self.root)
            dialog.title("Mobile Scanner")
            dialog.resizable(False, False)
            
            theme = app_settings.get_theme()
            bg = theme["bg_color"]
            fg = theme["text_color"]
            dialog.configure(bg=bg)
            
            # Title
            tk.Label(
                dialog,
                text="Mobile Scanner",
                font=("Arial", 14, "bold"),
                bg=bg,
                fg=fg
            ).pack(pady=10)
            
            # QR code
            qr_label = tk.Label(dialog, image=qr_photo, bg=bg)
            setattr(dialog, "qr_photo", qr_photo)  # Keep a reference to prevent garbage collection
            qr_label.pack(pady=10)
            
            # URL text
            tk.Label(
                dialog,
                text=url,
                font=("Arial", 10),
                bg=bg,
                fg=fg,
                wraplength=400
            ).pack(pady=10)
            
            # Instructions
            tk.Label(
                dialog,
                text="Scan this QR code from your phone camera\nor open the URL in your browser.",
                font=("Arial", 9),
                bg=bg,
                fg=fg
            ).pack(pady=5)
            
            tk.Label(
                dialog,
                text="Desktop and phone must be on the same network.",
                font=("Arial", 9, "italic"),
                bg=bg,
                fg=fg
            ).pack(pady=(5, 15))
            
            # Close button
            tk.Button(
                dialog,
                text="Close",
                command=dialog.destroy,
                font=ui_styles.BUTTON_FONT,
                **ui_styles.PRIMARY_BUTTON,
            ).pack(pady=10)
            
            dialog.geometry("450x550")
            dialog.grab_set()
            
        except Exception as e:
            messagebox.showerror("Error", f"Could not generate QR code: {str(e)}", parent=self.root)

    def show_notification(self, message: str, success: bool = True) -> None:
        color = "#2e7d32" if success else "#c62828"
        self.notification.config(text=message, bg=color)
        # Show notifications just below the Back button so they
        # remain fully visible and are not covered.
        self.notification.place(relx=1.0, x=-10, y=50, anchor="ne")
        self.root.after(2000, self.notification.place_forget)

    def play_beep(self, success: bool = True) -> None:
        winsound.Beep(1200 if success else 600, 150 if success else 300)

    def flash_border(self, color: str) -> None:
        self.video_label.config(highlightthickness=4, highlightbackground=color)
        self.root.after(300, lambda: self.video_label.config(highlightthickness=0))

    # ================= CAMERA LOOP =================

    def update_frame(self) -> None:
        if not self.running:
            return

        ret, frame = self.cap.read()
        if not ret:
            self.after_id = self.root.after(50, self.update_frame)
            return

        # Update current course with safe fallbacks
        self.current_course = None
        get_current_course = self._resolve_callable(
            timetable_db, "get_current_course", "timetable_db"
        )
        if get_current_course is not None:
            try:
                current = get_current_course()
                if isinstance(current, dict):
                    self.current_course = current
            except Exception:
                self.current_course = None

        if self.current_course:
            lecturer_display = (
                self.current_course.get("lecturer_name")
                or self.current_course.get("lecturer")
                or str(self.current_course.get("lecturer_id", ""))
            )
            self.class_label.config(
                text=f"{self.current_course.get('course_code','')} - "
                     f"{self.current_course.get('course_name','')} "
                     f"({lecturer_display})"
            )
        else:
            self.class_label.config(text="No class in session")

        qr_data = scan_qr_live(frame)

        if qr_data and not self.processing_scan and self.scanning_enabled:
            now = datetime.now()
            last = self.last_scan_time.get(qr_data)

            if not last or (now - last).seconds >= self.scan_cooldown:
                self.processing_scan = True
                self.last_scan_time[qr_data] = now
                self.root.after(1, lambda d=qr_data: self.process_scan_async(d))

        # display frame
        frame = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
        frame = cv2.resize(frame, (500, 320))
        img = Image.fromarray(frame)
        self._video_img = ImageTk.PhotoImage(img, master=self.root)
        if self._video_img is not None:
            self.video_label.configure(image=self._video_img)

        self.after_id = self.root.after(10, self.update_frame)

    # ================= SCAN PROCESSING =================

    def process_scan_async(self, student_id: Any) -> None:
        try:
            self.process_scan(student_id)
        finally:
            self.root.after(300, self.release_scan)

    def release_scan(self) -> None:
        self.processing_scan = False

    def process_scan(self, student_id: Any) -> None:
        student_id = str(student_id)

        # Ensure there's a class in session
        if self.current_course is None:
            self.show_notification("No class in session", False)
            self.play_beep(False)
            self.flash_border("red")
            return

        get_student = self._resolve_callable(student_db, "get_student", "student_db")
        student = None
        if get_student is not None:
            try:
                student = get_student(student_id)
            except Exception:
                student = None

        if not student:
            self.show_notification("Student not found", False)
            self.play_beep(False)
            self.flash_border("red")
            return

        assert self.current_course is not None
        course_code = self.current_course.get("course_code")
        if not course_code:
            self.show_notification("No course code available", False)
            self.play_beep(False)
            self.flash_border("red")
            return

        user_id = None
        try:
            if isinstance(session.current_user, dict):
                user_id = session.current_user.get("id")
        except Exception:
            user_id = None

        allowed_raw = []
        get_lecturer_courses = self._resolve_callable(
            lecturer_db, "get_lecturer_courses", "lecturer_db"
        )
        try:
            if user_id is not None and get_lecturer_courses is not None:
                allowed_raw = get_lecturer_courses(user_id)
        except Exception:
            allowed_raw = []

        # Normalize allowed courses into a set of codes
        allowed_set: Set[str] = set()
        try:
            if allowed_raw is None:
                allowed_set = set()
            elif isinstance(allowed_raw, list) and len(allowed_raw) > 0 and isinstance(allowed_raw[0], dict):
                allowed_set = {c.get("course_code") for c in allowed_raw if c.get("course_code")}
            elif hasattr(allowed_raw, "__iter__"):
                allowed_set = set(str(x) for x in allowed_raw)
            else:
                allowed_set = set()
        except Exception:
            allowed_set = set()

        if course_code not in allowed_set:
            self.show_notification("You are not assigned to this course", False)
            self.play_beep(False)
            self.flash_border("red")
            return

        # Ensure the student is actually registered for this course
        is_registered_fn = self._resolve_callable(
            course_registration_db, "is_student_registered", "course_registration_db"
        )
        is_registered = True
        try:
            if is_registered_fn is not None:
                is_registered = bool(is_registered_fn(student_id, course_code))
        except Exception:
            # Fail open here to avoid blocking attendance entirely if there is
            # a temporary database or import problem; logs would capture errors.
            is_registered = True

        if not is_registered:
            self.show_notification("Student not registered for this course", False)
            self.play_beep(False)
            self.flash_border("red")
            return

        # Call mark_attendance safely (don't assume it returns a tuple)
        result = None
        try:
            result = attendance_db.mark_attendance(student_id, course_code)
        except Exception:
            result = None

        if isinstance(result, tuple):
            success = bool(result[0])
            remaining = result[1] if len(result) > 1 else None
        else:
            success = bool(result)
            remaining = None

        if not success:
            minutes = int(remaining.total_seconds() // 60) if isinstance(remaining, timedelta) else 0
            self.show_notification(f"Already marked ({minutes}m left)", False)
            self.play_beep(False)
            self.flash_border("red")
        else:
            if isinstance(remaining, str) and remaining.lower() == "late":
                self.show_notification(f"{student.get('name','Unknown')} ✓ marked late for {course_code}", True)
            else:
                self.show_notification(f"{student.get('name','Unknown')} ✓ marked for {course_code}", True)
            self.play_beep(True)
            self.flash_border("green")

            self.scanned_today.add(student_id)
            self.counter_label.config(text=f"Scanned Today: {len(self.scanned_today)}")

    # ================= CLEANUP =================

    def stop_camera(self) -> None:
        self.running = False
        if self.after_id:
            try:
                self.root.after_cancel(self.after_id)
            except Exception:
                pass
        if self.cap and self.cap.isOpened():
            self.cap.release()
        cv2.destroyAllWindows()

    def on_close(self) -> None:
        self.stop_camera()
        try:
            self.root.destroy()
        except Exception:
            pass
        if self.parent is not None:
            try:
                self.parent.deiconify()
                try:
                    self.parent.state("zoomed")
                except Exception:
                    pass
            except Exception:
                pass