# -*- mode: python ; coding: utf-8 -*-
import glob
import os


project_root = os.path.abspath('.')
datas = []
for subdir in ('resources',):
    for f in glob.glob(os.path.join(subdir, '**', '*'), recursive=True):
        if os.path.isfile(f):
            datas.append((f, os.path.dirname(f)))
datas.append(('apps/DesktopAnnotation.exe', 'apps'))
datas.append(('default_config.json', '.'))

hiddenimports = [
    'settings',
    'settings.main',
    'settings.icc_ce',
    'settings.none',
    'settings.update',
    'settings.ica_series',
    'settings.custom'
    'unhide_annotation_apps',
    'unhide_annotation_apps.icc_ce',
    'unhide_annotation_apps.none',
    'unhide_annotation_apps.custom',
    'unhide_annotation_apps.ica_series'
    'PIL',
    'PIL.Image',
    'numpy',
    'windows_toasts',
    'winrt_runtime',
    'winrt_Windows.Data.Xml.Dom',
    'winrt_Windows.Foundation',
    'winrt_Windows.Foundation.Collections',
    'winrt_Windows.UI.Notifications',
]

a = Analysis(
    ['main.py'],
    pathex=[project_root],
    binaries=[],
    datas=datas,
    hiddenimports=hiddenimports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    noarchive=False,
    optimize=0,
)
pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name='Annotation',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    console=False,
    icon='resources/icon.ico',
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
)
coll = COLLECT(
    exe,
    a.binaries,
    a.datas,
    strip=False,
    upx=True,
    upx_exclude=[],
    name='Seewo-DesktopAnnotation-Replacement',
)
