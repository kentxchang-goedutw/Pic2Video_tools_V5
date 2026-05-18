# -*- mode: python ; coding: utf-8 -*-

from pathlib import Path

ROOT = Path(SPECPATH)
APP_NAME = "多功能圖片影音製作器V5.3"
ENTRY_SCRIPT = ROOT / "多功能圖片影音製作器V5.py"

# FFmpeg 執行檔 (若有)
ffmpeg_binaries = []
ffmpeg_path = ROOT / "ffmpeg"
if ffmpeg_path.exists():
    ffmpeg_binaries = [
        (str(path), "ffmpeg/bin")
        for path in (ffmpeg_path / "bin").glob("*")
        if path.is_file()
    ]

# 資源檔案
datas = [
    (str(ROOT / "ico.png"), "."),
    (str(ROOT / "assets" / "app-icon.png"), "assets"),
    (str(ROOT / "licenses" / "FFmpeg-LICENSE.txt"), "licenses"),
    (str(ROOT / "licenses" / "NotoSansTC-LICENSE.txt"), "licenses"),
]

# 字型檔案 (若有)
fonts_path = ROOT / "fonts"
if fonts_path.exists():
    datas.append((str(fonts_path / "NotoSansTC-VF.ttf"), "fonts"))

a = Analysis(
    [str(ENTRY_SCRIPT)],
    pathex=[str(ROOT)],
    binaries=ffmpeg_binaries,
    datas=datas,
    hiddenimports=[
        "PyQt5.QtMultimedia",
        "PyQt5.QtMultimediaWidgets",
    ],
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
    name=APP_NAME,
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
    icon=str(ROOT / "assets" / "app.ico"),
)
