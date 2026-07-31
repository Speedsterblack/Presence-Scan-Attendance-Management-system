from database.lecturer_db import add_lecturer


def main() -> None:
    """Ensure a default admin lecturer exists.

    Creates username=admin, password=admin with role='admin' if not present.
    """

    add_lecturer("admin", "Administrator", "admin", "admin", department_id=1)
    print("Default admin user ensured (username='admin', password='admin').")


if __name__ == "__main__":
    main()
