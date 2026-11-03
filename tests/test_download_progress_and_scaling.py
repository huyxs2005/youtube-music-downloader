import contextlib
import io
from pathlib import Path
import tempfile
import unittest
from unittest.mock import MagicMock, patch

import ytmusic_downloader as engine


class DownloadProgressAndScalingTests(unittest.TestCase):
    def test_sparse_selection_batches_status_and_limits_manifest_writes(self):
        with tempfile.TemporaryDirectory() as temporary:
            folder = Path(temporary)
            tracks = [engine.Track(i, f"song-{i}", None, f"Song {i}", ["Artist"], None, None, f"song-{i}.opus") for i in range(1, 1001)]
            selected = {"song-1", "song-2"}
            updates, events = [], []
            def download(track, output, options):
                path = output / (track.video_id + ".temp.opus")
                path.write_bytes(b"fixture audio")
                return track, path, None
            with contextlib.redirect_stdout(io.StringIO()), patch.object(engine, "save_manifest", wraps=engine.save_manifest) as saves, \
                 patch.object(engine, "download_track_job", side_effect=download), patch.object(engine, "apply_track_metadata", return_value=False):
                result = engine.sync_playlist("https://music.youtube.com/playlist?list=PL-large", folder, engine.DownloadOptions(),
                    selected_video_ids=selected, prepared_playlist=("PL-large", "Large", 1000, tracks, []),
                    on_batch=lambda batch: updates.append(batch), on_track=lambda track, status: events.append((track.video_id, status)))
            self.assertEqual(result, 0)
            self.assertEqual(saves.call_count, 4, "One preparation save, two completed downloads, and one final save")
            self.assertEqual(len(updates), 1)
            self.assertEqual(len(updates[0]), 1000)
            self.assertEqual(len(events), 4, "Only selected songs should generate individual status events")
            self.assertTrue(all(video_id in selected for video_id, _ in events))
            contents=(folder / "Large.m3u8").read_text(encoding="utf-8")
            self.assertEqual([line for line in contents.splitlines() if line and not line.startswith('#')], ["song-1.opus", "song-2.opus"])

    def test_transfer_hooks_report_percentage_and_processing_without_rewriting_cookie_export(self):
        with tempfile.TemporaryDirectory() as temporary:
            folder=Path(temporary)
            song=engine.Track(1,"fixture",None,"Song",["Artist"],None,None,"song.opus")
            values=[]
            options=engine.DownloadOptions(cookies_file="fixture-cookies.txt",on_progress=lambda track, percent, stage: values.append((percent,stage)))
            context=MagicMock()
            downloader=context.__enter__.return_value
            def factory(settings):
                self.assertNotIn("cookiefile",settings)
                def download(urls):
                    hook=settings["progress_hooks"][0]
                    hook(dict(status="downloading",downloaded_bytes=25,total_bytes=100))
                    hook(dict(status="finished"))
                    (folder / "temporary.opus").write_bytes(b"fixture")
                downloader.download.side_effect=download
                return context
            with patch.object(engine,"initialize_yt_dlp_plugins"),patch.object(engine,"YoutubeDL",side_effect=factory):
                engine.run_yt_dlp_download(song,folder,options,folder / "temporary","bestaudio")
            self.assertEqual(values,[(25.0,"Downloading"),(100.0,"Processing")])
            downloader.cookiejar.load.assert_called_once_with("fixture-cookies.txt")

    def test_error_messages_remove_credentials_and_signed_query_parameters(self):
        result=engine.safe_error_message("HTTP 403 https://user:password@example.com/audio?secret=token\nCookie: private-cookie\nAuthorization: private-header")
        for secret in ("password","secret=token","private-cookie","private-header"):
            self.assertNotIn(secret,result)
        self.assertIn("HTTP 403",result)

    def test_bundled_quickjs_is_enabled_explicitly(self):
        with patch.object(engine.shutil,"which",side_effect=lambda name: "C:/app/tools/qjs.exe" if name=="qjs" else None):
            self.assertEqual(engine.javascript_runtimes(),{"quickjs":{"path":"C:/app/tools/qjs.exe"}})
