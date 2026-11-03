import contextlib
import io
import tempfile
import unittest
from dataclasses import asdict
from pathlib import Path
from unittest.mock import patch

import desktop_bridge as bridge
import ytmusic_downloader as engine


def track(index, video_id, title=None):
    return engine.Track(index, video_id, None, title or video_id, ["Artist"], None, None,
                        f"Artist - {video_id} [{video_id}].opus", 120 + index)


class DesktopSelectionTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.folder = Path(self.temp.name)
        self.tracks = [track(1, "a"), track(2, "b"), track(3, "c")]
        self.url = "https://music.youtube.com/playlist?list=PL-test"
        self.prepared = ("PL-test", "My Playlist", 3, self.tracks, [])

    def tearDown(self):
        self.temp.cleanup()

    def sync(self, selected):
        def download(song, folder, options):
            path = folder / (song.video_id + ".temp.opus")
            path.write_bytes(b"downloaded audio")
            return song, path, None
        with contextlib.redirect_stdout(io.StringIO()), \
             patch.object(engine, "download_track_job", side_effect=download) as job, \
             patch.object(engine, "apply_track_metadata", return_value=True), \
             patch.object(engine, "fetch_playlist_tracks", side_effect=AssertionError("Do not refetch the reviewed playlist")):
            code = engine.sync_playlist(self.url, self.folder, engine.DownloadOptions(),
                selected_video_ids=selected, prepared_playlist=self.prepared)
        return code, [call.args[0].video_id for call in job.call_args_list]

    def playlist_files(self):
        return [line for line in (self.folder / "My Playlist.m3u8").read_text(encoding="utf-8").splitlines()
                if line and not line.startswith("#")]

    def test_selection_downloads_only_checked_and_keeps_unchecked_existing_in_order(self):
        (self.folder / self.tracks[0].filename).write_bytes(b"existing")
        code, downloaded = self.sync({"c"})
        self.assertEqual(code, 0)
        self.assertEqual(downloaded, ["c"])
        self.assertEqual(self.playlist_files(), [self.tracks[0].filename, self.tracks[2].filename])
        manifest = engine.load_manifest(self.folder / engine.MANIFEST_NAME)
        self.assertEqual([entry["videoId"] for entry in manifest["tracks"]], ["a", "b", "c"])
        self.assertFalse((self.folder / self.tracks[1].filename).exists())

    def test_empty_selection_still_refreshes_m3u8_without_downloading(self):
        (self.folder / self.tracks[1].filename).write_bytes(b"existing")
        code, downloaded = self.sync(set())
        self.assertEqual((code, downloaded), (0, []))
        self.assertEqual(self.playlist_files(), [self.tracks[1].filename])

    def test_later_sync_downloads_previously_unchecked_missing_song(self):
        self.sync({"c"})
        code, downloaded = self.sync({"a", "b", "c"})
        self.assertEqual(code, 0)
        self.assertEqual(set(downloaded), {"a", "b"})
        self.assertEqual(self.playlist_files(), [song.filename for song in self.tracks])

    def test_download_failure_is_reported_and_not_in_playlist(self):
        with contextlib.redirect_stdout(io.StringIO()), \
             patch.object(engine, "download_track_job", return_value=(self.tracks[0], None, RuntimeError("offline"))):
            events = []
            code = engine.sync_playlist(self.url, self.folder, engine.DownloadOptions(),
                prepared_playlist=self.prepared, selected_video_ids={"a"},
                on_track=lambda song, status: events.append((song.video_id, status)))
        self.assertEqual(code, 1)
        self.assertIn(("a", "Failed"), events)
        self.assertEqual(self.playlist_files(), [])
        self.assertTrue((self.folder / engine.FAILED_DOWNLOADS_NAME).exists())

    def test_folder_matching_uses_id_even_when_title_changes(self):
        old = self.folder / "Old name"
        old.mkdir()
        engine.save_manifest(old / engine.MANIFEST_NAME, "PL-test", {}, "Old name")
        self.assertEqual(bridge.resolve_folder(self.folder, "PL-test", "New name"), old)
        self.assertEqual(bridge.resolve_folder(old, "PL-test", "New name"), old)
        with self.assertRaises(ValueError):
            bridge.resolve_folder(old, "PL-other", "New name")

    def test_title_collision_cannot_overwrite_other_playlist(self):
        target = self.folder / "My Playlist"
        target.mkdir()
        engine.save_manifest(target / engine.MANIFEST_NAME, "PL-other", {}, "My Playlist")
        with self.assertRaises(ValueError):
            bridge.resolve_folder(self.folder, "PL-test", "My Playlist")

    def test_scan_is_read_only_and_exposes_numeric_metadata(self):
        with patch.object(engine, "fetch_playlist_tracks", return_value=self.prepared):
            result = bridge.scan(dict(url=self.url, folder=str(self.folder)))
        self.assertEqual(result["rows"][0]["duration"], 121)
        self.assertIsNone(result["rows"][0]["fileSize"])
        self.assertIsNone(result["rows"][0]["genre"])
        self.assertFalse(Path(result["folder"]).exists())

    def test_backend_refuses_changed_playlist_folder(self):
        engine.save_manifest(self.folder / engine.MANIFEST_NAME, "other", {}, "Other")
        snapshot = dict(url=self.url, folder=str(self.folder), playlistId="PL-test",
                        title="My Playlist", single=False, total=3, skipped=[],
                        tracks=[asdict(t) for t in self.tracks])
        with self.assertRaises(ValueError):
            bridge.download(dict(snapshot=snapshot, selected=[]))


if __name__ == "__main__":
    unittest.main()
