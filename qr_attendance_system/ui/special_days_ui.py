import tkinter as tk
from tkinter import ttk, messagebox
from datetime import datetime, date

from database import special_days_db
from ui import styles as ui_styles


class SpecialDaysUI:
    def __init__(self, root: tk.Toplevel, parent: tk.Tk) -> None:
        self.root = root
        self.parent = parent
        self.department_id = special_days_db.get_current_department_id()
        if self.department_id is None:
            raise RuntimeError("Could not determine the current department")
        self.root.title("Special Days")

        self.root.configure(bg="#ecf0f1")

        tk.Label(
            root,
            text="Special Days (No-School Days)",
            font=("Arial", 16, "bold"),
            bg="#ecf0f1",
        ).pack(pady=(10, 6))

        container = tk.Frame(root, bg="#ecf0f1")
        container.pack(fill="both", expand=True, padx=12, pady=8)

        # Top form to add/update a special day
        form = tk.Frame(container, bg="#ecf0f1")
        form.pack(fill="x", pady=(0, 10))

        tk.Label(form, text="Date (YYYY-MM-DD):", bg="#ecf0f1").grid(row=0, column=0, sticky="w", padx=(0, 4))
        self._date_var = tk.StringVar(master=self.root, value=date.today().strftime("%Y-%m-%d"))
        tk.Entry(form, textvariable=self._date_var, width=12).grid(row=0, column=1, sticky="w")

        tk.Label(form, text="Label:", bg="#ecf0f1").grid(row=0, column=2, sticky="w", padx=(10, 4))
        self._label_var = tk.StringVar(master=self.root)
        tk.Entry(form, textvariable=self._label_var, width=24).grid(row=0, column=3, sticky="w")

        self._no_school_var = tk.BooleanVar(master=self.root, value=True)
        ttk.Checkbutton(form, text="No-school day", variable=self._no_school_var).grid(row=0, column=4, sticky="w", padx=(10, 0))

        tk.Button(
            form,
            text="Save",
            width=10,
            command=self._on_save,
            font=ui_styles.BUTTON_FONT,
            **ui_styles.PRIMARY_BUTTON,
        ).grid(row=0, column=5, padx=(10, 0))

        # List of existing special days
        list_frame = tk.Frame(container, bg="#ecf0f1")
        list_frame.pack(fill="both", expand=True)

        columns = ("day", "label", "no_school")
        self._tree = ttk.Treeview(list_frame, columns=columns, show="headings", height=10)
        self._tree.heading("day", text="Date")
        self._tree.heading("label", text="Label")
        self._tree.heading("no_school", text="No school?")
        self._tree.column("day", width=110, anchor="center")
        self._tree.column("label", width=260, anchor="w")
        self._tree.column("no_school", width=90, anchor="center")
        self._tree.pack(side="left", fill="both", expand=True)

        scrollbar = ttk.Scrollbar(list_frame, orient="vertical", command=self._tree.yview)
        scrollbar.pack(side="right", fill="y")
        self._tree.configure(yscrollcommand=scrollbar.set)

        btn_frame = tk.Frame(container, bg="#ecf0f1")
        btn_frame.pack(fill="x", pady=(8, 0))

        tk.Button(
            btn_frame,
            text="Delete selected",
            width=14,
            command=self._on_delete,
            font=ui_styles.BUTTON_FONT,
            **ui_styles.DANGER_BUTTON,
        ).pack(side="left")

        tk.Button(
            btn_frame,
            text="Close",
            width=10,
            command=self._on_close,
            font=ui_styles.BUTTON_FONT,
            **ui_styles.MUTED_BUTTON,
        ).pack(side="right")

        try:
            self.root.protocol("WM_DELETE_WINDOW", self._on_close)
        except Exception:
            pass

        self._reload()

        self.root.update_idletasks()
        # Keep special days window at reasonable size (not full screen)
        self.root.minsize(600, 400)

    def _parse_date(self, text: str) -> date | None:
        text = (text or "").strip()
        try:
            return datetime.strptime(text, "%Y-%m-%d").date()
        except Exception:
            return None

    def _reload(self) -> None:
        for iid in self._tree.get_children():
            self._tree.delete(iid)

        try:
            rows = special_days_db.list_special_days(self.department_id)
        except Exception as exc:
            messagebox.showerror("Error", f"Could not load special days:\n{exc}")
            return

        for day, label, is_no_school in rows:
            self._tree.insert("", "end", values=(day.strftime("%Y-%m-%d"), label, "Yes" if is_no_school else "No"))

    def _on_save(self) -> None:
        d = self._parse_date(self._date_var.get())
        if d is None:
            messagebox.showerror("Invalid date", "Please enter a valid date in YYYY-MM-DD format.")
            return

        label = (self._label_var.get() or "").strip()
        is_no_school = bool(self._no_school_var.get())

        try:
            special_days_db.add_special_day(d, label, is_no_school, self.department_id)
        except Exception as exc:
            messagebox.showerror("Error", f"Could not save special day:\n{exc}")
            return

        self._reload()

    def _on_delete(self) -> None:
        selection = self._tree.selection()
        if not selection:
            messagebox.showinfo("Delete", "Please select a row to delete.")
            return

        item_id = selection[0]
        values = self._tree.item(item_id, "values")
        if not values:
            return

        try:
            d = datetime.strptime(values[0], "%Y-%m-%d").date()
        except Exception:
            return

        if not messagebox.askokcancel("Confirm", f"Delete special day {values[0]}?"):
            return

        try:
            special_days_db.delete_special_day(d, self.department_id)
        except Exception as exc:
            messagebox.showerror("Error", f"Could not delete special day:\n{exc}")
            return

        self._reload()

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
