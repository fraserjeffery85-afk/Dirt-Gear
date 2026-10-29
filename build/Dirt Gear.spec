# -*- mode: python ; coding: utf-8 -*-
# Portable PyInstaller spec for Dirt Gear. Run from anywhere:
#   python -m PyInstaller --noconfirm --distpath dist --workpath work "build/Dirt Gear.spec"
import os
from PyInstaller.utils.hooks import collect_all

SRC = os.path.abspath(os.path.join(SPECPATH, '..', 'source'))
datas = [(os.path.join(SRC, 'static'), 'static'), (os.path.join(SRC, 'fonts'), 'fonts'), (os.path.join(SRC, 'icon.ico'), '.'),
         (os.path.join(SRC, '..', 'VERSION.txt'), '.'), (os.path.join(SRC, 'update_public_key.pem'), '.')]
# Written by the release workflow; builds without it never check for updates.
if os.path.isfile(os.path.join(SRC, 'update_repo.txt')):
    datas.append((os.path.join(SRC, 'update_repo.txt'), '.'))
binaries = []
hiddenimports = ['aggdraw', 'webview.platforms.edgechromium']
for package in ('psd_tools', 'skimage', 'scipy'):
    d, b, h = collect_all(package)
    datas += d; binaries += b; hiddenimports += h

a = Analysis(
    [os.path.join(SRC, 'app.py')],
    pathex=[SRC],
    binaries=binaries,
    datas=datas,
    hiddenimports=hiddenimports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=['PyQt5', 'PyQt6', 'PySide2', 'PySide6', 'tkinter'],
    noarchive=False,
    optimize=0,
)
pyz = PYZ(a.pure)
exe = EXE(pyz, a.scripts, [], exclude_binaries=True, name='Dirt Gear', debug=False,
          bootloader_ignore_signals=False, strip=False, upx=True, console=False,
          disable_windowed_traceback=False, argv_emulation=False, target_arch=None,
          codesign_identity=None, entitlements_file=None, icon=[os.path.join(SRC, 'icon.ico')])
coll = COLLECT(exe, a.binaries, a.datas, strip=False, upx=True, upx_exclude=[], name='Dirt Gear')
