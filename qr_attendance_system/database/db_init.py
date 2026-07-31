from database.db_config import get_connection

def create_tables():
    conn = get_connection()

    cur = conn.cursor()

    schema_sql = """

    -- 1. University
    CREATE TABLE IF NOT EXISTS University (
        university_id SERIAL PRIMARY KEY,
        university_name VARCHAR(150) NOT NULL UNIQUE
    );

    -- Optional human-readable university code (string ID)
    ALTER TABLE IF EXISTS University
        ADD COLUMN IF NOT EXISTS university_code VARCHAR(20);

    CREATE UNIQUE INDEX IF NOT EXISTS idx_University_university_code
        ON University(university_code);

    -- 2. Departments
    CREATE TABLE IF NOT EXISTS departments (
        department_id SERIAL PRIMARY KEY,
        department_name VARCHAR(150) NOT NULL,
        university_id INT NOT NULL,
        FOREIGN KEY (university_id) REFERENCES University(university_id) ON DELETE CASCADE
    );

    -- Optional human-readable department code (string ID)
    ALTER TABLE IF EXISTS departments
        ADD COLUMN IF NOT EXISTS department_code VARCHAR(20);

    CREATE UNIQUE INDEX IF NOT EXISTS idx_departments_department_code
        ON departments(department_code);

    -- 3b. Semesters / academic sessions
    CREATE TABLE IF NOT EXISTS semesters (
        semester_id SERIAL PRIMARY KEY,
        semester_name VARCHAR(150) NOT NULL,
        start_date DATE NOT NULL DEFAULT CURRENT_DATE,
        end_date DATE,
        status VARCHAR(20) NOT NULL DEFAULT 'active',
        created_at TIMESTAMP NOT NULL DEFAULT NOW(),
        closed_at TIMESTAMP,
        CONSTRAINT semester_status_check CHECK (status IN ('active', 'closed'))
    );

    CREATE INDEX IF NOT EXISTS idx_semesters_status
        ON semesters(status);

    -- 3. HODs
    CREATE TABLE IF NOT EXISTS hods (
        hod_id VARCHAR(20) PRIMARY KEY,
        hod_name VARCHAR(150) NOT NULL,
        password VARCHAR(255) NOT NULL,
        department_id INT UNIQUE NOT NULL,
        FOREIGN KEY (department_id) REFERENCES departments(department_id) ON DELETE CASCADE
    );

    -- 4. Lecturers
    CREATE TABLE IF NOT EXISTS lecturers (
        lecturer_id VARCHAR(20) PRIMARY KEY,
        lecturer_name VARCHAR(150) NOT NULL,
        password VARCHAR(255) NOT NULL,
        department_id INT NOT NULL,
        FOREIGN KEY (department_id) REFERENCES departments(department_id) ON DELETE CASCADE
    );

    -- 5. Students
    CREATE TABLE IF NOT EXISTS students (
        student_id VARCHAR(20) PRIMARY KEY,
        student_name VARCHAR(150) NOT NULL,
        Department VARCHAR(150),
        level VARCHAR(50),
        qr_code VARCHAR(255) UNIQUE
    );

    -- 6. Courses
    CREATE TABLE IF NOT EXISTS courses (
        course_id SERIAL PRIMARY KEY,
        course_code VARCHAR(20) NOT NULL,
        course_title VARCHAR(150) NOT NULL,
        department_id INT NOT NULL,
        lecturer_id VARCHAR(20) NOT NULL,
        credit_hours INT NOT NULL DEFAULT 0,
        grace_minutes INT NOT NULL DEFAULT 0,
        FOREIGN KEY (department_id) REFERENCES departments(department_id) ON DELETE CASCADE,
        FOREIGN KEY (lecturer_id) REFERENCES lecturers(lecturer_id)
    );

    -- Ensure course_code is unique so INSERT ... ON CONFLICT (course_code) works
    CREATE UNIQUE INDEX IF NOT EXISTS idx_courses_course_code
        ON courses(course_code);

    -- 7. Course Registrations (Many-to-Many)
    CREATE TABLE IF NOT EXISTS course_registrations (
        student_id VARCHAR(20),
        course_id INT,
        semester_id INT NOT NULL,
        PRIMARY KEY (student_id, course_id, semester_id),
        FOREIGN KEY (student_id) REFERENCES students(student_id) ON DELETE CASCADE,
        FOREIGN KEY (course_id) REFERENCES courses(course_id) ON DELETE CASCADE,
        FOREIGN KEY (semester_id) REFERENCES semesters(semester_id) ON DELETE CASCADE
    );

    -- 6b. Backwards-compatible alteration for existing databases
    ALTER TABLE IF EXISTS courses
        ADD COLUMN IF NOT EXISTS grace_minutes INT NOT NULL DEFAULT 0;
    ALTER TABLE IF EXISTS courses
        ADD COLUMN IF NOT EXISTS credit_hours INT NOT NULL DEFAULT 0;

        -- 6c. Backwards-compatible alteration for existing students table
        ALTER TABLE IF EXISTS students
		ADD COLUMN IF NOT EXISTS Department VARCHAR(150),
		ADD COLUMN IF NOT EXISTS level VARCHAR(50);

        -- Migrate legacy Department/level data encoded in qr_code (if present)
        UPDATE students
        SET
		Department = COALESCE(Department, NULLIF(split_part(qr_code, '|', 1), '')),
		level = COALESCE(level, NULLIF(split_part(qr_code, '|', 2), ''))
        WHERE qr_code IS NOT NULL;

        -- Ensure qr_code itself is unique per student by defaulting to student_id
        UPDATE students
    	SET qr_code = student_id;

    -- 8. Timetable
    CREATE TABLE IF NOT EXISTS timetable (
        timetable_id SERIAL PRIMARY KEY,
        course_id INT NOT NULL,
        day_of_week VARCHAR(20) NOT NULL,
        start_time TIME NOT NULL,
        end_time TIME NOT NULL,
        FOREIGN KEY (course_id) REFERENCES courses(course_id) ON DELETE CASCADE
    );
  
    -- 9. Attendance
    CREATE TABLE IF NOT EXISTS attendance (
        attendance_id SERIAL PRIMARY KEY,
        timetable_id INT NOT NULL,
        student_id VARCHAR(20) NOT NULL,
        semester_id INT NOT NULL,
        attendance_date DATE NOT NULL DEFAULT CURRENT_DATE,
        status VARCHAR(10) CHECK (status IN ('Present', 'Absent', 'Late')) NOT NULL,
        FOREIGN KEY (timetable_id) REFERENCES timetable(timetable_id) ON DELETE CASCADE,
        FOREIGN KEY (student_id) REFERENCES students(student_id) ON DELETE CASCADE,
        FOREIGN KEY (semester_id) REFERENCES semesters(semester_id) ON DELETE CASCADE,
        UNIQUE (timetable_id, student_id, attendance_date, semester_id)
    );

    -- Ensure attendance records are tracked per calendar day so
    -- analytics and dashboards can show "today's" data instead
    -- of an all-time aggregate. Existing databases are migrated
    -- in a backwards-compatible way.

    -- Add attendance_date column if missing.
    ALTER TABLE IF EXISTS attendance
        ADD COLUMN IF NOT EXISTS attendance_date DATE;

    -- For legacy rows that pre-date this column, approximate
    -- their date as "yesterday" so they no longer appear in
    -- "today" analytics but are still kept for reference.
    UPDATE attendance
       SET attendance_date = COALESCE(attendance_date, CURRENT_DATE - INTERVAL '1 day');

    -- From now on, attendance_date defaults to the current date
    -- and is required.
    ALTER TABLE IF EXISTS attendance
        ALTER COLUMN attendance_date SET DEFAULT CURRENT_DATE,
        ALTER COLUMN attendance_date SET NOT NULL;

    -- Allow one record per student, timetable and day instead of
    -- a single record for all time. Drop the old unique constraint
    -- if it exists and replace it with a daily unique index.
    ALTER TABLE IF EXISTS attendance
        DROP CONSTRAINT IF EXISTS attendance_status_check;
    ALTER TABLE IF EXISTS attendance
        ADD CONSTRAINT attendance_status_check CHECK (status IN ('Present', 'Absent', 'Late'));
    ALTER TABLE IF EXISTS attendance
        DROP CONSTRAINT IF EXISTS attendance_timetable_id_student_id_key;

    CREATE UNIQUE INDEX IF NOT EXISTS idx_attendance_daily_unique
        ON attendance(timetable_id, student_id, attendance_date);

    -- 10. Special days / no-school days
    CREATE TABLE IF NOT EXISTS special_days (
        special_day_id SERIAL PRIMARY KEY,
        department_id INT NOT NULL REFERENCES departments(department_id) ON DELETE CASCADE,
        day DATE NOT NULL,
        label VARCHAR(150),
        is_no_school BOOLEAN NOT NULL DEFAULT TRUE
    );

    -- 11. Audit log
    CREATE TABLE IF NOT EXISTS audit_log (
        audit_id SERIAL PRIMARY KEY,
        actor_id VARCHAR(20),
        actor_role VARCHAR(20),
        action VARCHAR(80) NOT NULL,
        details TEXT,
        created_at TIMESTAMP NOT NULL DEFAULT NOW()
    );

    """

    # Create tables and indexes
    cur.execute(schema_sql)

    # Ensure there is at least one default university and department
    # so that code using DEFAULT_DEPARTMENT_ID = 1 has a valid FK target.
    cur.execute(
        "INSERT INTO University (university_id, university_name)\n"
        "VALUES (1, 'Default University')\n"
        "ON CONFLICT (university_id) DO NOTHING"
    )
    cur.execute(
        "INSERT INTO departments (department_id, department_name, university_id)\n"
        "VALUES (1, 'Default Department', 1)\n"
        "ON CONFLICT (department_id) DO NOTHING"
    )

    # Ensure there is always one active semester available for new registrations
    cur.execute(
        "SELECT semester_id, semester_name FROM semesters WHERE status = 'active' ORDER BY start_date DESC, semester_id DESC LIMIT 1"
    )
    active_semester = cur.fetchone()
    if not active_semester:
        cur.execute(
            "INSERT INTO semesters (semester_name, start_date, status)\n"
            "VALUES (%s, CURRENT_DATE, 'active')",
            ('Semester 1',),
        )
        cur.execute(
            "SELECT semester_id, semester_name FROM semesters WHERE status = 'active' ORDER BY start_date DESC, semester_id DESC LIMIT 1"
        )
        active_semester = cur.fetchone()

    active_semester_id = int(active_semester[0]) if active_semester else 1

    # Backfill semesters for legacy course registrations and attendance rows.
    cur.execute("ALTER TABLE IF EXISTS course_registrations ADD COLUMN IF NOT EXISTS semester_id INT")
    cur.execute("ALTER TABLE IF EXISTS attendance ADD COLUMN IF NOT EXISTS semester_id INT")
    cur.execute(
        "UPDATE course_registrations SET semester_id = COALESCE(semester_id, %s)",
        (active_semester_id,),
    )
    cur.execute(
        "UPDATE attendance SET semester_id = COALESCE(semester_id, %s)",
        (active_semester_id,),
    )
    cur.execute(
        "DO $$ BEGIN\n"
        "    ALTER TABLE course_registrations\n"
        "        ADD CONSTRAINT course_registrations_semester_id_fkey\n"
        "        FOREIGN KEY (semester_id) REFERENCES semesters(semester_id) ON DELETE CASCADE;\n"
        "EXCEPTION WHEN duplicate_object THEN NULL; END $$;"
    )
    cur.execute(
        "DO $$ BEGIN\n"
        "    ALTER TABLE attendance\n"
        "        ADD CONSTRAINT attendance_semester_id_fkey\n"
        "        FOREIGN KEY (semester_id) REFERENCES semesters(semester_id) ON DELETE CASCADE;\n"
        "EXCEPTION WHEN duplicate_object THEN NULL; END $$;"
    )
    cur.execute("ALTER TABLE IF EXISTS course_registrations DROP CONSTRAINT IF EXISTS course_registrations_pkey")
    cur.execute(
        "ALTER TABLE IF EXISTS course_registrations\n"
        "    ADD PRIMARY KEY (student_id, course_id, semester_id)"
    )
    cur.execute(
        "ALTER TABLE IF EXISTS course_registrations\n"
        "    ALTER COLUMN semester_id SET NOT NULL"
    )
    cur.execute(
        "ALTER TABLE IF EXISTS attendance\n"
        "    ALTER COLUMN semester_id SET DEFAULT %s",
        (active_semester_id,),
    )
    cur.execute(
        "ALTER TABLE IF EXISTS attendance\n"
        "    ALTER COLUMN semester_id SET NOT NULL"
    )
    cur.execute("DROP INDEX IF EXISTS idx_attendance_daily_unique")
    cur.execute(
        "CREATE UNIQUE INDEX IF NOT EXISTS idx_attendance_daily_unique\n"
        "    ON attendance(timetable_id, student_id, attendance_date, semester_id)"
    )

    # Migrate legacy special-days rows that were shared across all
    # departments so that each department keeps its own copy.
    cur.execute(
        "SELECT EXISTS (\n"
        "  SELECT 1\n"
        "  FROM information_schema.columns\n"
        "  WHERE table_name = 'special_days' AND column_name = 'department_id'\n"
        ") AS has_department_id,\n"
        "EXISTS (\n"
        "  SELECT 1\n"
        "  FROM information_schema.table_constraints\n"
        "  WHERE table_name = 'special_days' AND constraint_name = 'special_days_day_key'\n"
        ") AS has_day_unique"
    )
    special_days_meta = cur.fetchone() or (False, False)
    has_department_id = bool(special_days_meta[0])
    has_day_unique = bool(special_days_meta[1])

    if has_day_unique:
        cur.execute("ALTER TABLE IF EXISTS special_days DROP CONSTRAINT IF EXISTS special_days_day_key")

    if not has_department_id:
        cur.execute(
            "ALTER TABLE IF EXISTS special_days\n"
            "    ADD COLUMN IF NOT EXISTS department_id INT REFERENCES departments(department_id) ON DELETE CASCADE"
        )
        cur.execute("UPDATE special_days SET department_id = 1 WHERE department_id IS NULL")
        cur.execute(
            "ALTER TABLE IF EXISTS special_days\n"
            "    ALTER COLUMN department_id SET DEFAULT 1,\n"
            "    ALTER COLUMN department_id SET NOT NULL"
        )
        cur.execute(
            "INSERT INTO special_days (department_id, day, label, is_no_school)\n"
            "SELECT d.department_id, s.day, s.label, s.is_no_school\n"
            "FROM special_days s\n"
            "CROSS JOIN departments d\n"
            "WHERE s.department_id = 1\n"
            "  AND d.department_id <> 1\n"
            "  AND NOT EXISTS (\n"
            "      SELECT 1\n"
            "      FROM special_days existing\n"
            "      WHERE existing.department_id = d.department_id\n"
            "        AND existing.day = s.day\n"
            "  )"
        )

    cur.execute(
        "CREATE UNIQUE INDEX IF NOT EXISTS idx_special_days_department_day\n"
        "    ON special_days(department_id, day)"
    )

    # Align sequences with current max ids so future inserts using the
    # SERIAL/sequence do not collide with the manually inserted id=1
    # records above or any other existing rows.
    cur.execute(
        "SELECT setval(\n"
        "  pg_get_serial_sequence('University', 'university_id'),\n"
        "  COALESCE((SELECT MAX(university_id) FROM University), 1)\n"
        ")"
    )
    cur.execute(
        "SELECT setval(\n"
        "  pg_get_serial_sequence('departments', 'department_id'),\n"
        "  COALESCE((SELECT MAX(department_id) FROM departments), 1)\n"
        ")"
    )
    conn.commit()

    cur.close()
    conn.close()

    print("All tables created successfully.")


if __name__ == "__main__":
    create_tables()