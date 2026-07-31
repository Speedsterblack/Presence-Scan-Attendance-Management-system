import tkinter as tk
from tkinter import messagebox, ttk
from typing import List, Tuple, Optional, Union

from utils import session
from ui import styles as ui_styles
from ui.assets_utils import apply_background_image, get_logo_image

from database.course_db import get_all_courses
from database.student_db import get_student
from database import course_registration_db


class CourseRegistrationUI:
    """UI for lecturers to register existing students to their courses.

    Admins handle student creation and QR generation. Lecturers use this
    screen to attach those students to specific courses (course_registrations
    table), which is then enforced by the QR scanner.
    """

    def __init__(
        self,
        root: Union[tk.Tk, tk.Toplevel],
        parent: Optional[Union[tk.Tk, tk.Toplevel]] = None,
    ) -> None:
        self.root = root
        self.parent = parent

        self.root.title("Course Registration")
        self.root.protocol("WM_DELETE_WINDOW", self.on_close)

        # Subtle centered background image behind content
        self._bg_label = apply_background_image(self.root, (520, 520))

        # Small header logo
        self._logo_image = get_logo_image((64, 64))
        if self._logo_image is not None:
            tk.Label(self.root, image=self._logo_image, borderwidth=0).pack(pady=(8, 0))

        tk.Label(
            self.root,
            text="Register Students to Course",
            font=("Arial", 16, "bold"),
        ).pack(pady=8)

        # Resolve lecturer from session; this UI is intended for lecturers.
        try:
            user = session.current_user
        except Exception:
            user = None

        self.lecturer_id = None
        if isinstance(user, dict):
            role = (user.get("role") or "").lower()
            if role == "lecturer":
                self.lecturer_id = str(user.get("id", ""))

        if not self.lecturer_id:
            messagebox.showerror(
                "Access Denied",
                "Course registration is only available for lecturer accounts.",
            )
            self.safe_close()
            return

        # ===== COURSE SELECTION =====
        courses = get_all_courses()
        # filter to only this lecturer's courses
        self.courses: List[Tuple[str, str]] = [
            (c[0], c[1])  # (course_code, title)
            for c in courses
            if str(c[3]) == self.lecturer_id
        ]

        if not self.courses:
            messagebox.showinfo(
                "No Courses",
                "No courses are assigned to your account yet.",
            )
            self.safe_close()
            return

        selector_frame = tk.Frame(self.root)
        selector_frame.pack(pady=6)

        tk.Label(selector_frame, text="Course:").pack(side="left", padx=(0, 4))
        self.course_var = tk.StringVar()
        # Map human label -> course_code
        self.course_labels = []
        for code, title in self.courses:
            label = f"{code} - {title}"
            self.course_labels.append(label)
        self.course_var.set(self.course_labels[0])

        course_menu = ttk.Combobox(
            selector_frame,
            textvariable=self.course_var,
            values=self.course_labels,
            state="readonly",
            width=40,
        )
        course_menu.pack(side="left")
        course_menu.bind("<<ComboboxSelected>>", lambda _e: self.refresh_registered())

        # Hint text
        tk.Label(
            self.root,
            text=(
                "Enter a student's ID to register them for the selected course.\n"
                "Students must already exist in the system (created by Admin)."
            ),
            font=("Arial", 9),
        ).pack(pady=(2, 6))

        # ===== REGISTRATION FORM =====
        form = tk.Frame(self.root)
        form.pack(pady=4)

        tk.Label(form, text="Student ID:").grid(row=0, column=0, sticky="w", padx=(0, 4), pady=2)
        self.student_id_entry = tk.Entry(form, width=24)
        self.student_id_entry.grid(row=0, column=1, pady=2)

        tk.Button(
            form,
            text="Register",
            command=self.register_student,
            width=14,
            font=ui_styles.BUTTON_FONT,
            **ui_styles.PRIMARY_BUTTON,
        ).grid(row=0, column=2, padx=(6, 0), pady=2)

        # ===== REGISTERED STUDENTS LIST =====
        list_frame = tk.Frame(self.root)
        list_frame.pack(fill="both", expand=True, padx=8, pady=(8, 4))

        tk.Label(list_frame, text="Registered Students for Course:").pack(anchor="w")

        self.tree = ttk.Treeview(list_frame, columns=("student_id",), show="headings", height=10)
        self.tree.heading("student_id", text="Student ID", anchor='w')
        self.tree.column("student_id", width=160, anchor="w")
        self.tree.pack(side="left", fill="both", expand=True)

        vs = ttk.Scrollbar(list_frame, orient="vertical", command=self.tree.yview)
        vs.pack(side="right", fill="y")
        self.tree.configure(yscrollcommand=vs.set)

        # Bottom controls
        btn_frame = tk.Frame(self.root)
        btn_frame.pack(fill="x", pady=(4, 8))

        tk.Button(
            btn_frame,
            text="Close",
            command=self.on_close,
            width=12,
            font=ui_styles.BUTTON_FONT,
            **ui_styles.MUTED_BUTTON,
        ).pack(side="right", padx=8)

        # Ensure the window is comfortably sized and not too small
        self.root.update_idletasks()
        self.root.minsize(self.root.winfo_width(), self.root.winfo_height())

        # Initial load
        self.refresh_registered()

    # ================= HELPERS =================

    def get_selected_course_code(self) -> str:
        label = self.course_var.get()
        for (code, title), lbl in zip(self.courses, self.course_labels):
            if lbl == label:
                return code
        # Fallback: try to split on ' - '
        if " - " in label:
            return label.split(" - ", 1)[0].strip()
        return label.strip()

    def refresh_registered(self) -> None:
        """Reload the list of students registered for the selected course."""
        course_code = self.get_selected_course_code()
        try:
            student_ids = course_registration_db.get_students_for_course(course_code)
        except Exception as e:
            messagebox.showerror("Error", f"Could not load registrations:\n{e}")
            student_ids = []

        # Clear and repopulate treeview
        for item in self.tree.get_children():
            self.tree.delete(item)
        for sid in student_ids:
            self.tree.insert("", "end", values=(sid,))

    def register_student(self) -> None:
        student_id = self.student_id_entry.get().strip()
        if not student_id:
            messagebox.showerror("Error", "Please enter a student ID.")
            return

        # Ensure student exists
        try:
            student = get_student(student_id)
        except Exception as e:
            messagebox.showerror("Error", f"Could not look up student:\n{e}")
            return

        if not student:
            messagebox.showerror("Error", "No student found with that ID.")
            return

        course_code = self.get_selected_course_code()

        try:
            course_registration_db.register_student_to_course(student_id, course_code)
        except Exception as e:
            messagebox.showerror("Error", f"Could not register student to course:\n{e}")
            return

        messagebox.showinfo(
            "Registered",
            f"Student {student_id} has been registered for {course_code}.",
        )
        self.student_id_entry.delete(0, tk.END)
        self.refresh_registered()

    def safe_close(self) -> None:
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

    def on_close(self) -> None:
        self.safe_close()
