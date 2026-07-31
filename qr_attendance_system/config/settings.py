from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any, Dict

from utils import session as _session
from utils.security import hash_password, is_hashed_password


_BASE_DIR = Path(__file__).resolve().parent
_SETTINGS_FILE = _BASE_DIR / "settings.json"


_DEFAULT_SETTINGS: Dict[str, Any] = {
	"theme": {
		# logical theme name; "light", "dark" or "system"
		"name": "light",
	},
	"scanner": {
		# cooldown between scans for the same student (seconds)
		"cooldown_seconds": 3,
	},
	"attendance": {
		# global default grace period (minutes) used when creating courses
		"default_grace_minutes": 0,
	},
	"export": {
		# default directory for exported CSVs/reports
		"default_directory": str((_BASE_DIR.parent / "reports").resolve()),
	},
	"admin": {
		# auto-refresh for the admin analytics dashboard
		"auto_refresh_enabled": True,
		"auto_refresh_interval_seconds": 10,
		# hashed PIN used for semester rollover and sensitive admin actions
		"pin_hash": "",
	},
	"developer": {
		# Hashed password used for hidden developer tools entrypoints
		# (institution setup). Existing plaintext settings are migrated.
		"password_hash": "pbkdf2_sha256$260000$QHEUHT5o44pUi3XNk43srQ$9MLOLupYh9synv76iLVfce5i0IXxMuCD771JmCrHJP8",
	},
}


_THEMES: Dict[str, Dict[str, str]] = {
	"light": {
		"bg_color": "#ecf0f1",
		"primary_color": "#1e90ff",
		"text_color": "#2c3e50",
	},
	"dark": {
		"bg_color": "#2c3e50",
		"primary_color": "#1e88e5",
		"text_color": "#ecf0f1",
	},
}


def _get_current_role() -> str | None:

	try:
		user = _session.current_user
	except Exception:
		return None

	role: Any
	if isinstance(user, dict):
		role = user.get("role")
	elif isinstance(user, (list, tuple)) and len(user) >= 3:
		role = user[2]
	else:
		role = None

	if not role:
		return None

	return str(role).lower()


def _deep_update(base: Dict[str, Any], updates: Dict[str, Any]) -> Dict[str, Any]:
	"""Recursively merge *updates* into *base* and return base.

	This keeps nested dicts while allowing partial updates from the settings
	file or from the Settings UI.
	"""

	for key, value in updates.items():
		if (
			isinstance(value, dict)
			and isinstance(base.get(key), dict)
		):
			_deep_update(base[key], value)  # type: ignore[arg-type]
		else:
			base[key] = value
	return base


def load_settings() -> Dict[str, Any]:
	"""Load settings from JSON, falling back to defaults.

	The returned dict is always complete (defaults merged in).
	"""

	data: Dict[str, Any] = {}
	if _SETTINGS_FILE.exists():
		try:
			raw = _SETTINGS_FILE.read_text(encoding="utf-8")
			data = json.loads(raw) if raw.strip() else {}
		except Exception:
			data = {}

	merged: Dict[str, Any] = {}
	_deep_update(merged, _DEFAULT_SETTINGS)
	if data:
		_deep_update(merged, data)
	return merged


def save_settings(settings: Dict[str, Any]) -> None:
	"""Persist the provided settings dict to disk.

	Callers should typically obtain the current dict with load_settings(),
	modify it, then pass it back here.
	"""

	try:
		_SETTINGS_FILE.parent.mkdir(parents=True, exist_ok=True)
		_SETTINGS_FILE.write_text(json.dumps(settings, indent=2), encoding="utf-8")
	except Exception:
		# Avoid raising from settings persistence in the UI layer; failures
		# here should not crash the application.
		pass


def update_settings(partial: Dict[str, Any]) -> Dict[str, Any]:
	"""Merge *partial* into existing settings and persist.

	Returns the merged settings dict.
	"""

	current = load_settings()
	_deep_update(current, partial)
	save_settings(current)
	return current


def _get_system_theme_name() -> str:
	"""Best-effort detection of the OS theme.

	On Windows, this reads the AppsUseLightTheme registry value.
	On other platforms or on failure, it falls back to the
	default theme name.
	"""
	try:
		if sys.platform != "win32":
			return str(_DEFAULT_SETTINGS["theme"]["name"]).lower()

		try:
			import winreg  # type: ignore[import-not-found]
		except Exception:
			return str(_DEFAULT_SETTINGS["theme"]["name"]).lower()

		key_path = r"Software\\Microsoft\\Windows\\CurrentVersion\\Themes\\Personalize"
		key = winreg.OpenKey(winreg.HKEY_CURRENT_USER, key_path)
		value, _ = winreg.QueryValueEx(key, "AppsUseLightTheme")
		winreg.CloseKey(key)
		try:
			use_light = int(value) != 0
		except Exception:
			use_light = True
		return "light" if use_light else "dark"
	except Exception:
		return str(_DEFAULT_SETTINGS["theme"]["name"]).lower()


def get_theme() -> Dict[str, str]:
	settings = load_settings()
	role = _get_current_role()
	name: Any | None = None
	if role:
		name = (
			settings.get("roles", {})
			.get(role, {})
			.get("theme", {})
			.get("name")
		)
	if not name:
		name = (
			settings.get("theme", {}).get("name")
			or _DEFAULT_SETTINGS["theme"]["name"]
		)
	name_str = str(name).lower()
	if name_str == "system":
		name_str = _get_system_theme_name()
	return _THEMES.get(name_str, _THEMES["light"])


