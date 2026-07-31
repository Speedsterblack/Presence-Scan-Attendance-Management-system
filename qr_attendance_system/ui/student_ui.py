import tkinter as tk
from tkinter import messagebox
from tkinter import ttk
from ui.register_student_ui import RegisterStudentUI, open_students_browser
from database.student_db import get_all_students, delete_student, add_student, get_student
from ui.assets_utils import apply_background_image, get_logo_image
from ui import styles as ui_styles
from ui.transcript_ui import TranscriptUI

BG_COLOR = ui_styles.WINDOW_BG
PRIMARY = ui_styles.PRIMARY_COLOR
TEXT = ui_styles.WINDOW_TEXT

class StudentUI:
    def __init__(self, root, parent):
        self.root = root
        self.parent = parent
        # store last deleted students for undo (list of tuples)
        self.last_deleted_students = []

        self.root.title("Manage Students")
        self.root.configure(bg=BG_COLOR)

        # Subtle centered background image behind content
        self._bg_label = apply_background_image(self.root, (520, 520))

        self.root.protocol("WM_DELETE_WINDOW", self.go_back)

        # Small header logo
        self._logo_image = get_logo_image((72, 72))
        if self._logo_image is not None:
            tk.Label(root, image=self._logo_image, bg=BG_COLOR, borderwidth=0).pack(pady=(10, 0))

        tk.Label(
            root,
            text="Student Management",
            font=ui_styles.TITLE_FONT,
            fg=TEXT,
            bg=BG_COLOR,
        ).pack(pady=15)

        tk.Button(
            root,
            text="Register Student",
            command=self.open_register_student_ui,
            width=20,
            font=ui_styles.BUTTON_FONT,
            **ui_styles.PRIMARY_BUTTON,
        ).pack(pady=15)

        tk.Button(
            root,
            text="View Students",
            command=self.open_view_students_ui,
            width=20,
            font=ui_styles.BUTTON_FONT,
            **ui_styles.SUCCESS_BUTTON,
        ).pack(pady=5)

        tk.Button(
            root,
            text="Transcript History",
            command=self.open_transcript_ui,
            width=20,
            font=ui_styles.BUTTON_FONT,
            **ui_styles.SECONDARY_BUTTON,
        ).pack(pady=5)

        tk.Button(
            root,
            text="Remove Student",
            command=self.open_remove_student_ui,
            width=20,
            font=ui_styles.BUTTON_FONT,
            **ui_styles.DANGER_BUTTON,
        ).pack(pady=5)

        tk.Button(
            root,
            text="Go Back",
            command=self.go_back,
            width=20,
            font=ui_styles.BUTTON_FONT,
            **ui_styles.PRIMARY_BUTTON,
        ).pack(pady=20)

        # Lock in a larger default size so the page content is
        # clearly visible and resembles a full application page.
        self.root.update_idletasks()
        screen_w = self.root.winfo_screenwidth()
        # Maximize student window on startup
        self.root.update_idletasks()
        self.root.state('zoomed')
        self.root.minsize(900, 600)

    def create_field(self, label):
        tk.Label(self.root, text=label, bg=BG_COLOR, fg=TEXT, font=ui_styles.LABEL_FONT).pack()
        tk.Entry(self.root, width=40).pack(pady=5)
        
    def open_register_student_ui(self):  
        try:
            was_zoomed = self.root.state() == "zoomed"
        except Exception:
            was_zoomed = False

        self.root.withdraw()
        window = tk.Toplevel()
        try:
            window.state('zoomed')
        except Exception:
            pass
        RegisterStudentUI(window, parent=self.root)

    def open_remove_student_ui(self):
        try:
            was_zoomed = self.root.state() == "zoomed"
        except Exception:
            was_zoomed = False

        self.root.withdraw()
        win = tk.Toplevel(self.root)
        win.title('Remove Student')
        win.geometry('1080x640')
        try:
            win.minsize(980, 560)
        except Exception:
            pass

        try:
            win.state('zoomed')
        except Exception:
            pass

        tk.Label(win, text='Select student(s) to remove', font=('Arial', 12, 'bold')).pack(pady=8)

        # search/filter
        search_frame = tk.Frame(win)
        search_frame.pack(fill='x', padx=10, pady=(10, 4))
        tk.Label(search_frame, text='Search:').pack(side='left')
        search_var = tk.StringVar()
        search_entry = tk.Entry(search_frame, textvariable=search_var)
        search_entry.pack(side='left', fill='x', expand=True, padx=(6,10))

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
        current_filter = tk.StringVar(value='all')

        cols = ('student_id', 'name', 'Department', 'level')
        table_wrap = tk.Frame(win)
        table_wrap.pack(fill='both', expand=True, padx=10, pady=4)
        tree = ttk.Treeview(table_wrap, columns=cols, show='headings', selectmode='extended')
        tree.heading('student_id', text='Student ID', anchor='w')
        tree.heading('name', text='Name', anchor='w')
        tree.heading('Department', text='Department', anchor='w')
        tree.heading('level', text='Level', anchor='w')
        tree.column('student_id', width=150, minwidth=130, anchor='w', stretch=False)
        tree.column('name', width=280, minwidth=200, anchor='w', stretch=True)
        tree.column('Department', width=260, minwidth=180, anchor='w', stretch=True)
        tree.column('level', width=100, minwidth=90, anchor='center', stretch=False)
        tree.pack(side='left', fill='both', expand=True)

        vs = ttk.Scrollbar(table_wrap, orient='vertical', command=tree.yview)
        vs.pack(side='right', fill='y')
        hs = ttk.Scrollbar(win, orient='horizontal', command=tree.xview)
        hs.pack(fill='x', padx=10)
        tree.configure(yscrollcommand=vs.set)
        tree.configure(xscrollcommand=hs.set)

        count_var = tk.StringVar(value='0 student(s)')
        tk.Label(win, textvariable=count_var, anchor='w').pack(fill='x', padx=10, pady=(0, 4))

        # populate
        try:
            rows = get_all_students()
        except Exception as e:
            messagebox.showerror('Error', f'Could not load students:\n{e}')
            win.destroy()
            try:
                self.root.deiconify()
                try:
                    self.root.state("zoomed")
                except Exception:
                    pass
            except Exception:
                pass
            return

        # keep a master list for filtering
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

        btnf = tk.Frame(win)
        btnf.pack(fill='x', padx=10, pady=8)

        def do_delete():
            sel = tree.selection()
            if not sel:
                messagebox.showerror('Error', 'No students selected')
                return
            if not messagebox.askyesno('Confirm', f'Delete the {len(sel)} selected student(s)?'):
                return
            successes = 0
            failures = []
            # clear previous undo buffer
            self.last_deleted_students = []
            for iid in sel:
                values = tree.item(iid, 'values')
                sid = str(values[0]) if values else ''
                if not sid:
                    continue
                try:
                    # capture full student data for undo
                    srow = get_student(sid)
                    if srow:
                        self.last_deleted_students.append((srow[0], srow[1], srow[2], srow[3]))
                    delete_student(sid)
                    successes += 1
                except Exception as e:
                    failures.append((sid, str(e)))

            # refresh filtered view after deletions
            try:
                refreshed_rows = get_all_students()
                master_items.clear()
                for r in refreshed_rows:
                    sid, name, Department, level = r
                    txt = f"{sid} - {name} ({Department}, {level})"
                    master_items.append((sid, name, Department, level, txt))
                filter_list()
            except Exception:
                pass

            message = f'Deleted: {successes}. Failures: {len(failures)}'
            if failures:
                message += '\n' + '\n'.join([f'{s}: {m}' for s, m in failures])
            messagebox.showinfo('Remove Students', message)

        undo_btn = tk.Button(btnf, text='Undo Last Delete', command=lambda: undo_delete(), state='normal' if self.last_deleted_students else 'disabled')
        undo_btn.pack(side='left', padx=6)
        tk.Button(btnf, text='Delete Selected', bg='#e53935', fg='white', command=lambda: (do_delete(), undo_btn.config(state='normal' if self.last_deleted_students else 'disabled'))).pack(side='left', padx=6)
        def _cancel_and_restore():
            try:
                win.destroy()
            except Exception:
                pass
            try:
                self.root.deiconify()
                try:
                    self.root.state("zoomed")
                except Exception:
                    pass
            except Exception:
                pass

        tk.Button(btnf, text='Cancel', command=_cancel_and_restore).pack(side='right', padx=6)

        def undo_delete():
            if not self.last_deleted_students:
                messagebox.showinfo('Undo', 'Nothing to undo')
                return
            restored = 0
            errs = []
            for sid, name, Department, level in self.last_deleted_students:
                try:
                    add_student(sid, name, Department, level)
                    restored += 1
                except Exception as e:
                    errs.append((sid, str(e)))
            self.last_deleted_students = []
            # reload master_items and listbox
            try:
                new_rows = get_all_students()
                master_items.clear()
                for r in new_rows:
                    sid, name, Department, level = r
                    txt = f"{sid} - {name} ({Department}, {level})"
                    master_items.append((sid, name, Department, level, txt))
                filter_list()
            except Exception:
                pass
            msg = f'Restored: {restored}. Failures: {len(errs)}'
            if errs:
                msg += '\n' + '\n'.join([f'{s}: {m}' for s, m in errs])
            messagebox.showinfo('Undo Delete', msg)

        # initial render + focus
        filter_list()
        try:
            search_entry.focus_set()
        except Exception:
            pass

    def open_view_students_ui(self):
        # Open the shared student browser window while keeping this
        # Student Management page visible in the background.
        open_students_browser(self.root)

    def open_transcript_ui(self):
        try:
            was_zoomed = self.root.state() == "zoomed"
        except Exception:
            was_zoomed = False

        self.root.withdraw()
        window = tk.Toplevel(self.root)
        TranscriptUI(window, parent=self.root)
        try:
            window.state("zoomed")
        except Exception:
            pass

    def go_back(self):
        self.root.destroy()
        try:
            self.parent.deiconify()
            try:
                self.parent.state("zoomed")
            except Exception:
                pass
        except Exception:
            pass