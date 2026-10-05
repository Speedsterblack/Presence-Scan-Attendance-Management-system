# Presence Scan User Manual

## 1. System Overview

Presence Scan is an attendance management system that works without internet access.
It uses local SQLite databases and communicates between the Head of University and
lecturer computers over the university Wi-Fi or LAN.

The system has three parts:

- **Head of University app:** central LAN hub for university, department, HOD,
  and master-data management.
- **Lecturer app:** manages courses, students, timetables, attendance, reports,
  and lecturer access.
- **Mobile scanner:** optional phone browser interface connected to a lecturer
  computer on the same local network.

Internet access and Supabase are not required.

## 2. First-Time Head Setup

1. Start `HeadOfUniversity.exe` on the Head of University computer.
2. On the first launch, enter the university code.
3. Enter the full university name.
4. Select **Save and continue**.
5. The application opens the Departments workspace.

The Head application displays a secure LAN hub address similar to:

```text
https://192.168.1.20:8765
```

The Head application also displays a pairing token. Give the address and token
only to authorized lecturer computers. Lecturer computers use both values to
connect to the Head hub.

The Head computer must remain powered on and connected to the university LAN
when lecturer computers need to download central data or upload attendance.

## 3. Manage Departments and HOD Accounts

From the Head application:

1. Select **Add Department**.
2. Enter the department ID and department name.
3. Enter an HOD/admin ID and password if the department needs an HOD account.
4. Select **Add Department**.

To change a department:

1. Select the department in the list.
2. Edit its details.
3. Select **Update Selected**.

To remove a department, select it and choose **Delete**. Deleting a department
also affects records that belong to that department, so confirm the action
carefully.

The university filter is not required because the Head installation manages one
university.

## 4. Connect a Lecturer Computer

When using the GUI installer, enter the Head hub URL during installation. The
installer stores this address for the lecturer application automatically. Enter
the pairing token later in Settings.

When running from source or changing the connection later:

1. Start the lecturer application, `PresenceScan.exe`.
2. Open **Settings**.
3. Find the **University LAN** section.
4. Enter the Head hub address, for example:

```text
https://192.168.1.20:8765
```

5. Enter the Head pairing token.
6. Select **Save**.
7. Restart the lecturer application.

At startup, the lecturer app attempts to pull master data from the Head hub.
If the Head computer is unavailable, the lecturer app continues using its last
local data.

Both computers must be connected to the same Wi-Fi or wired LAN. Windows
Firewall must allow TCP port `8765` on the Head computer. Requests without the
pairing token are rejected.

## 5. Lecturer and HOD Workflows

After signing in, lecturers and HODs can use the functions allowed for their
account, including:

- Student registration and student browsing
- Course creation and course registration
- Lecturer management
- Timetable management
- Semester management
- QR attendance scanning
- Attendance reports and exports
- Transcript and student attendance views

Changes are stored locally first. Successful attendance records are also sent
to the Head hub over the LAN when a Head URL is configured.

## 6. Use the Phone QR Scanner

The phone scanner is optional. It does not use the internet.

1. Connect the phone and lecturer computer to the same Wi-Fi or LAN.
2. Sign in to the lecturer application.
3. Open the QR scanning screen.
4. Choose the course and select **Open Mobile Scanner**.
5. Open the displayed address on the phone browser.
6. Allow camera access if requested.
7. Scan student QR codes.

Attendance is processed by the lecturer computer and saved to its database.
Keep the lecturer application running while using the phone scanner.

If the phone cannot connect:

- Confirm both devices use the same network.
- Confirm the displayed IP address is the lecturer computer's LAN address.
- Allow the scanner port through Windows Firewall.
- Try the address again without switching to mobile data.

## 7. Attendance Rules

Attendance can be recorded only when:

- The student QR code is valid.
- The course exists locally.
- The lecturer is permitted to teach the course.
- A timetable session is active.
- The day is not configured as a no-school day.
- Attendance has not already been recorded for that student and session.

Scans outside the configured grace period may be recorded as **Late**. A
student cannot be recorded twice for the same timetable session and date.

## 8. Reports and Exports

Use the report and attendance screens to filter records by the available course,
department, semester, student, and date options. Exported CSV files are saved
to the configured export folder.

The default report location is the project's `reports` directory when running
from source. Packaged installations store data under the user's local
application data directory.

## 9. Semester Management

An admin can close the active semester from Settings after confirming the admin
PIN. Closing a semester:

- Marks it as closed.
- Preserves its historical registrations and attendance.
- Creates the next active semester according to the entered semester name.

Course registrations are semester-specific. Students may need to be registered
again for courses in the new semester.

## 10. Offline and LAN Behavior

The application does not require internet access. The following behavior is
available without internet:

- Local login and database operations
- Student, course, timetable, and attendance management
- Reports and CSV exports
- Phone-to-lecturer QR scanning over LAN
- Lecturer-to-Head master-data and attendance communication over LAN

If the Head hub is offline, local lecturer work continues. Data pulled from the
Head is not automatically available until the lecturer application reconnects.

## 11. Database Locations

Packaged applications use separate local databases:

- Lecturer app: `%LOCALAPPDATA%\Presence Scan\data\presence_scan.db`
- Head app: `%LOCALAPPDATA%\Presence Scan Head\data\presence_scan.db`

Do not delete these files unless you intend to remove the corresponding local
data. Close the application before copying or backing up a database.

## 12. Common Problems

### The Head app does not open

Start `HeadOfUniversity.exe`. If the application was built from source, run
`python -m main.head_main` from the
`qr_attendance_system` directory.

### The university setup form does not appear

The Head database already contains a university record. To configure a fresh
installation, use a new Head database or back up and replace the existing one
while the app is closed.

### Lecturer data is not updated

Check that:

- The Head app is running.
- The Head URL is correct.
- Both computers are on the same LAN.
- TCP port `8765` is allowed through Windows Firewall.
- The lecturer app was restarted after saving the URL.

### The phone scanner cannot connect

Check the LAN connection, the displayed IP address, the scanner port shown by
the application, and Windows Firewall. The phone must be connected to Wi-Fi,
not only mobile data.

### Attendance is missing from the Head app

The lecturer computer keeps its local attendance record even when the Head hub
is unavailable. Reconnect both computers to the same LAN and run the lecturer
application again so the LAN upload can be attempted.

## 13. Backups

Back up both local database files regularly. Recommended backup steps:

1. Close the relevant application.
2. Copy the database file to a secure backup folder.
3. Record the backup date and the computer it came from.
4. Restore only while the application is closed.
