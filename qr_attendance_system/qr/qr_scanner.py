"""Helpers for live QR scanning.

This module prefers ``pyzbar`` when its native ZBar dependency is
available, but falls back to OpenCV's built-in ``QRCodeDetector`` on
Windows systems where ``libzbar`` is missing.
"""

from __future__ import annotations

from typing import Optional

import cv2

try:
    from pyzbar import pyzbar
    from pyzbar.pyzbar import ZBarSymbol
except Exception:
    pyzbar = None
    ZBarSymbol = None


_QR_DETECTOR = cv2.QRCodeDetector()


def _decode_with_pyzbar(frame) -> Optional[str]:
    if pyzbar is None or ZBarSymbol is None:
        return None

    try:
        qr_codes = pyzbar.decode(frame, symbols=[ZBarSymbol.QRCODE])
    except Exception as e:
        try:
            print(f"pyzbar.decode error: {e}")
        except Exception:
            pass
        return None

    if not qr_codes:
        return None

    try:
        data = qr_codes[0].data
        if isinstance(data, bytes):
            return data.decode("utf-8", errors="ignore")
        return str(data)
    except Exception:
        return None


def _decode_with_opencv(frame) -> Optional[str]:
    try:
        data, _points, _straight = _QR_DETECTOR.detectAndDecode(frame)
        if data:
            return str(data)
    except Exception as e:
        try:
            print(f"cv2.QRCodeDetector error: {e}")
        except Exception:
            pass
    return None


def scan_qr_live(frame):
    """Detect a QR code from a camera frame and return its text.

    Returns ``None`` when nothing is detected or decoding fails.
    """

    result = _decode_with_pyzbar(frame)
    if result:
        return result

    return _decode_with_opencv(frame)
