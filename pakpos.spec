# -*- mode: python ; coding: utf-8 -*-
"""
PyInstaller spec file for PakPOS.
Generates a standalone single-folder distribution for Windows.
"""

block_cipher = None

a = Analysis(
    ['pakpos/main.py'],
    pathex=['.'],
    binaries=[],
    datas=[
        ('pakpos/config', 'pakpos/config'),
    ],
    hiddenimports=[
        'sqlalchemy.ext.baked',
        'sqlalchemy.dialects.sqlite',
        'PySide6.QtCore',
        'PySide6.QtGui',
        'PySide6.QtWidgets',
        'bcrypt',
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
    console=False,  # GUI application, no console window
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
