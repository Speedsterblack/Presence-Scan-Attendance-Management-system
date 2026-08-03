import tkinter as tk
from tkinter import messagebox, ttk

from database.lecturer_db import get_all_lecturers, add_lecturer, update_lecturer_profile, update_password, delete_lecturer
from database.hod_db import get_hod_department
from database.department_db import get_department
from utils import session
from ui.assets_utils import apply_background_image, get_logo_image
from ui import styles as ui_styles


class ManageLecturersUI:
    def __init__(self, root, parent):
        self.root = root
        self.parent = parent
        self.department_id = self._get_admin_department_id()
        root.title("Manage Lecturers")
        root.protocol("WM_DELETE_WINDOW", self.go_back)

        # Subtle centered background image behind content
        self._bg_label = apply_background_image(root, (520, 520))

        # Small header logo
        self._logo_image = get_logo_image((64, 64), master=root)
        if self._logo_image is not None:
            tk.Label(root, image=self._logo_image, borderwidth=0).pack(pady=(8, 0))

        tk.Label(root, text="Lecturer Management", font=ui_styles.SUBTITLE_FONT).pack(pady=8)

        frame = tk.Frame(root)
        frame.pack(fill='both', expand=True, padx=8, pady=6)

        left = tk.Frame(frame)
        left.pack(side='left', fill='both', expand=True, padx=(0,8))

        tk.Label(left, text='Existing Lecturers').pack(anchor='w')
        # columns: Lecturer_ID, full name, role
        self.tree = ttk.Treeview(left, columns=('Lecturer_ID','full_name','role'), show='headings', selectmode='browse')
        for c, w in (('Lecturer_ID',140), ('full_name',260), ('role',80)):
            heading_text = c.replace('_', ' ').title()
            if heading_text.endswith(" Id"):
                heading_text = heading_text[:-3] + " ID"
            self.tree.heading(c, text=heading_text, anchor='w')
            self.tree.column(c, width=w, anchor='w')
        self.tree.pack(fill='both', expand=True)
        self.tree.bind('<<TreeviewSelect>>', self.on_select)

        btnf = tk.Frame(left)
        btnf.pack(fill='x', pady=6)
        tk.Button(
            btnf,
            text='Refresh',
            command=self.load,
            font=ui_styles.BUTTON_FONT,
            **ui_styles.PRIMARY_BUTTON,
        ).pack(side='left', padx=6)
        tk.Button(
            btnf,
            text='Delete',
            command=self.delete_selected,
            font=ui_styles.BUTTON_FONT,
            **ui_styles.DANGER_BUTTON,
        ).pack(side='left', padx=6)

        right = tk.Frame(frame)
        right.pack(side='left', fill='y')

        tk.Label(right, text='Add / Update Lecturer', font=ui_styles.SECTION_FONT).pack(anchor='w')

        tk.Label(right, text='Lecturer_ID').pack(anchor='w')
        self.id_e = tk.Entry(right)
        self.id_e.pack(fill='x')

        tk.Label(right, text='Name').pack(anchor='w')
        self.name_e = tk.Entry(right)
        self.name_e.pack(fill='x')

        tk.Label(right, text='Password').pack(anchor='w')
        self.pw_e = tk.Entry(right, show='*')
        self.pw_e.pack(fill='x')

        tk.Label(right, text='Role').pack(anchor='w')
        self.role_var = tk.StringVar(master=root, value='lecturer')
        # Only lecturers are managed here; admin/HOD accounts live in
        # their own table so that each department has exactly one HOD.
        role_menu = ttk.Combobox(right, textvariable=self.role_var, values=['lecturer'], state='readonly', width=18)
        role_menu.pack(fill='x')

        tk.Button(
            right,
            text='Save New',
            command=self.add_lecturer_local,
            font=ui_styles.BUTTON_FONT,
            **ui_styles.PRIMARY_BUTTON,
        ).pack(pady=8, fill='x')
        tk.Button(
            right,
            text='Update Selected',
            command=self.update_lecturer_local,
            font=ui_styles.BUTTON_FONT,
            **ui_styles.SECONDARY_BUTTON,
        ).pack(pady=(0,6), fill='x')
        tk.Button(
            right,
            text='Reset Password',
            command=self.reset_password_local,
            font=ui_styles.BUTTON_FONT,
            **ui_styles.SECONDARY_BUTTON,
        ).pack(pady=(0,6), fill='x')

        tk.Button(
            root,
            text='Close',
            command=self.go_back,
            font=ui_styles.BUTTON_FONT,
            **ui_styles.MUTED_BUTTON,
        ).pack(pady=6)

        self.load()

        # Set a minimum size so all lecturer management
        # controls are visible without manual resizing.
        root.update_idletasks()
        root.minsize(root.winfo_width(), root.winfo_height())

    def load(self):
        for iid in self.tree.get_children():
            self.tree.delete(iid)
        try:
            rows = get_all_lecturers()
            for r in rows:
                # r -> (Lecturer_ID, full_name, role)
                self.tree.insert('', 'end', values=(r[0], r[1], r[2]))
        except Exception as e:
            messagebox.showerror('Error', f'Could not load lecturers:\n{e}')

    def on_select(self, event):
        sel = self.tree.selection()
        if not sel:
            return
        vals = self.tree.item(sel[0])['values']
        # vals: (Lecturer_ID, full_name, role)
        self.id_e.delete(0, 'end')
        self.id_e.insert(0, vals[0])
        self.name_e.delete(0, 'end')
        self.name_e.insert(0, vals[1])
        self.role_var.set(vals[2])

    def add_lecturer_local(self):
        lid = self.id_e.get().strip()  # Lecturer_ID
        name = self.name_e.get().strip()  # full name
        pw = self.pw_e.get().strip()
        role = self.role_var.get().strip() or 'lecturer'
        if not all([lid, name, pw]):
            messagebox.showerror('Error', 'ID, Name and Password are required')
            return
        try:
            add_lecturer(lid, name, pw, role, department_id=self.department_id)
            messagebox.showinfo('Added', f'Lecturer {lid} added')
            self.pw_e.delete(0, 'end')
            self.load()
        except Exception as e:
            messagebox.showerror('Error', f'Could not add lecturer:\n{e}')

    def update_lecturer_local(self):
        lid = self.id_e.get().strip()
        name = self.name_e.get().strip()
        role = self.role_var.get().strip() or 'lecturer'
        if not lid or not name:
            messagebox.showerror('Error', 'Select a lecturer and enter a name')
            return
        if not messagebox.askyesno('Confirm', f'Update lecturer {lid}?'):
            return
        try:
            update_lecturer_profile(lid, name, role)
            messagebox.showinfo('Updated', f'Lecturer {lid} updated')
            self.load()
        except Exception as e:
            messagebox.showerror('Error', f'Could not update lecturer:\n{e}')

    def reset_password_local(self):
        lid = self.id_e.get().strip()  # Lecturer_ID
        np = self.pw_e.get().strip()
        if not lid or not np:
            messagebox.showerror('Error', 'Select a lecturer and enter a new password')
            return
        if not messagebox.askyesno('Confirm', f'Reset the password for {lid}?'):
            return
        try:
            update_password(lid, np)
            messagebox.showinfo('Updated', 'Password updated')
            self.pw_e.delete(0, 'end')
        except Exception as e:
            messagebox.showerror('Error', f'Could not update password:\n{e}')

    def delete_selected(self):
        sel = self.tree.selection()
        if not sel:
            messagebox.showerror('Error', 'No lecturer selected')
            return
        # values are (Lecturer_ID, full_name, role)
        lid = str(self.tree.item(sel[0])['values'][0]).strip()
        if not messagebox.askyesno('Confirm', f'Delete lecturer {lid}?'):
            return
        try:
            delete_lecturer(lid)
            messagebox.showinfo('Deleted', f'{lid} removed')
            self.load()
        except Exception as e:
            messagebox.showerror('Error', f'Could not delete lecturer:\n{e}')

    def _get_admin_department_id(self) -> int:
        """Return the department ID for the logged-in admin (HOD)."""
        try:
            user = session.current_user
            if isinstance(user, dict) and user.get("role", "").lower() == "admin":
                hod_id = str(user.get("id", "")).strip()
                if hod_id:
                    dept_id = get_hod_department(hod_id)
                    if dept_id is not None:
                        return int(dept_id)
        except Exception:
            pass
        raise RuntimeError("Could not determine the current admin department")

    def go_back(self):
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
