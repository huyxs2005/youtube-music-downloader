"""Line-delimited JSON bridge for the WPF app; stdout is protocol only."""
from __future__ import annotations

import contextlib
from dataclasses import asdict
import json
from pathlib import Path
import sys
import time
import re
import math
from threading import Lock

import ytmusic_downloader as engine

_write_lock = Lock()
_protocol = sys.stdout


def validate_cookies(path: str | None) -> str:
    """Check the exported file locally without logging cookie names or values."""
    if not path:
        raise ValueError("Cookies required. Add a YouTube cookies.txt file to continue.")
    cookie_path = Path(path).expanduser().resolve()
    try:
        lines = cookie_path.read_text(encoding="utf-8-sig").splitlines()
    except (OSError, UnicodeError):
        raise ValueError("Cannot read this cookie file. Add an accessible cookies.txt file.") from None
    if not lines or not re.match(r"^#(?: Netscape)? HTTP Cookie File", lines[0]):
        raise ValueError("Invalid cookie format. Export a Netscape cookies.txt file from YouTube.")
    youtube = usable = 0
    for raw in lines[1:]:
        line = raw.removeprefix("#HttpOnly_")
        if not line.strip() or line.startswith("#"):
            continue
        fields = line.split("\t")
        if (len(fields) != 7 or not fields[0] or any(c.isspace() for c in fields[0])
                or fields[1] not in ("TRUE", "FALSE") or fields[3] not in ("TRUE", "FALSE")
                or fields[0].startswith(".") != (fields[1] == "TRUE") or not fields[2].startswith("/")
                or (fields[4] and not re.fullmatch(r"[0-9]+(?:\.[0-9]+)?", fields[4]))):
            raise ValueError("Malformed cookie entries. Export a fresh Netscape cookies.txt file from YouTube.")
        expires = float(fields[4] or 0)
        if not math.isfinite(expires):
            raise ValueError("Invalid cookie expiry values. Export a fresh cookies.txt file.")
        domain = fields[0].lstrip(".").lower()
        if domain != "youtube.com" and not domain.endswith(".youtube.com"):
            continue
        youtube += 1
        if (expires == 0 or expires > time.time()) and fields[5] and fields[6]:
            usable += 1
    if not usable:
        raise ValueError("No usable YouTube cookies remain. Export fresh cookies from YouTube." if youtube
                         else "No YouTube cookies found. Export cookies while on youtube.com or music.youtube.com.")
    return str(cookie_path)


def emit(kind: str, **values) -> None:
    with _write_lock:
        _protocol.write(json.dumps({"type": kind, **values}, ensure_ascii=False) + "\n")
        _protocol.flush()


def resolve_folder(parent: Path, playlist_id: str, title: str) -> Path:
    """Accept either a managed playlist folder or its parent; never mix IDs."""
    manifest = engine.load_manifest(parent / engine.MANIFEST_NAME)
    if manifest.get("playlist_id") == playlist_id:
        return parent
    if manifest.get("playlist_id"):
        raise ValueError("The selected folder belongs to another playlist. Choose the music parent folder.")
    existing = engine.find_existing_playlist_folder(parent, playlist_id)
    target = existing or parent / engine.sanitize_filename_part(title, "downloads")
    target_manifest = engine.load_manifest(target / engine.MANIFEST_NAME)
    if target_manifest.get("playlist_id") not in (None, playlist_id):
        raise ValueError("A different playlist already uses this folder name. Choose another location.")
    return target


def row(track: engine.Track, folder: Path) -> dict:
    path = folder / track.filename
    duration = track.duration_seconds
    genre = track.genre
    if path.is_file():
        try:
            from mutagen import File
            audio = File(path)
            if audio is not None:
                duration = audio.info.length
                genre = (audio.get("genre") or [genre])[0]
        except Exception:
            pass  # Damaged/missing tags don't hide a locally existing file.
    return dict(videoId=track.video_id, position=track.index, title=track.title,
                artist=engine.artists_to_text(track.artists), album=track.album,
                genre=genre, duration=duration, fileSize=path.stat().st_size if path.is_file() else None,
                status="Downloaded" if path.is_file() else "Missing")


