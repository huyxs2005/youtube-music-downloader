# YouTube Music Downloader v2.0.0 — WPF-UI Desktop

A portable Windows desktop release with the complete app and its supporting files.

## Download and run

1. Download **YouTubeMusicDownloader-Desktop-v2.0.0-win-x64.zip** from the assets below. The automatically generated **Source code** archives are for developers.
2. Right-click the ZIP and choose **Extract All**.
3. Open the extracted **YouTubeMusicDownloader-Desktop** folder and double-click **YouTubeMusicDownloader.Desktop.exe**.
4. Put your exported YouTube **cookies.txt** beside the EXE, or select it with **Add cookies.txt**. Existing valid cookie files are detected automatically.
5. Paste a playlist URL, choose a music folder, scan, select songs, and download.

Keep the entire extracted folder together. Python, .NET, FFmpeg, and FFprobe are included; normal users do not need to install them or run CMD/BAT files.

## What's new

- Native WPF-UI interface and a custom Windows app icon.
- Large song table with checkboxes, Select all, search, and status filters.
- Clickable ascending/descending sorting for title, artist, album, genre, duration, position, and file size.
- Dedicated Downloads tab with queued, downloading, downloaded, and failed statuses.
- Collapsible setup controls that give the song list more space after scanning.
- Required cookie-file validation, automatic discovery, and remembered file selection.
- Existing audio and filenames are reused during playlist updates.
- M3U8 files keep YouTube order and include existing local audio even when unchecked.

## Requirements and notes

- 64-bit Windows. Keep the app in a normal writable folder.
- A valid Netscape-format YouTube cookie file is required for downloading. Private cookies and downloaded music are never included in this release.
- Some downloads need the optional Docker PO-token provider; see the README for setup.
- This build is unsigned, so Windows may display an unknown-publisher warning.
- The ZIP's SHA-256 checksum is provided as a separate `.sha256` asset.

Validation: 44 Python tests and 50 desktop checks, including the packaged engine. Screenshots were inspected with 925-song sample playlists. A live YouTube download was not part of these checks.
