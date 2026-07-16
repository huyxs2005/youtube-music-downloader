import io
import unittest
from concurrent.futures import ThreadPoolExecutor
from contextlib import redirect_stderr, redirect_stdout
from unittest.mock import patch

import ytmusic_downloader as downloader


class QuietOptionalProviderTests(unittest.TestCase):
    def test_unavailable_optional_provider_prints_nothing(self) -> None:
        stdout = io.StringIO()
        stderr = io.StringIO()

        with (
            patch.object(downloader, "ensure_docker_desktop_running", return_value=False),
            redirect_stdout(stdout),
            redirect_stderr(stderr),
        ):
            downloader.ensure_po_provider_running()

        self.assertEqual(stdout.getvalue(), "")
        self.assertEqual(stderr.getvalue(), "")

    def test_yt_dlp_logger_discards_token_provider_messages(self) -> None:
        logger = downloader.QuietYtdlpLogger()

        self.assertIsNone(logger.debug("debug"))
        self.assertIsNone(logger.info("info"))
        self.assertIsNone(logger.warning("token provider warning"))
        self.assertIsNone(logger.error("docker token provider error"))

    def test_concurrent_workers_initialize_yt_dlp_plugins_only_once(self) -> None:
        original_initialized = downloader._YT_DLP_PLUGINS_INITIALIZED
        downloader._YT_DLP_PLUGINS_INITIALIZED = False
        try:
            with patch.object(downloader, "gen_extractor_classes") as initialize:
                with ThreadPoolExecutor(max_workers=4) as executor:
                    futures = [
                        executor.submit(downloader.initialize_yt_dlp_plugins)
                        for _ in range(8)
                    ]
                    for future in futures:
                        future.result()

            initialize.assert_called_once_with()
        finally:
            downloader._YT_DLP_PLUGINS_INITIALIZED = original_initialized

    def test_stderr_filter_hides_only_duplicate_bgutils_registration(self) -> None:
        output = io.StringIO()
        filtered = downloader.DuplicateProviderStderrFilter(output)
        duplicate = (
            "Error while importing module "
            "'yt_dlp_plugins.extractor.getpot_bgutil_http'\n"
            "Traceback (most recent call last):\n"
            "AssertionError: PoTokenProvider BgUtilHTTP already registered\n"
        )

        self.assertEqual(filtered.write(duplicate), len(duplicate))
        filtered.write("Real download error\n")

        self.assertEqual(output.getvalue(), "Real download error\n")

    def test_stderr_filter_does_not_hide_other_plugin_import_errors(self) -> None:
        output = io.StringIO()
        filtered = downloader.DuplicateProviderStderrFilter(output)
        real_plugin_error = (
            "Error while importing module "
            "'yt_dlp_plugins.extractor.some_other_plugin'\n"
            "RuntimeError: broken plugin\n"
        )

        filtered.write(real_plugin_error)

        self.assertEqual(output.getvalue(), real_plugin_error)


if __name__ == "__main__":
    unittest.main()
