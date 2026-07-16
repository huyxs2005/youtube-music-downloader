#!/usr/bin/env python3
"""Download a YouTube Music playlist as stable OPUS files with an M3U8."""

from __future__ import annotations

import argparse
import base64
import json
import re
import shutil
import struct
import sys
import subprocess
import time
import urllib.request
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass
from pathlib import Path
from threading import Lock
from typing import Any
from urllib.parse import parse_qs, urlparse

from ytmusicapi import YTMusic
from yt_dlp import YoutubeDL
from yt_dlp.extractor import gen_extractor_classes
from yt_dlp.utils import DownloadError


MANIFEST_NAME = "playlist_manifest.json"
DEFAULT_COOKIES_NAME = "cookies.txt"
FAILED_DOWNLOADS_NAME = "failed_downloads.txt"
DOWNLOAD_ERRORS_NAME = "download_errors.log"
USER_CANCELLED_EXIT_CODE = 20
YT_DLP_SLEEP_REQUESTS_SECONDS = 5
YT_DLP_SLEEP_INTERVAL_SECONDS = 10
YT_DLP_MAX_SLEEP_INTERVAL_SECONDS = 30
YT_DLP_RETRIES = 3
YT_DLP_FRAGMENT_RETRIES = 3
EMBEDDED_THUMBNAIL_SIZE = 1008
INVALID_WINDOWS_CHARS = r'<>:"/\|?*'
RESERVED_WINDOWS_NAMES = {
    "CON",
    "PRN",
    "AUX",
    "NUL",
    *(f"COM{i}" for i in range(1, 10)),
    *(f"LPT{i}" for i in range(1, 10)),
}
_YT_DLP_PLUGIN_LOCK = Lock()
_YT_DLP_PLUGINS_INITIALIZED = False


@dataclass
class Track:
    index: int
    video_id: str
    set_video_id: str | None
    title: str
    artists: list[str]
    album: str | None
    thumbnail_url: str | None
    filename: str


@dataclass
class DownloadOptions:
    cookies_file: str | None = None


class QuietYtdlpLogger:
    """Suppress yt-dlp internals; this script reports failed tracks itself."""

    @staticmethod
    def debug(_message: str) -> None:
        pass

    @staticmethod
    def info(_message: str) -> None:
        pass

    @staticmethod
    def warning(_message: str) -> None:
        pass

    @staticmethod
    def error(_message: str) -> None:
        pass


class DuplicateProviderStderrFilter:
    """Hide only yt-dlp's harmless duplicate BgUtils provider traceback."""

    def __init__(self, stream: Any) -> None:
        self.stream = stream

    @staticmethod
    def is_duplicate_provider_message(message: str) -> bool:
        return (
            "Error while importing module "
            "'yt_dlp_plugins.extractor.getpot_bgutil_" in message
            and "AssertionError: PoTokenProvider" in message
            and "already registered" in message
        )

    def write(self, message: str) -> int:
        if self.is_duplicate_provider_message(message):
            return len(message)
        return self.stream.write(message)

    def flush(self) -> None:
        self.stream.flush()

    def isatty(self) -> bool:
        return bool(getattr(self.stream, "isatty", lambda: False)())

    def fileno(self) -> int:
        return self.stream.fileno()

    @property
    def encoding(self) -> str | None:
        return getattr(self.stream, "encoding", None)

    @property
    def errors(self) -> str | None:
        return getattr(self.stream, "errors", None)


def install_duplicate_provider_stderr_filter() -> None:
    """Install the targeted stderr filter once for the CMD process."""
    if not isinstance(sys.stderr, DuplicateProviderStderrFilter):
        sys.stderr = DuplicateProviderStderrFilter(sys.stderr)


def initialize_yt_dlp_plugins() -> None:
    """Load yt-dlp plugins once, before concurrent workers can race to do it."""
    global _YT_DLP_PLUGINS_INITIALIZED
    if _YT_DLP_PLUGINS_INITIALIZED:
        return
    with _YT_DLP_PLUGIN_LOCK:
        if _YT_DLP_PLUGINS_INITIALIZED:
            return
        gen_extractor_classes()
        _YT_DLP_PLUGINS_INITIALIZED = True


def parse_playlist_id(playlist_url: str) -> str:
    """Extract the playlist id from a YouTube Music playlist URL."""
    parsed = urlparse(playlist_url)
    playlist_id = parse_qs(parsed.query).get("list", [None])[0]
    if not playlist_id:
        raise ValueError("Could not find a playlist id in the URL. Expected ?list=PLAYLIST_ID.")
    return playlist_id


def parse_video_id(song_url: str) -> str:
    """Extract a videoId from a YouTube or YouTube Music song URL."""
    parsed = urlparse(song_url)
    if parsed.netloc.lower() == "youtu.be":
        video_id = parsed.path.strip("/").split("/", 1)[0]
    else:
        video_id = parse_qs(parsed.query).get("v", [None])[0]
    if not video_id:
        raise ValueError("Could not find a video id in the URL. Expected ?v=VIDEO_ID.")
    return video_id


def is_playlist_url(youtube_url: str) -> bool:
    parsed = urlparse(youtube_url)
    query = parse_qs(parsed.query)
    if parsed.netloc.lower() == "youtu.be" or query.get("v", [None])[0]:
        return False
    return bool(query.get("list", [None])[0])


