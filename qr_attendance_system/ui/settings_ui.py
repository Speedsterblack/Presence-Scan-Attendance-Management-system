import tkinter as tk
from tkinter import messagebox, filedialog, ttk, simpledialog
import re
from typing import Optional, Any

from utils import session
from utils import export_utils
from config import settings as app_settings
from config.settings import get_semester_weeks
from database import semester_db
from database.semester_tools_db import copy_previous_semester_registrations_to_active
from database.audit_db import list_audit_logs
from ui.assets_utils import apply_background_image, get_logo_image
from services.auth_service import change_password
from services.auth_service import authenticate_user
from ui import styles as ui_styles
from ui.semester_archive_ui import SemesterArchiveUI
from ui.import_center_ui import ImportCenterUI


def apply_theme_recursive(widget: Any, theme: dict | None = None) -> None:
    """Apply theme colors to *widget* and all its children.

    This updates backgrounds/text colors in-place so theme changes from the
    settings page take effect immediately without reopening windows.
    """

    if theme is None:
        theme = app_settings.get_theme()

    bg = theme.get("bg_color", "#030303")
    fg = theme.get("text_color", "#0c0c0c")
    primary = theme.get("primary_color", "#1e90ff")

    try:
        keys = widget.keys()  # type: ignore[assignment]
    except Exception:
        keys = []

    def _set(option: str, value: str) -> None:
        try:
            if option in keys:
                widget.configure(**{option: value})
        except Exception:
            pass

    # Backgrounds
    if isinstance(widget, (tk.Tk, tk.Toplevel, tk.Frame, tk.LabelFrame)):
        _set("bg", bg)
        _set("background", bg)
    elif isinstance(widget, tk.Button):
        _set("bg", primary)
        _set("background", primary)
        _set("fg", "white")
        _set("foreground", "white")
        try:
            widget.configure(font=ui_styles.BUTTON_FONT)
        except Exception:
            pass
    else:
        _set("bg", bg)
        _set("background", bg)

    # Text colors for labels / checkbuttons / radios etc.
    if isinstance(widget, (tk.Label, tk.Checkbutton, tk.Radiobutton, tk.LabelFrame)):
        _set("fg", fg)
        _set("foreground", fg)

    # Recurse into children
    for child in getattr(widget, "winfo_children", lambda: [])():
        apply_theme_recursive(child, theme)



