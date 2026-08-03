import tkinter as tk
from tkinter import messagebox, filedialog, ttk
import os
import csv
import sys
import inspect
from typing import Any, Callable, Optional

from ui import styles as ui_styles
from utils import session
from database.hod_db import get_hod_department
from database.department_db import get_department

try:
    from PIL import Image, ImageTk  # type: ignore[import-not-found]
except ImportError:
    tk.Tk().withdraw()
    messagebox.showerror("Error", "PIL (Pillow) is not installed. Please run: pip install Pillow")
    sys.exit(1)

from database import student_db
from qr.qr_generator import generate_qr
from ui.assets_utils import apply_background_image, get_logo_image


def _get_db_fn(*names: str) -> Optional[Callable[..., Any]]:
    for name in names:
        fn = getattr(student_db, name, None)
        if callable(fn):
            return fn
    return None


def _get_student_safe(student_id: str):
    fn = _get_db_fn("get_student", "fetch_student", "find_student")
    return fn(student_id) if fn else None


def _get_all_students_safe():
    fn = _get_db_fn("get_all_students", "fetch_all_students", "list_students")
    return fn() if fn else []


def _add_student_safe(student_id: str, name: str, Department: str, level: str):
    fn = _get_db_fn("add_student", "create_student", "insert_student")
    if not fn:
        raise AttributeError("No student add function found in database.student_db")

    # Try a few positional signatures seen in various DB layers
    for args in [
        (student_id, name, Department, level),
        (student_id, name, Department),
        (student_id, name),
    ]:
        try:
            return fn(*args)
        except TypeError:
            pass

    # Try keyword mapping by parameter names
    sig = inspect.signature(fn)
    kwargs: dict[str, Any] = {}
    for p in sig.parameters.values():
        n = p.name.lower()
        if n in ("student_id", "sid", "id"):
            kwargs[p.name] = student_id
        elif n in ("name", "full_name", "student_name"):
            kwargs[p.name] = name
        elif n in ("department", "dept", "Department", "program", "course"):
            kwargs[p.name] = Department
        elif n in ("level", "year"):
            kwargs[p.name] = level

    return fn(**kwargs)