def validate_download_url(youtube_url: str) -> str:
    youtube_url = youtube_url.strip().strip('"')
    if not youtube_url:
        raise ValueError("A playlist or song URL is required.")

    parsed = urlparse(youtube_url)
    if parsed.scheme not in {"http", "https"}:
        raise ValueError("The URL must start with http:// or https://.")

    host = parsed.netloc.lower()
    valid_hosts = {
        "music.youtube.com",
        "www.youtube.com",
        "youtube.com",
        "m.youtube.com",
        "youtu.be",
    }
    if host not in valid_hosts:
        raise ValueError("Expected a YouTube or YouTube Music playlist or song URL.")

    if is_playlist_url(youtube_url):
        parse_playlist_id(youtube_url)
    else:
        parse_video_id(youtube_url)
    return youtube_url


def validate_playlist_url(playlist_url: str) -> str:
    """Backward-compatible strict validator for playlist-only callers."""
    playlist_url = validate_download_url(playlist_url)
    parse_playlist_id(playlist_url)
    return playlist_url


def sanitize_filename_part(value: str, fallback: str) -> str:
    """Make one filename segment safe on Windows while keeping it readable."""
    value = value.strip() or fallback
    for char in INVALID_WINDOWS_CHARS:
        value = value.replace(char, "_")
    value = re.sub(r"\s+", " ", value)
    value = value.rstrip(" .")
    if not value:
        value = fallback
    if value.upper() in RESERVED_WINDOWS_NAMES:
        value = f"{value}_"
    return value[:120]


