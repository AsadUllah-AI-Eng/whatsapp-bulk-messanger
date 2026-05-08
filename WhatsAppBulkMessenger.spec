# -*- mode: python ; coding: utf-8 -*-
"""
PyInstaller spec for WhatsApp Bulk Messenger.

Build:   pyinstaller --noconfirm WhatsAppBulkMessenger.spec
Output:  dist\WhatsAppBulkMessenger\WhatsAppBulkMessenger.exe

One-folder mode (not --onefile):
  * Faster startup — no temp extraction on every launch.
  * Inno Setup ships a folder of files cleanly.
  * Easier to debug — you can see what's actually bundled.
"""
import os
from PyInstaller.utils.hooks import collect_all, collect_data_files, collect_submodules

block_cipher = None

# webdriver_manager and selenium have data files / lazy imports that
# PyInstaller's static analysis misses. Pull them in explicitly.
hidden = (
    collect_submodules('webdriver_manager')
    + collect_submodules('selenium')
    + ['openpyxl', 'pandas']
)

datas = [
    ('templates', 'templates'),     # source -> dest inside the bundle
]
# Include static/ if you have one; harmless if missing.
if os.path.isdir('static'):
    datas.append(('static', 'static'))
datas += collect_data_files('webdriver_manager')

# pywebview ships .NET assemblies and platform shims that PyInstaller's
# static analysis can't see. collect_all pulls in every datafile, binary,
# and submodule the package installs.
extra_binaries = []
for pkg in ('webview', 'clr_loader', 'pythonnet', 'proxy_tools', 'bottle'):
    pkg_datas, pkg_binaries, pkg_hidden = collect_all(pkg)
    datas += pkg_datas
    extra_binaries += pkg_binaries
    hidden += pkg_hidden


a = Analysis(
    ['launcher.py'],
    pathex=[],
    binaries=extra_binaries,
    datas=datas,
    hiddenimports=hidden,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=['tkinter', 'matplotlib', 'pytest'],
    noarchive=False,
    optimize=0,
)
pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name='WhatsAppBulkMessenger',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    console=False,          # native pywebview window — no CMD prompt
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon='icon.ico' if os.path.exists('icon.ico') else None,
)
coll = COLLECT(
    exe,
    a.binaries,
    a.zipfiles,
    a.datas,
    strip=False,
    upx=False,
    upx_exclude=[],
    name='WhatsAppBulkMessenger',
)
