import tkinter as tk

from database.db_init import create_tables
from ui.login_ui import LoginUI


def main() -> None:
	create_tables()
	root = tk.Tk()
	LoginUI(root)
	root.mainloop()


if __name__ == "__main__":
	main()
