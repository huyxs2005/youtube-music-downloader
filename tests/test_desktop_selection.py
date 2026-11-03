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
        with patch.object(engine, "fetch_playlist_tracks", return_value=self.prepared), patch.object(bridge, "emit"):
            result = bridge.scan(dict(url=self.url, folder=str(self.folder)))
        self.assertEqual(result["rows"][0]["duration"], 121)
        self.assertIsInstance(result["rows"][0]["fileSize"], int)
        self.assertGreater(result["rows"][0]["fileSize"], 0)
        self.assertTrue(result["rows"][0]["sizeEstimated"])
        self.assertIsNone(result["rows"][0]["genre"])
        self.assertFalse(Path(result["folder"]).exists())

    def test_custom_order_keeps_existing_unchecked_audio_and_can_return_to_youtube_order(self):
        for song in self.tracks:
            (self.folder / song.filename).write_bytes(b"existing")
        with contextlib.redirect_stdout(io.StringIO()), patch.object(engine, "download_track_job") as download:
            code = engine.sync_playlist(self.url, self.folder, engine.DownloadOptions(),
                selected_video_ids=set(), prepared_playlist=self.prepared, custom_order=["c", "a"])
            self.assertEqual(code, 0)
            self.assertEqual(self.playlist_files(), [self.tracks[i].filename for i in (2, 0, 1)])
            self.assertEqual(engine.load_manifest(self.folder / engine.MANIFEST_NAME)["custom_order"], ["c", "a"])
            engine.sync_playlist(self.url, self.folder, engine.DownloadOptions(),
                selected_video_ids=set(), prepared_playlist=self.prepared)
            self.assertEqual(self.playlist_files(), [song.filename for song in self.tracks])
            self.assertEqual(engine.load_manifest(self.folder / engine.MANIFEST_NAME)["custom_order"], [])
            download.assert_not_called()

    def test_scan_progress_counts_real_rows_and_ignores_continuation_buttons(self):
        from playlist_progress import ProgressYTMusic
        client = object.__new__(ProgressYTMusic)
        counts = []
        client.report = lambda songs, unavailable: counts.append((songs, unavailable))
        client.progress_items, client.progress_reliable = [], True
        client.detected = client.unavailable = 0
        items = [{"musicResponsiveListItemRenderer": song} for song in (
            {"videoId": "a"}, {"videoId": None}, {"videoId": "b", "isAvailable": False}, {"videoId": "c"})]
        items.insert(2, {"continuationItemRenderer": {}})
        response = {"onResponseReceivedActions": [{"appendContinuationItemsAction": {"continuationItems": items}}]}
        with patch.object(engine.YTMusic, "_send_request", return_value=response), \
             patch("playlist_progress.parse_playlist_items", side_effect=lambda rows: [rows[0]["musicResponsiveListItemRenderer"]]):
            self.assertIs(client._send_request("browse", {}), response)
        self.assertEqual(counts, [(1, 0), (1, 1), (1, 2), (2, 2)])
        self.assertEqual(len(client.progress_items), 4)

    def test_unavailable_song_with_video_id_is_skipped(self):
        self.assertIsNone(engine.track_from_ytmusic({"videoId": "blocked", "title": "Unavailable", "isAvailable": False}, 1))

    def test_complete_playlist_keeps_missing_references_repeated_songs_and_saved_order(self):
        tracks = [track(1,"a"),track(2,"b"),track(3,"a"),track(4,"c")]
        (self.folder / tracks[0].filename).write_bytes(b"existing")
        prepared=("PL-test","My Playlist",4,tracks,[])
        with contextlib.redirect_stdout(io.StringIO()), patch.object(engine,"download_track_job") as download:
            code=engine.sync_playlist(self.url,self.folder,engine.DownloadOptions(),selected_video_ids=set(),prepared_playlist=prepared,include_missing=True)
            self.assertEqual(code,0)
            self.assertEqual(self.playlist_files(),[song.filename for song in tracks])
            self.assertFalse((self.folder / tracks[1].filename).exists())
            manifest=engine.load_manifest(self.folder / engine.MANIFEST_NAME)
            self.assertEqual(manifest["youtube_order"],["a","b","a","c"])
            self.assertTrue(manifest["include_missing"])
            (self.folder / "My Playlist.m3u8").unlink()
            recovered=engine.current_manifest_playlist_tracks(self.folder,manifest)
            self.assertEqual([song.video_id for song in recovered],["a","b","a","c"])
            engine.sync_playlist(self.url,self.folder,engine.DownloadOptions(),selected_video_ids=set(),prepared_playlist=prepared)
            self.assertEqual(self.playlist_files(),[song.filename for song in tracks])
            download.assert_not_called()

    def test_repeated_song_downloads_once_but_keeps_both_playlist_positions(self):
        tracks=[track(1,"a"),track(2,"a")]
        def download(song,folder,options):
            output=folder / "fixture.temp.opus"
            output.write_bytes(b"downloaded fixture")
            return song,output,None
        with contextlib.redirect_stdout(io.StringIO()), patch.object(engine,"download_track_job",side_effect=download) as job, \
             patch.object(engine,"apply_track_metadata",return_value=False):
            result=engine.sync_playlist(self.url,self.folder,engine.DownloadOptions(),selected_video_ids={"a"},
                prepared_playlist=("PL-test","My Playlist",2,tracks,[]),include_missing=True)
        self.assertEqual(result,0)
        self.assertEqual(job.call_count,1)
        self.assertEqual(self.playlist_files(),[tracks[0].filename,tracks[0].filename])

    def test_backend_refuses_changed_playlist_folder(self):
        engine.save_manifest(self.folder / engine.MANIFEST_NAME, "other", {}, "Other")
        snapshot = dict(url=self.url, folder=str(self.folder), playlistId="PL-test",
                        title="My Playlist", single=False, total=3, skipped=[],
                        tracks=[asdict(t) for t in self.tracks])
        with self.assertRaises(ValueError):
            bridge.download(dict(snapshot=snapshot, selected=[]))


if __name__ == "__main__":
    unittest.main()
