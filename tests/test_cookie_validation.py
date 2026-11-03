import tempfile
import time
import unittest
from pathlib import Path
from unittest.mock import patch
from dataclasses import asdict

import desktop_bridge as bridge
import ytmusic_downloader as engine

HEADER = "# Netscape HTTP Cookie File\n"


class CookieValidationTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.folder = Path(self.temp.name)
        self.path = self.folder / "cookies.txt"

    def tearDown(self):
        self.temp.cleanup()

    def write(self, domain=".youtube.com", expiry="0", prefix="", value="fixture-only"):
        self.path.write_text(HEADER + f"{prefix}{domain}\tTRUE\t/\tTRUE\t{expiry}\tTEST_COOKIE\t{value}\n", encoding="utf-8")

    def test_session_and_http_only_youtube_cookies_are_accepted(self):
        for prefix in ("", "#HttpOnly_"):
            self.write(prefix=prefix)
            self.assertEqual(bridge.validate_cookies(str(self.path)), str(self.path.resolve()))

    def test_future_expiry_is_accepted_and_expired_entries_are_ignored(self):
        self.write(expiry=str(int(time.time()) + 3600))
        with self.path.open("a", encoding="utf-8") as file:
            file.write(".youtube.com\tTRUE\t/\tTRUE\t1\tOLD_COOKIE\told\n")
        self.assertEqual(bridge.validate_cookies(str(self.path)), str(self.path.resolve()))

    def test_missing_empty_and_json_files_are_rejected(self):
        with self.assertRaises(ValueError): bridge.validate_cookies(None)
        with self.assertRaises(ValueError): bridge.validate_cookies(str(self.path))
        for contents in ("", "[]", '{"cookies": []}'):
            self.path.write_text(contents, encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "format"):
                bridge.validate_cookies(str(self.path))

    def test_unrelated_and_lookalike_domains_are_rejected(self):
        for domain in (".example.com", ".youtube.com.example.com", ".notyoutube.com", ".google.com"):
            self.write(domain=domain)
            with self.assertRaisesRegex(ValueError, "No YouTube cookies"):
                bridge.validate_cookies(str(self.path))

    def test_all_expired_or_empty_values_are_rejected(self):
        for expiry, value in (("1", "fixture-only"), ("0", "")):
            self.write(expiry=expiry, value=value)
            with self.assertRaisesRegex(ValueError, "No usable"):
                bridge.validate_cookies(str(self.path))

    def test_bom_and_music_subdomain_are_accepted(self):
        self.write(domain=".music.youtube.com")
        self.path.write_text(self.path.read_text(encoding="utf-8"), encoding="utf-8-sig")
        self.assertEqual(bridge.validate_cookies(str(self.path)), str(self.path.resolve()))

    def test_malformed_lines_are_rejected_without_leaking_contents(self):
        secret = "PRIVATE_FIXTURE_VALUE"
        for line in (f"bad\t{secret}", f".youtube.com\tTRUE\t/\tTRUE\tbad\tTEST\t{secret}",
                     f"youtube.com\tTRUE\t/\tTRUE\t0\tTEST\t{secret}"):
            self.path.write_text(HEADER + line + "\n", encoding="utf-8")
            with self.assertRaises(ValueError) as caught:
                bridge.validate_cookies(str(self.path))
            self.assertNotIn(secret, str(caught.exception))

    def test_backend_refuses_missing_cookies_before_download_or_writes(self):
        song = engine.Track(1, "a", None, "A", ["Artist"], None, None, "a.opus")
        snapshot = dict(url="https://music.youtube.com/playlist?list=PL-test", folder=str(self.folder),
                        playlistId="PL-test", title="Test", single=False, total=1, skipped=[], tracks=[asdict(song)])
        with patch.object(engine, "check_ffmpeg") as check, patch.object(engine, "sync_playlist") as sync:
            with self.assertRaisesRegex(ValueError, "Cookies required"):
                bridge.download(dict(snapshot=snapshot, selected=["a"]))
            check.assert_not_called()
            sync.assert_not_called()
        self.assertFalse((self.folder / engine.MANIFEST_NAME).exists())


if __name__ == "__main__":
    unittest.main()
