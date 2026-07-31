import os
from database.db_config import init_db_pool
init_db_pool(os.getenv("DATABASE_URL"))
from database.course_db import add_course, get_all_courses
add_course("CS101","Intro to CS", None, 3, "Dr Test")
print(get_all_courses())