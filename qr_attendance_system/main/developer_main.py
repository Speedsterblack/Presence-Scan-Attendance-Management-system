"""Head of University central LAN application entry point."""

import tkinter as tk
from tkinter import messagebox

from database.db_init import create_tables
from database.university_db import add_university, get_all_University
from services.head_hub import start_head_hub_server
from ui.institution_setup_ui import InstitutionSetupUI


def _setup_university(root: tk.Tk) -> bool:
    """Collect the required university identity on first launch."""

    if get_all_University():
        return True

    root.title("University Setup")
    root.deiconify()
    root.update_idletasks()
    dialog = tk.Toplevel(root)
    dialog.title("University Setup")
    dialog.geometry("460x250")
    dialog.resizable(False, False)
    dialog.configure(bg="#ecf0f1")
    dialog.grab_set()

    tk.Label(
        dialog,
        text="Set up your university",
        font=("Arial", 16, "bold"),
        bg="#ecf0f1",
        fg="#2c3e50",
    ).pack(pady=(22, 14))

    form = tk.Frame(dialog, bg="#ecf0f1")
    form.pack(fill="x", padx=32)
    tk.Label(form, text="University code:", bg="#ecf0f1", fg="#2c3e50").grid(
        row=0, column=0, sticky="w", pady=6
    )
    code_entry = tk.Entry(form, width=34)
    code_entry.grid(row=0, column=1, padx=(12, 0), pady=6)
    tk.Label(form, text="University name:", bg="#ecf0f1", fg="#2c3e50").grid(
        row=1, column=0, sticky="w", pady=6
    )
    name_entry = tk.Entry(form, width=34)
    name_entry.grid(row=1, column=1, padx=(12, 0), pady=6)

    result = {"saved": False}

    def save() -> None:
        code = code_entry.get().strip()
        name = name_entry.get().strip()
        if not code or not name:
            messagebox.showerror("Required details", "Enter both the university code and name.", parent=dialog)
            return
        try:
            add_university(code, name)
        except Exception as error:
            messagebox.showerror("University setup failed", str(error), parent=dialog)
            return
        result["saved"] = True
        dialog.destroy()

    buttons = tk.Frame(dialog, bg="#ecf0f1")
    buttons.pack(fill="x", padx=32, pady=18)
    save_button = tk.Button(
        buttons,
        text="Save and continue",
        command=save,
    )
    save_button.pack(side="left")
    save_button.configure(width=18)

    cancel_button = tk.Button(
        buttons,
        text="Cancel",
        command=dialog.destroy,
    )
    cancel_button.pack(side="right")
    cancel_button.configure(width=12)
    code_entry.focus_set()
    dialog.bind("<Return>", lambda _event: save())
    dialog.wait_window()
    return bool(result["saved"])


def main() -> None:
    root = tk.Tk()
    create_tables()
    if not _setup_university(root):
        root.destroy()
        return
    start_head_hub_server()
    root.title("Head of University")
    InstitutionSetupUI(root, root)
    root.mainloop()


if __name__ == "__main__":  # pragma: no cover
    main()