def open_students_browser(parent: tk.Tk | tk.Toplevel, show_qr_func: Optional[Callable[[str, str], None]] = None):
    """Open a window listing all students with optional QR preview/print.

    This is shared between the registration screen and other parts of the
    application (for example, the main Student Management page). To avoid
    multiple full-size windows stacking on top of each other, the ``parent``
    window is temporarily hidden while this browser is open and restored
    when it closes.

    If ``show_qr_func`` is provided, it will be called as
    ``show_qr_func(qr_path, student_id)`` when the user clicks Preview QR.
    """

    # Hide the parent while the list is open so the user only sees
    # one main window at a time.
    try:
        parent.withdraw()
    except Exception:
        pass

    win = tk.Toplevel(parent)
    win.title('Students')
    win.geometry('1080x640')
    try:
        win.minsize(980, 560)
    except Exception:
        pass
    try:
        win.state('zoomed')
    except Exception:
        pass
    cols = ('student_id', 'name', 'Department', 'level')

    # Search/filter area
    search_frame = tk.Frame(win)
    search_frame.pack(fill='x', padx=10, pady=(10, 4))
    tk.Label(search_frame, text='Search:').pack(side='left')
    search_var = tk.StringVar(master=win)
    search_entry = tk.Entry(search_frame, textvariable=search_var)
    search_entry.pack(side='left', fill='x', expand=True, padx=(6, 10))


    def clear_search():
        search_var.set('')
        current_filter.set('all')
        filter_list()
        try:
            search_entry.focus_set()
        except Exception:
            pass

    tk.Button(
        search_frame,
        text='Clear Search',
        command=clear_search,
        font=ui_styles.BUTTON_FONT,
        **ui_styles.MUTED_BUTTON,
    ).pack(side='left')


    filter_frame = tk.Frame(win)
    filter_frame.pack(fill='x', padx=10, pady=(0, 6))
    tk.Label(filter_frame, text='Quick filters:').pack(side='left', padx=(0, 8))
    current_filter = tk.StringVar(master=win, value='all')

    table_wrap = tk.Frame(win)
    table_wrap.pack(fill='both', expand=True, padx=10, pady=4)
    tree = ttk.Treeview(table_wrap, columns=cols, show='headings', selectmode='browse')
    for c in cols:
        heading_text = c.replace('_', ' ').title()
        if heading_text.endswith(" Id"):
            heading_text = heading_text[:-3] + " ID"
        tree.heading(c, text=heading_text, anchor='w')
        if c == 'student_id':
            tree.column(c, width=150, minwidth=130, anchor='w', stretch=False)
        elif c == 'name':
            tree.column(c, width=280, minwidth=200, anchor='w', stretch=True)
        elif c == 'Department':
            tree.column(c, width=260, minwidth=180, anchor='w', stretch=True)
        else:
            tree.column(c, width=100, minwidth=90, anchor='center', stretch=False)
    tree.pack(side='left', fill='both', expand=True)

    vs = ttk.Scrollbar(table_wrap, orient='vertical', command=tree.yview)
    vs.pack(side='right', fill='y')
    hs = ttk.Scrollbar(win, orient='horizontal', command=tree.xview)
    hs.pack(fill='x', padx=10)
    tree.configure(yscrollcommand=vs.set)
    tree.configure(xscrollcommand=hs.set)

    count_var = tk.StringVar(master=win, value='0 student(s)')
    tk.Label(win, textvariable=count_var, anchor='w').pack(fill='x', padx=10, pady=(0, 4))

    try:
        rows = _get_all_students_safe()
    except Exception as e:  # pragma: no cover - defensive UI code
        messagebox.showerror('Error', f'Could not load students:\n{e}')
        win.destroy()
        try:
            parent.deiconify()
            try:
                parent.state("zoomed")
            except Exception:
                pass
        except Exception:
            pass
        return
        return

    # master list for filtering
    master_items = []
    for r in rows:
        sid, name, Department, level = r
        txt = f"{sid} - {name} ({Department}, {level})"
        master_items.append((sid, name, Department, level, txt))
        tree.insert('', 'end', values=(sid, name, Department, level))

    def _to_level_number(level: str) -> int:
        digits = ''.join(ch for ch in str(level or '') if ch.isdigit())
        return int(digits) if digits else -1

    def _passes_quick_filter(sid, name, Department, level, txt):
        mode = current_filter.get()
        level_num = _to_level_number(level)
        if mode == 'lvl100':
            return level_num == 100
        if mode == 'lvl200':
            return level_num == 200
        if mode == 'lvl300':
            return level_num == 300
        if mode == 'lvl400':
            return level_num == 400
        if mode == 'no_Department':
            return not str(Department or '').strip()
        return True

    def filter_list(*_):
        q = search_var.get().strip().lower()
        tree.delete(*tree.get_children())
        visible = 0
        for sid, name, Department, level, txt in master_items:
            if _passes_quick_filter(sid, name, Department, level, txt) and (not q or q in txt.lower()):
                tree.insert('', 'end', values=(sid, name, Department, level))
                visible += 1
        count_var.set(f'{visible} student(s)')

    def _set_filter(mode):
        current_filter.set(mode)
        filter_list()

    chip_specs = [
        ('All', 'all', ui_styles.SECONDARY_BUTTON),
        ('Level 100', 'lvl100', ui_styles.INFO_BUTTON),
        ('Level 200', 'lvl200', ui_styles.INFO_BUTTON),
        ('Level 300', 'lvl300', ui_styles.SUCCESS_BUTTON),
        ('Level 400', 'lvl400', ui_styles.WARNING_BUTTON),
        ('No Department', 'no_Department', ui_styles.WARNING_BUTTON),
    ]
    for text, mode, style in chip_specs:
        tk.Button(
            filter_frame,
            text=text,
            command=lambda m=mode: _set_filter(m),
            font=ui_styles.BUTTON_FONT,
            **style,
        ).pack(side='left', padx=(0, 6))

    search_var.trace_add('write', filter_list)

    def close_browser():
        try:
            win.destroy()
        except Exception:
            pass
        try:
            parent.deiconify()
            try:
                parent.state("zoomed")
            except Exception:
                pass
        except Exception:
            pass

    # Controls: Preview / Print / Close
    btnf = tk.Frame(win)
    btnf.pack(fill='x', padx=10, pady=8)

    preview_btn = tk.Button(
        btnf,
        text='Preview QR',
        state='disabled',
        font=ui_styles.BUTTON_FONT,
        **ui_styles.SUCCESS_BUTTON,
    )
    preview_btn.pack(side='left', padx=6)
    print_btn = tk.Button(
        btnf,
        text='Print QR',
        state='disabled',
        font=ui_styles.BUTTON_FONT,
        **ui_styles.INFO_BUTTON,
    )
    print_btn.pack(side='left', padx=6)
    tk.Button(
        btnf,
        text='Close',
        command=close_browser,
        font=ui_styles.BUTTON_FONT,
        **ui_styles.MUTED_BUTTON,
    ).pack(side='right')
    win.protocol("WM_DELETE_WINDOW", close_browser)

    def get_selected_sid():
        sel = tree.selection()
        if not sel:
            return None
        vals = tree.item(sel[0])['values']
        if not vals:
            return None
        return str(vals[0])

    def update_buttons(*_):
        sid = get_selected_sid()
        state = 'normal' if sid else 'disabled'
        # Preview only makes sense if we have a callback
        preview_btn.config(state=state if show_qr_func else 'disabled')
        print_btn.config(state=state)

    tree.bind('<<TreeviewSelect>>', update_buttons)

    def find_qr_path(sid: str):
        # Try assets mirror first, then primary folder
        candidates = [
            os.path.join('assets', 'qrcodes', f"{sid}.png"),
            os.path.join('qr_codes', f"{sid}.png"),
        ]
        for c in candidates:
            if os.path.exists(c):
                return c
        return None

    def on_preview():
        if not show_qr_func:
            messagebox.showinfo('Preview', 'QR preview is not available in this view.')
            return
        sid = get_selected_sid()
        if not sid:
            return
        path = find_qr_path(sid)
        if not path:
            if messagebox.askyesno('Generate QR', f'No QR found for {sid}. Generate now?'):
                try:
                    path = generate_qr(sid)
                except Exception as e:  # pragma: no cover - UI error
                    messagebox.showerror('Error', f'Could not generate QR:\n{e}')
                    return
            else:
                return

        try:
            show_qr_func(path, sid)
        except Exception as e:  # pragma: no cover - UI error
            messagebox.showerror('Error', f'Could not open QR:\n{e}')

    def on_print():
        sid = get_selected_sid()
        if not sid:
            return
        path = find_qr_path(sid)
        if not path:
            if messagebox.askyesno('Generate QR', f'No QR found for {sid}. Generate now?'):
                try:
                    path = generate_qr(sid)
                except Exception as e:  # pragma: no cover - UI error
                    messagebox.showerror('Error', f'Could not generate QR:\n{e}')
                    return
            else:
                return

        try:
            os.startfile(path, 'print')
            messagebox.showinfo('Print', 'QR sent to printer')
        except Exception as e:  # pragma: no cover - UI error
            messagebox.showerror('Error', f'Printing failed:\n{e}')

    preview_btn.config(command=on_preview)
    print_btn.config(command=on_print)

    # initial render + focus
    filter_list()
    try:
        search_entry.focus_set()
    except Exception:
        pass


