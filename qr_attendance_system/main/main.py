import tkinter as tk

from database.db_init import create_tables
from database import attendance_cache
from services import lan_sync
from ui.login_ui import LoginUI
import logging, os, sys
if getattr(sys, "frozen", False):
       log_dir = os.path.join(os.environ.get("LOCALAPPDATA", "."), "Presence Scan")
       os.makedirs(log_dir, exist_ok=True)
       logging.basicConfig(filename=os.path.join(log_dir, "app.log"), level=logging.ERROR)


def main() -> None:
	create_tables()
	try:
		lan_sync.pull_from_head()
	except Exception:
		# The lecturer app remains usable with its last local data if the hub is offline.
		pass
	attendance_cache.maintain()
	root = tk.Tk()
	LoginUI(root)
	root.mainloop()


if __name__ == "__main__":
	main()
