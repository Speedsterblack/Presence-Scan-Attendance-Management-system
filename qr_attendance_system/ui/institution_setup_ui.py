import tkinter as tk
from tkinter import ttk, messagebox
from typing import Union

from config import settings as app_settings
from ui import styles as ui_styles
from ui.assets_utils import apply_background_image, get_logo_image
from database.university_db import (
    get_all_University,
)
from database.department_db import (
    get_all_departments,
    add_department,
    update_department,
    delete_department,
)
from database.hod_db import get_hod_credentials_for_department, upsert_hod_for_department
from services.head_hub import get_hub_token, get_head_hub_url

_THEME = app_settings.get_theme()
BG_COLOR = _THEME["bg_color"]
TEXT = _THEME["text_color"]


class InstitutionSetupUI:
    """Manage the head university's details and departments.

    HOD/admin accounts are still created in the ``hods`` table
    directly; this screen focuses on the university/department
    hierarchy that those HODs belong to.
    """

    def __init__(
        self,
        root: Union[tk.Tk, tk.Toplevel],
        parent: Union[tk.Tk, tk.Toplevel],
    ) -> None:
        self.root = root
        self.parent = parent

        self.root.title("Head of University")
        self.root.configure(bg=BG_COLOR)
        self.root.protocol("WM_DELETE_WINDOW", self._go_back)

        # Subtle background and logo for consistency
        self._bg_label = apply_background_image(self.root, (520, 520))
        self._logo_image = get_logo_image((140, 140), master=self.root)
        if self._logo_image is not None:
            tk.Label(self.root, image=self._logo_image, bg=BG_COLOR, borderwidth=0).pack(pady=(8, 0))

        tk.Label(
            self.root,
            text="Head of University",
            font=ui_styles.SUBTITLE_FONT,
            bg=BG_COLOR,
            fg=TEXT,
        ).pack(pady=4)
        tk.Label(
            self.root,
            text=f"University LAN hub: {get_head_hub_url()}  Pairing token: {get_hub_token()}",
            bg=BG_COLOR,
            fg=TEXT,
        ).pack(pady=(0, 4))

        notebook = ttk.Notebook(self.root)
        notebook.pack(fill="both", expand=True, padx=8, pady=6)

        self._build_department_tab(notebook)

        # Ensure the institution setup window opens at a comfortable,
        # large size similar to the admin dashboard.
        self.root.update_idletasks()

    # ================= DEPARTMENTS =================

    def _build_department_tab(self, notebook: ttk.Notebook) -> None:
        frame = tk.Frame(notebook, bg=BG_COLOR)
        notebook.add(frame, text="Departments")

        # Department list
        tree = ttk.Treeview(
            frame,
            columns=("code", "name", "admin_id", "admin_password", "university", "internal_id"),
            show="headings",
            selectmode="browse",
            height=10,
        )
        tree.heading("code", text="Department ID", anchor="w")
        tree.heading("name", text="Department Name", anchor="w")
        tree.heading("admin_id", text="Admin ID", anchor="w")
        tree.heading("admin_password", text="Admin Password", anchor="w")
        tree.heading("internal_id", text="", anchor="w")
        tree.column("code", width=120, anchor="w")
        tree.column("name", width=250, anchor="w")
        tree.column("admin_id", width=150, anchor="w")
        tree.column("admin_password", width=150, anchor="w")
        tree.column("internal_id", width=0, stretch=False)
        tree.pack(fill="both", expand=True, padx=8, pady=(4, 8))
        self.dept_tree = tree

        # Form section with better organization
        form_container = tk.Frame(frame, bg=BG_COLOR)
        form_container.pack(fill="x", padx=8, pady=(8, 4))

        # Section title
        tk.Label(
            form_container,
            text="Department Information",
            font=ui_styles.SECTION_FONT,
            bg=BG_COLOR,
            fg=TEXT,
        ).pack(anchor="w", pady=(0, 8))

        # Row 1: Department ID and Name
        row1 = tk.Frame(form_container, bg=BG_COLOR)
        row1.pack(fill="x", pady=6)

        tk.Label(row1, text="Department ID", bg=BG_COLOR, fg=TEXT, width=14).pack(side="left", anchor="w")
        self.dept_id_e = tk.Entry(row1, width=16)
        self.dept_id_e.pack(side="left", padx=(0, 16), fill="x", expand=False)

        tk.Label(row1, text="Department Name", bg=BG_COLOR, fg=TEXT, width=16).pack(side="left", anchor="w")
        self.dept_name_e = tk.Entry(row1)
        self.dept_name_e.pack(side="left", fill="x", expand=True)

        # Separator
        tk.Frame(form_container, bg="#37474f", height=1).pack(fill="x", pady=8)

        # Section title for admin credentials
        tk.Label(
            form_container,
            text="Admin Account (HOD)",
            font=ui_styles.SECTION_FONT,
            bg=BG_COLOR,
            fg="#ffb300",
        ).pack(anchor="w", pady=(8, 8))

        # Row 2: Admin ID and Password
        row2 = tk.Frame(form_container, bg=BG_COLOR)
        row2.pack(fill="x", pady=6)

        tk.Label(row2, text="Admin ID", bg=BG_COLOR, fg=TEXT, width=14).pack(side="left", anchor="w")
        self.dept_admin_id_e = tk.Entry(row2, width=16)
        self.dept_admin_id_e.pack(side="left", padx=(0, 16), fill="x", expand=False)

        tk.Label(row2, text="Admin Password", bg=BG_COLOR, fg=TEXT, width=16).pack(side="left", anchor="w")
        self.dept_admin_pw_e = tk.Entry(row2, show="•")
        self.dept_admin_pw_e.pack(side="left", fill="x", expand=True)

        # Info text
        info_text = "(Leave blank to skip admin account creation. Credentials are required for department login.)"
        tk.Label(
            form_container,
            text=info_text,
            font=("Arial", 9),
            bg=BG_COLOR,
            fg="#90a4ae",
            wraplength=400,
            justify="left",
        ).pack(anchor="w", pady=(4, 0))

        # Button section
        btnf = tk.Frame(frame, bg=BG_COLOR)
        btnf.pack(fill="x", padx=8, pady=(8, 8))

        tk.Button(
            btnf,
            text="Add Department",
            command=self._add_department_clicked,
            font=ui_styles.BUTTON_FONT,
            **ui_styles.PRIMARY_BUTTON,
        ).pack(side="left", padx=4)

        tk.Button(
            btnf,
            text="Update Selected",
            command=self._update_department_clicked,
            font=ui_styles.BUTTON_FONT,
            **ui_styles.SECONDARY_BUTTON,
        ).pack(side="left", padx=4)

        tk.Button(
            btnf,
            text="Delete",
            command=self._delete_department,
            font=ui_styles.BUTTON_FONT,
            **ui_styles.DANGER_BUTTON,
        ).pack(side="left", padx=4)

        tree.bind("<<TreeviewSelect>>", self._on_dept_select)

        self._refresh_dept_University()
        self._load_departments()

    def _refresh_dept_University(self) -> None:
        try:
            University = get_all_University()
        except Exception:
            University = []
        self._uni_id_to_code: dict[int, str] = {}
        self._university_id: int | None = None
        for uid, code, _name in University[:1]:
            self._university_id = uid
            self._uni_id_to_code[uid] = code or str(uid)

    def _current_dept_university_id(self) -> int | None:
        return self._university_id

    def _load_departments(self) -> None:
        for iid in self.dept_tree.get_children():
            self.dept_tree.delete(iid)
        try:
            rows = get_all_departments()
        except Exception as e:
            messagebox.showerror("Error", f"Could not load departments:\n{e}")
            return

        current_uid = self._current_dept_university_id()
        for did, code, name, uid in rows:
            if current_uid is not None and uid == current_uid:
                display_code = code or ""
                uni_display = self._uni_id_to_code.get(uid, str(uid))
                credentials = get_hod_credentials_for_department(did)
                admin_id = credentials[0] if credentials else ""
                admin_password = "********" if credentials and credentials[1] else "Not configured"
                self.dept_tree.insert(
                    "",
                    "end",
                    values=(display_code, name, admin_id, admin_password, uni_display, did),
                )

    def _on_dept_select(self, _event=None) -> None:
        sel = self.dept_tree.selection()
        if not sel:
            return
        vals = self.dept_tree.item(sel[0])["values"]
        if not vals:
            return
        # (code, name, university_id, internal_id)
            # (code, name, admin_id, admin_password, university_id, internal_id)
        self.dept_id_e.delete(0, "end")
        self.dept_id_e.insert(0, vals[0] or "")
        self.dept_name_e.delete(0, "end")
        self.dept_name_e.insert(0, vals[1] or "")
        # Do not auto-fill admin credentials for security; leave blank
        # so the developer must explicitly set or change them.
            # explicitly when changing the department administrator.
        self.dept_admin_id_e.delete(0, "end")
        self.dept_admin_pw_e.delete(0, "end")

    def _save_department(self) -> None:
        code = self.dept_id_e.get().strip()
        name = self.dept_name_e.get().strip()
        uid = self._current_dept_university_id()
        if not (code and name and uid is not None):
            messagebox.showerror("Error", "Department ID, name and university are required")
            return
        admin_id = self.dept_admin_id_e.get().strip()
        admin_pw = self.dept_admin_pw_e.get().strip()
        sel = self.dept_tree.selection()
        try:
            if sel:
                vals = self.dept_tree.item(sel[0])["values"]
                did = int(vals[5])
                update_department(did, code, name, uid)
                if admin_id and admin_pw:
                    # Use department name as the HOD display name by default.
                    upsert_hod_for_department(admin_id, name, admin_pw, did)
            else:
                did = add_department(code, name, uid)
                if admin_id and admin_pw:
                    upsert_hod_for_department(admin_id, name, admin_pw, did)
            self._load_departments()
        except Exception as e:
            messagebox.showerror("Error", f"Could not save department:\n{e}")

    def _add_department_clicked(self) -> None:
        """Prepare to add a new department and save it."""
        try:
            self.dept_tree.selection_remove(self.dept_tree.selection())
        except Exception:
            pass
        self._save_department()

    def _update_department_clicked(self) -> None:
        """Update the currently selected department using the form."""
        self._save_department()

    def _delete_department(self) -> None:
        sel = self.dept_tree.selection()
        if not sel:
            messagebox.showerror("Error", "No department selected")
            return
        vals = self.dept_tree.item(sel[0])["values"]
        did = int(vals[5])
        code = vals[0] or did
        if not messagebox.askyesno("Confirm", f"Delete department {code}?"):
            return
        try:
            delete_department(did)
            self._load_departments()
        except Exception as e:
            messagebox.showerror("Error", f"Could not delete department:\n{e}")

    # ================= COMMON =================

    def _go_back(self) -> None:
        try:
            self.root.destroy()
        except Exception:
            pass
        try:
            self.parent.deiconify()
            try:
                self.parent.state("zoomed")
            except Exception:
                pass
        except Exception:
            pass
