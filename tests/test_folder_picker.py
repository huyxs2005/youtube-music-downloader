import unittest
from unittest.mock import patch

import ytmusic_downloader as downloader


PLAYLIST_URL = "https://music.youtube.com/playlist?list=playlist-id"
SONG_URL = "https://music.youtube.com/watch?v=video-id"


class FolderPickerTests(unittest.TestCase):
    def test_double_click_flow_uses_folder_picker(self) -> None:
        args = downloader.parse_args([])

        with (
            patch("builtins.input", return_value=PLAYLIST_URL),
            patch.object(
                downloader,
                "choose_output_folder",
                return_value=r"D:\Music\Selected Playlist",
            ) as folder_picker,
        ):
            result = downloader.ask_for_missing_inputs(args)

        folder_picker.assert_called_once_with("Choose where to save this playlist")
        self.assertEqual(result.output, r"D:\Music\Selected Playlist")

    def test_command_line_url_does_not_open_folder_picker(self) -> None:
        args = downloader.parse_args([PLAYLIST_URL])

        with patch.object(downloader, "choose_output_folder") as folder_picker:
            result = downloader.ask_for_missing_inputs(args)

        folder_picker.assert_not_called()
        self.assertIsNone(result.output)

    def test_next_playlist_uses_folder_picker(self) -> None:
        args = downloader.parse_args([PLAYLIST_URL, "--output", r"D:\Music\Old"])

        with (
            patch("builtins.input", return_value=PLAYLIST_URL),
            patch.object(
                downloader,
                "choose_output_folder",
                return_value=r"D:\Music\Next Playlist",
            ) as folder_picker,
        ):
            result = downloader.ask_for_next_playlist(args)

        folder_picker.assert_called_once_with("Choose where to save the next playlist")
        self.assertEqual(result.output, r"D:\Music\Next Playlist")

    def test_double_click_song_flow_requires_existing_playlist_folder(self) -> None:
        args = downloader.parse_args([])

        with (
            patch("builtins.input", return_value=SONG_URL),
            patch.object(
                downloader,
                "choose_output_folder",
                return_value=r"D:\Music\Existing Playlist",
            ) as folder_picker,
        ):
            result = downloader.ask_for_missing_inputs(args)

        folder_picker.assert_called_once_with(
            "Choose the existing playlist folder for this song"
        )
        self.assertEqual(result.output, r"D:\Music\Existing Playlist")

    def test_cancelling_playlist_folder_picker_ends_process(self) -> None:
        args = downloader.parse_args([])

        with (
            patch("builtins.input", return_value=PLAYLIST_URL),
            patch.object(downloader, "choose_output_folder", return_value=None),
        ):
            with self.assertRaises(SystemExit) as raised:
                downloader.ask_for_missing_inputs(args)

        self.assertEqual(raised.exception.code, downloader.USER_CANCELLED_EXIT_CODE)

    def test_cancelling_song_folder_picker_ends_process(self) -> None:
        args = downloader.parse_args([])

        with (
            patch("builtins.input", return_value=SONG_URL),
            patch.object(downloader, "choose_output_folder", return_value=None),
        ):
            with self.assertRaises(SystemExit) as raised:
                downloader.ask_for_missing_inputs(args)

        self.assertEqual(raised.exception.code, downloader.USER_CANCELLED_EXIT_CODE)

    def test_command_line_song_url_is_accepted(self) -> None:
        args = downloader.parse_args(
            [SONG_URL, "--output", r"D:\Music\Existing Playlist"]
        )

        result = downloader.ask_for_missing_inputs(args)

        self.assertEqual(result.playlist_url, SONG_URL)
        self.assertEqual(result.output, r"D:\Music\Existing Playlist")


if __name__ == "__main__":
    unittest.main()
