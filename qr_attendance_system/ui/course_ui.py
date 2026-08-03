import tkinter as tk
from tkinter import messagebox, filedialog
import csv
import os
import tempfile
from tkinter import ttk

from database.course_db import get_all_courses, get_course
from database.timetable_db import add_timetable
from database.lecturer_db import get_all_lecturers
from config import settings as app_settings
from ui.assets_utils import apply_background_image, get_logo_image
from ui import styles as ui_styles
from services.course_service import (
    create_course_with_timetable,
    update_course_with_timetable,
    remove_course,
    clear_timetable_for_course,
    restore_timetable_for_course,
    assign_lecturer_to_course,
)

BG_COLOR = ui_styles.WINDOW_BG
PRIMARY = ui_styles.PRIMARY_COLOR
TEXT = ui_styles.WINDOW_TEXT


class CourseUI:
    def __init__(self, root, parent):
        self.root = root
        self.parent = parent

        self.root.title("Manage Courses")
        self.root.configure(bg=BG_COLOR)
        self.root.protocol("WM_DELETE_WINDOW", self.go_back)

        # Subtle centered background image behind content
        self._bg_label = apply_background_image(self.root, (520, 520))

        # Larger header logo (kept in a right column) and page title
        self._logo_image = get_logo_image((160, 160), master=self.root)
        self._logo_label = None
        if self._logo_image is not None:
            self._logo_label = tk.Label(self.root, image=self._logo_image, bg=BG_COLOR, borderwidth=0)

        tk.Label(
            self.root,
            text="Course Management",
            font=ui_styles.TITLE_FONT,
            fg=TEXT,
            bg=BG_COLOR,
        ).pack(pady=(8, 12))

        # Create a two-column content area so form fields align left
        content = tk.Frame(self.root, bg=BG_COLOR)
        content.pack(fill='both', expand=True, padx=8)

        # Left: form container; Right: logo / decorative area
        self.form_container = tk.Frame(content, bg=BG_COLOR)
        self.form_container.pack(side='left', fill='both', expand=True, padx=(50, 16))
        self.right_container = tk.Frame(content, bg=BG_COLOR)
        self.right_container.pack(side='right', fill='y', padx=50)

        # Place the logo in the right column (if available)
        if self._logo_label is not None:
            self._logo_label.pack(in_=self.right_container, pady=(6, 8))

        # ===== FORM FIELDS =====
        self.course_code = self.create_field("Course Code")
        self.course_name = self.create_field("Course Name")
        # Lecturer selector (populated from DB) - place in a labelled row
        # so it lines up with other input fields.
        # This StringVar will hold the LECTURER NAME for display;
        # we map it back to an ID when saving.
        self.lecturer_var = tk.StringVar(master=self.parent)
        self.lecturer_var.set("Assign a lecturer")

        lf = tk.Frame(self.form_container, bg=BG_COLOR)
        lf.pack(fill='x', pady=6)
        lbl = tk.Label(lf, text="Lecturer", bg=BG_COLOR, fg=TEXT, font=ui_styles.LABEL_FONT)
        lbl.config(width=20, anchor='w')
        lbl.grid(row=0, column=0, sticky='w')

        self.lecturer_menu = tk.OptionMenu(lf, self.lecturer_var, "")
        self.lecturer_menu.config(width=40)
        try:
            self.lecturer_menu.config(font=ui_styles.LABEL_FONT)
        except Exception:
            pass
        self.lecturer_menu.grid(row=0, column=1, sticky='w', padx=(18,0))

        # map lecturer id -> name
        self.lecturer_map = {}

        # populate lecturer dropdown
        try:
            self.load_lecturers()
        except Exception:
            pass

        self.credit_hours = self.create_field("Credit Hours")
        # optional per-course grace period (minutes) used for attendance;
        # default comes from global settings.
        self.grace_minutes = self.create_field("Grace Period (minutes)")
        try:
            default_grace = app_settings.get_default_grace_minutes()
            if default_grace:
                self.grace_minutes.insert(0, str(default_grace))
        except Exception:
            pass

        # per-day time inputs
        self.create_day_selector()

        # ===== BUTTONS =====
        # Action buttons (centered row) - uniform sizing and consistent style
        btn_frame = tk.Frame(self.root, bg=BG_COLOR)
        btn_frame.pack(pady=12)

        # CSV import button (allows bulk import of courses + timetables)
        btn_import = tk.Button(btn_frame, text="Import CSV", width=16, font=ui_styles.BUTTON_FONT, command=self.import_from_csv)
        btn_import.config(**ui_styles.INFO_BUTTON)
        btn_import.pack(side="left", padx=8)

        btn_view = tk.Button(btn_frame, text="View Courses", width=16, font=ui_styles.BUTTON_FONT, command=self.open_view_courses)
        btn_view.config(**ui_styles.SUCCESS_BUTTON)
        btn_view.pack(side="left", padx=8)

        b_add = tk.Button(btn_frame, text="Add Course", width=16, font=ui_styles.BUTTON_FONT, command=self.add_course)
        b_add.config(**ui_styles.PRIMARY_BUTTON)
        b_add.pack(side="left", padx=8)

        # undo state kept in the view dialog instead of main form
        self._undo_after_id = None
        self.last_cleared_timetable = None
        self.undo_btn = tk.Button(btn_frame, text="Undo Clear Timetable", width=20, font=ui_styles.BUTTON_FONT, command=self._undo_clear)
        self.undo_btn.config(**ui_styles.WARNING_BUTTON)
        self.undo_btn.pack(side='left', padx=8)

        # Go Back is a secondary action - align under buttons
        b_back = tk.Button(self.root, text="Go Back", width=18, font=ui_styles.BUTTON_FONT, command=self.go_back)
        b_back.config(**ui_styles.MUTED_BUTTON)
        b_back.pack(pady=(8,12))

        # Ensure the course management window opens large enough
        # to resemble a full application page.
        self.root.update_idletasks()
        screen_w = self.root.winfo_screenwidth()
        screen_h = self.root.winfo_screenheight()
        win_w = max(int(screen_w * 0.7), 1100)
        # Maximize course window on startup
        self.root.update_idletasks()
        self.root.state('zoomed')
        self.root.minsize(1000, 650)

    # ================= HELPERS =================

    def create_field(self, label_text):
        # use a small frame so labels and entries align nicely
        parent = getattr(self, 'form_container', self.root)
        frame = tk.Frame(parent, bg=BG_COLOR)
        frame.pack(fill='x', pady=6)

        lbl = tk.Label(frame, text=label_text, bg=BG_COLOR, fg=TEXT, font=ui_styles.LABEL_FONT)
        # fixed label width so fields align vertically
        lbl.config(width=20, anchor='w')
        lbl.grid(row=0, column=0, sticky='w')

        entry = tk.Entry(frame, width=48, font=ui_styles.LABEL_FONT)
        entry.grid(row=0, column=1, sticky='w', padx=(18,0))
        return entry

    def create_day_selector(self):
        parent = getattr(self, 'form_container', self.root)
        tk.Label(
            parent,
            text="Course Timetable (select days and enter start/end times)",
            bg=BG_COLOR,
            fg=TEXT,
            font=ui_styles.LABEL_FONT,
        ).pack(anchor="w")

        # create rows for each day with checkbox + start/end time entries
        frame = tk.Frame(parent, bg=BG_COLOR)
        frame.pack(pady=6, anchor='w')

        tk.Label(frame, text="Day", bg=BG_COLOR, fg=TEXT, width=6, font=ui_styles.LABEL_FONT).grid(row=0, column=0)
        tk.Label(frame, text="Enabled", bg=BG_COLOR, fg=TEXT, width=8, font=ui_styles.LABEL_FONT).grid(row=0, column=1)
        tk.Label(frame, text="Start (HH:MM)", bg=BG_COLOR, fg=TEXT, width=12, font=ui_styles.LABEL_FONT).grid(row=0, column=2)
        tk.Label(frame, text="End (HH:MM)", bg=BG_COLOR, fg=TEXT, width=12, font=ui_styles.LABEL_FONT).grid(row=0, column=3)

        self.day_vars = {}
        # Only allow weekdays (Monday to Friday)
        for i, day in enumerate(["Mon", "Tue", "Wed", "Thu", "Fri"], start=1):
            tk.Label(frame, text=day, bg=BG_COLOR, fg=TEXT, width=6, font=ui_styles.LABEL_FONT).grid(row=i, column=0, sticky='w', pady=2)
            var = tk.BooleanVar(master=self.parent)
            cb = tk.Checkbutton(frame, variable=var, bg=BG_COLOR)
            cb.grid(row=i, column=1)

            start_entry = tk.Entry(frame, width=14, font=ui_styles.LABEL_FONT)
            start_entry.grid(row=i, column=2, padx=6, pady=2)

            end_entry = tk.Entry(frame, width=14, font=ui_styles.LABEL_FONT)
            end_entry.grid(row=i, column=3, padx=6, pady=2)

            self.day_vars[day] = (var, start_entry, end_entry)

    def clear_fields(self):
        self.course_code.delete(0, tk.END)
        self.course_name.delete(0, tk.END)
        # lecturer is now a dropdown; reset via `lecturer_var` below
        self.credit_hours.delete(0, tk.END)
        self.grace_minutes.delete(0, tk.END)
        try:
            default_grace = app_settings.get_default_grace_minutes()
            if default_grace:
                self.grace_minutes.insert(0, str(default_grace))
        except Exception:
            pass
        # clear per-day time entries
        for day, (var, start_e, end_e) in self.day_vars.items():
            var.set(False)
            start_e.delete(0, tk.END)
            end_e.delete(0, tk.END)

        # reset lecturer selection
        try:
            self.lecturer_var.set("")
        except Exception:
            pass

    # ================= LOGIC =================

    def add_course(self):
        code = self.course_code.get().strip()
        name = self.course_name.get().strip()
        lecturer_name = self.lecturer_var.get().strip()   # display name
        hours = self.credit_hours.get().strip()
        grace = self.grace_minutes.get().strip()

        selected_days = [
            day for day, (var, s, e) in self.day_vars.items() if var.get()
        ]

        # resolve lecturer_id from selected name
        lecturer_id = None
        for lid, lname in self.lecturer_map.items():
            if lname == lecturer_name:
                lecturer_id = lid
                break

        # ===== VALIDATION =====
        if not all([code, name, lecturer_name, hours]):
            messagebox.showerror("Error", "All fields are required")
            return

        if lecturer_id is None:
            messagebox.showerror("Error", "Invalid lecturer selected")
            return

        if not selected_days:
            messagebox.showerror("Error", "Select at least one day")
            return

        if not hours.isdigit():
            messagebox.showerror("Error", "Credit hours must be numeric")
            return

        grace_val = 0
        if grace:
            if not grace.isdigit():
                messagebox.showerror("Error", "Grace period must be numeric minutes")
                return
            grace_val = int(grace)

        try:
            # collect raw day entries; validation is handled in the service layer
            day_entries = []
            for day, (var, start_e, end_e) in self.day_vars.items():
                if var.get():
                    s = start_e.get().strip()
                    e = end_e.get().strip()
                    day_entries.append((day, s, e))

            # Delegate business rules and persistence to the service layer
            create_course_with_timetable(
                code,
                name,
                lecturer_id,
                int(hours),
                grace_val,
                day_entries,
            )

            messagebox.showinfo("Success", "Course added successfully")
            self.clear_fields()
            self.load_courses()

        except ValueError as e:
            # business-rule violations from course_service
            messagebox.showerror("Error", str(e))
        except Exception as e:
            messagebox.showerror("Error", f"Could not add course:\n{e}")

    # ================= NAV =================

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

    # ================= Course list helpers =================

    def load_courses(self):
        """Refresh any course-related state on the main form.

        The older inline "Existing Courses" listbox has been removed
        in favour of the dedicated View Courses dialog, so this now
        simply reloads lecturer options as needed.
        """

        # ensure lecturer list is current
        self.load_lecturers()

    # ================ VIEW COURSES ================
    def open_view_courses(self):
        from database.course_db import get_all_courses, get_course

        # Treat the courses list as a full-page view inside the
        # Course Management flow: hide this window while the list
        # is open, then restore it when the user closes the list.
        try:
            was_zoomed = self.root.state() == "zoomed"
        except Exception:
            was_zoomed = False

        self.root.withdraw()

        win = tk.Toplevel(self.root)
        win.title('Courses')
        win.geometry('1080x640')
        try:
            win.minsize(980, 560)
        except Exception:
            pass
        try:
            win.state('zoomed')
        except Exception:
            pass

        def close_view():
            win.destroy()
            try:
                if was_zoomed:
                    self.root.state("zoomed")
                self.root.deiconify()
            except Exception:
                pass

        win.protocol("WM_DELETE_WINDOW", close_view)

        # Search + quick filters
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

        cols = ('course_code', 'course_name', 'lecturer', 'hours', 'start', 'end', 'grace_min')
        table_wrap = tk.Frame(win)
        table_wrap.pack(fill='both', expand=True, padx=10, pady=4)
        tree = ttk.Treeview(table_wrap, columns=cols, show='headings', selectmode='browse')
        for c in cols:
            heading_text = c.replace('_', ' ').title()
            if heading_text.endswith(' Min'):
                heading_text = 'Grace (min)'
            tree.heading(c, text=heading_text, anchor='w')
            if c == 'course_code':
                tree.column(c, width=120, minwidth=110, anchor='w', stretch=False)
            elif c == 'course_name':
                tree.column(c, width=320, minwidth=220, anchor='w', stretch=True)
            elif c == 'lecturer':
                tree.column(c, width=200, minwidth=140, anchor='w', stretch=True)
            elif c == 'hours':
                tree.column(c, width=90, minwidth=80, anchor='center', stretch=False)
            elif c in ('start', 'end'):
                tree.column(c, width=110, minwidth=90, anchor='center', stretch=False)
            else:
                tree.column(c, width=110, minwidth=90, anchor='center', stretch=False)
        tree.pack(side='left', fill='both', expand=True)

        vs = ttk.Scrollbar(table_wrap, orient='vertical', command=tree.yview)
        vs.pack(side='right', fill='y')
        hs = ttk.Scrollbar(win, orient='horizontal', command=tree.xview)
        hs.pack(fill='x', padx=10)
        tree.configure(yscrollcommand=vs.set)
        tree.configure(xscrollcommand=hs.set)

        count_var = tk.StringVar(master=win, value='0 courses')
        tk.Label(win, textvariable=count_var, anchor='w').pack(fill='x', padx=10, pady=(0, 4))

        try:
            rows = get_all_courses()
        except Exception as e:
            messagebox.showerror('Error', f'Could not load courses:\n{e}')
            win.destroy()
            return

        # build lecturer id -> name map for display
        try:
            lec_list = get_all_lecturers()
            lec_map = {str(l[0]): l[1] for l in lec_list}
        except Exception:
            lec_map = {}

        # import here to avoid circular imports at module load
        try:
            from database.timetable_db import get_timetable_for_course
        except Exception:
            get_timetable_for_course = None

        master_items = []
        for r in rows:
            # schema from course_db: (course_code, course_title, department_id, lecturer_id, credit_hours, grace_minutes)
            code = r[0]
            name = r[1]
            lecturer_id = r[3]
            hours_val = r[4] if len(r) > 4 else 0
            grace_val = r[5] if len(r) > 5 else 0
            lecturer_name = lec_map.get(str(lecturer_id), str(lecturer_id) or '')

            # derive a simple start/end summary from the timetable
            start_disp = ''
            end_disp = ''
            if get_timetable_for_course is not None:
                try:
                    trows = get_timetable_for_course(code)
                    if trows:
                        # use earliest start and latest end across all days
                        starts = [tr[1] for tr in trows]
                        ends = [tr[2] for tr in trows]
                        start_disp = min(starts)
                        end_disp = max(ends)
                except Exception:
                    start_disp = ''
                    end_disp = ''

            txt = f"{code} - {name} ({lecturer_name}, {hours_val}h, {start_disp}-{end_disp}, grace {grace_val}m)"
            master_items.append((code, name, lecturer_name, hours_val, start_disp, end_disp, grace_val, txt))
            tree.insert('', 'end', values=(code, name, lecturer_name, hours_val, start_disp, end_disp, grace_val))

        def _passes_quick_filter(code, name, lecturer_name, hours, start_disp, end_disp, grace_val):
            mode = current_filter.get()
            if mode == 'with_tt':
                return bool(start_disp and end_disp)
            if mode == 'without_tt':
                return not (start_disp and end_disp)
            if mode == 'high_credit':
                try:
                    return int(hours or 0) >= 4
                except Exception:
                    return False
            if mode == 'low_grace':
                try:
                    return int(grace_val or 0) <= 0
                except Exception:
                    return False
            return True

        def filter_list(*_):
            q = search_var.get().strip().lower()
            tree.delete(*tree.get_children())
            visible = 0
            for code, name, lecturer_name, hours, start_disp, end_disp, grace_val, txt in master_items:
                if _passes_quick_filter(code, name, lecturer_name, hours, start_disp, end_disp, grace_val) and (not q or q in txt.lower()):
                    tree.insert('', 'end', values=(code, name, lecturer_name, hours, start_disp, end_disp, grace_val))
                    visible += 1
            count_var.set(f'{visible} course(s)')

        def _set_filter(mode):
            current_filter.set(mode)
            filter_list()

        chip_specs = [
            ('All', 'all', ui_styles.SECONDARY_BUTTON),
            ('With Timetable', 'with_tt', ui_styles.SUCCESS_BUTTON),
            ('No Timetable', 'without_tt', ui_styles.WARNING_BUTTON),
            ('Credit >= 4', 'high_credit', ui_styles.INFO_BUTTON),
            ('Grace <= 0', 'low_grace', ui_styles.MUTED_BUTTON),
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

        def populate_main():
            sel = tree.selection()
            if not sel:
                messagebox.showerror('Error', 'No course selected')
                return
            vals = tree.item(sel[0])['values']
            code = str(vals[0])
            try:
                row = get_course(code)
                if not row:
                    messagebox.showerror('Error', 'Course not found')
                    return
                # populate fields on main form
                self.course_code.delete(0, 'end')
                self.course_code.insert(0, row[0])
                self.course_name.delete(0, 'end')
                self.course_name.insert(0, row[1])

                # Set lecturer selector to the lecturer NAME instead of ID
                try:
                    lec_name = None
                    try:
                        # ensure lecturer map is up to date
                        self.load_lecturers()
                    except Exception:
                        pass
                    lec_name = self.lecturer_map.get(str(row[3]))
                    if lec_name:
                        self.lecturer_var.set(lec_name)
                except Exception:
                    pass
                # populate credit hours and grace period
                self.credit_hours.delete(0, 'end')
                self.credit_hours.insert(0, str(row[4] if len(row) > 4 else '0'))
                self.grace_minutes.delete(0, 'end')
                self.grace_minutes.insert(0, str(row[5] if len(row) > 5 else '0'))
                # load timetable
                try:
                    from database.timetable_db import get_timetable_for_course
                    trows = get_timetable_for_course(row[0])
                    for d, (var, s_e, e_e) in self.day_vars.items():
                        var.set(False)
                        s_e.delete(0, 'end')
                        e_e.delete(0, 'end')
                    # Populate at most one entry per day to avoid
                    # duplicated times when multiple timetable rows
                    # exist for the same (course, day).
                    seen_days = set()
                    for tro in trows:
                        d = tro[0]
                        if d in seen_days or d not in self.day_vars:
                            continue
                        s, e = str(tro[1]), str(tro[2])
                        # Trim seconds if present (HH:MM:SS -> HH:MM)
                        if s.count(":") == 2:
                            hh, mm, _ = s.split(":", 2)
                            s = f"{hh}:{mm}"
                        if e.count(":") == 2:
                            hh, mm, _ = e.split(":", 2)
                            e = f"{hh}:{mm}"
                        var, s_e, e_e = self.day_vars[d]
                        var.set(True)
                        s_e.insert(0, s)
                        e_e.insert(0, e)
                        seen_days.add(d)
                except Exception:
                    pass
                # Use the same close logic as the window's close
                # button so that the main Course Management window
                # is restored instead of remaining hidden.
                close_view()
            except Exception as e:
                messagebox.showerror('Error', f'Could not populate course:\n{e}')

        tk.Button(btnf, text='Populate', bg='#1e90ff', fg='white', command=populate_main).pack(side='left', padx=6)

        def export_csv():
            sel = tree.selection()
            rows_to_export = []
            if sel:
                for s in sel:
                    vals = tree.item(s)['values']
                    rows_to_export.append(vals)
            else:
                for iid in tree.get_children():
                    rows_to_export.append(tree.item(iid)['values'])

            if not rows_to_export:
                messagebox.showerror('Error', 'No rows to export')
                return

            path = filedialog.asksaveasfilename(title='Save CSV', defaultextension='.csv', filetypes=[('CSV files','*.csv')])
            if not path:
                return
            try:
                with open(path, 'w', newline='', encoding='utf-8') as f:
                    w = csv.writer(f)
                    w.writerow(['course_code','course_name','lecturer','hours','start','end','grace_min'])
                    for vals in rows_to_export:
                        w.writerow(vals[:7])
                messagebox.showinfo('Export', f'Exported {len(rows_to_export)} rows to {path}')
            except Exception as e:
                messagebox.showerror('Error', f'Export failed:\n{e}')

        def edit_selected():
            sel = tree.selection()
            if not sel:
                messagebox.showerror('Error', 'No course selected')
                return
            vals = tree.item(sel[0])['values']
            code = str(vals[0])
            try:
                row = get_course(code)
                if not row:
                    messagebox.showerror('Error', 'Course not found')
                    return
            except Exception as e:
                messagebox.showerror('Error', f'Could not load course:\n{e}')
                return

            # open edit dialog
            ed = tk.Toplevel(win)
            ed.title(f'Edit {code}')
            ed.geometry('420x320')
            try:
                ed.state('zoomed')
            except Exception:
                pass

            tk.Label(ed, text='Course Code (readonly)').pack(anchor='w', padx=8, pady=(8,0))
            code_e = tk.Entry(ed)
            code_e.pack(fill='x', padx=8)
            code_e.insert(0, row[0])
            code_e.config(state='readonly')

            tk.Label(ed, text='Course Name').pack(anchor='w', padx=8, pady=(8,0))
            name_e = tk.Entry(ed)
            name_e.pack(fill='x', padx=8)
            name_e.insert(0, row[1])

            # Lecturer selector: show human-readable names instead of IDs
            tk.Label(ed, text='Lecturer').pack(anchor='w', padx=8, pady=(8,0))
            try:
                lecturers = get_all_lecturers()
            except Exception:
                lecturers = []

            lec_id_to_name = {str(l[0]): l[1] for l in lecturers}
            lec_name_to_id = {v: k for k, v in lec_id_to_name.items()}

            lec_var = tk.StringVar(master=ed)
            current_lec_name = lec_id_to_name.get(str(row[3]), '')
            if current_lec_name:
                lec_var.set(current_lec_name)
            elif lecturers:
                lec_var.set(lecturers[0][1])
            else:
                lec_var.set('')

            lec_menu = tk.OptionMenu(ed, lec_var, *(l[1] for l in lecturers) if lecturers else ())
            lec_menu.pack(fill='x', padx=8)

            tk.Label(ed, text='Credit Hours').pack(anchor='w', padx=8, pady=(8,0))
            hours_e = tk.Entry(ed)
            hours_e.pack(fill='x', padx=8)
            hours_e.insert(0, str(row[4] if len(row) > 4 else '0'))

            tk.Label(ed, text='Grace Period (minutes)').pack(anchor='w', padx=8, pady=(8,0))
            grace_e = tk.Entry(ed)
            grace_e.pack(fill='x', padx=8)
            grace_e.insert(0, str(row[5] if len(row) > 5 else '0'))

            tk.Label(ed, text='Timetable (compact format)').pack(anchor='w', padx=8, pady=(8,0))
            tt_e = tk.Entry(ed)
            tt_e.pack(fill='x', padx=8)
            # preload current timetable
            try:
                from database.timetable_db import get_timetable_for_course
                trows = get_timetable_for_course(code)

                # De-duplicate by day and normalise times to HH:MM so
                # the compact format is clean and matches the main UI.
                seen_days = {}
                for d, s_raw, e_raw in trows:
                    if d in seen_days:
                        continue
                    s = str(s_raw)
                    e = str(e_raw)
                    if s.count(":") == 2:
                        hh, mm, _ = s.split(":", 2)
                        s = f"{hh}:{mm}"
                    if e.count(":") == 2:
                        hh, mm, _ = e.split(":", 2)
                        e = f"{hh}:{mm}"
                    seen_days[d] = (s, e)

                compact = ';'.join(f"{d}|{s}|{e}" for d, (s, e) in seen_days.items())
                tt_e.insert(0, compact)
            except Exception:
                pass

            def save_edit():
                new_name = name_e.get().strip()
                selected_lec_name = lec_var.get().strip()
                new_lid = lec_name_to_id.get(selected_lec_name, '').strip()
                new_hours = hours_e.get().strip()
                new_grace = grace_e.get().strip()
                new_tt = tt_e.get().strip()
                if not all([new_name, new_lid]):
                    messagebox.showerror('Error', 'Name and Lecturer are required')
                    return
                try:
                    if not new_hours.isdigit() or int(new_hours) <= 0:
                        messagebox.showerror('Error', 'Credit hours must be a positive integer')
                        return
                    hours_val = int(new_hours)

                    grace_val = 0
                    if new_grace:
                        if not new_grace.isdigit():
                            messagebox.showerror('Error', 'Grace period must be numeric minutes')
                            return
                        grace_val = int(new_grace)

                    parts = self._parse_timetable_field(new_tt)
                    if not parts:
                        messagebox.showerror('Error', 'Provide at least one timetable entry in Day|HH:MM|HH:MM format')
                        return

                    # One timetable slot per weekday in this editor.
                    unique_by_day = {}
                    for d, s, e in parts:
                        day = d.strip().title()
                        if day not in self.day_vars:
                            continue
                        if s.count(":") == 2:
                            hh, mm, _ = s.split(":", 2)
                            s = f"{hh}:{mm}"
                        if e.count(":") == 2:
                            hh, mm, _ = e.split(":", 2)
                            e = f"{hh}:{mm}"
                        if day not in unique_by_day:
                            unique_by_day[day] = (s.strip(), e.strip())

                    day_entries = [(d, s, e) for d, (s, e) in unique_by_day.items()]
                    if not day_entries:
                        messagebox.showerror('Error', 'Timetable must use weekdays Mon-Fri')
                        return

                    # Service validates and saves both course + timetable atomically.
                    update_course_with_timetable(code, new_name, new_lid, hours_val, grace_val, day_entries)

                    # Update current row and in-memory filter source so search stays accurate.
                    starts = [s for _d, s, _e in day_entries]
                    ends = [e for _d, _s, e in day_entries]
                    start_disp = min(starts) if starts else ''
                    end_disp = max(ends) if ends else ''
                    tree.item(sel[0], values=(code, new_name, selected_lec_name, hours_val, start_disp, end_disp, grace_val))
                    for idx, item in enumerate(master_items):
                        if item[0] == code:
                            txt = f"{code} - {new_name} ({selected_lec_name}, {hours_val}h, {start_disp}-{end_disp}, grace {grace_val}m)"
                            master_items[idx] = (code, new_name, selected_lec_name, hours_val, start_disp, end_disp, grace_val, txt)
                            break
                    messagebox.showinfo('Saved', 'Course updated')
                    ed.destroy()
                    # refresh both views
                    self.load_courses()
                    filter_list()
                except Exception as e:
                    messagebox.showerror('Error', f'Could not save changes:\n{e}')

            tk.Button(ed, text='Save', bg='#1e90ff', fg='white', command=save_edit).pack(pady=12)
            tk.Button(ed, text='Cancel', command=ed.destroy).pack()

        # ---- Actions moved from main form: Update/Delete ----
        def delete_selected():
            sel = tree.selection()
            if not sel:
                messagebox.showerror('Error', 'No course selected')
                return
            vals = tree.item(sel[0])['values']
            code = str(vals[0])
            if not messagebox.askyesno('Confirm', f'Delete course {code}?'):
                return
            try:
                remove_course(code)
                tree.delete(sel[0])
                self.load_courses()
                messagebox.showinfo('Deleted', f'Course {code} removed')
            except Exception as e:
                messagebox.showerror('Error', f'Could not delete course:\n{e}')

        tk.Button(btnf, text='Delete Selected', bg='#e53935', fg='white', command=delete_selected).pack(side='left', padx=6)
        tk.Button(btnf, text='Export CSV', command=export_csv).pack(side='left', padx=6)
        tk.Button(btnf, text='Close', command=close_view).pack(side='right')

        # initial render and focus
        filter_list()
        try:
            search_entry.focus_set()
        except Exception:
            pass

    def on_course_select(self, event):
        sel = event.widget.curselection()
        if not sel:
            return
        idx = sel[0]
        item = event.widget.get(idx)
        course_code = item.split(' - ')[0]
        row = get_course(course_code)
        if not row:
            return

        # populate fields
        self.course_code.delete(0, 'end')
        self.course_code.insert(0, row[0])
        self.course_name.delete(0, 'end')
        self.course_name.insert(0, row[1])
        # set lecturer selector to lecturer NAME
        try:
            lec_name = self.lecturer_map.get(str(row[3]))
            if lec_name:
                self.lecturer_var.set(lec_name)
        except Exception:
            pass

        # load timetable for this course
        try:
            from database.timetable_db import get_timetable_for_course
            trows = get_timetable_for_course(row[0])
            # clear all first
            for d, (var, s_e, e_e) in self.day_vars.items():
                var.set(False)
                s_e.delete(0, tk.END)
                e_e.delete(0, tk.END)

            for tro in trows:
                d, s, e = tro[0], tro[1], tro[2]
                if d in self.day_vars:
                    var, s_e, e_e = self.day_vars[d]
                    var.set(True)
                    s_e.insert(0, s)
                    e_e.insert(0, e)
        except Exception:
            pass
        # populate credit hours and grace period from DB
        self.credit_hours.delete(0, 'end')
        self.credit_hours.insert(0, str(row[4] if len(row) > 4 else '0'))
        self.grace_minutes.delete(0, 'end')
        self.grace_minutes.insert(0, str(row[5] if len(row) > 5 else '0'))

    def update_course(self):
        code = self.course_code.get().strip()
        name = self.course_name.get().strip()
        lecturer_name = self.lecturer_var.get().strip()
        # resolve lecturer_id from name
        lecturer_id = None
        for lid, lname in self.lecturer_map.items():
            if lname == lecturer_name:
                lecturer_id = lid
                break
        hours = self.credit_hours.get().strip()

        grace = self.grace_minutes.get().strip()

        if not all([code, name, lecturer_name]):
            messagebox.showerror("Error", "All fields are required")
            return

        if lecturer_id is None:
            messagebox.showerror("Error", "Invalid lecturer selected")
            return

        try:
            hours_val = int(hours) if hours.isdigit() else 0
            grace_val = None
            if grace:
                if not grace.isdigit():
                    messagebox.showerror("Error", "Grace period must be numeric minutes")
                    return
                grace_val = int(grace)
            # collect raw day entries; validation & replacement handled by service
            day_entries = []
            for day, (var, start_e, end_e) in self.day_vars.items():
                if var.get():
                    s = start_e.get().strip()
                    e = end_e.get().strip()
                    day_entries.append((day, s, e))

            update_course_with_timetable(
                code,
                name,
                lecturer_id,
                hours_val,
                grace_val,
                day_entries,
            )
            messagebox.showinfo("Success", "Course updated")
            self.load_courses()
        except ValueError as e:
            messagebox.showerror("Error", str(e))
        except Exception as e:
            messagebox.showerror("Error", f"Could not update course:\n{e}")

    def delete_course(self):
        code = self.course_code.get().strip()
        if not code:
            messagebox.showerror("Error", "Select a course to delete")
            return
        if not messagebox.askyesno("Confirm", f"Delete course {code}?"):
            return
        try:
            remove_course(code)
            messagebox.showinfo("Deleted", "Course removed")
            self.clear_fields()
            self.load_courses()
        except Exception as e:
            messagebox.showerror("Error", f"Could not delete course:\n{e}")

    def clear_timetable(self):
        code = self.course_code.get().strip()
        if not code:
            messagebox.showerror("Error", "Select a course first")
            return
        if not messagebox.askyesno("Confirm", f"Clear the timetable for {code}?"):
            return
        try:
            # delegate timetable manipulation to the service layer
            self.last_cleared_timetable = clear_timetable_for_course(code)
            messagebox.showinfo("Cleared", "Timetable cleared")

            # clear UI entries
            for d, (var, s_e, e_e) in self.day_vars.items():
                var.set(False)
                s_e.delete(0, tk.END)
                e_e.delete(0, tk.END)

            # show undo button for a short period
            try:
                self.undo_btn.pack(pady=6)
                # cancel existing timer
                if self._undo_after_id:
                    self.root.after_cancel(self._undo_after_id)
                # auto-hide undo after 10 seconds
                self._undo_after_id = self.root.after(10000, self._hide_undo)
            except Exception:
                pass
        except Exception as e:
            messagebox.showerror("Error", f"Could not clear timetable:\n{e}")

    def _hide_undo(self):
        try:
            self.undo_btn.pack_forget()
        except Exception:
            pass
        self.last_cleared_timetable = None
        self._undo_after_id = None

    def _undo_clear(self):
        code = self.course_code.get().strip()
        if not code or not self.last_cleared_timetable:
            messagebox.showerror("Error", "Nothing to undo")
            return
        try:
            # rows already normalised to (day, start, end) by service
            entries = list(self.last_cleared_timetable)
            restore_timetable_for_course(code, entries)

            # refresh UI
            for d, (var, s_e, e_e) in self.day_vars.items():
                var.set(False)
                s_e.delete(0, tk.END)
                e_e.delete(0, tk.END)

            for d, s, e in entries:
                if d in self.day_vars:
                    var, s_e, e_e = self.day_vars[d]
                    var.set(True)
                    s_e.insert(0, s)
                    e_e.insert(0, e)

            messagebox.showinfo("Restored", "Timetable restored")
            self._hide_undo()
        except Exception as e:
            messagebox.showerror("Error", f"Could not restore timetable:\n{e}")

    def open_assign_lecturer(self):
        # small dialog to assign a lecturer to this course (in lecturer_courses)
        code = self.course_code.get().strip()
        if not code:
            messagebox.showerror("Error", "Select a course first")
            return

        win = tk.Toplevel(self.root)
        win.title("Assign Lecturer")
        win.geometry("360x160")
        try:
            win.state('zoomed')
        except Exception:
            pass

        tk.Label(win, text=f"Assign lecturer to {code}", font=("Arial", 12, "bold")).pack(pady=8)

        try:
            lecturers = get_all_lecturers()
        except Exception:
            lecturers = []

        # build name -> id map for this dialog
        name_to_id = {str(name): str(lid) for (lid, name, *_) in lecturers}

        lid_var = tk.StringVar(master=win)
        # populate OptionMenu with NAMES
        menu = tk.OptionMenu(win, lid_var, *(name_to_id.keys() or []))
        menu.pack(pady=6)

        def do_assign():
            lname = lid_var.get().strip()
            if not lname:
                messagebox.showerror("Error", "Select a lecturer")
                return
            lid = name_to_id.get(lname, "")
            try:
                assign_lecturer_to_course(code, lid)
                messagebox.showinfo("Assigned", f"{lname} assigned to {code}")
                win.destroy()
            except Exception as e:
                messagebox.showerror("Error", f"Could not assign lecturer:\n{e}")

        tk.Button(win, text="Assign", command=do_assign, bg="#1e90ff", fg="white").pack(pady=8)

    def load_lecturers(self):
        # populate the lecturer OptionMenu with id - name display, but store id->name map
        try:
            lecturers = get_all_lecturers()
        except Exception:
            lecturers = []

        menu = self.lecturer_menu['menu']
        menu.delete(0, 'end')
        names = []
        self.lecturer_map = {}
        for lid, name, role in lecturers:
            sid = str(lid)
            self.lecturer_map[sid] = name
            names.append(name)
            menu.add_command(label=name, command=lambda v=name: self.lecturer_var.set(v))

        # set placeholder text for display; user must pick a lecturer
        self.lecturer_var.set("Assign a lecturer")

    # ---------------- CSV IMPORT ----------------
    def _parse_timetable_field(self, cell):
        """Parse a compact timetable specification into a list of (day, start, end)."""
        if not cell:
            return []
        parts = []
        for seg in str(cell).split(';'):
            seg = seg.strip()
            if not seg:
                continue
            if '|' in seg:
                try:
                    d, s, e = seg.split('|')
                    parts.append((d.strip(), s.strip(), e.strip()))
                except Exception:
                    continue
            elif ':' in seg and '-' in seg:
                try:
                    d, times = seg.split(':', 1)
                    s, e = times.split('-', 1)
                    parts.append((d.strip(), s.strip(), e.strip()))
                except Exception:
                    continue
            else:
                # unknown format, skip
                continue
        return parts

    def import_from_csv(self, path=None, dry_run=False):
        """Import courses and timetables from CSV."""
        try:
            if not path:
                path = filedialog.askopenfilename(title='Select CSV file', filetypes=[('CSV files', '*.csv'), ('All files', '*.*')])
                if not path:
                    return

            parsed = []
            with open(path, newline='', encoding='utf-8') as f:
                text = f.read()
                # strip leading blank lines that break DictReader
                from io import StringIO
                s = StringIO(text.lstrip('\r\n'))
                reader = csv.DictReader(s)
                # normalize fieldnames to strip possible BOM or invisible chars
                if reader.fieldnames:
                    reader.fieldnames = [fn.lstrip('\ufeff') if fn else fn for fn in reader.fieldnames]
                for i, row in enumerate(reader, start=1):
                    code = (row.get('course_code') or row.get('code') or '').strip()
                    name = (row.get('course_name') or row.get('name') or '').strip()
                    lecturer = (row.get('lecturer_id') or row.get('lecturer') or '').strip()
                    hours = (row.get('credit_hours') or row.get('hours') or '').strip()
                    timetable_cell = row.get('timetable') or row.get('schedule') or ''

                    if not (code and name and lecturer and hours):
                        # skip incomplete rows but collect info for reporting
                        parsed.append((False, i, code, name, 'missing required fields'))
                        continue

                    try:
                        hours_i = int(hours)
                    except Exception:
                        parsed.append((False, i, code, name, 'invalid credit_hours'))
                        continue

                    tt = self._parse_timetable_field(timetable_cell)
                    parsed.append((True, i, code, name, lecturer, hours_i, tt))

            if dry_run:
                return parsed

            # show preview and allow selecting rows to import
            self._show_import_preview(parsed, path)
            return parsed
        except Exception as e:
            messagebox.showerror('Error', f'Could not import CSV:\n{e}')

    def _show_import_preview(self, parsed, path):
        win = tk.Toplevel(self.root)
        win.title('Import Preview - Courses')
        win.geometry('800x420')
        try:
            win.state('zoomed')
        except Exception:
            pass

        lbl = tk.Label(win, text=f'Preview {len(parsed)} rows (select rows to import)', font=('Arial', 12, 'bold'))
        lbl.pack(pady=6)

        frame = tk.Frame(win)
        frame.pack(fill='both', expand=True, padx=8, pady=4)

        cols = ('#','course_code','course_name','lecturer','hours','timetable')
        tree = ttk.Treeview(frame, columns=cols, show='headings', selectmode='extended')
        for c in cols:
            tree.heading(c, text=c)
            tree.column(c, width=140 if c!='#' else 40, anchor='w')
        tree.pack(side='left', fill='both', expand=True)

        vs = ttk.Scrollbar(frame, orient='vertical', command=tree.yview)
        vs.pack(side='left', fill='y')
        tree.configure(yscrollcommand=vs.set)

        # populate tree
        for item in parsed:
            if item[0]:
                _, i, code, name, lecturer, hours_i, tt = item
                tt_str = ';'.join([f"{d}|{s}|{e}" for (d,s,e) in tt]) if tt else ''
                tree.insert('', 'end', values=(i, code, name, lecturer, hours_i, tt_str))
            else:
                _, i, code, name, reason = item
                tree.insert('', 'end', values=(i, code or '<missing>', name or '<missing>', reason, '', ''))

        ctrl_frame = tk.Frame(win)
        ctrl_frame.pack(fill='x', pady=6)

        sel_all = tk.Button(ctrl_frame, text='Select All', command=lambda: tree.selection_set(tree.get_children()))
        sel_all.pack(side='left', padx=6)
        desel_all = tk.Button(ctrl_frame, text='Deselect All', command=lambda: tree.selection_remove(tree.get_children()))
        desel_all.pack(side='left', padx=6)

        progress = ttk.Progressbar(win, orient='horizontal', mode='determinate')
        progress.pack(fill='x', padx=8, pady=(6,2))
        status = tk.Label(win, text='Ready')
        status.pack(fill='x', padx=8)

        # build lecturer id->name map once for imports
        try:
            lec_list = get_all_lecturers()
            lec_map = {str(l[0]): l[1] for l in lec_list}
        except Exception:
            lec_map = {}

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
                try:
                    code = str(vals[1]).strip()
                    name = str(vals[2]).strip()
                    lecturer = str(vals[3]).strip()   # lecturer_id from CSV/preview
                    hours_i = int(vals[4]) if vals[4] else 0
                    tt_str = vals[5]
                    tt = []
                    if tt_str:
                        for seg in str(tt_str).split(';'):
                            if not seg:
                                continue
                            try:
                                d,s,e = seg.split('|')
                                tt.append((d.strip(), s.strip(), e.strip()))
                            except Exception:
                                continue
                except Exception:
                    failures.append((vals, 'malformed row'))
                    progress['value'] = idx
                    status.config(text=f'Processed {idx}/{total}')
                    win.update_idletasks()
                    continue

                try:
                    # resolve lecturer_name
                    lect_id = str(lecturer)
                    lect_name = lec_map.get(lect_id, '')
                    # build summary fields
                    days_summary = ';'.join([f"{d}|{s}|{e}" for (d,s,e) in tt]) if tt else ''
                    first_start = tt[0][1] if tt else ''
                    first_end = tt[0][2] if tt else ''
                    # delegate validation and persistence to the service layer
                    create_course_with_timetable(
                        code,
                        name,
                        lect_id,
                        int(hours_i),
                        0,
                        tt,
                    )
                    success += 1
                except Exception as e:
                    failures.append((code, str(e)))

                progress['value'] = idx
                status.config(text=f'Processed {idx}/{total} — successes: {success} failures: {len(failures)}')
                win.update_idletasks()

            if failures:
                lines = [f'Imported: {success}. Failures: {len(failures)}', 'Top failures:']
                for f in failures[:10]:
                    if isinstance(f, tuple) and len(f) >= 3:
                        # common failure tuple: (False, row_index, code, name, reason)
                        lines.append(f"- row {f[1]} ({f[2]}): {f[-1]}")
                    else:
                        lines.append(f'- {f}')
                summary = '\n'.join(lines)
                messagebox.showinfo('Import Complete', summary)
            else:
                messagebox.showinfo('Import Complete', f'Imported: {success}. Failures: 0')

            win.destroy()

        import_btn = tk.Button(ctrl_frame, text='Import Selected', bg='#1e90ff', fg='white', command=do_import)
        import_btn.pack(side='right', padx=6)

        cancel_btn = tk.Button(ctrl_frame, text='Cancel', command=win.destroy)
        cancel_btn.pack(side='right', padx=6)