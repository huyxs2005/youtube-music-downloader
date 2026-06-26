#!/usr/bin/env python3
"""Download a YouTube Music playlist as ordered OPUS files."""

from __future__ import annotations

import argparse
import json
import re
import shutil
import sys
import traceback
import subprocess
import time
import urllib.request
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass
from pathlib import Path
from typing import Any
from urllib.parse import parse_qs, urlparse

from ytmusicapi import YTMusic
from yt_dlp import YoutubeDL
from yt_dlp.utils import DownloadError


MANIFEST_NAME = "playlist_manifest.json"
DEFAULT_COOKIES_NAME = "cookies.txt"
INVALID_WINDOWS_CHARS = r'<>:"/\|?*'
RESERVED_WINDOWS_NAMES = {
    "CON",
    "PRN",
    "AUX",
    "NUL",
    *(f"COM{i}" for i in range(1, 10)),
    *(f"LPT{i}" for i in range(1, 10)),
}


@dataclass
class Track:
    index: int
    video_id: str
    set_video_id: str | None
    title: str
    artists: list[str]
    filename: str


@dataclass
class DownloadOptions:
    cookies_file: str | None = None


def parse_playlist_id(playlist_url: str) -> str:
    """Extract the playlist id from a YouTube Music playlist URL."""
    parsed = urlparse(playlist_url)
    playlist_id = parse_qs(parsed.query).get("list", [None])[0]
    if not playlist_id:
        raise ValueError("Could not find a playlist id in the URL. Expected ?list=PLAYLIST_ID.")
    return playlist_id


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


def save_manifest(path: Path, playlist_id: str, tracks_by_video_id: dict[str, dict[str, Any]]) -> None:
    ordered_tracks = sorted(tracks_by_video_id.values(), key=lambda item: item["playlist_index"])
    data = {
        "playlist_id": playlist_id,
        "tracks": ordered_tracks,
    }
    temp_path = path.with_suffix(".json.tmp")
    with temp_path.open("w", encoding="utf-8") as file:
        json.dump(data, file, ensure_ascii=False, indent=2)
        file.write("\n")
    temp_path.replace(path)


def artists_to_text(artists: list[str]) -> str:
    return ", ".join(artist for artist in artists if artist) or "Unknown Artist"


def build_filename(index: int, artists: list[str], title: str) -> str:
    artist_text = sanitize_filename_part(artists_to_text(artists), "Unknown Artist")
    title_text = sanitize_filename_part(title, "Untitled")
    return f"{index:03d} - {artist_text} - {title_text}.opus"


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
    return Track(
        index=index,
        video_id=video_id,
        set_video_id=raw_track.get("setVideoId"),
        title=title,
        artists=artists,
        filename=build_filename(index, artists, title),
    )


def fetch_playlist_tracks(playlist_url: str) -> tuple[str, int, list[Track], list[int]]:
    """Fetch ordered tracks with ytmusicapi, not yt-dlp playlist parsing.

    Number only valid/downloadable tracks, so skipped playlist items do not
    create gaps like 023, 025.
    """
    playlist_id = parse_playlist_id(playlist_url)
    playlist = YTMusic().get_playlist(playlist_id, limit=None)
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

    return playlist_id, len(playlist_items), tracks, skipped_items


def manifest_by_video_id(manifest: dict[str, Any]) -> dict[str, dict[str, Any]]:
    result: dict[str, dict[str, Any]] = {}
    for item in manifest.get("tracks", []):
        video_id = item.get("videoId")
        if video_id:
            result[video_id] = dict(item)
    return result


def path_is_same(a: Path, b: Path) -> bool:
    try:
        return a.resolve() == b.resolve()
    except OSError:
        return a.absolute() == b.absolute()


def unique_temp_stem(output_dir: Path, video_id: str) -> Path:
    safe_video_id = sanitize_filename_part(video_id, "video")
    return output_dir / f".download-{safe_video_id}"


