import csv
from pathlib import Path

from database.attendance_db import get_attendance_by_course


def export_attendance_csv(course_code, filename):
    records = get_attendance_by_course(course_code)
    # records comes back as (student_id, student_name, course_code, status)
    total_present = sum(1 for r in records if r[3] == "Present")
    # Current schema has only Present/Absent, so late count is 0
    total_late = 0

    with open(filename, "w", newline="") as f:
        writer = csv.writer(f)

        # Header section
        writer.writerow(["Attendance Report"])
        writer.writerow(["Course", course_code])
        writer.writerow(["Total Present", total_present])
        writer.writerow(["Total Late", total_late])
        writer.writerow([])

        # Table header
        writer.writerow(["Student ID", "Student Name", "Course", "Status"])

        for student_id, student_name, course, status in records:
            writer.writerow([student_id, student_name, course, status])


def export_students_template_csv(filename: str) -> None:
    """Write a blank student import template."""

    with open(filename, "w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(["student_id", "student_name", "Department", "level"])
        writer.writerow(["S001", "Jane Doe", "Computer Science", "100"])


def export_courses_template_csv(filename: str) -> None:
    """Write a blank course import template."""

    with open(filename, "w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(["course_code", "course_title", "lecturer_id", "credit_hours", "grace_minutes"])
        writer.writerow(["CSC101", "Introduction to Computing", "L001", "3", "5"])


def export_registrations_template_csv(filename: str) -> None:
    """Write a blank course-registration import template."""

    with open(filename, "w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(["student_id", "course_code"])
        writer.writerow(["S001", "CSC101"])