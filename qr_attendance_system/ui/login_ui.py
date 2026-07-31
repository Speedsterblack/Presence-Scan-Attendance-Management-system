import tkinter as tk
from tkinter import messagebox, ttk
from services.auth_service import authenticate_user
from utils.session import login
from ui.assets_utils import get_logo_image
from ui import styles as ui_styles


class LoginUI:
    def __init__(self, root):
        self.root = root
        self.root.title("Attendance System - Login")
        # Let Tk compute natural size based on content; we'll
        # lock this in as the minimum once widgets are created
        # and also set a comfortable default size similar to
        # a typical application window.

        # Window icon
        self._icon_image = get_logo_image((64, 64))
        if self._icon_image is not None:
            try:
                self.root.iconphoto(False, self._icon_image)
            except Exception:
                pass

        # ===== Layout with background image panel =====
        # Dark primary background across the whole window
        self.root.configure(bg="#0b1020")

        container = tk.Frame(root, bg="#0b1020")
        container.pack(fill="both", expand=True)

        # Left: large logo as a background-style image
        image_frame = tk.Frame(container, bg="#0b1020")
        image_frame.pack(side="left", fill="both", expand=True)

        self._bg_image = get_logo_image((420, 420))
        if self._bg_image is not None:
            tk.Label(
                image_frame,
                image=self._bg_image,
                bg="#0b1020",
                borderwidth=0,
            ).place(relx=0.5, rely=0.5, anchor="center")

        # Right: login form on a light card
        form_frame = tk.Frame(container, bg="#f8fafc", width=300, padx=24, pady=28)
        form_frame.pack(side="right", fill="y", padx=70, pady=40)
        form_frame.pack_propagate(False)

        self._logo_image = get_logo_image((96, 96))
        if self._logo_image is not None:
            tk.Label(form_frame, image=self._logo_image, bg="#f8fafc", borderwidth=0).pack(pady=(0, 14))

        tk.Label(
            form_frame,
            text="Login",
            font=("Arial", 30, "bold"),
            bg="#f8fafc",
        ).pack(pady=(0, 20))

        # Configure ttk style so the role radio buttons visually
        # match the themed ones used on the settings page.
        try:
            style = ttk.Style(self.root)
            style.configure("AppLogin.TRadiobutton", background="#f8fafc", foreground="#2c3e50")
        except Exception:
            style = None

        # Role selection: Admin vs Lecturer
        role_frame = tk.Frame(form_frame, bg="#f8fafc")
        role_frame.pack(pady=12, fill="x")
        tk.Label(role_frame, text="Login as:", bg="#f8fafc").pack(anchor="w")
        self.role_var = tk.StringVar(value="lecturer")
        ttk.Radiobutton(
            role_frame,
            text="Admin",
            variable=self.role_var,
            value="admin",
            style="AppLogin.TRadiobutton",
        ).pack(side="left", padx=10)
        ttk.Radiobutton(
            role_frame,
            text="Lecturer",
            variable=self.role_var,
            value="lecturer",
            style="AppLogin.TRadiobutton",
        ).pack(side="left", padx=10)

        tk.Label(form_frame, text="User ID", bg="#f8fafc", font=("Arial", 11)).pack(anchor="w", pady=(12, 0))
        self.username_entry = tk.Entry(form_frame, font=("Arial", 12))
        self.username_entry.pack(fill="x", pady=6, ipady=4)

        tk.Label(form_frame, text="Password", bg="#f8fafc", font=("Arial", 11)).pack(anchor="w", pady=(8, 0))
        self.password_entry = tk.Entry(form_frame, show="*", font=("Arial", 12))
        self.password_entry.pack(fill="x", pady=6, ipady=4)

        tk.Button(
            form_frame,
            text="Login",
            width=18,
            font=ui_styles.BUTTON_FONT,
            command=self.login,
            **ui_styles.PRIMARY_BUTTON,
        ).pack(pady=24)

        # Maximize window on startup
        self.root.update_idletasks()
        self.root.state('zoomed')
        self.root.minsize(800, 600)

    def login(self):
        user_id = self.username_entry.get()
        password = self.password_entry.get()
        role_choice = self.role_var.get() if hasattr(self, "role_var") else None
        user = authenticate_user(user_id, password, role_choice)

        if not user:
            messagebox.showerror("Login Failed", "Invalid User ID or Password.")
            return
        
        login(user)

        self.root.destroy()
        role = user[2] if isinstance(user, (list, tuple)) else user.get("role") if isinstance(user, dict) else "lecturer"

        if role == "admin":
            from ui.admin_dashboard_ui import AdminDashboardUI
            root = tk.Tk()
            AdminDashboardUI(root)
            root.mainloop()
        else:
            from ui.dashboard_ui import DashboardUI
            root = tk.Tk()
            DashboardUI(root)
            root.mainloop()