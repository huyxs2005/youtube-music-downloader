# Python runtime for the WPF desktop; the JSON bridge runs without a visible console.
from pathlib import Path
from PyInstaller.utils.hooks import collect_all, collect_submodules

datas, binaries, hiddenimports = [], [], ["PIL.Image", "mutagen.oggopus"]
for package in ("yt_dlp", "ytmusicapi", "mutagen"):
    data, binary, imports = collect_all(package)
    datas += data
    binaries += binary
    hiddenimports += imports
hiddenimports += collect_submodules("yt_dlp_plugins.extractor")
root = Path(SPECPATH).resolve().parent
a = Analysis([str(root / "desktop_bridge.py")], pathex=[str(root)],
    binaries=binaries, datas=datas, hiddenimports=hiddenimports,
    hookspath=[], hooksconfig={}, runtime_hooks=[],
    excludes=["PIL.AvifImagePlugin", "PIL._avif", "PIL.ImageFont", "PIL._imagingft",
              "PIL.ImageCms", "PIL._imagingcms", "PIL.ImageTk", "PIL.ImageQt", "tkinter"], noarchive=False)
pyz = PYZ(a.pure)
exe = EXE(pyz, a.scripts, [], exclude_binaries=True, name="YouTubeMusicEngine",
    debug=False, strip=False, upx=False, console=True)
coll = COLLECT(exe, a.binaries, a.datas, strip=False, upx=False, name="YouTubeMusicEngine")
