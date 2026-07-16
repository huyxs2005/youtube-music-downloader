import io
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import ytmusic_downloader as downloader


SONG_URL = "https://music.youtube.com/watch?v=new-video"


def make_track(
    index: int,
    video_id: str,
    title: str,
    artist: str,
    filename: str | None = None,
) -> downloader.Track:
    return downloader.Track(
        index=index,
        video_id=video_id,
        set_video_id=None,
        title=title,
        artists=[artist],
        album=None,
        thumbnail_url=None,
        filename=filename or downloader.build_filename([artist], title, video_id),
    )


class SingleSongSyncTests(unittest.TestCase):
    def setUp(self) -> None:
        self.stdout_patch = patch.object(downloader.sys, "stdout", io.StringIO())
        self.stdout_patch.start()
        self.temp_dir = tempfile.TemporaryDirectory()
        self.output_dir = Path(self.temp_dir.name)
        self.manifest_path = self.output_dir / downloader.MANIFEST_NAME
        self.old_tracks = [
            make_track(1, "old-a", "First Song", "First Artist", "001 - First.opus"),
            make_track(2, "old-b", "Second Song", "Second Artist", "002 - Second.opus"),
        ]
        for track in self.old_tracks:
            (self.output_dir / track.filename).write_bytes(b"existing audio")
        known_tracks = {
            track.video_id: downloader.manifest_entry(track)
            for track in self.old_tracks
        }
        downloader.save_manifest(
            self.manifest_path,
            "playlist-id",
            known_tracks,
            "Unicode Playlist 音楽",
            "Unicode Playlist 音楽.m3u8",
        )
        downloader.write_poweramp_m3u8(
            self.output_dir,
            "Unicode Playlist 音楽",
            self.old_tracks,
            known_tracks,
        )

    def tearDown(self) -> None:
        self.temp_dir.cleanup()
        self.stdout_patch.stop()

    def read_manifest(self) -> dict:
        return json.loads(self.manifest_path.read_text(encoding="utf-8"))

    def read_playlist_audio_lines(self) -> list[str]:
        m3u8_path = self.output_dir / self.read_manifest()["m3u8_filename"]
        return [
            line
            for line in m3u8_path.read_text(encoding="utf-8").splitlines()
            if line and not line.startswith("#")
        ]

    def test_new_unicode_song_is_downloaded_once_and_inserted_first(self) -> None:
        new_track = make_track(1, "new-video", "新しい歌", "Beyoncé")

        def fake_download(track, output_dir, options):
            temp_path = output_dir / ".download-new-video.opus"
            temp_path.write_bytes(b"new audio")
            return temp_path

        with (
            patch.object(downloader, "fetch_single_track", return_value=new_track),
            patch.object(downloader, "download_track", side_effect=fake_download) as download,
            patch.object(downloader, "apply_track_metadata", return_value=True),
        ):
            result = downloader.sync_single_track(
                SONG_URL,
                self.output_dir,
                downloader.DownloadOptions(),
            )

        self.assertEqual(result, 0)
        download.assert_called_once()
        manifest = self.read_manifest()
        entries = {item["videoId"]: item for item in manifest["tracks"]}
        self.assertEqual(entries["new-video"]["playlist_index"], 1)
        self.assertTrue(entries["new-video"]["manually_added"])
        self.assertEqual(entries["old-a"]["playlist_index"], 2)
        self.assertEqual(entries["old-b"]["playlist_index"], 3)
        self.assertEqual(
            self.read_playlist_audio_lines(),
            [new_track.filename, "001 - First.opus", "002 - Second.opus"],
        )
        m3u8_text = (self.output_dir / manifest["m3u8_filename"]).read_text(
            encoding="utf-8"
        )
        self.assertIn("#EXTINF:-1,Beyoncé - 新しい歌", m3u8_text)

    def test_existing_song_moves_first_without_download_or_rename(self) -> None:
        existing_track = make_track(1, "old-b", "Updated title", "Updated artist")

        with (
            patch.object(downloader, "fetch_single_track", return_value=existing_track),
            patch.object(downloader, "download_track") as download,
            patch.object(downloader, "apply_track_metadata") as metadata,
        ):
            result = downloader.sync_single_track(
                "https://music.youtube.com/watch?v=old-b",
                self.output_dir,
                downloader.DownloadOptions(),
            )

        self.assertEqual(result, 0)
        download.assert_not_called()
        metadata.assert_not_called()
        manifest = self.read_manifest()
        entries = {item["videoId"]: item for item in manifest["tracks"]}
        self.assertEqual(entries["old-b"]["output_filename"], "002 - Second.opus")
        self.assertEqual(entries["old-b"]["playlist_index"], 1)
        self.assertEqual(
            self.read_playlist_audio_lines(),
            ["002 - Second.opus", "001 - First.opus"],
        )

    def test_failed_new_song_is_reported_but_not_added_to_m3u8(self) -> None:
        new_track = make_track(1, "new-video", "Missing Song", "Artist")

        with (
            patch.object(downloader, "fetch_single_track", return_value=new_track),
            patch.object(downloader, "download_track", side_effect=RuntimeError("failed")),
        ):
            result = downloader.sync_single_track(
                SONG_URL,
                self.output_dir,
                downloader.DownloadOptions(),
            )

        self.assertEqual(result, 1)
        self.assertNotIn(new_track.filename, self.read_playlist_audio_lines())
        failed_text = (self.output_dir / downloader.FAILED_DOWNLOADS_NAME).read_text(
            encoding="utf-8"
        )
        self.assertIn("Missing Song", failed_text)
        self.assertIn("new-video", failed_text)
        error_text = (self.output_dir / downloader.DOWNLOAD_ERRORS_NAME).read_text(
            encoding="utf-8"
        )
        self.assertEqual(error_text, downloader.failed_track_line(new_track) + "\n")
        self.assertNotIn("RuntimeError", error_text)
        self.assertNotIn("Traceback", error_text)

    def test_future_playlist_sync_keeps_manual_song_at_top(self) -> None:
        manual = make_track(1, "manual", "Local First", "Artist")
        manual.filename = "Artist - Local First [manual].opus"
        (self.output_dir / manual.filename).write_bytes(b"manual audio")
        manifest = self.read_manifest()
        known_tracks = downloader.manifest_by_video_id(manifest)
        known_tracks[manual.video_id] = downloader.manifest_entry(manual, True)
        downloader.save_manifest(
            self.manifest_path,
            "playlist-id",
            known_tracks,
            "Unicode Playlist 音楽",
            manifest["m3u8_filename"],
        )
        remote_tracks = [
            make_track(1, "old-b", "Second Song", "Second Artist"),
            make_track(2, "old-a", "First Song", "First Artist"),
        ]

        with (
            patch.object(
                downloader,
                "fetch_playlist_tracks",
                return_value=(
                    "playlist-id",
                    "Unicode Playlist 音楽",
                    2,
                    remote_tracks,
                    [],
                ),
            ),
            patch.object(downloader, "apply_track_metadata", return_value=False),
        ):
            result = downloader.sync_playlist(
                "https://music.youtube.com/playlist?list=playlist-id",
                self.output_dir,
                downloader.DownloadOptions(),
                max_workers=1,
            )

        self.assertEqual(result, 0)
        self.assertEqual(
            self.read_playlist_audio_lines(),
            [manual.filename, "002 - Second.opus", "001 - First.opus"],
        )


class UrlValidationTests(unittest.TestCase):
    def test_song_urls_are_accepted(self) -> None:
        self.assertEqual(downloader.validate_download_url(SONG_URL), SONG_URL)
        short_url = "https://youtu.be/new-video"
        self.assertEqual(downloader.validate_download_url(short_url), short_url)

    def test_watch_url_with_playlist_context_is_still_a_single_song(self) -> None:
        url = "https://music.youtube.com/watch?v=new-video&list=playlist-id"
        self.assertEqual(downloader.validate_download_url(url), url)
        self.assertFalse(downloader.is_playlist_url(url))


if __name__ == "__main__":
    unittest.main()