def download_track(track: Track, output_dir: Path, options: DownloadOptions) -> Path:
    """Download one videoId only, writing to a temp name before final rename."""
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
    ydl_opts = {
        "format": format_selector,
        "outtmpl": str(temp_stem) + ".%(ext)s",
        "noplaylist": True,
        "quiet": True,
        "no_warnings": True,
        "noprogress": True,
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


def ensure_final_path(temp_path: Path, final_path: Path) -> None:
    if final_path.exists():
        backup_path = final_path.with_name(f"{final_path.stem}.replaced{final_path.suffix}")
        counter = 1
        while backup_path.exists():
            backup_path = final_path.with_name(f"{final_path.stem}.replaced-{counter}{final_path.suffix}")
            counter += 1
        final_path.replace(backup_path)
    temp_path.replace(final_path)


def rename_existing_file(current_path: Path, final_path: Path) -> bool:
    """Rename a previously downloaded track when playlist order or metadata changes."""
    if path_is_same(current_path, final_path):
        return False
    if not current_path.exists():
        return False
    if final_path.exists():
        backup_path = final_path.with_name(f"{final_path.stem}.replaced{final_path.suffix}")
        counter = 1
        while backup_path.exists():
            backup_path = final_path.with_name(f"{final_path.stem}.replaced-{counter}{final_path.suffix}")
            counter += 1
        final_path.replace(backup_path)
    current_path.replace(final_path)
    return True


def manifest_entry(track: Track) -> dict[str, Any]:
    return {
        "videoId": track.video_id,
        "setVideoId": track.set_video_id,
        "title": track.title,
        "artists": track.artists,
        "playlist_index": track.index,
        "output_filename": track.filename,
    }


def sync_playlist(
    playlist_url: str,
    output_dir: Path,
    options: DownloadOptions,
    stop_after_video_id: str | None = None,
    max_workers: int = 10,
) -> int:
    output_dir.mkdir(parents=True, exist_ok=True)
    manifest_path = output_dir / MANIFEST_NAME

    playlist_id, total_items, tracks, skipped_items = fetch_playlist_tracks(playlist_url)
    print(f"Total playlist items found: {total_items}")
    print(f"Total tracks found: {len(tracks)}")
    for item_index in skipped_items:
        print(f"Skipping playlist item {item_index:03d}: no videoId found")

    manifest = load_manifest(manifest_path)
    known_tracks = manifest_by_video_id(manifest)
    success_count = 0
    skipped_count = 0
    renamed_count = 0
    downloaded_count = 0
    failed_count = 0
    pending_downloads: list[Track] = []

    for track in tracks:
        final_path = output_dir / track.filename
        old_entry = known_tracks.get(track.video_id)
        old_filename = old_entry.get("output_filename") if old_entry else None
        old_path = output_dir / old_filename if old_filename else None

        try:
            if old_path and old_path.exists():
                if rename_existing_file(old_path, final_path):
                    print(f"Renaming: {old_filename} -> {track.filename}")
                    renamed_count += 1
                else:
                    print(f"Skipping: {track.filename}")
                    skipped_count += 1
            elif old_entry and final_path.exists():
                # The manifest says this videoId was downloaded, and the file is
                # already at today's desired ordered filename.
                print(f"Skipping: {track.filename}")
                skipped_count += 1
            else:
                print(f"Queueing download: {track.index:03d} - {artists_to_text(track.artists)} - {track.title}")
                pending_downloads.append(track)

            if track not in pending_downloads:
                known_tracks[track.video_id] = manifest_entry(track)
                save_manifest(manifest_path, playlist_id, known_tracks)
                success_count += 1
        except Exception as exc:  # Keep the playlist moving if one song fails.
            failed_count += 1
            print(f"Failed: {track.index:03d} - {track.title} ({track.video_id})")
            print(f"  {exc}")
            with (output_dir / "download_errors.log").open("a", encoding="utf-8") as log_file:
                log_file.write(f"{track.index:03d} {track.video_id} {track.title}\n")
                log_file.write("".join(traceback.format_exception(exc)))
                log_file.write("\n")

        if stop_after_video_id and track.video_id == stop_after_video_id:
            print(f"Stopping after requested test videoId: {stop_after_video_id}")
            break

    if pending_downloads:
        worker_count = max(1, min(max_workers, len(pending_downloads)))
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
                    print(f"Failed: {track.index:03d} - {track.title} ({track.video_id})")
                    print(f"  {exc}")
                    with (output_dir / "download_errors.log").open("a", encoding="utf-8") as log_file:
                        log_file.write(f"{track.index:03d} {track.video_id} {track.title}\n")
                        log_file.write("".join(traceback.format_exception(exc)))
                        log_file.write("\n")
                    continue

                print(f"Downloaded: {track.filename}")
                ensure_final_path(temp_output, final_path)
                known_tracks[track.video_id] = manifest_entry(track)
                save_manifest(manifest_path, playlist_id, known_tracks)
                downloaded_count += 1
                success_count += 1

    print("")
    print("Final summary")
    print(f"  Successful tracks: {success_count}")
    print(f"  Downloaded: {downloaded_count}")
    print(f"  Skipped: {skipped_count}")
    print(f"  Renamed: {renamed_count}")
    print(f"  Failed: {failed_count}")
    print(f"  Output: {output_dir}")
    print(f"  Manifest: {manifest_path}")
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
    parser = argparse.ArgumentParser(description="Download a YouTube Music playlist as ordered OPUS files.")
    parser.add_argument("playlist_url", nargs="?", help="YouTube Music playlist URL, for example https://music.youtube.com/playlist?list=...")
    parser.add_argument("--output", help="Output folder for OPUS files and playlist_manifest.json.")
    parser.add_argument("--workers", type=int, default=10, help="Number of songs to download at the same time. Default: 10.")
    parser.add_argument("--cookies", help="Path to a cookies.txt file exported from your browser.")
    parser.add_argument("--stop-after-video-id", help=argparse.SUPPRESS)
    return parser.parse_args(argv)


def ask_for_missing_inputs(args: argparse.Namespace) -> argparse.Namespace:
    """Prompt for required values when the script is launched by double-click."""
    launched_without_required_inputs = not args.playlist_url or not args.output
    if not launched_without_required_inputs:
        return args

    print("YouTube Music Playlist Downloader")
    print("")
    if not args.playlist_url:
        args.playlist_url = input("Paste the YouTube Music playlist URL: ").strip().strip('"')
    if not args.output:
        default_output = str(Path.cwd() / "downloads")
        output = input(f"Output folder [{default_output}]: ").strip().strip('"')
        args.output = output or default_output
    if not args.cookies:
        print("")
        print("If YouTube shows a bot/sign-in error, export cookies with")
        print("'Get cookies.txt LOCALLY' and put the file here:")
        print(Path(__file__).resolve().with_name(DEFAULT_COOKIES_NAME))
    print("")
    return args

def ensure_docker_desktop_running() -> bool:
    """Open Docker Desktop if Docker engine is not available yet."""
    docker_desktop_paths = [
        Path(r"C:\Program Files\Docker\Docker\Docker Desktop.exe"),
        Path(r"C:\Users\Huy\AppData\Local\Docker\Docker Desktop.exe"),
    ]

    def docker_engine_ready() -> bool:
        result = subprocess.run(
            ["docker", "info"],
            capture_output=True,
            text=True,
        )
        return result.returncode == 0

    if docker_engine_ready():
        return True

    print("Docker engine is not ready. Trying to start Docker Desktop...")

    docker_desktop = next((path for path in docker_desktop_paths if path.exists()), None)

    if not docker_desktop:
        print("Could not find Docker Desktop.exe.")
        print("Please open Docker Desktop manually.")
        return False

    subprocess.Popen(
        [str(docker_desktop)],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )

    print("Waiting for Docker Desktop to start...")

    for _ in range(60):
        if docker_engine_ready():
            print("Docker Desktop is running.")
            return True
        time.sleep(2)

    print("Docker Desktop did not become ready in time.")
    print("Please open Docker Desktop manually.")
    return False

def ensure_po_provider_running() -> None:
    """Start the bgutil PO-token provider Docker container if available."""
    if not ensure_docker_desktop_running():
        print("Continuing without PO-token provider. Downloads may hit HTTP 403.")
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
        print("PO-token provider is already running.")
        return

    print("Starting PO-token provider Docker container...")

    # Try starting existing container first.
    start_result = subprocess.run(
        ["docker", "start", container_name],
        capture_output=True,
        text=True,
    )

    # If container does not exist, create it.
    if start_result.returncode != 0:
        print("PO-token container not found. Creating it...")
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

        if run_result.returncode != 0:
            print("Could not start PO-token provider.")
            print(run_result.stderr.strip())
            print("Continuing anyway, but downloads may hit HTTP 403.")
            return

    # Wait a bit for the server to become ready.
    for _ in range(10):
        if provider_is_alive():
            print("PO-token provider is running.")
            return
        time.sleep(1)

    print("PO-token provider did not respond on http://127.0.0.1:4416/ping")
    print("Continuing anyway, but downloads may hit HTTP 403.")

def main(argv: list[str] | None = None) -> int:
    # Some Windows consoles cannot encode every title/artist in large playlists.
    # Replacing unsupported characters keeps progress printing from crashing.
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(errors="replace")
    if hasattr(sys.stderr, "reconfigure"):
        sys.stderr.reconfigure(errors="replace")

    args = ask_for_missing_inputs(parse_args(argv or sys.argv[1:]))
    check_ffmpeg()
    options = prepare_download_options(args)

    ensure_po_provider_running()

    while True:
        result = sync_playlist(
            args.playlist_url,
            Path(args.output),
            options,
            stop_after_video_id=args.stop_after_video_id,
            max_workers=args.workers,
        )

        if result == 0:
            return 0

        print("")
        answer = input("Some songs failed. Try again? [y/N]: ").strip().lower()

        if answer not in {"y", "yes"}:
            return result

        print("")
        print("Trying again...")
        print("")


if __name__ == "__main__":
    raise SystemExit(main())
