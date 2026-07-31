"""Centralised visual styles for the Tkinter UI.

This module plays a similar role to a CSS file in the
web world: colours, fonts and common widget style
presets live here instead of being hard‑coded inline
in each screen.
"""

from __future__ import annotations

from typing import Any, Dict, Tuple

from config import settings as app_settings


_THEME = app_settings.get_theme()
BG_COLOR: str = _THEME["bg_color"]
PRIMARY_COLOR: str = _THEME["primary_color"]
TEXT_COLOR: str = _THEME["text_color"]

# ---- Base colours ----

WINDOW_BG: str = BG_COLOR
WINDOW_TEXT: str = TEXT_COLOR

# Login specific backgrounds (match current design)
DARK_BG: str = "#0b1020"
LIGHT_CARD_BG: str = "#f8fafc"

# ---- Fonts ----

TITLE_FONT: Tuple[str, int, str] = ("Arial", 20, "bold")
SUBTITLE_FONT: Tuple[str, int, str] = ("Arial", 18, "bold")
SECTION_FONT: Tuple[str, int, str] = ("Arial", 12, "bold")
LABEL_FONT: Tuple[str, int] = ("Arial", 11)
BUTTON_FONT: Tuple[str, int, str] = ("Arial", 11, "bold")

# ---- Button style presets ----
# Use Any for values so these presets can be expanded into
# tk.Button keyword arguments without type-checker complaints.

PRIMARY_BUTTON: Dict[str, Any] = {
    "bg": PRIMARY_COLOR,
    "fg": "white",
    "activebackground": PRIMARY_COLOR,
    "activeforeground": "white",
}

SECONDARY_BUTTON: Dict[str, Any] = {
    "bg": "#607d8b",
    "fg": "white",
    "activebackground": "#455a64",
    "activeforeground": "white",
}

SUCCESS_BUTTON: Dict[str, Any] = {
    "bg": "#4caf50",
    "fg": "white",
    "activebackground": "#43a047",
    "activeforeground": "white",
}

INFO_BUTTON: Dict[str, Any] = {
    "bg": "#1e90ff",
    "fg": "white",
    "activebackground": "#1976d2",
    "activeforeground": "white",
}

WARNING_BUTTON: Dict[str, Any] = {
    "bg": "#ffb300",
    "fg": "black",
    "activebackground": "#ffa000",
    "activeforeground": "black",
}

DANGER_BUTTON: Dict[str, Any] = {
    "bg": "#d32f2f",
    "fg": "white",
    "activebackground": "#c62828",
    "activeforeground": "white",
}

MUTED_BUTTON: Dict[str, Any] = {
    "bg": "#9e9e9e",
    "fg": "white",
    "activebackground": "#757575",
    "activeforeground": "white",
}
