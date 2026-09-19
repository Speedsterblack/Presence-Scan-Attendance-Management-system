Presence Scan sample data (100 students)
==========================

Student IDs contain exactly 8 digits.
Lecturer IDs contain 6 digits and are valid within the required 6-8 digit range.

Files:
- students_sample.csv: import from the Import Center student import.
- lecturers_sample.csv: import these lecturer accounts from Import Lecturers CSV.
  The sample password for each lecturer is Password123!.
- courses_sample.csv: import after the lecturer accounts exist. It includes day, start, and end timetable values. Each sample course has a total weekly 3-hour class duration to match its 3 credit hours; that duration may be split across multiple days.
- registrations_sample.csv: import after the students and courses exist. It contains one registration for each of the 100 students.

Recommended order:
1. Create or confirm the department used by the sample data.
2. Import lecturers_sample.csv using Import Lecturers CSV.
3. Import students_sample.csv.
4. Import courses_sample.csv.
5. Import registrations_sample.csv.

The sample data is intended for local testing only. Change all sample passwords before production use.