def load_manifest(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {"playlist_id": None, "tracks": []}
    with path.open("r", encoding="utf-8-sig") as file:
        data = json.load(file)
    if not isinstance(data, dict):
        raise ValueError(f"{path} is not a valid manifest object.")
    data.setdefault("tracks", [])
    return data


def save_manifest(
    path: Path,
    playlist_id: str,
    tracks_by_video_id: dict[str, dict[str, Any]],
    playlist_title: str | None = None,
    m3u8_filename: str | None = None,
) -> None:
    ordered_tracks = sorted(
        tracks_by_video_id.values(),
        key=lambda item: (item.get("playlist_index", sys.maxsize), str(item.get("videoId", ""))),
    )
    data = {
        "playlist_id": playlist_id,
        "tracks": ordered_tracks,
    }
    if playlist_title is not None:
        data["playlist_title"] = playlist_title
    if m3u8_filename is not None:
        data["m3u8_filename"] = m3u8_filename
    temp_path = path.with_suffix(".json.tmp")
    with temp_path.open("w", encoding="utf-8") as file:
        json.dump(data, file, ensure_ascii=False, indent=2)
        file.write("\n")
    temp_path.replace(path)


def artists_to_text(artists: list[str]) -> str:
    return ", ".join(artist for artist in artists if artist) or "Unknown Artist"


def best_thumbnail_url(thumbnails: list[dict[str, Any]]) -> str | None:
    valid_thumbnails = [
        item
        for item in thumbnails
        if isinstance(item, dict) and item.get("url")
    ]
    if not valid_thumbnails:
        return None
    best = max(
        valid_thumbnails,
        key=lambda item: int(item.get("width") or 0) * int(item.get("height") or 0),
    )
    return str(best["url"])


def build_filename(artists: list[str], title: str, video_id: str) -> str:
    artist_text = sanitize_filename_part(artists_to_text(artists), "Unknown Artist")
    title_text = sanitize_filename_part(title, "Untitled")
    video_id_text = sanitize_filename_part(video_id, "video")
    return f"{artist_text} - {title_text} [{video_id_text}].opus"


def build_m3u8_filename(playlist_title: str) -> str:
    safe_title = sanitize_filename_part(playlist_title, "YouTube Music Playlist")
    return f"{safe_title}.m3u8"


def safe_manifest_filename(value: Any, suffix: str) -> str | None:
    """Return a manifest filename only when it cannot escape the output folder."""
    if not isinstance(value, str) or not value or "/" in value or "\\" in value:
        return None
    if value in {".", ".."} or not value.lower().endswith(suffix.lower()):
        return None
    return value


def track_from_ytmusic(raw_track: dict[str, Any], index: int) -> Track | None:
    """Normalize the small subset of ytmusicapi playlist data this script needs."""
    video_id = raw_track.get("videoId")
    if not video_id:
        return None
    artists = [
        item.get("name", "").strip()
        for item in raw_track.get("artists", [])
        if isinstance(item, dict) and item.get("name")
    ]
    title = str(raw_track.get("title") or "Untitled").strip()
    album = raw_track.get("album")
    album_name = str(album.get("name")).strip() if isinstance(album, dict) and album.get("name") else None
    return Track(
        index=index,
        video_id=video_id,
        set_video_id=raw_track.get("setVideoId"),
        title=title,
        artists=artists,
        album=album_name,
        thumbnail_url=best_thumbnail_url(
            raw_track.get("thumbnails") or raw_track.get("thumbnail") or []
        ),
        filename=build_filename(artists, title, video_id),
    )


def fetch_playlist_tracks(playlist_url: str) -> tuple[str, str, int, list[Track], list[int]]:
    """Fetch ordered tracks with ytmusicapi, not yt-dlp playlist parsing.

    Number only valid/downloadable tracks, so skipped playlist items do not
    create gaps like 023, 025.
    """
    playlist_id = parse_playlist_id(playlist_url)
    playlist = YTMusic().get_playlist(playlist_id, limit=None)

    playlist_title = str(playlist.get("title") or playlist_id).strip()
    playlist_items = playlist.get("tracks", [])

    tracks: list[Track] = []
    skipped_items: list[int] = []

    track_number = 1

    for original_index, raw_track in enumerate(playlist_items, start=1):
        track = track_from_ytmusic(raw_track, track_number)

        if track:
            tracks.append(track)
            track_number += 1
        else:
            skipped_items.append(original_index)

    return playlist_id, playlist_title, len(playlist_items), tracks, skipped_items


def fetch_single_track(song_url: str) -> Track:
    """Fetch metadata for one YouTube Music song URL."""
    video_id = parse_video_id(song_url)
    watch_playlist = YTMusic().get_watch_playlist(videoId=video_id, limit=1)
    raw_tracks = watch_playlist.get("tracks", [])
    raw_track = next(
        (
            item
            for item in raw_tracks
            if isinstance(item, dict) and item.get("videoId") == video_id
        ),
        None,
    )
    if raw_track is None:
        raise ValueError(f"YouTube Music returned no metadata for videoId {video_id}.")
    track = track_from_ytmusic(raw_track, 1)
    if track is None:
        raise ValueError(f"YouTube Music returned an unavailable track for videoId {video_id}.")
    return track


def manifest_by_video_id(manifest: dict[str, Any]) -> dict[str, dict[str, Any]]:
    result: dict[str, dict[str, Any]] = {}
    for item in manifest.get("tracks", []):
        video_id = item.get("videoId")
        if video_id:
            result[video_id] = dict(item)
    return result


def unique_temp_stem(output_dir: Path, video_id: str) -> Path:
    safe_video_id = sanitize_filename_part(video_id, "video")
    return output_dir / f".download-{safe_video_id}"


def download_track(track: Track, output_dir: Path, options: DownloadOptions) -> Path:
    """Download one videoId only, writing to a temp name before the final move."""
    temp_stem = unique_temp_stem(output_dir, track.video_id)
    for old_temp in output_dir.glob(f"{temp_stem.name}*"):
        if old_temp.is_file():
            old_temp.unlink()

    try:
        return run_yt_dlp_download(
            track,
            output_dir,
            options,
            temp_stem,
            "bestaudio[ext=webm]/bestaudio/best",
        )
    except DownloadError as exc:
        if "Requested format is not available" not in str(exc):
            raise
        print(f"Retrying with fallback format: {track.index:03d} - {track.title}")
        for old_temp in output_dir.glob(f"{temp_stem.name}*"):
            if old_temp.is_file():
                old_temp.unlink()
        return run_yt_dlp_download(track, output_dir, options, temp_stem, "bestaudio/best")


def run_yt_dlp_download(
    track: Track,
    output_dir: Path,
    options: DownloadOptions,
    temp_stem: Path,
    format_selector: str,
) -> Path:
    initialize_yt_dlp_plugins()
    ydl_opts = {
        "format": format_selector,
        "outtmpl": str(temp_stem) + ".%(ext)s",
        "noplaylist": True,
        "quiet": True,
        "no_warnings": True,
        "noprogress": True,
        "logger": QuietYtdlpLogger(),
        "sleep_interval_requests": YT_DLP_SLEEP_REQUESTS_SECONDS,
        "sleep_interval": YT_DLP_SLEEP_INTERVAL_SECONDS,
        "max_sleep_interval": YT_DLP_MAX_SLEEP_INTERVAL_SECONDS,
        "retries": YT_DLP_RETRIES,
        "fragment_retries": YT_DLP_FRAGMENT_RETRIES,
        "remote_components": ["ejs:github"],
        "extractor_args": {
            "youtube": {
                "player_client": ["web_music", "web_safari"],
            }
        },
        "postprocessors": [
            {
                "key": "FFmpegExtractAudio",
                "preferredcodec": "opus",
                "preferredquality": "0",
            }
        ],
    }
    if options.cookies_file:
        ydl_opts["cookiefile"] = options.cookies_file

    url = f"https://music.youtube.com/watch?v={track.video_id}"
    with YoutubeDL(ydl_opts) as ydl:
        ydl.download([url])

    opus_path = temp_stem.with_suffix(".opus")
    if opus_path.exists():
        return opus_path

    candidates = sorted(
        [path for path in output_dir.glob(f"{temp_stem.name}*") if path.is_file()],
        key=lambda path: path.stat().st_mtime,
        reverse=True,
    )
    if not candidates:
        raise FileNotFoundError(f"yt-dlp completed but no output file was found for {track.video_id}.")
    return candidates[0]


def download_track_job(
    track: Track,
    output_dir: Path,
    options: DownloadOptions,
) -> tuple[Track, Path | None, BaseException | None]:
    """Thread-pool wrapper so one failed song does not cancel other downloads."""
    try:
        return track, download_track(track, output_dir, options), None
    except BaseException as exc:
        return track, None, exc


def automatic_worker_count(track_count: int) -> int:
    if track_count <= 10:
        return 4
    if track_count >= 100:
        return 2
    return 3


def ensure_final_path(temp_path: Path, final_path: Path) -> None:
    if final_path.exists():
        backup_path = final_path.with_name(f"{final_path.stem}.replaced{final_path.suffix}")
        counter = 1
        while backup_path.exists():
            backup_path = final_path.with_name(f"{final_path.stem}.replaced-{counter}{final_path.suffix}")
            counter += 1
        final_path.replace(backup_path)
    temp_path.replace(final_path)


def flac_picture_block(image_bytes: bytes, mime_type: str, width: int = 0, height: int = 0) -> str:
    """Build a base64 FLAC picture block for Ogg Opus cover art metadata."""
    mime_bytes = mime_type.encode("ascii", errors="ignore") or b"image/jpeg"
    description = b""
    block = b"".join(
        [
            struct.pack(">I", 3),  # Front cover
            struct.pack(">I", len(mime_bytes)),
            mime_bytes,
            struct.pack(">I", len(description)),
            description,
            struct.pack(">I", width),
            struct.pack(">I", height),
            struct.pack(">I", 0),  # Color depth unknown
            struct.pack(">I", 0),  # Indexed colors
            struct.pack(">I", len(image_bytes)),
            image_bytes,
        ]
    )
    return base64.b64encode(block).decode("ascii")


def thumbnail_url_candidates(thumbnail_url: str | None) -> list[str]:
    if not thumbnail_url:
        return []

    candidates = []
    for size in [EMBEDDED_THUMBNAIL_SIZE, 800, 544]:
        larger_url = re.sub(r"=w\d+-h\d+([^?&]*)", rf"=w{size}-h{size}\1", thumbnail_url)
        larger_url = re.sub(r"=s\d+([^?&]*)", rf"=s{size}\1", larger_url)
        candidates.append(larger_url)
    candidates.append(thumbnail_url)

    unique_candidates = []
    for candidate in candidates:
        if candidate not in unique_candidates:
            unique_candidates.append(candidate)
    return unique_candidates


def image_size(image_bytes: bytes) -> tuple[int, int]:
    try:
        from io import BytesIO
        from PIL import Image

        with Image.open(BytesIO(image_bytes)) as image:
            return image.size
    except Exception:
        return 0, 0


def download_thumbnail(thumbnail_url: str | None) -> tuple[bytes, str, int, int] | None:
    if not thumbnail_url:
        return None

    last_error: Exception | None = None
    for candidate_url in thumbnail_url_candidates(thumbnail_url):
        request = urllib.request.Request(
            candidate_url,
            headers={"User-Agent": "Mozilla/5.0"},
        )
        try:
            with urllib.request.urlopen(request, timeout=20) as response:
                mime_type = response.headers.get_content_type() or "image/jpeg"
                if mime_type not in {"image/jpeg", "image/png", "image/webp"}:
                    mime_type = "image/jpeg"
                image_bytes = response.read()
                width, height = image_size(image_bytes)
                return image_bytes, mime_type, width, height
        except Exception as exc:
            last_error = exc
            continue

    if last_error:
        print(f"Warning: could not download thumbnail for metadata ({last_error})")
    return None


def apply_track_metadata(path: Path, track: Track) -> bool:
    """Write Android-friendly OPUS title, artist, album, track, and cover-art tags."""
    if not path.exists():
        return False

    try:
        from mutagen.oggopus import OggOpus
    except ImportError:
        print("Warning: mutagen is not installed, so OPUS metadata could not be written.")
        print("  Install it with: python -m pip install -U mutagen")
        return False

    try:
        audio = OggOpus(path)
        artist_text = artists_to_text(track.artists)
        audio["title"] = [track.title]
        audio["artist"] = [artist_text]
        audio["albumartist"] = [artist_text]
        audio["tracknumber"] = [str(track.index)]
        if track.album:
            audio["album"] = [track.album]
        else:
            audio.pop("album", None)

        thumbnail = download_thumbnail(track.thumbnail_url)
        if thumbnail:
            image_bytes, mime_type, width, height = thumbnail
            audio["metadata_block_picture"] = [flac_picture_block(image_bytes, mime_type, width, height)]

        audio.save()
        return True
    except Exception as exc:
        print(f"Warning: could not write metadata for {path.name}")
        print(f"  {exc}")
        return False


def failed_track_line(track: Track) -> str:
    artist_text = artists_to_text(track.artists)
    url = f"https://music.youtube.com/watch?v={track.video_id}"
    return f"{track.index:03d}. {artist_text} - {track.title} ({url})"


def write_download_errors(output_dir: Path, failed_tracks: list[Track]) -> Path:
    """Write only the current failed songs, replacing any stale error details."""
    path = output_dir / DOWNLOAD_ERRORS_NAME
    if not failed_tracks:
        if path.exists():
            path.unlink()
        return path

    temp_path = path.with_name(f"{path.name}.tmp")
    with temp_path.open("w", encoding="utf-8", newline="\n") as file:
        for track in failed_tracks:
            file.write(failed_track_line(track))
            file.write("\n")
    temp_path.replace(path)
    return path


def manifest_entry(track: Track, manually_added: bool = False) -> dict[str, Any]:
    entry = {
        "videoId": track.video_id,
        "setVideoId": track.set_video_id,
        "title": track.title,
        "artists": track.artists,
        "album": track.album,
        "thumbnail_url": track.thumbnail_url,
        "playlist_index": track.index,
        "output_filename": track.filename,
    }
    if manually_added:
        entry["manually_added"] = True
    return entry


def track_from_manifest_entry(entry: dict[str, Any]) -> Track | None:
    video_id = entry.get("videoId")
    filename = safe_manifest_filename(entry.get("output_filename"), ".opus")
    if not video_id or not filename:
        return None
    artists = entry.get("artists")
    if not isinstance(artists, list):
        artists = []
    return Track(
        index=int(entry.get("playlist_index") or 0),
        video_id=str(video_id),
        set_video_id=entry.get("setVideoId"),
        title=str(entry.get("title") or "Untitled"),
        artists=[str(artist) for artist in artists if artist],
        album=str(entry["album"]) if entry.get("album") else None,
        thumbnail_url=(
            str(entry["thumbnail_url"]) if entry.get("thumbnail_url") else None
        ),
        filename=filename,
    )


def prepend_manual_tracks(
    manifest: dict[str, Any],
    playlist_tracks: list[Track],
) -> list[Track]:
    """Keep locally added songs ahead of the current remote playlist order."""
    manual_entries = sorted(
        (
            entry
            for entry in manifest.get("tracks", [])
            if isinstance(entry, dict) and entry.get("manually_added")
        ),
        key=lambda entry: int(entry.get("playlist_index") or sys.maxsize),
    )
    manual_tracks = [
        track
        for entry in manual_entries
        if (track := track_from_manifest_entry(entry)) is not None
    ]
    manual_video_ids = {track.video_id for track in manual_tracks}
    combined_tracks = manual_tracks + [
        track for track in playlist_tracks if track.video_id not in manual_video_ids
    ]
    for index, track in enumerate(combined_tracks, start=1):
        track.index = index
    return combined_tracks


def write_poweramp_m3u8(
    output_dir: Path,
    playlist_title: str,
    tracks: list[Track],
    tracks_by_video_id: dict[str, dict[str, Any]],
    previous_filename: Any = None,
) -> tuple[Path, int]:
    """Atomically write the current, existing-file-only Poweramp playlist."""
    m3u8_filename = build_m3u8_filename(playlist_title)
    m3u8_path = output_dir / m3u8_filename
    lines = ["#EXTM3U"]
    included_count = 0

    for track in tracks:
        entry = tracks_by_video_id.get(track.video_id, {})
        output_filename = safe_manifest_filename(entry.get("output_filename"), ".opus")
        if not output_filename or not (output_dir / output_filename).is_file():
            continue

        artist_title = f"{artists_to_text(track.artists)} - {track.title}"
        artist_title = re.sub(r"[\r\n]+", " ", artist_title).strip()
        lines.append(f"#EXTINF:-1,{artist_title}")
        lines.append(output_filename)
        included_count += 1

    temp_path = m3u8_path.with_name(f"{m3u8_path.name}.tmp")
    with temp_path.open("w", encoding="utf-8", newline="\n") as file:
        file.write("\n".join(lines))
        file.write("\n")
    temp_path.replace(m3u8_path)

    old_filename = safe_manifest_filename(previous_filename, ".m3u8")
    if old_filename and old_filename != m3u8_filename:
        old_path = output_dir / old_filename
        if old_path.is_file():
            old_path.unlink()

    return m3u8_path, included_count


def current_manifest_playlist_tracks(
    output_dir: Path,
    manifest: dict[str, Any],
) -> list[Track]:
    """Rebuild the active playlist order from its M3U8 and manifest."""
    entries_by_filename = {
        filename: entry
        for entry in manifest.get("tracks", [])
        if isinstance(entry, dict)
        and (filename := safe_manifest_filename(entry.get("output_filename"), ".opus"))
    }
    m3u8_filename = safe_manifest_filename(manifest.get("m3u8_filename"), ".m3u8")
    ordered_entries: list[dict[str, Any]] = []
    if m3u8_filename:
        m3u8_path = output_dir / m3u8_filename
        if m3u8_path.is_file():
            for line in m3u8_path.read_text(encoding="utf-8-sig").splitlines():
                filename = line.strip()
                if filename and not filename.startswith("#"):
                    entry = entries_by_filename.get(filename)
                    if entry:
                        ordered_entries.append(entry)

    if not ordered_entries:
        ordered_entries = sorted(
            (
                entry
                for entry in manifest.get("tracks", [])
                if isinstance(entry, dict)
            ),
            key=lambda entry: int(entry.get("playlist_index") or sys.maxsize),
        )

    return [
        track
        for entry in ordered_entries
        if (track := track_from_manifest_entry(entry)) is not None
    ]


def sync_single_track(
    song_url: str,
    output_dir: Path | None,
    options: DownloadOptions,
) -> int:
    """Download one song into an existing playlist and insert it first."""
    if output_dir is None:
        print("A single song requires an existing playlist folder.")
        return 1
    if not output_dir.is_dir():
        print(f"Existing playlist folder not found: {output_dir}")
        return 1

    manifest_path = output_dir / MANIFEST_NAME
    if not manifest_path.is_file():
        print(f"No {MANIFEST_NAME} was found in: {output_dir}")
        print("Choose a folder previously created by this downloader.")
        return 1

    manifest = load_manifest(manifest_path)
    playlist_id = str(manifest.get("playlist_id") or "local-playlist")
    playlist_title = str(manifest.get("playlist_title") or output_dir.name)
    previous_m3u8_filename = manifest.get("m3u8_filename")
    known_tracks = manifest_by_video_id(manifest)
    current_tracks = current_manifest_playlist_tracks(output_dir, manifest)
    track = fetch_single_track(song_url)
    old_entry = known_tracks.get(track.video_id)
    old_filename = safe_manifest_filename(
        old_entry.get("output_filename") if old_entry else None,
        ".opus",
    )
    if old_filename:
        track.filename = old_filename

    ordered_tracks = [track] + [
        existing_track
        for existing_track in current_tracks
        if existing_track.video_id != track.video_id
    ]
    for index, ordered_track in enumerate(ordered_tracks, start=1):
        ordered_track.index = index
        existing_entry = known_tracks.get(ordered_track.video_id, {})
        manually_added = (
            ordered_track.video_id == track.video_id
            or bool(existing_entry.get("manually_added"))
        )
        known_tracks[ordered_track.video_id] = manifest_entry(
            ordered_track,
            manually_added,
        )

    save_manifest(
        manifest_path,
        playlist_id,
        known_tracks,
        playlist_title,
        previous_m3u8_filename,
    )

    final_path = output_dir / track.filename
    download_failed = False
    if final_path.is_file():
        print(f"Already downloaded; moving to playlist position 1: {track.filename}")
    else:
        print(f"Downloading single song: {artists_to_text(track.artists)} - {track.title}")
        try:
            temp_output = download_track(track, output_dir, options)
            ensure_final_path(temp_output, final_path)
            print(f"Downloaded: {track.filename}")
            if apply_track_metadata(final_path, track):
                print(f"Updated metadata: {track.filename}")
        except Exception:
            download_failed = True
            print(f"Failed: {track.title} ({track.video_id})")

    write_download_errors(output_dir, [track] if download_failed else [])

    failed_tracks = [
        ordered_track
        for ordered_track in ordered_tracks
        if not (output_dir / ordered_track.filename).is_file()
    ]
    failed_downloads_path = output_dir / FAILED_DOWNLOADS_NAME
    if failed_tracks:
        with failed_downloads_path.open("w", encoding="utf-8") as file:
            file.write(f"Failed downloads for {playlist_title}\n")
            file.write(f"Latest song: {song_url}\n")
            file.write(f"Count: {len(failed_tracks)}\n\n")
            for failed_track in failed_tracks:
                file.write(failed_track_line(failed_track))
                file.write("\n")
    elif failed_downloads_path.exists():
        failed_downloads_path.unlink()

    m3u8_path, included_count = write_poweramp_m3u8(
        output_dir,
        playlist_title,
        ordered_tracks,
        known_tracks,
        previous_m3u8_filename,
    )
    save_manifest(
        manifest_path,
        playlist_id,
        known_tracks,
        playlist_title,
        m3u8_path.name,
    )

    print("")
    print("Single-song update complete")
    print(f"  Playlist position: 1")
    print(f"  Audio: {final_path}")
    print(f"  Manifest: {manifest_path}")
    print(f"  M3U8: {m3u8_path} ({included_count} tracks)")
    if failed_tracks:
        print(f"  Failed list: {failed_downloads_path}")
    return 1 if download_failed else 0


def sync_playlist(
    playlist_url: str,
    output_dir: Path | None,
    options: DownloadOptions,
    stop_after_video_id: str | None = None,
    max_workers: int | None = None,
) -> int:
    playlist_id, playlist_title, total_items, tracks, skipped_items = fetch_playlist_tracks(playlist_url)

    if output_dir is None:
        safe_playlist_title = sanitize_filename_part(playlist_title, "downloads")
        output_dir = Path(__file__).resolve().parent / safe_playlist_title

    output_dir.mkdir(parents=True, exist_ok=True)
    manifest_path = output_dir / MANIFEST_NAME
    manifest = load_manifest(manifest_path)
    tracks = prepend_manual_tracks(manifest, tracks)
    manual_track_count = sum(
        1 for item in manifest.get("tracks", []) if item.get("manually_added")
    )

    print(f"Playlist: {playlist_title}")
    print(f"Total playlist items found: {total_items}")
    print(f"Total tracks found: {len(tracks)}")
    if manual_track_count:
        print(f"Manually added tracks kept at top: {manual_track_count}")
    selected_max_workers = max_workers if max_workers is not None else automatic_worker_count(len(tracks))
    print(f"Worker mode: {'manual' if max_workers is not None else 'auto'} ({selected_max_workers} workers max)")
    for item_index in skipped_items:
        print(f"Skipping playlist item {item_index:03d}: no videoId found")

    known_tracks = manifest_by_video_id(manifest)
    previous_m3u8_filename = manifest.get("m3u8_filename")
    success_count = 0
    skipped_count = 0
    downloaded_count = 0
    metadata_count = 0
    failed_count = 0
    failed_tracks: list[Track] = []
    pending_downloads: list[Track] = []

    for track in tracks:
        old_entry = known_tracks.get(track.video_id)
        old_filename = safe_manifest_filename(
            old_entry.get("output_filename") if old_entry else None,
            ".opus",
        )
        if old_filename:
            # The manifest owns this name permanently. Playlist reordering and
            # metadata changes must never rename an existing audio file.
            track.filename = old_filename

        final_path = output_dir / track.filename
        manually_added = bool(old_entry and old_entry.get("manually_added"))
        known_tracks[track.video_id] = manifest_entry(track, manually_added)
        save_manifest(
            manifest_path,
            playlist_id,
            known_tracks,
            playlist_title,
            previous_m3u8_filename,
        )

        try:
            if final_path.is_file():
                print(f"Skipping: {track.filename}")
                skipped_count += 1
            else:
                print(f"Queueing download: {track.index:03d} - {artists_to_text(track.artists)} - {track.title}")
                pending_downloads.append(track)

            if track not in pending_downloads:
                save_manifest(
                    manifest_path,
                    playlist_id,
                    known_tracks,
                    playlist_title,
                    previous_m3u8_filename,
                )
                success_count += 1
        except Exception:  # Keep the playlist moving if one song fails.
            failed_count += 1
            failed_tracks.append(track)
            print(f"Failed: {track.index:03d} - {track.title} ({track.video_id})")

        if stop_after_video_id and track.video_id == stop_after_video_id:
            print(f"Stopping after requested test videoId: {stop_after_video_id}")
            break

    if pending_downloads:
        worker_count = max(1, min(selected_max_workers, len(pending_downloads)))
        print("")
        print(f"Downloading {len(pending_downloads)} queued tracks with {worker_count} workers...")
        with ThreadPoolExecutor(max_workers=worker_count) as executor:
            future_to_track = {
                executor.submit(download_track_job, track, output_dir, options): track
                for track in pending_downloads
            }
            for future in as_completed(future_to_track):
                track, temp_output, exc = future.result()
                final_path = output_dir / track.filename
                if exc:
                    failed_count += 1
                    failed_tracks.append(track)
                    print(f"Failed: {track.index:03d} - {track.title} ({track.video_id})")
                    continue

                print(f"Downloaded: {track.filename}")
                ensure_final_path(temp_output, final_path)
                if apply_track_metadata(final_path, track):
                    print(f"Updated metadata: {track.filename}")
                    metadata_count += 1
                downloaded_entry = known_tracks.get(track.video_id, {})
                known_tracks[track.video_id] = manifest_entry(
                    track,
                    bool(downloaded_entry.get("manually_added")),
                )
                save_manifest(
                    manifest_path,
                    playlist_id,
                    known_tracks,
                    playlist_title,
                    previous_m3u8_filename,
                )
                downloaded_count += 1
                success_count += 1

    write_download_errors(output_dir, failed_tracks)
    failed_downloads_path = output_dir / FAILED_DOWNLOADS_NAME
    if failed_tracks:
        with failed_downloads_path.open("w", encoding="utf-8") as file:
            file.write(f"Failed downloads for {playlist_title}\n")
            file.write(f"Playlist: {playlist_url}\n")
            file.write(f"Count: {len(failed_tracks)}\n")
            file.write("\n")
            for failed_track in failed_tracks:
                file.write(failed_track_line(failed_track))
                file.write("\n")
    elif failed_downloads_path.exists():
        failed_downloads_path.unlink()

    m3u8_path, m3u8_track_count = write_poweramp_m3u8(
        output_dir,
        playlist_title,
        tracks,
        known_tracks,
        previous_m3u8_filename,
    )
    save_manifest(
        manifest_path,
        playlist_id,
        known_tracks,
        playlist_title,
        m3u8_path.name,
    )

    print("")
    print("Final summary")
    print(f"  Successful tracks: {success_count}")
    print(f"  Downloaded: {downloaded_count}")
    print(f"  Skipped: {skipped_count}")
    print(f"  Metadata updated: {metadata_count}")
    print(f"  Failed: {failed_count}")
    print(f"  Output: {output_dir}")
    print(f"  Manifest: {manifest_path}")
    print(f"  M3U8: {m3u8_path} ({m3u8_track_count} tracks)")
    if failed_tracks:
        print(f"  Failed list: {failed_downloads_path}")
    return 0 if failed_count == 0 else 1


def check_ffmpeg() -> None:
    if shutil.which("ffmpeg"):
        return
    print("Warning: ffmpeg was not found on PATH. yt-dlp needs ffmpeg to produce .opus files.")


def prepare_download_options(args: argparse.Namespace) -> DownloadOptions:
    if args.cookies:
        cookies_path = Path(args.cookies)
        print(f"Using cookies file: {cookies_path}")
        return DownloadOptions(cookies_file=str(cookies_path))

    default_cookies = Path(__file__).resolve().with_name(DEFAULT_COOKIES_NAME)
    if default_cookies.exists():
        print(f"Using cookies file: {default_cookies}")
        return DownloadOptions(cookies_file=str(default_cookies))

    print(f"No {DEFAULT_COOKIES_NAME} file found next to the script. Continuing without cookies.")
    return DownloadOptions()


def parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Download a YouTube Music playlist, or add one song to an existing downloaded playlist."
    )
    parser.add_argument(
        "playlist_url",
        nargs="?",
        help="YouTube Music playlist or song URL.",
    )
    parser.add_argument("--output", help="Output folder for OPUS files and playlist_manifest.json.")
    parser.add_argument(
        "--workers",
        type=int,
        default=None,
        help="Override automatic worker count. Auto uses 4 workers for <=10 tracks, 3 for 11-99, and 2 for 100+.",
    )
    parser.add_argument("--cookies", help="Path to a cookies.txt file exported from your browser.")
    parser.add_argument("--stop-after-video-id", help=argparse.SUPPRESS)
    return parser.parse_args(argv)


