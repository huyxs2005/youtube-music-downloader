# YouTube Music Downloader v2.2.3

- The desktop app now writes the complete M3U8 playlist order, including filenames for songs that have not been downloaded yet. Checkboxes still control which audio files are downloaded. Missing references become playable when those files are downloaded later; some players hide missing entries until the playlist is refreshed.
- Repeated songs keep their separate playlist positions, while the audio is downloaded only once. The complete original order is retained in the manifest for recovery.
- Added **Open download folder** after downloading, including runs with failed songs and scans of existing downloads. It opens the actual playlist folder in File Explorer.
- Replaced user-facing "sync" wording with download wording, including **Download selected** and **Download completed**.

Close the old app before extracting over it. Keep the launcher and `app` subfolder together, and preserve your private cookies and playlist folders. Regular ZIP and optional **…-extract.exe** downloads contain the same app; the extractor opens the inner app folder when finished.

No missing songs are automatically downloaded just because their references appear in the M3U8. Unavailable YouTube items without usable song metadata remain excluded.

Validation: 56 Python tests and 76 WPF/bridge checks passed, including complete playlists with missing and repeated songs, single-download handling of repeated audio, and opening the correct completed-download folder.
