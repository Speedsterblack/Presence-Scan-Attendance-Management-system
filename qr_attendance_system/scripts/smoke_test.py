from database.db_init import create_tables
from database.university_db import get_all_University
from database.department_db import get_all_departments
from database.semester_db import get_active_semester


create_tables()
print(get_all_University())
print(get_all_departments())
print(get_active_semester())