def scan(request: dict) -> dict:
    url = engine.validate_download_url(request["url"])
    parent = Path(request["folder"]).expanduser().resolve()
    if not parent.is_dir():
        raise ValueError("Choose an existing music folder first.")
    single = not engine.is_playlist_url(url)
    if single:
        manifest = engine.load_manifest(parent / engine.MANIFEST_NAME)
        if not manifest.get("playlist_id"):
            raise ValueError("For a single song, choose an existing playlist folder containing playlist_manifest.json.")
        track = engine.fetch_single_track(url)
        playlist_id = str(manifest["playlist_id"])
        title = str(manifest.get("playlist_title") or playlist_id)
        tracks, total, skipped, folder = [track], 1, [], parent
    else:
        playlist_id, title, total, tracks, skipped = engine.fetch_playlist_tracks(url)
        folder = resolve_folder(parent, playlist_id, title)
        manifest = engine.load_manifest(folder / engine.MANIFEST_NAME)
        tracks = engine.prepend_manual_tracks(manifest, tracks)
    known = engine.manifest_by_video_id(manifest)
    for track in tracks:
        entry = known.get(track.video_id, {})
        filename = engine.safe_manifest_filename(entry.get("output_filename"), ".opus")
        if filename:
            track.filename = filename
    return dict(url=url, folder=str(folder), playlistId=playlist_id, title=title,
                single=single, total=total, skipped=skipped,
                tracks=[asdict(track) for track in tracks], rows=[row(track, folder) for track in tracks])


def download(request: dict) -> None:
    snapshot = request["snapshot"]
    url = engine.validate_download_url(snapshot["url"])
    folder = Path(snapshot["folder"]).resolve()
    manifest = engine.load_manifest(folder / engine.MANIFEST_NAME)
    if manifest.get("playlist_id") not in (None, snapshot["playlistId"]):
        raise ValueError("The destination now belongs to a different playlist. Scan again.")
    tracks = [engine.Track(**track) for track in snapshot["tracks"]]
    for track in tracks:
        if engine.safe_manifest_filename(track.filename, ".opus") != track.filename:
            raise ValueError("Invalid audio filename. Scan again.")
    selected = set(request.get("selected", []))
    options = engine.DownloadOptions(cookies_file=validate_cookies(request.get("cookies")))
    missing_selected = any(t.video_id in selected and not (folder / t.filename).is_file() for t in tracks)
    if missing_selected:
        engine.check_ffmpeg()
        emit("log", message="Preparing download services…")
        engine.ensure_po_provider_running()
    def progress(track, status):
        emit("track", **{**row(track, folder), "status": status})
    if snapshot["single"]:
        if tracks[0].video_id not in selected:
            emit("done", result=0, message="Song not selected; playlist unchanged.")
            return
        code = engine.sync_single_track(url, folder, options)
        progress(tracks[0], "Downloaded" if (folder / tracks[0].filename).is_file() else "Failed")
    else:
        if engine.parse_playlist_id(url) != snapshot["playlistId"]:
            raise ValueError("Playlist changed. Scan again.")
        code = engine.sync_playlist(url, folder, options,
            selected_video_ids=selected,
            prepared_playlist=(snapshot["playlistId"], snapshot["title"], snapshot["total"], tracks, snapshot["skipped"]),
            on_track=progress)
    emit("done", result=code, message="Sync complete." if code == 0 else "Sync finished with failed songs. Select Retry failed to try again.")


def main() -> int:
    try:
        request = json.loads(sys.stdin.readline())
        engine.configure_bundled_tools()
        # Libraries and the legacy engine write diagnostics to stderr, never JSON stdout.
        with contextlib.redirect_stdout(sys.stderr):
            if request["action"] == "scan":
                emit("scan", snapshot=scan(request))
            elif request["action"] == "download":
                download(request)
            else:
                raise ValueError("Unknown desktop action.")
        return 0
    except Exception as exc:
        emit("error", message=str(exc))
        return 1


if __name__ == "__main__":
    sys.stdin.reconfigure(encoding="utf-8")
    sys.stdout.reconfigure(encoding="utf-8")
    sys.stderr.reconfigure(encoding="utf-8")
    raise SystemExit(main())
