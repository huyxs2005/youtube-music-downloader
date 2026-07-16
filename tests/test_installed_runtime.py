import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import ytmusic_downloader as downloader


class InstalledRuntimeTests(unittest.TestCase):
    def test_source_application_dir_is_script_folder(self) -> None:
        self.assertEqual(
            downloader.application_dir(),
            Path(downloader.__file__).resolve().parent,
        )

    def test_frozen_application_dir_and_cookie_path_use_executable_folder(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            executable = Path(temp_dir) / "YouTubeMusicDownloader.exe"
            with (
                patch.object(downloader.sys, "frozen", True, create=True),
                patch.object(downloader.sys, "executable", str(executable)),
            ):
                self.assertEqual(downloader.application_dir(), Path(temp_dir))
                self.assertEqual(
                    downloader.default_cookies_path(),
                    Path(temp_dir) / "cookies.txt",
                )

    def test_bundled_tools_are_prepended_to_path(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            app_dir = Path(temp_dir)
            tools_dir = app_dir / "tools"
            tools_dir.mkdir()
            with (
                patch.object(downloader, "application_dir", return_value=app_dir),
                patch.dict(os.environ, {"PATH": "existing-path"}, clear=False),
            ):
                downloader.configure_bundled_tools()
                self.assertEqual(
                    os.environ["PATH"].split(os.pathsep)[0],
                    str(tools_dir),
                )

    def test_docker_candidates_do_not_contain_a_hardcoded_username(self) -> None:
        with patch.dict(
            os.environ,
            {
                "ProgramFiles": r"C:\Program Files",
                "LOCALAPPDATA": r"C:\Users\Example\AppData\Local",
            },
            clear=False,
        ):
            candidates = downloader.docker_desktop_candidates()

        self.assertIn(
            Path(r"C:\Program Files\Docker\Docker\Docker Desktop.exe"),
            candidates,
        )
        self.assertIn(
            Path(
                r"C:\Users\Example\AppData\Local\Programs\DockerDesktop\Docker Desktop.exe"
            ),
            candidates,
        )
        self.assertNotIn("Huy", "\n".join(str(path) for path in candidates))


if __name__ == "__main__":
    unittest.main()
