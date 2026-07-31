import tkinter as tk
from tkinter import ttk, messagebox
from typing import Union

from config import settings as app_settings
from ui import styles as ui_styles
from ui.assets_utils import apply_background_image, get_logo_image
from database.university_db import (
    get_all_University,
    add_university,
    update_university,
    delete_university,
)
from database.department_db import (
    get_all_departments,
    add_department,
    update_department,
    delete_department,
)
from database.hod_db import upsert_hod_for_department

_THEME = app_settings.get_theme()
BG_COLOR = _THEME["bg_color"]
TEXT = _THEME["text_color"]


class InstitutionSetupUI:
    """Manage University and departments.

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

        self.root.title("Institution Setup")
        self.root.configure(bg=BG_COLOR)
        self.root.protocol("WM_DELETE_WINDOW", self._go_back)

        # Subtle background and logo for consistency
        self._bg_label = apply_background_image(self.root, (520, 520))
        self._logo_image = get_logo_image((140, 140))
        if self._logo_image is not None:
            tk.Label(self.root, image=self._logo_image, bg=BG_COLOR, borderwidth=0).pack(pady=(8, 0))

        tk.Label(
            self.root,
            text="Institution Setup",
            font=ui_styles.SUBTITLE_FONT,
            bg=BG_COLOR,
            fg=TEXT,
        ).pack(pady=4)

        notebook = ttk.Notebook(self.root)
        notebook.pack(fill="both", expand=True, padx=8, pady=6)

        self._build_university_tab(notebook)
        self._build_department_tab(notebook)

        # Ensure the institution setup window opens at a comfortable,
        # large size similar to the admin dashboard.
        self.root.update_idletasks()
        # Maximize institution setup window on startup
        self.root.update_idletasks()
        self.root.state('zoomed')
        self.root.minsize(1100, 700)

    # ================= University =================

    def _build_university_tab(self, notebook: ttk.Notebook) -> None:
        frame = tk.Frame(notebook, bg=BG_COLOR)
        notebook.add(frame, text="University")

        # Main content split into left (existing list) and right (form),
        # similar to the Manage Lecturers screen.
        main = tk.Frame(frame, bg=BG_COLOR)
        main.pack(fill="both", expand=True, padx=8, pady=6)

        # Left side: existing University list with Refresh/Delete buttons
        left = tk.Frame(main, bg=BG_COLOR)
        left.pack(side="left", fill="both", expand=True, padx=(0, 8))

        tk.Label(left, text="Existing University", bg=BG_COLOR, fg=TEXT).pack(anchor="w")

        # columns: human-readable University ID (string), Name, internal numeric id (hidden)
        tree = ttk.Treeview(
            left,
            columns=("code", "name", "internal_id"),
            show="headings",
            selectmode="browse",
        )
        tree.heading("code", text="University ID", anchor="w")
        tree.heading("name", text="Name", anchor="w")
        tree.heading("internal_id", text="", anchor="w")
        tree.column("code", width=140, anchor="w")
        tree.column("name", width=260, anchor="w")
        tree.column("internal_id", width=0, stretch=False)
        tree.pack(fill="both", expand=True)
        self.uni_tree = tree

        btnf_left = tk.Frame(left, bg=BG_COLOR)
        btnf_left.pack(fill="x", pady=6)
        tk.Button(
            btnf_left,
            text="Refresh",
            command=self._load_University,
            font=ui_styles.BUTTON_FONT,
            **ui_styles.PRIMARY_BUTTON,
        ).pack(side="left", padx=6)
        tk.Button(
            btnf_left,
            text="Delete",
            command=self._delete_university,
            font=ui_styles.BUTTON_FONT,
            **ui_styles.DANGER_BUTTON,
        ).pack(side="left", padx=6)

        # Right side: add / update university form
        right = tk.Frame(main, bg=BG_COLOR)
        right.pack(side="left", fill="y")

        tk.Label(
            right,
            text="Add / Update University",
            font=ui_styles.SECTION_FONT,
            bg=BG_COLOR,
            fg=TEXT,
        ).pack(anchor="w")

        tk.Label(right, text="University ID", bg=BG_COLOR, fg=TEXT).pack(anchor="w", pady=(8, 0))
        self.uni_id_e = tk.Entry(right)
        self.uni_id_e.pack(fill="x")

        tk.Label(right, text="Name", bg=BG_COLOR, fg=TEXT).pack(anchor="w", pady=(8, 0))
        self.uni_name_e = tk.Entry(right)
        self.uni_name_e.pack(fill="x")

        tk.Button(
            right,
            text="Add University",
            command=self._add_university_clicked,
            font=ui_styles.BUTTON_FONT,
            **ui_styles.PRIMARY_BUTTON,
        ).pack(pady=8, fill="x")
        tk.Button(
            right,
            text="Update Selected",
            command=self._update_university_clicked,
            font=ui_styles.BUTTON_FONT,
            **ui_styles.SECONDARY_BUTTON,
        ).pack(pady=(0, 6), fill="x")

        tree.bind("<<TreeviewSelect>>", self._on_uni_select)
        self._load_University()

    def _load_University(self) -> None:
        for iid in self.uni_tree.get_children():
            self.uni_tree.delete(iid)
        try:
            for uid, code, name in get_all_University():
                display_code = code or ""
                self.uni_tree.insert("", "end", values=(display_code, name, uid))
        except Exception as e:
            messagebox.showerror("Error", f"Could not load University:\n{e}")

    def _on_uni_select(self, _event=None) -> None:
        sel = self.uni_tree.selection()
        if not sel:
            return
        vals = self.uni_tree.item(sel[0])["values"]
        if not vals:
            return
        # (code, name, internal_id)
        self.uni_id_e.delete(0, "end")
        self.uni_id_e.insert(0, vals[0] or "")
        self.uni_name_e.delete(0, "end")
        self.uni_name_e.insert(0, vals[1] or "")

    def _add_university_clicked(self) -> None:
        """Prepare to add a new university and save it.

        Clears any current selection so _save_university() treats the
        entry as a new record.
        """
        try:
            self.uni_tree.selection_remove(self.uni_tree.selection())
        except Exception:
            pass
        self._save_university()

    def _update_university_clicked(self) -> None:
        """Update the currently selected university using the form."""
        self._save_university()

    def _save_university(self) -> None:
        code = self.uni_id_e.get().strip()
        name = self.uni_name_e.get().strip()
        if not (code and name):
            messagebox.showerror("Error", "University ID and name are required")
            return

        sel = self.uni_tree.selection()
        try:
            if sel:
                vals = self.uni_tree.item(sel[0])["values"]
                internal_id = int(vals[2])
                update_university(internal_id, code, name)
            else:
                add_university(code, name)
            self._load_University()
        except Exception as e:
            messagebox.showerror("Error", f"Could not save university:\n{e}")

    def _delete_university(self) -> None:
        sel = self.uni_tree.selection()
        if not sel:
            messagebox.showerror("Error", "No university selected")
            return
        vals = self.uni_tree.item(sel[0])["values"]
        uid = int(vals[2])
        code = vals[0] or uid
        if not messagebox.askyesno("Confirm", f"Delete university {code}?"):
            return
        try:
            delete_university(uid)
            self._load_University()
        except Exception as e:
            messagebox.showerror("Error", f"Could not delete university:\n{e}")

    # ================= DEPARTMENTS =================

    def _build_department_tab(self, notebook: ttk.Notebook) -> None:
        frame = tk.Frame(notebook, bg=BG_COLOR)
        notebook.add(frame, text="Departments")

        # Top section: University selector
        top = tk.Frame(frame, bg=BG_COLOR)
        top.pack(fill="x", padx=8, pady=(8, 4))

        tk.Label(
            top,
            text="Filter by University:",
            font=ui_styles.LABEL_FONT,
            bg=BG_COLOR,
            fg=TEXT,
        ).pack(side="left")
        self.dept_uni_var = tk.StringVar()
        self.dept_uni_combo = ttk.Combobox(
            top,
            textvariable=self.dept_uni_var,
            state="readonly",
            width=40,
            font=ui_styles.LABEL_FONT,
        )
        self.dept_uni_combo.pack(side="left", padx=(6, 0), fill="x", expand=True)
        self.dept_uni_combo.bind("<<ComboboxSelected>>", lambda _e: self._load_departments())

        # Department list
        tree = ttk.Treeview(
            frame,
            columns=("code", "name", "university", "internal_id"),
            show="headings",
            selectmode="browse",
            height=10,
        )
        tree.heading("code", text="Department ID", anchor="w")
        tree.heading("name", text="Department Name", anchor="w")
        tree.heading("university", text="University", anchor="w")
        tree.heading("internal_id", text="", anchor="w")
        tree.column("code", width=120, anchor="w")
        tree.column("name", width=250, anchor="w")
        tree.column("university", width=120, anchor="w")
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
        # Map combobox label -> internal id and also keep a reverse
        # mapping so we can display the human-readable University ID
        # for each department row.
        self._dept_uni_map = {}
        self._uni_id_to_code: dict[int, str] = {}
        for uid, code, name in University:
            label_code = code or str(uid)
            label = f"{label_code} - {name}"
            self._dept_uni_map[label] = uid
            self._uni_id_to_code[uid] = label_code
        values = list(self._dept_uni_map.keys()) or ["(none)"]
        self.dept_uni_combo["values"] = values
        if values:
            self.dept_uni_combo.current(0)

    def _current_dept_university_id(self) -> int | None:
        label = self.dept_uni_var.get()
        return self._dept_uni_map.get(label)

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
            if current_uid is None or uid == current_uid:
                display_code = code or ""
                uni_display = self._uni_id_to_code.get(uid, str(uid))
                self.dept_tree.insert("", "end", values=(display_code, name, uni_display, did))

    def _on_dept_select(self, _event=None) -> None:
        sel = self.dept_tree.selection()
        if not sel:
            return
        vals = self.dept_tree.item(sel[0])["values"]
        if not vals:
            return
        # (code, name, university_id, internal_id)
        self.dept_id_e.delete(0, "end")
        self.dept_id_e.insert(0, vals[0] or "")
        self.dept_name_e.delete(0, "end")
        self.dept_name_e.insert(0, vals[1] or "")
        # Do not auto-fill admin credentials for security; leave blank
        # so the developer must explicitly set or change them.
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
                did = int(vals[3])
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
        did = int(vals[3])
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
