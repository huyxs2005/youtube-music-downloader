import json
import tempfile
import unittest
from contextlib import redirect_stdout
from io import StringIO
from pathlib import Path
from unittest.mock import patch

import ytmusic_downloader as downloader


def make_track(index: int, video_id: str, artist: str, title: str) -> downloader.Track:
    return downloader.Track(
        index=index,
        video_id=video_id,
        set_video_id=None,
        title=title,
        artists=[artist],
        album=None,
        thumbnail_url=None,
        filename=downloader.build_filename([artist], title, video_id),
    )


class PowerampM3U8Tests(unittest.TestCase):
    def test_selected_parent_gets_playlist_title_subfolder(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            parent_dir = Path(temp_dir)
            playlist_dir = parent_dir / "Road Trip _ Summer"

            with (
                patch.object(
                    downloader,
                    "fetch_playlist_tracks",
                    return_value=("playlist-id", "Road Trip : Summer", 0, [], []),
                ),
                redirect_stdout(StringIO()),
            ):
                result = downloader.sync_playlist(
                    "https://music.youtube.com/playlist?list=playlist-id",
                    parent_dir,
                    downloader.DownloadOptions(),
                    output_is_parent=True,
                )

            self.assertEqual(result, 0)
            self.assertTrue((playlist_dir / downloader.MANIFEST_NAME).is_file())
            self.assertTrue((playlist_dir / "Road Trip _ Summer.m3u8").is_file())
            self.assertFalse((parent_dir / downloader.MANIFEST_NAME).exists())

    def test_title_change_reuses_folder_with_matching_playlist_id(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            parent_dir = Path(temp_dir)
            existing_dir = parent_dir / "Old Playlist Name"
            existing_dir.mkdir()
            downloader.save_manifest(
                existing_dir / downloader.MANIFEST_NAME,
                "playlist-id",
                {},
                "Old Playlist Name",
                "Old Playlist Name.m3u8",
            )
            (existing_dir / "Old Playlist Name.m3u8").write_text(
                "#EXTM3U\n",
                encoding="utf-8",
            )

            with (
                patch.object(
                    downloader,
                    "fetch_playlist_tracks",
                    return_value=("playlist-id", "New Playlist Name", 0, [], []),
                ),
                redirect_stdout(StringIO()),
            ):
                result = downloader.sync_playlist(
                    "https://music.youtube.com/playlist?list=playlist-id",
                    parent_dir,
                    downloader.DownloadOptions(),
                    output_is_parent=True,
                )

            self.assertEqual(result, 0)
            self.assertTrue((existing_dir / downloader.MANIFEST_NAME).is_file())
            self.assertTrue((existing_dir / "New Playlist Name.m3u8").is_file())
            self.assertFalse((parent_dir / "New Playlist Name").exists())

    def test_new_filenames_are_unicode_and_collision_resistant(self) -> None:
        first = downloader.build_filename(["宇多田ヒカル"], "花束を君に", "video-one")
        second = downloader.build_filename(["宇多田ヒカル"], "花束を君に", "video-two")

        self.assertEqual(first, "宇多田ヒカル - 花束を君に [video-one].opus")
        self.assertEqual(second, "宇多田ヒカル - 花束を君に [video-two].opus")
        self.assertNotEqual(first, second)

    def test_m3u8_uses_current_order_and_omits_missing_audio(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            output_dir = Path(temp_dir)
            missing = make_track(1, "missing-id", "Missing Artist", "Missing Song")
            unicode_track = make_track(2, "unicode-id", "宇多田ヒカル", "花束を君に")
            last = make_track(3, "last-id", "Last Artist", "Last Song")
            (output_dir / unicode_track.filename).write_bytes(b"audio")
            (output_dir / last.filename).write_bytes(b"audio")
            entries = {
                track.video_id: downloader.manifest_entry(track)
                for track in [missing, unicode_track, last]
            }

            m3u8_path, count = downloader.write_poweramp_m3u8(
                output_dir,
                "日本語プレイリスト",
                [missing, unicode_track, last],
                entries,
            )

            self.assertEqual(count, 2)
            self.assertEqual(m3u8_path.name, "日本語プレイリスト.m3u8")
            self.assertEqual(
                m3u8_path.read_text(encoding="utf-8"),
                "#EXTM3U\n"
                "#EXTINF:-1,宇多田ヒカル - 花束を君に\n"
                f"{unicode_track.filename}\n"
                "#EXTINF:-1,Last Artist - Last Song\n"
                f"{last.filename}\n",
            )
            self.assertFalse((output_dir / f"{m3u8_path.name}.tmp").exists())

    def test_reordered_legacy_manifest_keeps_numbered_files_without_download(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            output_dir = Path(temp_dir)
            first_filename = "001 - Artist A - Song A.opus"
            second_filename = "002 - Artist B - Song B.opus"
            (output_dir / first_filename).write_bytes(b"first")
            (output_dir / second_filename).write_bytes(b"second")
            manifest = {
                "playlist_id": "playlist-id",
                "tracks": [
                    {**downloader.manifest_entry(make_track(1, "a-id", "Artist A", "Song A")), "output_filename": first_filename},
                    {**downloader.manifest_entry(make_track(2, "b-id", "Artist B", "Song B")), "output_filename": second_filename},
                ],
            }
            (output_dir / downloader.MANIFEST_NAME).write_text(
                json.dumps(manifest, ensure_ascii=False),
                encoding="utf-8",
            )
            reordered = [
                make_track(1, "b-id", "Artist B", "Song B"),
                make_track(2, "a-id", "Artist A", "Song A"),
            ]
            newly_generated_names = [track.filename for track in reordered]

            with (
                patch.object(
                    downloader,
                    "fetch_playlist_tracks",
                    return_value=("playlist-id", "Road Trip", 2, reordered, []),
                ),
                patch.object(downloader, "apply_track_metadata", return_value=False) as metadata_update,
                patch.object(downloader, "download_track_job") as download_job,
                redirect_stdout(StringIO()),
            ):
                result = downloader.sync_playlist(
                    "https://music.youtube.com/playlist?list=playlist-id",
                    output_dir,
                    downloader.DownloadOptions(),
                )

            self.assertEqual(result, 0)
            download_job.assert_not_called()
            metadata_update.assert_not_called()
            self.assertEqual((output_dir / first_filename).read_bytes(), b"first")
            self.assertEqual((output_dir / second_filename).read_bytes(), b"second")
            for generated_name in newly_generated_names:
                self.assertFalse((output_dir / generated_name).exists())

            migrated = json.loads((output_dir / downloader.MANIFEST_NAME).read_text(encoding="utf-8"))
            migrated_by_id = {item["videoId"]: item for item in migrated["tracks"]}
            self.assertEqual(migrated_by_id["b-id"]["playlist_index"], 1)
            self.assertEqual(migrated_by_id["b-id"]["output_filename"], second_filename)
            self.assertEqual(migrated_by_id["a-id"]["playlist_index"], 2)
            self.assertEqual(migrated_by_id["a-id"]["output_filename"], first_filename)
            self.assertEqual(migrated["m3u8_filename"], "Road Trip.m3u8")
            self.assertEqual(
                (output_dir / "Road Trip.m3u8").read_text(encoding="utf-8"),
                "#EXTM3U\n"
                "#EXTINF:-1,Artist B - Song B\n"
                f"{second_filename}\n"
                "#EXTINF:-1,Artist A - Song A\n"
                f"{first_filename}\n",
            )

    def test_retry_regenerates_playlist_and_title_change_removes_only_old_generated_m3u8(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            output_dir = Path(temp_dir)
            track = make_track(1, "new-id", "Beyoncé", "Déjà Vu")
            old_playlist = output_dir / "Old Name.m3u8"
            unrelated_playlist = output_dir / "Keep Me.m3u8"
            old_playlist.write_text("old", encoding="utf-8")
            unrelated_playlist.write_text("user playlist", encoding="utf-8")
            (output_dir / downloader.MANIFEST_NAME).write_text(
                json.dumps(
                    {
                        "playlist_id": "playlist-id",
                        "playlist_title": "Old Name",
                        "m3u8_filename": old_playlist.name,
                        "tracks": [],
                    }
                ),
                encoding="utf-8",
            )

            def successful_download(queued_track, queued_output_dir, _options):
                temp_output = queued_output_dir / ".successful-download.opus"
                temp_output.write_bytes(b"audio")
                return queued_track, temp_output, None

            fetch_result = ("playlist-id", "New Name", 1, [track], [])
            with (
                patch.object(downloader, "fetch_playlist_tracks", return_value=fetch_result),
                patch.object(downloader, "apply_track_metadata", return_value=False),
                patch.object(
                    downloader,
                    "download_track_job",
                    return_value=(track, None, RuntimeError("download failed")),
                ),
                redirect_stdout(StringIO()),
            ):
                first_result = downloader.sync_playlist(
                    "https://music.youtube.com/playlist?list=playlist-id",
                    output_dir,
                    downloader.DownloadOptions(),
                )

            self.assertEqual(first_result, 1)
            self.assertEqual((output_dir / "New Name.m3u8").read_text(encoding="utf-8"), "#EXTM3U\n")
            self.assertTrue((output_dir / downloader.FAILED_DOWNLOADS_NAME).exists())
            error_text = (output_dir / downloader.DOWNLOAD_ERRORS_NAME).read_text(
                encoding="utf-8"
            )
            self.assertEqual(error_text, downloader.failed_track_line(track) + "\n")
            self.assertNotIn("download failed", error_text)
            self.assertFalse(old_playlist.exists())
            self.assertTrue(unrelated_playlist.exists())

            with (
                patch.object(downloader, "fetch_playlist_tracks", return_value=fetch_result),
                patch.object(downloader, "apply_track_metadata", return_value=False),
                patch.object(downloader, "download_track_job", side_effect=successful_download),
                redirect_stdout(StringIO()),
            ):
                retry_result = downloader.sync_playlist(
                    "https://music.youtube.com/playlist?list=playlist-id",
                    output_dir,
                    downloader.DownloadOptions(),
                )

            self.assertEqual(retry_result, 0)
            self.assertFalse((output_dir / downloader.FAILED_DOWNLOADS_NAME).exists())
            self.assertFalse((output_dir / downloader.DOWNLOAD_ERRORS_NAME).exists())
            playlist_text = (output_dir / "New Name.m3u8").read_text(encoding="utf-8")
            self.assertIn("#EXTINF:-1,Beyoncé - Déjà Vu", playlist_text)
            self.assertIn(track.filename, playlist_text)
            self.assertTrue(unrelated_playlist.exists())


if __name__ == "__main__":
    unittest.main()
