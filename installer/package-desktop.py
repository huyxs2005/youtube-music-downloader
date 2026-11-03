"""Create a portable desktop ZIP and SHA-256 file from a built release folder."""
from __future__ import annotations

import argparse
import hashlib
from pathlib import Path
import zipfile


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("folder", type=Path)
    parser.add_argument("--version", default="2.2.3")
    parser.add_argument("--output", type=Path, default=Path("dist/releases"))
    args = parser.parse_args()
    folder = args.folder.resolve()
    required = ["YouTubeMusicDownloader.Desktop.exe", "app/YouTubeMusicDownloader.Desktop.exe",
                "app/YouTubeMusicDownloader.Desktop.dll", "app/YouTubeMusicDownloader.Desktop.runtimeconfig.json", "app/coreclr.dll",
                "app/engine/YouTubeMusicEngine.exe", "app/tools/ffmpeg.exe", "app/tools/ffprobe.exe",
                "app/README.md", "app/THIRD_PARTY_NOTICES.txt", "app/DESKTOP_THIRD_PARTY_NOTICES.txt"]
    for name in required:
        if not (folder / name).is_file():
            raise SystemExit(f"Release folder is missing {name}")
    # Only distribute application files, never a user's adjacent cookies or playlist folders.
    files = [folder / "YouTubeMusicDownloader.Desktop.exe"] + sorted(path for path in (folder / "app").rglob("*") if path.is_file())
    for path in files:
        name = path.name.lower()
        if (name.startswith("cookies") and name.endswith(".txt")) or path.suffix.lower() in {".opus", ".m3u8"} or name in {
            "playlist_manifest.json", "failed_downloads.txt", "download_errors.log", "cookie-path.txt"
        }:
            raise SystemExit(f"Private or downloaded content must not be packaged: {path.relative_to(folder)}")
    args.output.mkdir(parents=True, exist_ok=True)
    archive = args.output / f"YouTubeMusicDownloader-Desktop-v{args.version}-win-x64.zip"
    if archive.exists():
        raise SystemExit(f"Archive already exists; choose a new output directory: {archive}")
    with zipfile.ZipFile(archive, "w", compression=zipfile.ZIP_DEFLATED, compresslevel=9) as output:
        for path in files:
            output.write(path, Path("YouTubeMusicDownloader-Desktop") / path.relative_to(folder))
    with zipfile.ZipFile(archive) as output:
        damaged = output.testzip()
        if damaged:
            raise SystemExit(f"Archive verification failed: {damaged}")
    with archive.open("rb") as source:
        digest = hashlib.file_digest(source, "sha256").hexdigest()
    checksum = archive.with_suffix(archive.suffix + ".sha256")
    checksum.write_text(f"{digest}  {archive.name}\n", encoding="ascii")
    print(f"ZIP: {archive.resolve()}", flush=True)
    print(f"SHA-256: {digest}", flush=True)
    print(f"Files: {len(files)}; size: {archive.stat().st_size:,} bytes", flush=True)


if __name__ == "__main__":
    main()
