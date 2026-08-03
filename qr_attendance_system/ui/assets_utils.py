import os
from typing import Optional, Tuple

import tkinter as tk
from PIL import Image, ImageTk 


# Single shared artwork used for both the small logo and
# larger background watermark across the app.
_LOGO_FILENAME = "background.png"


def _get_logo_path() -> str:
    base_dir = os.path.dirname(os.path.dirname(__file__))
    return os.path.join(base_dir, "assets", "images", _LOGO_FILENAME)


def get_logo_image(
    size: Optional[Tuple[int, int]] = None,
    master: Optional[tk.Misc] = None,
) -> Optional[ImageTk.PhotoImage]:
    """Return the project logo as a Tk-compatible image.

    If *size* is provided, the image is resized to (width, height).
    Returns None if the file cannot be loaded.
    """

    path = _get_logo_path()
    try:
        img = Image.open(path)
        if size is not None:
            img = img.resize(size, Image.Resampling.LANCZOS)
        return ImageTk.PhotoImage(img, master=master)
    except Exception:
        return None


def apply_background_image(
    root: tk.Misc,
    size: Tuple[int, int] = (420, 420),
) -> Optional[tk.Label]:
    """Apply the shared artwork as a centred background watermark.

    The same image file (background.png) is used everywhere; callers can
    control its rendered size via *size*. The label is lowered behind
    other widgets so it behaves like a subtle background rather than a
    foreground logo.
    """

    img = get_logo_image(size, master=root)
    if img is None:
        return None

    bg = getattr(root, "cget", lambda _k: "#000000")("bg")
    lbl = tk.Label(root, image=img, bg=bg, borderwidth=0)
    setattr(lbl, "image", img)  # keep reference
    lbl.place(relx=0.5, rely=0.5, anchor="center")
    try:
        lbl.lower()
    except Exception:
        pass
    return lbl