class SettingsUI:
    def __init__(self, root: Any, parent: Optional[Any] = None) -> None:
        self.root = root
        self.parent = parent
        self.root.title("Settings")

        theme = app_settings.get_theme()
        bg = theme["bg_color"]
        fg = theme["text_color"]

        self.root.configure(bg=bg)

        # Subtle centered background image behind content
        self._bg_label = apply_background_image(self.root, (520, 520))

        # Small header logo
        self._logo_image = get_logo_image((72, 72))
        if self._logo_image is not None:
            tk.Label(self.root, image=self._logo_image, bg=bg, borderwidth=0).pack(pady=(10, 0))

        tk.Label(
            self.root,
            text="Application Settings",
            font=("Arial", 18, "bold"),
            bg=bg,
            fg=fg,
        ).pack(pady=(12, 6))

        container = tk.Frame(self.root, bg=bg)
        container.pack(fill="both", expand=True, padx=16, pady=8)

        settings = app_settings.load_settings()

        try:
            user = session.current_user
        except Exception:
            user = None
        self.is_admin = isinstance(user, dict) and str(user.get("role", "")).lower() == "admin"

        # Configure ttk styles so radio buttons and checkboxes
        # visually match the current theme instead of using the
        # default platform colors.
        self._init_ttk_styles(theme)

        # ===== Theme settings =====
        theme_frame = tk.LabelFrame(container, text="Theme", bg=bg, fg=fg)
        theme_frame.pack(fill="x", pady=6)

        tk.Label(theme_frame, text="Color theme:").grid(row=0, column=0, sticky="w", padx=6, pady=4)
        self.theme_var = tk.StringVar(value=str(settings.get("theme", {}).get("name", "light")))
        ttk.Radiobutton(theme_frame, text="Light", value="light", variable=self.theme_var, style="App.TRadiobutton").grid(row=0, column=1, sticky="w", pady=4)
        ttk.Radiobutton(theme_frame, text="Dark", value="dark", variable=self.theme_var, style="App.TRadiobutton").grid(row=0, column=2, sticky="w", pady=4)
        ttk.Radiobutton(theme_frame, text="System (match device)", value="system", variable=self.theme_var, style="App.TRadiobutton").grid(row=0, column=3, sticky="w", pady=4, padx=(8, 0))

        # ===== Attendance / grace period =====
        grace_frame = tk.LabelFrame(container, text="Attendance", bg=bg, fg=fg)
        grace_frame.pack(fill="x", pady=6)

        tk.Label(grace_frame, text="Default grace period (minutes):", bg=bg, fg=fg).grid(row=0, column=0, sticky="w", padx=6, pady=4)
        self.grace_var = tk.StringVar(value=str(app_settings.get_default_grace_minutes()))
        self.grace_entry = ttk.Entry(grace_frame, textvariable=self.grace_var, width=8, style="App.TEntry")
        self.grace_entry.grid(row=0, column=1, sticky="w", pady=4)

        # ===== Admin PIN / semester security =====
        if self.is_admin:
            pin_frame = tk.LabelFrame(container, text="Admin PIN", bg=bg, fg=fg)
            pin_frame.pack(fill="x", pady=6)

            tk.Label(pin_frame, text="New admin PIN:", bg=bg, fg=fg).grid(row=0, column=0, sticky="w", padx=6, pady=4)
            self.admin_pin_var = tk.StringVar()
            self.admin_pin_entry = ttk.Entry(pin_frame, textvariable=self.admin_pin_var, width=18, show="*", style="App.TEntry")
            self.admin_pin_entry.grid(row=0, column=1, sticky="w", padx=6, pady=4)

            tk.Label(pin_frame, text="Confirm PIN:", bg=bg, fg=fg).grid(row=1, column=0, sticky="w", padx=6, pady=4)
            self.admin_pin_confirm_var = tk.StringVar()
            self.admin_pin_confirm_entry = ttk.Entry(pin_frame, textvariable=self.admin_pin_confirm_var, width=18, show="*", style="App.TEntry")
            self.admin_pin_confirm_entry.grid(row=1, column=1, sticky="w", padx=6, pady=4)

            tk.Button(
                pin_frame,
                text="Save PIN",
                command=self._on_save_admin_pin,
                font=ui_styles.BUTTON_FONT,
                **ui_styles.PRIMARY_BUTTON,
            ).grid(row=2, column=0, sticky="w", padx=6, pady=(4, 8))

        # ===== Semester management =====
        if self.is_admin:
            semester_frame = tk.LabelFrame(container, text="Semester management", bg=bg, fg=fg)
            semester_frame.pack(fill="x", pady=6)

            try:
                current_value = self._format_active_semester()
            except Exception:
                current_value = "Semester data is unavailable right now."

            tk.Label(semester_frame, text="Current semester:", bg=bg, fg=fg).grid(row=0, column=0, sticky="w", padx=6, pady=4)
            self.current_semester_var = tk.StringVar(value=current_value)
            tk.Label(semester_frame, textvariable=self.current_semester_var, bg=bg, fg=fg, justify="left", wraplength=900).grid(row=0, column=1, sticky="w", padx=6, pady=4)

            tk.Label(semester_frame, text="Next semester name:", bg=bg, fg=fg).grid(row=1, column=0, sticky="w", padx=6, pady=4)
            try:
                next_value = self._suggest_next_semester_name()
            except Exception:
                next_value = "Semester 2"
            self.next_semester_var = tk.StringVar(value=next_value)
            self.next_semester_entry = ttk.Entry(semester_frame, textvariable=self.next_semester_var, width=28, style="App.TEntry")
            self.next_semester_entry.grid(row=1, column=1, sticky="w", padx=6, pady=4)

            tk.Label(semester_frame, text="Semester weeks:", bg=bg, fg=fg).grid(row=2, column=0, sticky="w", padx=6, pady=4)
            self.sem_weeks_var = tk.StringVar(value=str(get_semester_weeks()))
            self.sem_weeks_entry = ttk.Entry(semester_frame, textvariable=self.sem_weeks_var, width=8, style="App.TEntry")
            self.sem_weeks_entry.grid(row=2, column=1, sticky="w", pady=4)

            btn_row = tk.Frame(semester_frame, bg=bg)
            btn_row.grid(row=3, column=0, columnspan=2, sticky="w", padx=6, pady=(4, 8))

            tk.Button(
                btn_row,
                text="Close current & start next",
                command=self._on_rollover_semester,
                font=ui_styles.BUTTON_FONT,
                **ui_styles.PRIMARY_BUTTON,
            ).pack(side="left", padx=(0, 8))

            tk.Button(
                btn_row,
                text="Refresh semester info",
                command=self._refresh_semester_info,
                font=ui_styles.BUTTON_FONT,
                **ui_styles.SECONDARY_BUTTON,
            ).pack(side="left", padx=(0, 8))

            tk.Button(
                btn_row,
                text="Open semester archive",
                command=self._open_semester_archive,
                font=ui_styles.BUTTON_FONT,
                **ui_styles.SECONDARY_BUTTON,
            ).pack(side="left")

            tk.Button(
                btn_row,
                text="Re-register last semester",
                command=self._copy_previous_semester_registrations,
                font=ui_styles.BUTTON_FONT,
                **ui_styles.SECONDARY_BUTTON,
            ).pack(side="left", padx=(8, 0))

            tk.Button(
                btn_row,
                text="View audit log",
                command=self._open_audit_log,
                font=ui_styles.BUTTON_FONT,
                **ui_styles.SECONDARY_BUTTON,
            ).pack(side="left", padx=(8, 0))

        # ===== Export settings =====
        export_frame = tk.LabelFrame(container, text="Export", bg=bg, fg=fg)
        export_frame.pack(fill="x", pady=6)

        tk.Label(export_frame, text="Default export folder:", bg=bg, fg=fg).grid(row=0, column=0, sticky="w", padx=6, pady=4)
        self.export_var = tk.StringVar(value=app_settings.get_export_directory())
        entry = ttk.Entry(export_frame, textvariable=self.export_var, width=40, style="App.TEntry")
        entry.grid(row=0, column=1, sticky="w", pady=4)

        def browse_export() -> None:
            path = filedialog.askdirectory(title="Select export folder")
            if path:
                self.export_var.set(path)

        tk.Button(
            export_frame,
            text="Browse...",
            command=browse_export,
            font=ui_styles.BUTTON_FONT,
            **ui_styles.SECONDARY_BUTTON,
        ).grid(row=0, column=2, padx=6, pady=4)

        if self.is_admin:
            tk.Button(
                export_frame,
                text="Export CSV Templates",
                command=self._export_csv_templates,
                font=ui_styles.BUTTON_FONT,
                **ui_styles.SECONDARY_BUTTON,
            ).grid(row=1, column=0, columnspan=3, sticky="w", padx=6, pady=(0, 6))

            tk.Button(
                export_frame,
                text="Open Import Center",
                command=self._open_import_center,
                font=ui_styles.BUTTON_FONT,
                **ui_styles.SECONDARY_BUTTON,
            ).grid(row=2, column=0, columnspan=3, sticky="w", padx=6, pady=(0, 6))

        # ===== Admin dashboard / auto-refresh =====
        if self.is_admin:
            admin_frame = tk.LabelFrame(container, text="Admin dashboard", bg=bg, fg=fg)
            admin_frame.pack(fill="x", pady=6)

            self.auto_var = tk.BooleanVar(value=app_settings.get_admin_auto_refresh_enabled())
            ttk.Checkbutton(admin_frame, text="Enable auto-refresh by default", variable=self.auto_var, style="App.TCheckbutton").grid(row=0, column=0, columnspan=2, sticky="w", padx=6, pady=4)

            tk.Label(admin_frame, text="Auto-refresh interval (seconds):").grid(row=1, column=0, sticky="w", padx=6, pady=4)
            self.auto_interval_var = tk.StringVar(value=str(app_settings.get_admin_auto_refresh_interval()))
            self.auto_interval_entry = ttk.Entry(admin_frame, textvariable=self.auto_interval_var, width=8, style="App.TEntry")
            self.auto_interval_entry.grid(row=1, column=1, sticky="w", pady=4)

        # ===== Password change =====
        pwd_frame = tk.LabelFrame(container, text="Account password", bg=bg, fg=fg)
        pwd_frame.pack(fill="x", pady=6)

        tk.Label(pwd_frame, text="Current password:", bg=bg, fg=fg).grid(row=0, column=0, sticky="w", padx=6, pady=(6,2))
        self.current_pwd = ttk.Entry(pwd_frame, show="*", style="App.TEntry")
        self.current_pwd.grid(row=0, column=1, sticky="w", pady=(6,2))

        tk.Label(pwd_frame, text="New password:", bg=bg, fg=fg).grid(row=1, column=0, sticky="w", padx=6, pady=2)
        self.new_pwd = ttk.Entry(pwd_frame, show="*", style="App.TEntry")
        self.new_pwd.grid(row=1, column=1, sticky="w", pady=2)

        tk.Label(pwd_frame, text="Confirm password:", bg=bg, fg=fg).grid(row=2, column=0, sticky="w", padx=6, pady=(2,6))
        self.confirm_pwd = ttk.Entry(pwd_frame, show="*", style="App.TEntry")
        self.confirm_pwd.grid(row=2, column=1, sticky="w", pady=(2,6))

        tk.Button(
            pwd_frame,
            text="Change password",
            command=self._on_change_password,
            font=ui_styles.BUTTON_FONT,
            **ui_styles.PRIMARY_BUTTON,
        ).grid(row=3, column=0, columnspan=2, pady=(0,8))

        # ===== Bottom buttons =====
        btn_frame = tk.Frame(self.root, bg=bg)
        btn_frame.pack(fill="x", pady=(4, 10))

        tk.Button(
            btn_frame,
            text="Save",
            width=10,
            command=self._on_save,
            font=ui_styles.BUTTON_FONT,
            **ui_styles.PRIMARY_BUTTON,
        ).pack(side="right", padx=6)
        tk.Button(
            btn_frame,
            text="Close",
            width=10,
            command=self._on_close,
            font=ui_styles.BUTTON_FONT,
            **ui_styles.MUTED_BUTTON,
        ).pack(side="right")

        # Ensure clicking the window close (X) button behaves the
        # same as the explicit Close button, restoring the parent
        # dashboard window instead of leaving it hidden.
        try:
            self.root.protocol("WM_DELETE_WINDOW", self._on_close)
        except Exception:
            pass

        # Maximize settings window on startup
        self.root.update_idletasks()
        self.root.state('zoomed')
        self.root.minsize(900, 600)

    def _init_ttk_styles(self, theme: dict) -> None:
        """Configure ttk styles so controls match the current theme."""
        bg = theme.get("bg_color", "#000000")
        fg = theme.get("text_color", "#000000")
        try:
            style = ttk.Style(self.root)
            # Use a platform-neutral base theme where possible
            try:
                style.theme_use(style.theme_use())
            except Exception:
                pass
            style.configure("App.TRadiobutton", background=bg, foreground=fg)
            style.configure("App.TCheckbutton", background=bg, foreground=fg)
            style.configure(
                "App.TEntry",
                # Use a light background with dark text so entry
                # contents remain clearly visible regardless of
                # whether the overall theme is light or dark.
                foreground="#111111",
                fieldbackground="#ffffff",
                insertcolor="#111111",
            )
        except Exception:
            pass

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

    def _format_active_semester(self) -> str:
        try:
            semester = semester_db.get_active_semester()
        except Exception:
            return "Semester data is unavailable."
        if not semester:
            return "No active semester"

        name = str(semester.get("semester_name") or "Semester")
        start_date = semester.get("start_date")
        end_date = semester.get("end_date")
        status = str(semester.get("status") or "active").title()
        pieces = [name, f"Status: {status}"]
        if start_date:
            pieces.append(f"Start: {start_date}")
        if end_date:
            pieces.append(f"End: {end_date}")
        return " | ".join(pieces)

    def _suggest_next_semester_name(self) -> str:
        try:
            active = semester_db.get_active_semester()
        except Exception:
            return "Semester 1"
        if not active:
            return "Semester 1"

        current_name = str(active.get("semester_name") or "Semester 1").strip()
        match = re.search(r"(\d+)$", current_name)
        if match:
            prefix = current_name[: match.start()].rstrip()
            return f"{prefix} {int(match.group(1)) + 1}".strip()
        return f"{current_name} Next"

    def _refresh_semester_info(self) -> None:
        if hasattr(self, "current_semester_var"):
            try:
                self.current_semester_var.set(self._format_active_semester())
            except Exception:
                self.current_semester_var.set("Semester data is unavailable.")
        if hasattr(self, "next_semester_var") and not self.next_semester_var.get().strip():
            try:
                self.next_semester_var.set(self._suggest_next_semester_name())
            except Exception:
                self.next_semester_var.set("Semester 1")

    def _on_rollover_semester(self) -> None:
        if not self.is_admin:
            messagebox.showerror("Access Denied", "Only admin accounts can manage semesters.")
            return

        user = None
        try:
            user = session.current_user
        except Exception:
            user = None

        if not isinstance(user, dict):
            messagebox.showerror("Error", "No logged-in admin session found.")
            return

        admin_id = str(user.get("id", "")).strip()
        admin_role = str(user.get("role", "")).strip() or "admin"
        if not admin_id:
            messagebox.showerror("Error", "Admin ID is missing from session.")
            return

        pin_hash = app_settings.get_admin_pin_hash()
        if not pin_hash:
            messagebox.showerror("Admin PIN Required", "Set an admin PIN in Settings before closing a semester.")
            return

        pin = simpledialog.askstring(
            "Admin PIN Required",
            "Enter your admin PIN to close the current semester:",
            parent=self.root,
            show="*",
        )
        if pin is None:
            return
        pin = pin.strip()
        if not pin:
            messagebox.showerror("Error", "Admin PIN is required.")
            return

        from utils.security import verify_password

        if not verify_password(pin, pin_hash):
            messagebox.showerror("Access Denied", "Invalid admin PIN. Semester was not closed.")
            return

        semester_name = self.next_semester_var.get().strip() if hasattr(self, "next_semester_var") else ""
        if not semester_name:
            messagebox.showerror("Error", "Enter a name for the next semester.")
            return

        if not messagebox.askyesno(
            "Confirm semester rollover",
            "This will close the current semester and create a new active semester. Continue?",
        ):
            return

        try:
            semester_db.close_and_start_next_semester(semester_name)
            self._refresh_semester_info()
            messagebox.showinfo("Semester", f"Semester rolled over to {semester_name}.")
        except Exception as e:
            messagebox.showerror("Error", f"Could not roll over semester:\n{e}")

    def _copy_previous_semester_registrations(self) -> None:
        if not self.is_admin:
            messagebox.showerror("Access Denied", "Only admin accounts can re-register courses.")
            return

        if not messagebox.askyesno(
            "Re-register courses",
            "Copy course registrations from the latest closed semester into the current active semester?",
        ):
            return

        try:
            copied = copy_previous_semester_registrations_to_active()
            messagebox.showinfo("Re-registration", f"Copied {copied} registration(s) into the active semester.")
        except Exception as e:
            messagebox.showerror("Error", f"Could not copy registrations:\n{e}")

    def _open_audit_log(self) -> None:
        if not self.is_admin:
            messagebox.showerror("Access Denied", "Only admin accounts can view the audit log.")
            return

        try:
            win = tk.Toplevel(self.root)
            try:
                win.state('zoomed')
            except Exception:
                pass
            win.title("Audit Log")
            theme = app_settings.get_theme()
            win.configure(bg=theme.get("bg_color", "#000000"))
            cols = ("created_at", "action", "actor", "details")
            tree = ttk.Treeview(win, columns=cols, show="headings", height=16)
            for col, text, width in (("created_at", "When", 160), ("action", "Action", 180), ("actor", "Actor", 130), ("details", "Details", 520)):
                tree.heading(col, text=text)
                tree.column(col, width=width, anchor="w")
            tree.pack(fill="both", expand=True, padx=10, pady=10)
            for row in list_audit_logs(200):
                tree.insert("", "end", values=(row.get("created_at"), row.get("action"), f"{row.get('actor_role') or ''} {row.get('actor_id') or ''}".strip(), row.get("details") or ""))
            tk.Button(win, text="Close", command=win.destroy, font=ui_styles.BUTTON_FONT, **ui_styles.MUTED_BUTTON).pack(pady=(0, 10))
        except Exception as e:
            messagebox.showerror("Error", f"Could not open audit log:\n{e}")

    def _export_csv_templates(self) -> None:
        if not self.is_admin:
            messagebox.showerror("Access Denied", "Only admin accounts can export templates.")
            return

        try:
            export_dir = app_settings.get_export_directory()
            paths = {
                "students": filedialog.asksaveasfilename(
                    title="Save student template",
                    initialdir=export_dir,
                    defaultextension=".csv",
                    filetypes=[("CSV files", "*.csv")],
                    initialfile="students_template.csv",
                ),
                "courses": filedialog.asksaveasfilename(
                    title="Save course template",
                    initialdir=export_dir,
                    defaultextension=".csv",
                    filetypes=[("CSV files", "*.csv")],
                    initialfile="courses_template.csv",
                ),
                "registrations": filedialog.asksaveasfilename(
                    title="Save registration template",
                    initialdir=export_dir,
                    defaultextension=".csv",
                    filetypes=[("CSV files", "*.csv")],
                    initialfile="registrations_template.csv",
                ),
            }

            if paths["students"]:
                export_utils.export_students_template_csv(paths["students"])
            if paths["courses"]:
                export_utils.export_courses_template_csv(paths["courses"])
            if paths["registrations"]:
                export_utils.export_registrations_template_csv(paths["registrations"])

            messagebox.showinfo("Templates", "CSV template export completed.")
        except Exception as e:
            messagebox.showerror("Error", f"Could not export templates:\n{e}")

    def _on_save_admin_pin(self) -> None:
        if not self.is_admin:
            messagebox.showerror("Access Denied", "Only admin accounts can set the admin PIN.")
            return

        pin = getattr(self, "admin_pin_var", tk.StringVar()).get().strip()
        confirm = getattr(self, "admin_pin_confirm_var", tk.StringVar()).get().strip()
        if not pin:
            messagebox.showerror("Error", "Enter a new admin PIN.")
            return
        if pin != confirm:
            messagebox.showerror("Error", "PINs do not match.")
            return

        try:
            app_settings.set_admin_pin(pin)
            messagebox.showinfo("Admin PIN", "Admin PIN updated successfully.")
            self.admin_pin_var.set("")
            self.admin_pin_confirm_var.set("")
        except Exception as e:
            messagebox.showerror("Error", f"Could not save admin PIN:\n{e}")

    def _open_semester_archive(self) -> None:
        if not self.is_admin:
            messagebox.showerror("Access Denied", "Only admin accounts can view the semester archive.")
            return

        try:
            archive_win = tk.Toplevel(self.root)
            try:
                archive_win.state('zoomed')
            except Exception:
                pass
            SemesterArchiveUI(archive_win, parent=self.root)
            try:
                self.root.withdraw()
            except Exception:
                pass
        except Exception as e:
            messagebox.showerror("Error", f"Could not open semester archive:\n{e}")

    def _open_import_center(self) -> None:
        if not self.is_admin:
            messagebox.showerror("Access Denied", "Only admin accounts can use the Import Center.")
            return

        try:
            win = tk.Toplevel(self.root)
            try:
                win.state('zoomed')
            except Exception:
                pass
            ImportCenterUI(win, parent=self.root)
            try:
                self.root.withdraw()
            except Exception:
                pass
        except Exception as e:
            messagebox.showerror("Error", f"Could not open Import Center:\n{e}")

    def _on_save(self) -> None:
        # validate numeric fields
        try:
            grace = int(self.grace_var.get().strip() or "0")
            if grace < 0:
                raise ValueError
        except Exception:
            messagebox.showerror("Error", "Grace period must be zero or a positive integer.")
            return

        interval = 0
        if self.is_admin:
            try:
                interval = int(self.auto_interval_var.get().strip() or "0")
                if interval <= 0:
                    raise ValueError
            except Exception:
                messagebox.showerror("Error", "Auto-refresh interval must be a positive integer.")
                return

        export_dir = self.export_var.get().strip()

        partial = {
            "theme": {"name": self.theme_var.get().strip() or "light"},
            "attendance": {"default_grace_minutes": grace},
            "export": {"default_directory": export_dir},
        }
        if self.is_admin:
            try:
                sem_weeks = int(self.sem_weeks_var.get().strip() or "15")
                if sem_weeks <= 0:
                    raise ValueError
            except Exception:
                messagebox.showerror("Error", "Semester weeks must be a positive integer.")
                return
            partial["attendance"]["semester_weeks"] = sem_weeks
            partial["admin"] = {
                "auto_refresh_enabled": bool(self.auto_var.get()),
                "auto_refresh_interval_seconds": int(interval),
            }

        try:
            # Save into the settings bucket for the current role
            app_settings.update_settings_for_current_role(partial)
            # Re-apply theme immediately to this window and its parent
            new_theme = app_settings.get_theme()
            self._init_ttk_styles(new_theme)
            apply_theme_recursive(self.root, new_theme)
            if self.parent is not None:
                apply_theme_recursive(self.parent, new_theme)
            messagebox.showinfo("Settings", "Settings saved. Some changes may require reopening windows to take effect.")
        except Exception as e:
            messagebox.showerror("Error", f"Could not save settings:\n{e}")

    def _on_change_password(self) -> None:
        user = None
        try:
            user = session.current_user
        except Exception:
            user = None

        if not isinstance(user, dict):
            messagebox.showerror("Error", "No logged-in user found.")
            return

        user_id = user.get("id")
        role = user.get("role")
