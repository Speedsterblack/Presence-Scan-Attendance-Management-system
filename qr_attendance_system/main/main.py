import tkinter as tk

from database.db_init import create_tables
from database import attendance_cache
from database import passive_sync
from ui.login_ui import LoginUI


def main() -> None:
	create_tables()
	try:
		passive_sync.sync_credentials_once()
	except Exception:
		# Login remains available when Supabase is temporarily unreachable.
		pass
	attendance_cache.maintain()
	passive_sync.start()
	root = tk.Tk()
	LoginUI(root)
	root.mainloop()


if __name__ == "__main__":
	main()