def choose_output_folder(dialog_title: str) -> str | None:
    """Open a native folder picker and return None when the user cancels."""
    print("Opening folder picker...")
    root = None
    try:
        import tkinter as tk
        from tkinter import filedialog

        root = tk.Tk()
        root.withdraw()
        root.attributes("-topmost", True)
        root.update()
        selected_folder = filedialog.askdirectory(
            parent=root,
            title=dialog_title,
            initialdir=str(Path(__file__).resolve().parent),
            mustexist=True,
        )
    except Exception as exc:
        print(f"Folder picker could not be opened ({exc}).")
        selected_folder = ""
    finally:
        if root is not None:
            root.destroy()

    if selected_folder:
        print(f"Output folder: {selected_folder}")
        return selected_folder

    print("Folder selection cancelled. Closing downloader.")
    return None


def ask_for_missing_inputs(args: argparse.Namespace) -> argparse.Namespace:
    """Prompt for required values when the script is launched by double-click."""
    launched_without_required_inputs = not args.playlist_url

    if not launched_without_required_inputs:
        try:
            args.playlist_url = validate_download_url(args.playlist_url)
        except ValueError as exc:
            raise SystemExit(f"Invalid YouTube Music URL: {exc}") from exc
        return args

    print("YouTube Music Downloader")
    print("")

    if not args.playlist_url:
        while True:
            try:
                args.playlist_url = validate_download_url(
                    input("Paste a YouTube Music playlist or song URL: ")
                )
                break
            except ValueError as exc:
                print(f"Invalid YouTube Music URL: {exc}")

    if not args.output:
        if is_playlist_url(args.playlist_url):
            args.output = choose_output_folder("Choose where to save this playlist")
        else:
            args.output = choose_output_folder(
                "Choose the existing playlist folder for this song"
            )
        if not args.output:
            raise SystemExit(USER_CANCELLED_EXIT_CODE)

    if not args.cookies:
        print("")
        print("If YouTube shows a bot/sign-in error, export cookies with")
        print("'Get cookies.txt LOCALLY' and put the file here:")
        print(Path(__file__).resolve().with_name(DEFAULT_COOKIES_NAME))

    print("")
    return args

