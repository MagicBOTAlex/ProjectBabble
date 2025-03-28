# -*- mode: python ; coding: utf-8 -*-


a = Analysis(
    ['BabbleApp\\babbleapp.py'],
    pathex=[],
    binaries=[],
    datas=[
        ("BabbleApp/Audio", "Audio"),
        ("BabbleApp/assets", "assets"),
        ("BabbleApp/Images", "Images"),
        ("BabbleApp/Models", "Models"),
    ],
    hiddenimports=['comtypes.stream',"cv2", "numpy"],
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
    a.binaries,
    a.datas,
    [],
    name='PB-Backend-x86_64-pc-windows-msvc',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=True,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon="BabbleApp/Images/logo.ico"
)
