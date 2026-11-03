import contextlib
import io
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import filename_migration as names
import ytmusic_downloader as engine


def track(video_id, title="Song", artist="Artist"):
    return engine.Track(1, video_id, None, title, [artist], None, None,
                        f"{artist} - {title} [{video_id}].opus")


class FilenameMigrationTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.folder = Path(self.temp.name)

    def tearDown(self):
        self.temp.cleanup()

    def test_scan_preserves_existing_filename_without_touching_audio(self):
        song = track("id")
        original = song.filename
        (self.folder / original).write_bytes(b"audio and artwork")
        self.assertEqual(names.assign_filenames([song], self.folder, {}), [])
        self.assertEqual(song.filename, original)
        self.assertEqual((self.folder / original).read_bytes(), b"audio and artwork")

    def test_migration_updates_audio_manifest_and_full_playlist_together(self):
        song, missing = track("id"), track("other", "Another")
        original = song.filename
        payload = b"audio and embedded artwork remain byte identical"
        (self.folder / original).write_bytes(payload)
        manifest_path = self.folder / engine.MANIFEST_NAME
        engine.save_manifest(manifest_path, "PL-test", {s.video_id: engine.manifest_entry(s) for s in [song, missing]}, "Playlist")
        with contextlib.redirect_stdout(io.StringIO()), patch.object(engine, "apply_track_metadata", return_value=False):
            code = engine.sync_playlist("https://music.youtube.com/playlist?list=PL-test", self.folder,
                engine.DownloadOptions(), selected_video_ids=set(), include_missing=True,
                prepared_playlist=("PL-test", "Playlist", 3, [song, missing, song], []))
        self.assertEqual(code, 0)
        self.assertFalse((self.folder / original).exists())
        self.assertEqual((self.folder / "Artist - Song.opus").read_bytes(), payload)
        manifest = engine.load_manifest(manifest_path)
        self.assertEqual(engine.manifest_by_video_id(manifest)["id"]["output_filename"], "Artist - Song.opus")
        entries = [s for s in (self.folder / "Playlist.m3u8").read_text().splitlines() if not s.startswith("#")]
        self.assertEqual(entries, ["Artist - Song.opus", "Artist - Another.opus", "Artist - Song.opus"])

    def test_two_videos_with_same_title_get_distinct_readable_names(self):
        first, second = track("one"), track("two")
        names.assign_filenames([first, second], self.folder, {}, migrate=True)
        self.assertEqual(first.filename, "Artist - Song.opus")
        self.assertEqual(second.filename, "Artist - Song (2).opus")

    def test_existing_collision_is_never_overwritten(self):
        song = track("id")
        (self.folder / song.filename).write_bytes(b"new recording")
        (self.folder / "Artist - Song.opus").write_bytes(b"old recording")
        names.assign_filenames([song], self.folder, {}, migrate=True)
        self.assertEqual(song.filename, "Artist - Song (2).opus")
        self.assertEqual((self.folder / song.filename).read_bytes(), b"new recording")
        self.assertEqual((self.folder / "Artist - Song.opus").read_bytes(), b"old recording")

    def test_legacy_match_accepts_punctuation_but_keeps_recording_versions_separate(self):
        song = track("one", artist="Chevy, CityGirl")
        other = track("two", "After Dark", "Mr.Kitty")
        legacy = ["Chevy & CityGirl - Song.opus", "Mr.Kitty - After Dark (Extended).opus"]
        names.assign_filenames([song, other], self.folder, {}, legacy, migrate=True)
        self.assertEqual(song.filename, legacy[0])
        self.assertEqual(other.filename, "Mr.Kitty - After Dark.opus")

    def test_ambiguous_legacy_names_are_not_guessed(self):
        song = track("one", artist="A, B")
        names.assign_filenames([song], self.folder, {}, ["A & B - Song.opus", "A+B - Song.opus"], migrate=True)
        self.assertEqual(song.filename, "A, B - Song.opus")

    def test_legacy_import_rejects_paths_and_comments(self):
        playlist = self.folder / "old.m3u8"
        playlist.write_text("#EXTM3U\nArtist - Song.opus\n../escape.opus\nD:\\other.opus\n", encoding="utf-8")
        self.assertEqual(names.read_legacy_playlist(playlist), ["Artist - Song.opus"])


if __name__ == "__main__":
    unittest.main()
