from __future__ import annotations

import base64
import hashlib
import hmac
import os
from typing import Final


_HASH_SCHEME: Final[str] = "pbkdf2_sha256"
_ITERATIONS: Final[int] = 260000
_SALT_BYTES: Final[int] = 16


def _b64e(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).decode("ascii").rstrip("=")


def _b64d(text: str) -> bytes:
    padding = "=" * (-len(text) % 4)
    return base64.urlsafe_b64decode((text + padding).encode("ascii"))


def hash_password(password: str) -> str:
    """Return a salted PBKDF2 hash for the provided password."""
    raw = (password or "").encode("utf-8")
    salt = os.urandom(_SALT_BYTES)
    digest = hashlib.pbkdf2_hmac("sha256", raw, salt, _ITERATIONS)
    return f"{_HASH_SCHEME}${_ITERATIONS}${_b64e(salt)}${_b64e(digest)}"


def is_hashed_password(value: str) -> bool:
    if not value or "$" not in value:
        return False
    parts = value.split("$")
    return len(parts) == 4 and parts[0] == _HASH_SCHEME


def verify_password(password: str, stored_value: str) -> bool:
    """Verify plaintext password against stored hash or legacy plaintext.

    Backward compatible: if `stored_value` is not hash-formatted, this falls
    back to constant-time plaintext comparison to support legacy rows.
    """
    candidate = (password or "")
    stored = (stored_value or "")

    if not is_hashed_password(stored):
        return hmac.compare_digest(candidate, stored)

    try:
        scheme, iter_text, salt_text, digest_text = stored.split("$", 3)
        if scheme != _HASH_SCHEME:
            return False
        iterations = int(iter_text)
        salt = _b64d(salt_text)
        expected = _b64d(digest_text)
        actual = hashlib.pbkdf2_hmac(
            "sha256",
            candidate.encode("utf-8"),
            salt,
            iterations,
        )
        return hmac.compare_digest(actual, expected)
    except Exception:
        return False
