# -*- mode: python ; coding: utf-8 -*-


from pathlib import Path


project_root = Path(SPECPATH).resolve()

datas = [
    (str(project_root / 'config' / 'settings.json'), 'config'),
    (str(project_root / 'templates' / 'mobile_scanner.html'), 'templates'),
    (str(project_root / 'assets' / 'images' / 'background.png'), 'assets/images'),
    (str(project_root / 'assets' / 'icons' / 'Presence_Scan.ico'), 'assets/icons'),
]


a = Analysis(
    ['main\\developer_main.py'],
    pathex=[str(project_root)],
    binaries=[],
    datas=datas,
    hiddenimports=['psycopg2', 'psycopg2.extras', 'flask'],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=['tkinter.test', 'unittest', 'pytest'],
    noarchive=False,
    optimize=0,
)
pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.datas,
    [],
    name='DeveloperPresenceScan',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
)