class RegisterStudentUI:
    def __init__(self, root, parent):
        self.parent = parent
        self.root = root

        self.root.title("Student Registration")
        self.root.protocol("WM_DELETE_WINDOW", self.open_student_ui)

        # Subtle centered background image behind content
        self._bg_label = apply_background_image(self.root, (520, 520))

        # Small header logo
        self._logo_image = get_logo_image((64, 64), master=self.root)
        if self._logo_image is not None:
            tk.Label(root, image=self._logo_image, borderwidth=0).pack(pady=(8, 0))

        tk.Label(
            root, text="Register Student",
            font=("Arial", 16, "bold")
        ).pack(pady=10)

        # Resolve the department for the current admin (HOD) user.
        # This department will be assigned automatically to every
        # registered student, so we do not ask for it in the form.
        self.department_name = self._get_admin_department_name()

        # Explicit attributes for type checkers
        self.student_id: tk.Entry = self.create_field("Student ID")
        self.full_name: tk.Entry = self.create_field("Full Name")
        self.level: tk.Entry = self.create_field("Level")

        # Show the department as read-only information so the
        # admin can see which department will be applied.
        dept_text = self.department_name or "(No department configured)"
        tk.Label(
            root,
            text=f"Department: {dept_text}",
            anchor="w",
        ).pack(pady=(0, 8))

        tk.Button(
            root,
            text="Register Student",
            command=self.register_student,
            width=20,
            font=ui_styles.BUTTON_FONT,
            **ui_styles.PRIMARY_BUTTON,
        ).pack(pady=8)
        # CSV import button
        tk.Button(
            root,
            text="Import CSV",
            command=self.import_from_csv,
            width=20,
            font=ui_styles.BUTTON_FONT,
            **ui_styles.INFO_BUTTON,
        ).pack(pady=6)

        # View students button
        tk.Button(
            root,
            text="View Students",
            command=self.open_view_students,
            width=20,
            font=ui_styles.BUTTON_FONT,
            **ui_styles.SUCCESS_BUTTON,
        ).pack(pady=6)

        tk.Button(
            root,
            text="Go Back",
            command=self.open_student_ui,
            width=20,
            font=ui_styles.BUTTON_FONT,
            **ui_styles.PRIMARY_BUTTON,
        ).pack(pady=6)

        # Ensure the registration form opens at a size that
        # shows all controls and can't be shrunk below that.
        self.root.update_idletasks()
        self.root.minsize(self.root.winfo_width(), self.root.winfo_height())

    def create_field(self, label_text):
        frame = tk.Frame(self.root)
        frame.pack(pady=5)

        tk.Label(frame, text=label_text, width=15, anchor="w").pack(side="left")
        entry = tk.Entry(frame, width=25)
        entry.pack(side="right")
        return entry

    def register_student(self):
        student_id = self.student_id.get().strip()
        name = self.full_name.get().strip()
        level = self.level.get().strip()

        # Use the admin's department as the Department/department
        # for all newly-registered students.
        Department = (self.department_name or "").strip()

        if not Department:
            messagebox.showerror(
                "Error",
                "No department is configured for the current admin. "
                "Please configure departments/HODs before registering students.",
            )
            return

        if not all([student_id, name, level]):
            messagebox.showerror("Error", "All fields are required")
            return

        if _get_student_safe(student_id):
            messagebox.showerror("Error", "Student ID already exists")
            return

        _add_student_safe(student_id, name, Department, level)

        qr_path = generate_qr(student_id)
        self.show_qr(qr_path, student_id)

        messagebox.showinfo(
            "Success",
            f"Student registered successfully!\nQR Code generated for {student_id}"
        )

        self.clear_fields()

    def clear_fields(self):
        self.student_id.delete(0, tk.END)
        self.full_name.delete(0, tk.END)
        self.level.delete(0, tk.END)

    def _get_admin_department_name(self) -> str:
        """Return the department name for the logged-in admin (HOD).

        If anything fails (no session, no department mapping), this
        safely returns an empty string.
        """
        try:
            user = session.current_user
        except Exception:
            user = None

        if not isinstance(user, dict):
            return ""

        # Only HOD/admin accounts have departments in this schema.
        role = str(user.get("role", "")).lower()
        if role != "admin":
            return ""

        hod_id = str(user.get("id", "")).strip()
        if not hod_id:
            return ""

        try:
            dept_id = get_hod_department(hod_id)
        except Exception:
            return ""

        if dept_id is None:
            return ""

        try:
            dept = get_department(int(dept_id))
        except Exception:
            return ""

        if not dept or len(dept) < 2:
            return ""

        # dept tuple is (id, name, university_id)
        return str(dept[1])

    def open_student_ui(self):
        try:
            self.root.destroy()

            self.parent.deiconify()
            try:
                self.parent.state("zoomed")
            except Exception:
                pass

        except Exception as e:
            print(f"Failed to open student UI: {e}")

    def show_qr(self, qr_path, student_id):
        qr_window = tk.Toplevel(self.root)
        qr_window.title("Student QR Code")
        qr_window.geometry("300x350")
        try:
            qr_window.state('zoomed')
        except Exception:
            pass

        img = Image.open(qr_path)
        img = img.resize((200, 200))
        photo = ImageTk.PhotoImage(img, master=qr_window)

        tk.Label(qr_window, image=photo).pack(pady=10)
        tk.Label(qr_window, text=f"Student ID: {student_id}").pack()

        tk.Button(
            qr_window,
            text="Print QR Code",
            command=lambda: os.startfile(qr_path, "print")
        ).pack(pady=10)
        setattr(qr_window, "_photo_ref", photo)  # prevent garbage collection without dynamic attribute warning

    # ================ VIEW STUDENTS ================
    def open_view_students(self):
        open_students_browser(self.root, self.show_qr)

    # ---------------- CSV IMPORT ----------------
    def import_from_csv(self, path=None, dry_run=False):
        """Import students from CSV.

        Expected columns: student_id, full_name (or name), level.
        The department/Department is always taken from the current
        admin (HOD) account, so any department column in the CSV is
        ignored.
        If path is None, a file dialog is shown. If dry_run=True the parsed
        rows are returned without writing to the DB.
        """
        try:
            # Resolve the admin's department once for the entire import.
            Department = (self.department_name or "").strip()
            if not Department:
                messagebox.showerror(
                    "Error",
                    "No department is configured for the current admin. "
                    "Cannot import students without a department.",
                )
                return

            if not path:
                path = filedialog.askopenfilename(title='Select student CSV', filetypes=[('CSV files','*.csv'),('All files','*.*')])
                if not path:
                    return

            parsed = []
            with open(path, newline='', encoding='utf-8') as f:
                reader = csv.DictReader(f)
                for i, row in enumerate(reader, start=1):
                    sid = (row.get('student_id') or row.get('id') or '').strip()
                    name = (row.get('full_name') or row.get('name') or '').strip()
                    level = (row.get('level') or '').strip()

                    if not (sid and name and level):
                        parsed.append((False, i, sid, name, 'missing required fields'))
                        continue

                    parsed.append((True, i, sid, name, Department, level))

            # The rest of the import logic would go here, if needed.
            if dry_run:
                return parsed

            # show preview dialog where user can select rows to import
            self._show_import_preview(parsed, path)
            return parsed

        except Exception as e:
            messagebox.showerror('Error', f'Could not import CSV:\n{e}')

    def _show_import_preview(self, parsed, path):
        win = tk.Toplevel(self.root)
        win.title('Import Preview')
        win.geometry('700x420')
        try:
            win.state('zoomed')
        except Exception:
            pass

        lbl = tk.Label(win, text=f'Preview {len(parsed)} rows (select rows to import)', font=('Arial', 12, 'bold'))
        lbl.pack(pady=6)

        frame = tk.Frame(win)
        frame.pack(fill='both', expand=True, padx=8, pady=4)

        cols = ('#','student_id','name','Department','level')
        tree = ttk.Treeview(frame, columns=cols, show='headings', selectmode='extended')
        for c in cols:
            if c == '#':
                heading_text = '#'
            else:
                heading_text = c.replace('_', ' ').title()
                if heading_text.endswith(" Id"):
                    heading_text = heading_text[:-3] + " ID"
            tree.heading(c, text=heading_text, anchor='w')
            tree.column(c, width=120 if c!='#' else 40, anchor='w')
        tree.pack(side='left', fill='both', expand=True)

        vs = ttk.Scrollbar(frame, orient='vertical', command=tree.yview)
        vs.pack(side='left', fill='y')
        tree.configure(yscrollcommand=vs.set)

        # populate tree and track validity
        row_valid = {}
        for item in parsed:
            if item[0]:
                _, i, sid, name, Department, level = item
                iid = tree.insert('', 'end', values=(i, sid, name, Department, level))
                row_valid[iid] = True
            else:
                _, i, sid, name, reason = item
                iid = tree.insert('', 'end', values=(i, sid or '<missing>', name or '<missing>', reason, ''))
                row_valid[iid] = False

        ctrl_frame = tk.Frame(win)
        ctrl_frame.pack(fill='x', pady=6)

        sel_all = tk.Button(
            ctrl_frame,
            text='Select All',
            command=lambda: tree.selection_set(tree.get_children()),
            font=ui_styles.BUTTON_FONT,
            **ui_styles.SECONDARY_BUTTON,
        )
        sel_all.pack(side='left', padx=6)
        desel_all = tk.Button(
            ctrl_frame,
            text='Deselect All',
            command=lambda: tree.selection_remove(tree.get_children()),
            font=ui_styles.BUTTON_FONT,
            **ui_styles.MUTED_BUTTON,
        )
        desel_all.pack(side='left', padx=6)

        skip_existing_var = tk.BooleanVar(master=win, value=True)
        generate_qr_var = tk.BooleanVar(master=win, value=True)
        tk.Checkbutton(ctrl_frame, text='Skip existing students', variable=skip_existing_var).pack(side='left', padx=12)
        tk.Checkbutton(ctrl_frame, text='Generate QR codes', variable=generate_qr_var).pack(side='left', padx=12)

        progress = ttk.Progressbar(win, orient='horizontal', mode='determinate')
        progress.pack(fill='x', padx=8, pady=(6,2))
        status = tk.Label(win, text='Ready')
        status.pack(fill='x', padx=8)

        def do_import():
            sel = tree.selection()
            if not sel:
                messagebox.showerror('Error', 'No rows selected')
                return
            total = len(sel)
            progress['maximum'] = total
            success = 0
            failures = []
            for idx, iid in enumerate(sel, start=1):
                vals = tree.item(iid)['values']

                if not row_valid.get(iid, False):
                    failures.append((vals, 'invalid row from CSV preview'))
                    progress['value'] = idx
                    status.config(text=f'Processed {idx}/{total}')
                    win.update_idletasks()
                    continue

                try:
                    sid = str(vals[1]).strip()
                    name = str(vals[2]).strip()
                    Department = str(vals[3]).strip()
                    level = str(vals[4]).strip()
                except Exception:
                    failures.append((vals, 'malformed row'))
                    progress['value'] = idx
                    status.config(text=f'Processed {idx}/{total}')
                    win.update_idletasks()
                    continue

                if not (sid and name and Department and level):
                    failures.append((sid or vals, 'missing required fields'))
                    progress['value'] = idx
                    status.config(text=f'Processed {idx}/{total}')
                    win.update_idletasks()
                    continue

                try:
                    if skip_existing_var.get() and _get_student_safe(sid):
                        failures.append((sid, 'exists'))
                    else:
                        _add_student_safe(sid, name, Department, level)
                        if generate_qr_var.get():
                            try:
                                generate_qr(sid)
                            except Exception:
                                pass
                        success += 1
                except Exception as e:
                    failures.append((sid, str(e)))

                progress['value'] = idx
                status.config(text=f'Processed {idx}/{total} — successes: {success} failures: {len(failures)}')
                win.update_idletasks()

            # show import summary
            if failures:
                lines = [f'Imported: {success}. Failures: {len(failures)}', 'Top failures:']
                for f in failures[:10]:
                    if isinstance(f, tuple) and len(f) == 2:
                        lines.append(f'- {f[0]}: {f[1]}')
                    else:
                        lines.append(f'- {f}')
                summary = '\n'.join(lines)
                messagebox.showinfo('Import Complete', summary)
            else:
                messagebox.showinfo('Import Complete', f'Imported: {success}. Failures: 0')

            win.destroy()

        import_btn = tk.Button(
            ctrl_frame,
            text='Import Selected',
            command=do_import,
            font=ui_styles.BUTTON_FONT,
            **ui_styles.PRIMARY_BUTTON,
        )
        import_btn.pack(side='right', padx=6)

        cancel_btn = tk.Button(
            ctrl_frame,
            text='Cancel',
            command=win.destroy,
            font=ui_styles.BUTTON_FONT,
            **ui_styles.MUTED_BUTTON,
        )
        cancel_btn.pack(side='right', padx=6)
