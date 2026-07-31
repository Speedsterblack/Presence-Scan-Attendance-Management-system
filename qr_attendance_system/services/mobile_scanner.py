"""Mobile phone-based QR scanning service.

Provides a local Flask web server that lecturers can access from their phones
to scan student QR codes. Attendance is recorded directly to the database.
Supports HTTPS with self-signed certificates for browser camera access.
"""

from __future__ import annotations

import threading
import socket
import ssl
from pathlib import Path
from flask import Flask, render_template, request, jsonify
from typing import Optional

from database import attendance_db, course_db
from utils import session


_server_thread: Optional[threading.Thread] = None
_is_running = False

# Get the templates directory (should be in qr_attendance_system/templates)
_TEMPLATES_DIR = str(Path(__file__).resolve().parent.parent / "templates")


def get_local_ip() -> str:
    """Get the local machine's IP address on the network."""
    try:
        # Connect to a public DNS (doesn't send data, just determines route)
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(("8.8.8.8", 80))
        ip = s.getsockname()[0]
        s.close()
        return ip
    except Exception:
        return "127.0.0.1"


def start_mobile_scanner_server(port: int = 5000, course_code: str = "") -> str:
    """Start the mobile scanner Flask server in a background thread.
    
    Args:
        port: Port to run the server on
        course_code: Optional course code to pass to the mobile interface
    
    Returns the URL (IP:PORT/?course=CODE) that lecturers should access from their phones.
    """
    global _server_thread, _is_running

    if _is_running:
        local_ip = get_local_ip()
        url = f"https://{local_ip}:{port}"
        if course_code:
            url += f"?course={course_code}"
        return url

    app = Flask(__name__, template_folder=_TEMPLATES_DIR)

    @app.route("/")
    def index() -> str:
        """Serve the mobile scanning page."""
        return render_template("mobile_scanner.html")

    @app.route("/api/scan", methods=["POST"])
    def api_scan() -> dict:
        """Handle a QR scan from the phone."""
        data = request.get_json() or {}
        qr_value = (data.get("qr_value") or "").strip()
        course_code = (data.get("course_code") or "").strip()

        if not qr_value or not course_code:
            return {"success": False, "message": "Missing QR value or course code."}

        try:
            # Verify that current user (lecturer) teaches this course
            user = getattr(session, "current_user", None)
            if not isinstance(user, dict):
                return {"success": False, "message": "No active session."}

            user_id = user.get("id")
            role = user.get("role")
            if not user_id or str(role).lower() != "lecturer":
                return {"success": False, "message": "Only lecturers can scan."}

            # Mark attendance (will handle grace period, status inference, etc.)
            result = attendance_db.mark_attendance(qr_value, course_code)
            
            # Handle both bool and tuple return types
            if isinstance(result, tuple):
                success, extra = result
                extra_msg = f"{extra}" if extra else ""
            else:
                success = result
                extra_msg = ""
            
            if success:
                return {"success": True, "message": f"Attendance recorded{extra_msg}"}
            else:
                return {"success": False, "message": extra_msg or "Attendance not recorded"}

        except Exception as exc:
            return {"success": False, "message": f"Error: {exc}"}

    def run_server() -> None:
        """Run Flask server in background with HTTPS."""
        try:
            # Load SSL certificates
            cert_file = Path(__file__).resolve().parent.parent / "cert.pem"
            key_file = Path(__file__).resolve().parent.parent / "key.pem"
            
            if cert_file.exists() and key_file.exists():
                # Use HTTPS with self-signed certificates
                ssl_context = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
                ssl_context.load_cert_chain(str(cert_file), str(key_file))
                app.run(
                    host="0.0.0.0", 
                    port=port, 
                    debug=False, 
                    use_reloader=False,
                    ssl_context=ssl_context
                )
            else:
                # Fallback to HTTP if certificates not found
                print(f"Warning: SSL certificates not found at {cert_file} or {key_file}")
                print("Falling back to HTTP (camera may not work on phone)")
                app.run(host="0.0.0.0", port=port, debug=False, use_reloader=False)
        except Exception as exc:
            print(f"Mobile scanner server error: {exc}")

    _server_thread = threading.Thread(target=run_server, daemon=True)
    _server_thread.start()
    _is_running = True

    local_ip = get_local_ip()
    url = f"https://{local_ip}:{port}"
    if course_code:
        url += f"?course={course_code}"
    return url


def stop_mobile_scanner_server() -> None:
    """Stop the mobile scanner server."""
    global _is_running
    _is_running = False
    # Flask will shut down when the app context ends


def get_mobile_scanner_url() -> Optional[str]:
    """Get the current mobile scanner URL if running, or None."""
    if _is_running:
        return f"https://{get_local_ip()}:5000"
    return None
