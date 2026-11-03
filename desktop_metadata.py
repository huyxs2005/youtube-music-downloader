"""Best-effort display metadata; never download audio or retain signed media URLs."""
from concurrent.futures import ThreadPoolExecutor, as_completed
import hashlib
import json
import math
import os
from pathlib import Path
import time

import ytmusic_downloader as engine


def positive_number(value):
    return value if isinstance(value, (int, float)) and math.isfinite(value) and value > 0 else None


def estimated_size(duration):
    seconds = positive_number(duration)
    return round(seconds * 160_000 / 8) if seconds else None


def fetch(track, cookies):
    video_id = track["video_id"]
    cache_root = Path(os.getenv("LOCALAPPDATA") or Path.home() / ".cache") / "YouTubeMusicDownloader" / "metadata"
    cache_path = cache_root / (hashlib.sha256(video_id.encode()).hexdigest() + ".json")
    try:
        cached = json.loads(cache_path.read_text(encoding="utf-8"))
        if cached.get("expires", 0) > time.time():
            return cached["row"]
    except (OSError, ValueError, KeyError):
        pass
    duration = positive_number(track.get("duration_seconds"))
    result = dict(videoId=video_id, genre=track.get("genre"), duration=duration,
                  fileSize=estimated_size(duration), sizeEstimated=True, metadataChecked=True)
    success = False
    try:
        options = dict(quiet=True, no_warnings=True, skip_download=True, noplaylist=True,
                       logger=engine.QuietYtdlpLogger(), socket_timeout=12, retries=0,
                       extractor_retries=0, remote_components=["ejs:github"],
                       js_runtimes=engine.javascript_runtimes(),
                       format="bestaudio[acodec=opus]/bestaudio/best")
        # Let the downloader's normal client selection find an available audio stream.
        with engine.YoutubeDL(options) as ydl:
            if cookies:
                # Load credentials into memory without making concurrent writers of the user's export.
                ydl.cookiejar.load(cookies)
            info = ydl.extract_info(f"https://music.youtube.com/watch?v={video_id}", download=False)
        duration = positive_number(info.get("duration")) or duration
        formats = [f for f in info.get("formats", []) if f.get("vcodec") == "none" and f.get("acodec") not in (None, "none")]
        opus = [f for f in formats if "opus" in str(f.get("acodec"))]
        selected = max(opus or formats, key=lambda f: positive_number(f.get("abr")) or positive_number(f.get("tbr")) or 0, default=info)
        size = positive_number(selected.get("filesize")) or positive_number(selected.get("filesize_approx"))
        bitrate = positive_number(selected.get("abr")) or positive_number(selected.get("tbr"))
        if not size and duration and bitrate:
            size = duration * bitrate * 1000 / 8
        result.update(duration=duration,
                      fileSize=round(size) if size else estimated_size(duration))
        success = True
    except Exception:
        # Keep the duration-based estimate when YouTube blocks stream inspection.
        pass
    result["metadataFailed"] = not success
    try:
        cache_root.mkdir(parents=True, exist_ok=True)
        temporary = cache_path.with_suffix(f".{os.getpid()}.tmp")
        temporary.write_text(json.dumps(dict(expires=time.time() + (604800 if success else 900), row=result)), encoding="utf-8")
        temporary.replace(cache_path)
    except OSError:
        pass
    return result


def stream(request, emit):
    engine.initialize_yt_dlp_plugins()
    unique = {track["video_id"]: track for track in request["snapshot"]["tracks"]}
    with ThreadPoolExecutor(max_workers=3) as pool:
        pending = [pool.submit(fetch, track, request.get("cookies")) for track in unique.values()]
        for future in as_completed(pending):
            emit("metadata", **future.result())
