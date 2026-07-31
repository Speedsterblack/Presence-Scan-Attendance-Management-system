import tkinter as tk

from ui.login_ui import LoginUI


def main() -> None:
	root = tk.Tk()
	LoginUI(root)
	root.mainloop()


if __name__ == "__main__":
	main()
