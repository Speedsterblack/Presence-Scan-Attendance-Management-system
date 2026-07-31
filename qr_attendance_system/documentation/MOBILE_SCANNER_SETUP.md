Mobile Scanner (Phone) — HTTPS, Auto-course & Usage

Overview
- The desktop application can serve a small mobile web page that uses the phone camera to scan student QR codes and post them back to the desktop app (local network).
- Modern mobile browsers require HTTPS for camera access. The desktop server will use self-signed certificates if `cert.pem` and `key.pem` are present in the project root (qr_attendance_system/). The dashboard generates a QR with an `https://<LOCAL_IP>:<PORT>/?course=CODE` URL.

How to start and use
- Ensure the desktop and phone are on the same Wi‑Fi / local network.
- Start the application (use `launch_university_app.bat` or run the main application). Log in as a lecturer.
- On the lecturer Dashboard click the "Open Mobile Scanner" (or similar) button. The app will start a small Flask server and display a QR dialog containing the https URL.
- Scan the displayed QR from your phone or open the URL in the phone browser.
- If the dashboard detected your course automatically, the URL will include `?course=COURSE_CODE` and the course input will be hidden on the phone page.
- On the phone, grant camera permission when prompted and present student QR codes to the phone camera.
- Successful scan behaviour: green confirmation text, an audible beep, and vibration feedback. Failures show a clear message from the server (e.g. "No class is active", "Duplicate attendance", "Class already ended").

Certificates (self-signed)
- To enable camera access you must use HTTPS. The project looks for `cert.pem` and `key.pem` in the project root. If they exist the Flask server runs with SSL.
- Quick OpenSSL command to generate a 1-year self-signed cert:
  - `openssl req -x509 -newkey rsa:4096 -nodes -keyout key.pem -out cert.pem -days 365 -subj "/CN=localhost"`
- Place `cert.pem` and `key.pem` into the `qr_attendance_system/` directory (same folder as the application). Restart the app after adding or regenerating certs.
- Alternately, a small Python script using the `cryptography` package can generate similar certs if OpenSSL is not available.

Accepting the certificate on a phone
- Self-signed certs will trigger a browser warning. You can usually proceed by choosing the advanced/continue option in Chrome/Firefox for Android.
- iOS Safari often blocks self-signed certificates more strictly; consider using Firefox on iOS/Android or temporarily trusting the certificate on the device (installing the cert into device trust stores). For long-term use, obtain a CA-signed cert.
- If the browser refuses to load the page, try using a different mobile browser or install the certificate on the device.

Auto-course behaviour
- The desktop Dashboard attempts to auto-detect the lecturer's active course and includes `?course=COURSE_CODE` in the mobile URL. When present, the mobile page hides the course input and submits attendance directly for that course.
- If multiple courses are assigned to the lecturer, the Dashboard prompts the lecturer to choose which course to serve to the phone.

Server response messages and what they mean
- Success: attendance recorded (may include "Late" if outside grace period).
- "No class is active": the scanned student does not match any currently active timetable slot for the selected course or department. Check the timetable and course selection.
- "Class already ended": the scanning window has closed; attendance will not be recorded.
- "Duplicate attendance": the student has already been recorded for the current timetable slot.
- Other messages from the desktop will be shown verbatim on the phone so the lecturer can see why a submission failed.

Troubleshooting
- Camera blocked / permission denied: ensure the page is loaded over HTTPS and that the browser has camera permission.
- Phone cannot access URL: confirm desktop IP and port are reachable from the phone (same network, firewall rules allow inbound connections to the host/port).
- Browser refuses to proceed on self-signed cert: try a different browser (Firefox often allows proceeding), or install the certificate onto the device.
- If QR dialog shows `http://` instead of `https://`, check that `cert.pem` and `key.pem` exist in the project root and restart the desktop app.

Regenerating certificates
- Regenerate with the OpenSSL command above and restart the desktop app. Certificates are short-lived in this setup; consider renewing annually or using a CA-signed certificate for production.

Security note
- Self-signed certificates are appropriate for local testing but produce browser warnings. For production or wider deployment use a certificate issued by a trusted CA to avoid warnings and to improve security.

Notes for deployment and testing
- This mobile scanner is intended for local, same-network usage (no internet dependency required).
- Always test end-to-end with a real phone: accept the cert or trust it, grant camera permission, and verify the success feedback and server messages.
