# -*- mode: python ; coding: utf-8 -*-
"""
PyInstaller spec file for PakPOS.
Generates a standalone single-folder distribution for Windows.

Packaging notes
---------------
* python-escpos is a declared dependency but is NOT on the production execution
  path.  WindowsPrinterAdapter uses win32print (Windows spooler) exclusively.
  Therefore escpos data files are NOT bundled here.

* win32print/pywin32 is imported dynamically inside WindowsPrinterAdapter and
  must be listed in hiddenimports so PyInstaller does not miss it.

* Alembic migration files are bundled so the frozen application can run
  schema migrations from sys._MEIPASS if required.  alembic.ini is included
  in the application root.
"""

from PyInstaller.utils.hooks import collect_data_files

block_cipher = None

# Alembic needs its .py and .mako files; PyInstaller will not discover them
# automatically because Alembic loads them at runtime by file path.
alembic_datas = [
    ('pakpos/database/migrations/env.py',         'pakpos/database/migrations'),
    ('pakpos/database/migrations/script.py.mako', 'pakpos/database/migrations'),
    ('pakpos/database/migrations/versions',        'pakpos/database/migrations/versions'),
    ('alembic.ini', '.'),
]

a = Analysis(
    ['pakpos/main.py'],
    pathex=['.'],
    binaries=[],
    datas=[
        ('pakpos/config', 'pakpos/config'),
    ] + alembic_datas,
    hiddenimports=[
        # SQLAlchemy / database
        'sqlalchemy.ext.baked',
        'sqlalchemy.dialects.sqlite',
        # PySide6 Qt
        'PySide6.QtCore',
        'PySide6.QtGui',
        'PySide6.QtWidgets',
        'PySide6.QtCharts',
        # Security
        'bcrypt',
        # ESC/POS Thermal Printing & Barcodes
        'escpos',
        'escpos.printer',
        'escpos.capabilities',
        'qrcode',
        'qrcode.image.pil',
        'reportlab',
        'reportlab.platypus',
        'reportlab.lib',
        'reportlab.lib.pagesizes',
        'reportlab.lib.colors',
        # Windows printing — dynamically imported in WindowsPrinterAdapter
        'win32print',
        'win32api',
        'win32con',
        'pywintypes',
        # Alembic runtime (uses internal dynamic imports)
        'alembic',
        'alembic.runtime.migration',
        'alembic.operations',
        'alembic.operations.ops',
        'alembic.script',
    ],

    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=['tkinter', 'unittest'],
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=block_cipher,
    noarchive=False,
)

pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name='PakPOS',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    console=False,  # GUI application — no console window
    disable_windowed_traceback=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon=None,
)

coll = COLLECT(
    exe,
    a.binaries,
    a.zipfiles,
    a.datas,
    strip=False,
    upx=True,
    upx_exclude=[],
    name='PakPOS',
)
