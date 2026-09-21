"""Developer entry point for institution setup.

Run this module (``python -m main.developer_main``) when you need to
manage University and departments. It is intentionally separate
from the normal login flow so only developers who know the developer
password can modify institutional structure.

The password value comes from configuration (see
``config/settings.json``; key ``developer.password_hash``) so it can be
changed without touching the code.
"""

import tkinter as tk
from tkinter import messagebox

from config import settings as app_settings
from database.db_init import create_tables
from database import passive_sync
from ui.institution_setup_ui import InstitutionSetupUI
from ui.assets_utils import get_logo_image
from ui import styles as ui_styles
from utils.security import verify_password


def _show_developer_login_dialog() -> str | None:
    """Show a styled developer password entry dialog."""
    dialog = tk.Toplevel()
    dialog.title("Developer Access")
    dialog.geometry("420x320")
    dialog.resizable(False, False)
    dialog.configure(bg="#0b1020")
    dialog.grab_set()
    
    # Center on screen
    dialog.update_idletasks()
    screen_w = dialog.winfo_screenwidth()
    screen_h = dialog.winfo_screenheight()
    x = (screen_w - 420) // 2
    y = (screen_h - 320) // 2
    dialog.geometry(f"420x320+{x}+{y}")
    
    # Logo
    logo_img = get_logo_image((100, 100))
    if logo_img:
        logo_label = tk.Label(dialog, image=logo_img, bg="#0b1020", borderwidth=0)
        logo_label.image = logo_img  # type: ignore[attr-defined]
        logo_label.pack(pady=(16, 8))
    
    # Title
    tk.Label(
        dialog,
        text="Developer Access",
        font=("Arial", 16, "bold"),
        bg="#0b1020",
        fg="#ffffff",
    ).pack(pady=4)
    
    # Subtitle
    tk.Label(
        dialog,
        text="Enter developer password to access",
        font=("Arial", 10),
        bg="#0b1020",
        fg="#b0bec5",
    ).pack(pady=(0, 16))
    
    # Password field
    input_frame = tk.Frame(dialog, bg="#0b1020")
    input_frame.pack(pady=12, padx=32, fill="x")
    
    tk.Label(
        input_frame,
        text="Password:",
        font=("Arial", 10),
        bg="#0b1020",
        fg="#cfd8dc",
    ).pack(anchor="w", pady=(0, 6))
    
    password_entry = tk.Entry(
        input_frame,
        show="*",
        font=("Arial", 11),
        bg="#1a2332",
        fg="#ffffff",
        insertbackground="#1e90ff",
        bd=1,
        relief="solid",
    )
    password_entry.pack(fill="x", ipady=6)
    password_entry.focus()
    
    # Result variable
    result = {"password": None, "submitted": False}
    
    def on_submit():
        result["password"] = password_entry.get()
        result["submitted"] = True
        dialog.destroy()
    
    def on_cancel():
        dialog.destroy()
    
    # Buttons
    btn_frame = tk.Frame(dialog, bg="#0b1020")
    btn_frame.pack(pady=20, fill="x", padx=32)
    
    tk.Button(
        btn_frame,
        text="Login",
        command=on_submit,
        font=ui_styles.BUTTON_FONT,
        **ui_styles.PRIMARY_BUTTON,
        width=12,
    ).pack(side="left", padx=4)
    
    tk.Button(
        btn_frame,
        text="Cancel",
        command=on_cancel,
        font=ui_styles.BUTTON_FONT,
        **ui_styles.MUTED_BUTTON,
        width=12,
    ).pack(side="right", padx=4)
    
    # Bind Enter key
    password_entry.bind("<Return>", lambda _: on_submit())
    
    # Wait for dialog to close
    dialog.wait_window()
    
    return result["password"] if result["submitted"] else None


def main() -> None:
    create_tables()
    try:
        # Push local institution changes before opening the setup screen.
        passive_sync.sync_once()
    except Exception:
        # Institution setup remains usable while Supabase is unavailable.
        pass
    passive_sync.start()
    root = tk.Tk()
    root.withdraw()

    # Show styled developer login dialog
    expected_pw_hash = app_settings.get_developer_password_hash().strip()
    entered = _show_developer_login_dialog()

    if not entered or not verify_password(entered.strip(), expected_pw_hash):
        messagebox.showerror("Developer Access Denied", "Invalid developer password.")
        root.destroy()
        return

    # Authentication successful; show the main window and launch the
    # institution setup UI using this root as both window and parent.
    root.deiconify()
    InstitutionSetupUI(root, root)
    root.mainloop()


if __name__ == "__main__":  # pragma: no cover
    main()

