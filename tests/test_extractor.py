import os
from pathlib import Path
import subprocess
import tempfile
import unittest
import zipfile


@unittest.skipUnless(os.name == "nt", "The optional extractor uses the Windows .NET Framework")
class ExtractorTests(unittest.TestCase):
    def compile_extractor(self, folder, entries):
        root = Path(__file__).resolve().parents[1]
        archive = folder / "fixture.zip"
        with zipfile.ZipFile(archive, "w") as output:
            for name, data in entries.items():
                output.writestr(name, data)
        compiler = Path(os.environ["WINDIR"]) / "Microsoft.NET/Framework64/v4.0.30319/csc.exe"
        if not compiler.exists():
            self.skipTest("Windows C# compiler unavailable")
        executable = folder / "extractor.exe"
        result = subprocess.run([str(compiler), "/nologo", "/target:winexe", "/reference:System.Windows.Forms.dll",
            "/reference:System.Drawing.dll", "/reference:System.IO.Compression.dll", "/reference:System.IO.Compression.FileSystem.dll",
            f"/resource:{archive},ReleaseArchive", f"/out:{executable}", str(root / "installer/DesktopExtractor.cs")],
            capture_output=True, text=True, timeout=30)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        return executable

    def test_extracts_into_inner_app_folder_and_preserves_private_files(self):
        with tempfile.TemporaryDirectory(prefix="ytm-extractor-check-") as temporary:
            folder = Path(temporary)
            executable = self.compile_extractor(folder, {
                "YouTubeMusicDownloader-Desktop/YouTubeMusicDownloader.Desktop.exe": b"fixture launcher",
                "YouTubeMusicDownloader-Desktop/app/fixture.dll": b"fixture support file"})
            destination = folder / "version-folder"
            app = destination / "YouTubeMusicDownloader-Desktop"
            app.mkdir(parents=True)
            (app / "cookies.txt").write_text("private fixture", encoding="utf-8")
            result = subprocess.run([str(executable), "--extract-only", str(destination)], timeout=30)
            self.assertEqual(result.returncode, 0)
            self.assertEqual((app / "app/fixture.dll").read_bytes(), b"fixture support file")
            self.assertEqual((app / "cookies.txt").read_text(encoding="utf-8"), "private fixture")
            self.assertTrue((app / "YouTubeMusicDownloader.Desktop.exe").is_file())
            self.assertFalse((destination / "YouTubeMusicDownloader.Desktop.exe").exists())

    def test_rejects_archive_paths_outside_destination(self):
        with tempfile.TemporaryDirectory(prefix="ytm-extractor-path-check-") as temporary:
            folder = Path(temporary)
            executable = self.compile_extractor(folder, {"../outside.dll": b"invalid fixture"})
            result = subprocess.run([str(executable), "--extract-only", str(folder / "destination")], timeout=30)
            self.assertNotEqual(result.returncode, 0)
            self.assertFalse((folder / "outside.dll").exists())