def ensure_docker_desktop_running() -> bool:
    """Quietly open Docker Desktop if the optional Docker engine is unavailable."""
    docker_desktop_paths = [
        Path(r"C:\Program Files\Docker\Docker\Docker Desktop.exe"),
        Path(r"C:\Users\Huy\AppData\Local\Docker\Docker Desktop.exe"),
    ]

    def docker_engine_ready() -> bool:
        try:
            result = subprocess.run(
                ["docker", "info"],
                capture_output=True,
                text=True,
            )
            return result.returncode == 0
        except OSError:
            return False

    if docker_engine_ready():
        return True

    docker_desktop = next((path for path in docker_desktop_paths if path.exists()), None)

    if not docker_desktop:
        return False

    try:
        subprocess.Popen(
            [str(docker_desktop)],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
    except OSError:
        return False

    for _ in range(60):
        if docker_engine_ready():
            return True
        time.sleep(2)

    return False

def ensure_po_provider_running() -> None:
    """Quietly start the optional bgutil PO-token provider when available."""
    if not ensure_docker_desktop_running():
        return

    container_name = "bgutil-provider"
    image_name = "brainicism/bgutil-ytdlp-pot-provider"
    ping_url = "http://127.0.0.1:4416/ping"

    def provider_is_alive() -> bool:
        try:
            with urllib.request.urlopen(ping_url, timeout=3) as response:
                return 200 <= response.status < 500
        except Exception:
            return False

    if provider_is_alive():
        return

    # Try starting existing container first.
    try:
        start_result = subprocess.run(
            ["docker", "start", container_name],
            capture_output=True,
            text=True,
        )
    except OSError:
        return

    # If container does not exist, create it.
    if start_result.returncode != 0:
        try:
            run_result = subprocess.run(
                [
                    "docker",
                    "run",
                    "-d",
                    "--name",
                    container_name,
                    "-p",
                    "4416:4416",
                    image_name,
                ],
                capture_output=True,
                text=True,
            )
        except OSError:
            return

        if run_result.returncode != 0:
            return

    # Wait a bit for the server to become ready.
    for _ in range(10):
        if provider_is_alive():
            return
        time.sleep(1)


def ask_yes_no(prompt: str, default: bool = False) -> bool:
    suffix = " [Y/n]: " if default else " [y/N]: "
    answer = input(prompt + suffix).strip().lower()
    if not answer:
        return default
    return answer in {"y", "yes"}


def ask_for_next_playlist(args: argparse.Namespace) -> argparse.Namespace:
    while True:
        try:
            args.playlist_url = validate_download_url(
                input("Paste the next YouTube Music playlist or song URL: ")
            )
            break
        except ValueError as exc:
            print(f"Invalid YouTube Music URL: {exc}")

    if is_playlist_url(args.playlist_url):
        args.output = choose_output_folder("Choose where to save the next playlist")
    else:
        args.output = choose_output_folder(
            "Choose the existing playlist folder for this song"
        )
    if not args.output:
        raise SystemExit(USER_CANCELLED_EXIT_CODE)

    print("")
    return args


def main(argv: list[str] | None = None) -> int:
    # Some Windows consoles cannot encode every title/artist in large playlists.
    # Replacing unsupported characters keeps progress printing from crashing.
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(errors="replace")
    if hasattr(sys.stderr, "reconfigure"):
        sys.stderr.reconfigure(errors="replace")
    install_duplicate_provider_stderr_filter()

    args = ask_for_missing_inputs(parse_args(argv or sys.argv[1:]))
    check_ffmpeg()
    options = prepare_download_options(args)

    ensure_po_provider_running()

    while True:
        while True:
            if is_playlist_url(args.playlist_url):
                result = sync_playlist(
                    args.playlist_url,
                    Path(args.output) if args.output else None,
                    options,
                    stop_after_video_id=args.stop_after_video_id,
                    max_workers=args.workers,
                )
            else:
                result = sync_single_track(
                    args.playlist_url,
                    Path(args.output) if args.output else None,
                    options,
                )

            if result == 0:
                break

            print("")
            if not ask_yes_no("Some songs failed. Try again?"):
                break

            print("")
            print("Trying again...")
            print("")

        print("")
        if not ask_yes_no("Download another playlist or song?"):
            return result

        print("")
        args = ask_for_next_playlist(args)


if __name__ == "__main__":
    raise SystemExit(main())
