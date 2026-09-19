from __future__ import annotations

from pathlib import Path

from database.db_config import DB_PATH, get_connection, is_postgres


def create_tables() -> None:
    """Create the configured database schema and seed defaults."""

    conn = get_connection()
    cur = conn.cursor()

    try:
        schema_sql = """
            PRAGMA foreign_keys = ON;

            CREATE TABLE IF NOT EXISTS University (
                university_id INTEGER PRIMARY KEY AUTOINCREMENT,
                university_code TEXT UNIQUE,
                university_name TEXT NOT NULL UNIQUE
            );

            CREATE TABLE IF NOT EXISTS departments (
                department_id INTEGER PRIMARY KEY AUTOINCREMENT,
                department_code TEXT,
                department_name TEXT NOT NULL,
                university_id INTEGER NOT NULL,
                FOREIGN KEY (university_id) REFERENCES University(university_id) ON DELETE CASCADE
            );

            CREATE TABLE IF NOT EXISTS semesters (
                semester_id INTEGER PRIMARY KEY AUTOINCREMENT,
                semester_name TEXT NOT NULL,
                start_date DATE NOT NULL DEFAULT CURRENT_DATE,
                end_date DATE,
                status TEXT NOT NULL DEFAULT 'active',
                created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
                closed_at TIMESTAMP,
                CONSTRAINT semester_status_check CHECK (status IN ('active', 'closed'))
            );

            CREATE TABLE IF NOT EXISTS hods (
                hod_id TEXT PRIMARY KEY,
                hod_name TEXT NOT NULL,
                password TEXT NOT NULL,
                department_id INTEGER UNIQUE NOT NULL,
                FOREIGN KEY (department_id) REFERENCES departments(department_id) ON DELETE CASCADE
            );

            CREATE TABLE IF NOT EXISTS lecturers (
                lecturer_id TEXT PRIMARY KEY,
                lecturer_name TEXT NOT NULL,
                password TEXT NOT NULL,
                department_id INTEGER,
                role TEXT NOT NULL DEFAULT 'lecturer',
                FOREIGN KEY (department_id) REFERENCES departments(department_id) ON DELETE CASCADE
            );

            CREATE TABLE IF NOT EXISTS students (
                student_id TEXT PRIMARY KEY,
                student_name TEXT NOT NULL,
                Department TEXT,
                level TEXT,
                qr_code TEXT UNIQUE
            );

            CREATE TABLE IF NOT EXISTS courses (
                course_id INTEGER PRIMARY KEY AUTOINCREMENT,
                course_code TEXT NOT NULL,
                course_title TEXT NOT NULL,
                department_id INTEGER NOT NULL,
                lecturer_id TEXT NOT NULL,
                credit_hours INTEGER NOT NULL DEFAULT 0,
                grace_minutes INTEGER NOT NULL DEFAULT 0,
                FOREIGN KEY (department_id) REFERENCES departments(department_id) ON DELETE CASCADE,
                FOREIGN KEY (lecturer_id) REFERENCES lecturers(lecturer_id)
            );

            CREATE TABLE IF NOT EXISTS course_registrations (
                student_id TEXT NOT NULL,
                course_id INTEGER NOT NULL,
                semester_id INTEGER NOT NULL,
                PRIMARY KEY (student_id, course_id, semester_id),
                FOREIGN KEY (student_id) REFERENCES students(student_id) ON DELETE CASCADE,
                FOREIGN KEY (course_id) REFERENCES courses(course_id) ON DELETE CASCADE,
                FOREIGN KEY (semester_id) REFERENCES semesters(semester_id) ON DELETE CASCADE
            );

            CREATE TABLE IF NOT EXISTS timetable (
                timetable_id INTEGER PRIMARY KEY AUTOINCREMENT,
                course_id INTEGER NOT NULL,
                day_of_week TEXT NOT NULL,
                start_time TIME NOT NULL,
                end_time TIME NOT NULL,
                FOREIGN KEY (course_id) REFERENCES courses(course_id) ON DELETE CASCADE
            );

            CREATE TABLE IF NOT EXISTS attendance (
                attendance_id INTEGER PRIMARY KEY AUTOINCREMENT,
                timetable_id INTEGER NOT NULL,
                student_id TEXT NOT NULL,
                semester_id INTEGER NOT NULL,
                attendance_date DATE NOT NULL DEFAULT CURRENT_DATE,
                status TEXT NOT NULL CHECK (status IN ('Present', 'Absent', 'Late')),
                FOREIGN KEY (timetable_id) REFERENCES timetable(timetable_id) ON DELETE CASCADE,
                FOREIGN KEY (student_id) REFERENCES students(student_id) ON DELETE CASCADE,
                FOREIGN KEY (semester_id) REFERENCES semesters(semester_id) ON DELETE CASCADE,
                UNIQUE (timetable_id, student_id, attendance_date, semester_id)
            );

            CREATE TABLE IF NOT EXISTS special_days (
                special_day_id INTEGER PRIMARY KEY AUTOINCREMENT,
                department_id INTEGER NOT NULL,
                day DATE NOT NULL,
                label TEXT,
                is_no_school INTEGER NOT NULL DEFAULT 1,
                FOREIGN KEY (department_id) REFERENCES departments(department_id) ON DELETE CASCADE
            );

            CREATE TABLE IF NOT EXISTS audit_log (
                audit_id INTEGER PRIMARY KEY AUTOINCREMENT,
                actor_id TEXT,
                actor_role TEXT,
                action TEXT NOT NULL,
                details TEXT,
                created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
            );
            """
        if is_postgres():
            schema_sql = schema_sql.replace("PRAGMA foreign_keys = ON;", "")
            schema_sql = schema_sql.replace(
                "INTEGER PRIMARY KEY AUTOINCREMENT",
                "INTEGER GENERATED BY DEFAULT AS IDENTITY PRIMARY KEY",
            )
            for statement in schema_sql.split(";"):
                if statement.strip():
                    cur.execute(statement)
        else:
            cur.executescript(schema_sql)

        cur.execute(
            "INSERT INTO University (university_id, university_code, university_name) "
            "VALUES (1, 'SCH001', 'Default University') "
            "ON CONFLICT DO NOTHING"
        )
        cur.execute(
            "INSERT INTO departments (department_id, department_code, department_name, university_id) "
            "VALUES (1, 'D001', 'Default Department', 1) "
            "ON CONFLICT DO NOTHING"
        )

        cur.execute("SELECT COUNT(*) AS active_count FROM semesters WHERE status = 'active'")
        active_row = cur.fetchone()
        active_count = int(active_row["active_count"]) if active_row is not None else 0
        if active_count == 0:
            cur.execute(
                "INSERT INTO semesters (semester_id, semester_name, start_date, status) "
                "VALUES (1, 'Semester 1', CURRENT_DATE, 'active') "
                "ON CONFLICT DO NOTHING"
            )
            cur.execute(
                "UPDATE semesters SET status = 'active' "
                "WHERE semester_id = (SELECT semester_id FROM semesters ORDER BY semester_id LIMIT 1)"
            )

        cur.execute(
            "CREATE UNIQUE INDEX IF NOT EXISTS idx_University_university_code "
            "ON University(university_code)"
        )
        if is_postgres():
            cur.execute(
                "ALTER TABLE departments DROP CONSTRAINT IF EXISTS departments_department_code_key"
            )
        cur.execute(
            "CREATE UNIQUE INDEX IF NOT EXISTS idx_departments_university_code "
            "ON departments(university_id, department_code)"
        )
        cur.execute("CREATE INDEX IF NOT EXISTS idx_semesters_status ON semesters(status)")
        cur.execute("CREATE UNIQUE INDEX IF NOT EXISTS idx_courses_course_code ON courses(course_code)")
        cur.execute(
            "CREATE UNIQUE INDEX IF NOT EXISTS idx_attendance_daily_unique "
            "ON attendance(timetable_id, student_id, attendance_date, semester_id)"
        )
        cur.execute(
            "CREATE UNIQUE INDEX IF NOT EXISTS idx_special_days_department_day "
            "ON special_days(department_id, day)"
        )

        conn.commit()
    finally:
        cur.close()
        conn.close()

    if is_postgres():
        print("PostgreSQL database ready")
    else:
        print(f"Local sqlite database ready at {Path(DB_PATH)}")


if __name__ == "__main__":
    create_tables()