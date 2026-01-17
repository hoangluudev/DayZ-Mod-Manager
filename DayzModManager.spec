# -*- mode: python ; coding: utf-8 -*-

import os
from pathlib import Path

block_cipher = None

_spec_file = globals().get('__file__')
project_dir = Path(_spec_file).resolve().parent if _spec_file else Path.cwd()

# Supported modes: prod | dev
build_mode = os.environ.get('DMM_BUILD_MODE', 'prod').strip().lower()
is_dev = build_mode == 'dev'

# Include custom folders (with contents) in the final onedir bundle.
# NOTE: Analysis() expects (src, dest) 2-tuples; we build those explicitly.
def collect_dir(src_dir: Path, dest_root: str):
    out = []
    if not src_dir.exists():
        return out
    for p in src_dir.rglob('*'):
        if p.is_file():
            rel_parent = p.relative_to(src_dir).parent
            dest = str(Path(dest_root) / rel_parent)
            out.append((str(p), dest))
    return out


datas = []
datas += collect_dir(project_dir / 'locales', 'locales')
_cfg_datas = collect_dir(project_dir / 'configs', 'configs')
# app.json is embedded into the exe (see tools/embed_app_config.py); do not ship it as plain JSON.
_app_json = str((project_dir / 'configs' / 'app.json').resolve())
datas += [t for t in _cfg_datas if str(Path(t[0]).resolve()) != _app_json]
datas += collect_dir(project_dir / 'assets', 'assets')
 # Do not bundle user data folders

a = Analysis(
    ['main.py'],
    pathex=[str(project_dir)],
    binaries=[],
    datas=datas,
    hiddenimports=[],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    # Exclude heavy/unused modules to reduce bundle size.
    # Note: do NOT use collect_all('PySide6') here; it causes bloat.
    excludes=[
        # PySide6 heavy modules (commonly unused in widget apps)
        'PySide6.QtWebEngineCore',
        'PySide6.QtWebEngineWidgets',
        'PySide6.QtWebEngineQuick',
        'PySide6.QtWebChannel',
        'PySide6.QtQml',
        'PySide6.QtQuick',
        'PySide6.QtQuickControls2',
        'PySide6.QtQuickWidgets',
        'PySide6.Qt3DCore',
        'PySide6.Qt3DRender',
        'PySide6.Qt3DInput',
        'PySide6.Qt3DLogic',
        'PySide6.Qt3DAnimation',
        'PySide6.Qt3DExtras',
        'PySide6.QtCharts',
        'PySide6.QtBluetooth',
        # Optional stacks that often drag many deps
        'PySide6.QtMultimedia',
        'PySide6.QtMultimediaWidgets',
        'PySide6.QtPdf',
        'PySide6.QtPdfWidgets',
        # Python stdlib GUI toolkit
        'tkinter',
        'tkinter.*',
    ],
    noarchive=False,
    optimize=0 if is_dev else 2,
)

pyz = PYZ(a.pure, cipher=block_cipher)

icon_file = project_dir / 'assets' / 'icons' / 'app_icon.ico'
icon_path = str(icon_file) if icon_file.exists() else None

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name='DayzModManager',
    icon=icon_path,
    debug=is_dev,
    bootloader_ignore_signals=False,
    strip=False,
    upx=(not is_dev),
    upx_exclude=[],
    runtime_tmpdir=None,
    console=is_dev,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
)

# One-directory output (fast startup, modular structure)
coll = COLLECT(
    exe,
    a.binaries,
    a.zipfiles,
    a.datas,
    strip=False,
    upx=(not is_dev),
    upx_exclude=[],
    name='DayzModManager',
)
