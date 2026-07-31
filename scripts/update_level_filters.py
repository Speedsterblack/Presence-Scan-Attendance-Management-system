import re
from pathlib import Path

files = [
    Path('qr_attendance_system/ui/register_student_ui.py'),
    Path('qr_attendance_system/ui/student_ui.py'),
]

for p in files:
    s = p.read_text(encoding='utf-8')
    # replace _passes_quick_filter
    s_new = re.sub(
        r"def _passes_quick_filter\([\s\S]*?return True\n\n",
        (
            "def _passes_quick_filter(sid, name, Department, level, txt):\n"
            "        mode = current_filter.get()\n"
            "        level_num = _to_level_number(level)\n"
            "        if mode == 'lvl100':\n"
            "            return level_num == 100\n"
            "        if mode == 'lvl200':\n"
            "            return level_num == 200\n"
            "        if mode == 'lvl300':\n"
            "            return level_num == 300\n"
            "        if mode == 'lvl400':\n"
            "            return level_num == 400\n"
            "        if mode == 'no_Department':\n"
            "            return not str(Department or '').strip()\n"
            "        return True\n\n"
        ),
        s,
        flags=re.M,
    )
    s = s_new
    # replace chip_specs block
    s_new = re.sub(
        r"chip_specs = \[[\s\S]*?\]\n",
        (
            "chip_specs = [\n"
            "        ('All', 'all', ui_styles.SECONDARY_BUTTON),\n"
            "        ('Level 100', 'lvl100', ui_styles.INFO_BUTTON),\n"
            "        ('Level 200', 'lvl200', ui_styles.INFO_BUTTON),\n"
            "        ('Level 300', 'lvl300', ui_styles.SUCCESS_BUTTON),\n"
            "        ('Level 400', 'lvl400', ui_styles.WARNING_BUTTON),\n"
            "        ('No Department', 'no_Department', ui_styles.WARNING_BUTTON),\n"
            "    ]\n"
        ),
        s,
        flags=re.M,
    )
    if s_new != s:
        p.write_text(s_new, encoding='utf-8')
        print(f'Updated {p}')
    else:
        print(f'No changes for {p}')
