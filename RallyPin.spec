# -*- mode: python ; coding: utf-8 -*-

from PyInstaller.utils.hooks import collect_all


imageio_datas, imageio_binaries, imageio_hiddenimports = collect_all("imageio_ffmpeg")

analysis = Analysis(
    ["run_rallypin.py"],
    pathex=["src"],
    binaries=imageio_binaries,
    datas=imageio_datas,
    hiddenimports=imageio_hiddenimports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    noarchive=False,
    optimize=1,
)
pyz = PYZ(analysis.pure)

executable = EXE(
    pyz,
    analysis.scripts,
    analysis.binaries,
    analysis.datas,
    [],
    name="RallyPin",
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