def get_scanner_cooldown() -> int:
	"""Return a fixed scanner cooldown in seconds.

	This value is intentionally not configurable from the Settings
	UI any more so that all environments behave consistently.
	"""
	return int(_DEFAULT_SETTINGS["scanner"]["cooldown_seconds"])


def get_default_grace_minutes() -> int:
	settings = load_settings()
	role = _get_current_role()
	value: Any | None = None
	if role:
		value = (
			settings.get("roles", {})
			.get(role, {})
			.get("attendance", {})
			.get("default_grace_minutes")
		)
	if value is None:
		value = (
			settings.get("attendance", {}).get("default_grace_minutes")
			or _DEFAULT_SETTINGS["attendance"]["default_grace_minutes"]
		)
	assert value is not None
	try:
		return int(value)
	except Exception:
		return int(_DEFAULT_SETTINGS["attendance"]["default_grace_minutes"])


def get_export_directory() -> str:
	settings = load_settings()
	role = _get_current_role()
	value: Any | None = None
	if role:
		value = (
			settings.get("roles", {})
			.get(role, {})
			.get("export", {})
			.get("default_directory")
		)
	if not value:
		value = (
			settings.get("export", {}).get("default_directory")
			or _DEFAULT_SETTINGS["export"]["default_directory"]
		)
	return str(value)


def get_admin_auto_refresh_enabled() -> bool:
	settings = load_settings()
	role = _get_current_role()
	value: Any | None = None
	if role:
		value = (
			settings.get("roles", {})
			.get(role, {})
			.get("admin", {})
			.get("auto_refresh_enabled")
		)
	if value is None:
		value = settings.get("admin", {}).get("auto_refresh_enabled")
	if isinstance(value, bool):
		return value
	return bool(_DEFAULT_SETTINGS["admin"]["auto_refresh_enabled"])


def get_admin_auto_refresh_interval() -> int:
	settings = load_settings()
	role = _get_current_role()
	value: Any | None = None
	if role:
		value = (
			settings.get("roles", {})
			.get(role, {})
			.get("admin", {})
			.get("auto_refresh_interval_seconds")
		)
	if value is None:
		value = (
			settings.get("admin", {}).get("auto_refresh_interval_seconds")
			or _DEFAULT_SETTINGS["admin"]["auto_refresh_interval_seconds"]
		)
	assert value is not None
	try:
		return int(value)
	except Exception:
		return int(_DEFAULT_SETTINGS["admin"]["auto_refresh_interval_seconds"])


def get_admin_pin_hash() -> str:
	"""Return the configured admin PIN hash, migrating legacy plaintext if present."""

	settings = load_settings()
	admin = settings.setdefault("admin", {})
	hashed_value: Any | None = admin.get("pin_hash")
	if hashed_value and is_hashed_password(str(hashed_value)):
		return str(hashed_value)

	legacy_plain: Any | None = admin.get("pin")
	if legacy_plain:
		migrated = hash_password(str(legacy_plain))
		admin["pin_hash"] = migrated
		admin.pop("pin", None)
		save_settings(settings)
		return migrated

	return ""


def set_admin_pin(pin: str) -> str:
	"""Store a new admin PIN hash and return it."""

	settings = load_settings()
	admin = settings.setdefault("admin", {})
	hashed = hash_password(pin)
	admin["pin_hash"] = hashed
	admin.pop("pin", None)
	save_settings(settings)
	return hashed


def get_developer_password_hash() -> str:
	"""Return developer password hash, migrating legacy plaintext value if needed."""
	settings = load_settings()
	developer = settings.setdefault("developer", {})

	hashed_value: Any | None = developer.get("password_hash")
	if hashed_value and is_hashed_password(str(hashed_value)):
		return str(hashed_value)

	legacy_plain: Any | None = developer.get("password")
	if legacy_plain:
		migrated = hash_password(str(legacy_plain))
		developer["password_hash"] = migrated
		developer.pop("password", None)
		save_settings(settings)
		return migrated

	default_hash = str(_DEFAULT_SETTINGS["developer"]["password_hash"])
	developer["password_hash"] = default_hash
	save_settings(settings)
	return default_hash


def get_developer_password() -> str:
	"""Backward-compatible alias returning developer password hash."""
	return get_developer_password_hash()


def update_settings_for_current_role(partial: Dict[str, Any]) -> Dict[str, Any]:
	"""Merge *partial* into settings for the current role and persist.

	If there is no current user/role, falls back to global update_settings.
	"""

	role = _get_current_role()
	if not role:
		return update_settings(partial)

	settings = load_settings()
	roles_section = settings.setdefault("roles", {})
	role_settings = roles_section.setdefault(role, {})
	_deep_update(role_settings, partial)
	save_settings(settings)
	return settings


def get_semester_weeks() -> int:
	"""Return the configured number of weeks in a semester (role-aware).

	Falls back to 15 when unset or invalid.
	"""
	settings = load_settings()
	role = _get_current_role()
	value: Any | None = None
	if role:
		value = (
			settings.get("roles", {})
			.get(role, {})
			.get("attendance", {})
			.get("semester_weeks")
		)
	if value is None:
		value = settings.get("attendance", {}).get("semester_weeks")
	try:
		return int(value or 15)
	except Exception:
		return 15

