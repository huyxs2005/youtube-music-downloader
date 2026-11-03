# YouTube Music Downloader v2.1.1 — Select-all header button

- Replaced the static check mark in the song table's top-left corner with a clickable selection button.
- Click once to select every scanned song; click again to deselect all. Filtered-out songs are included.
- The button shows unchecked, mixed, and all-selected states, with a tooltip and accessible action label.
- Selection is locked while downloads run. Table sorting and M3U8 order are unchanged.
- Bulk selection updates are batched so large playlists stay responsive.

## Download and run

Download **YouTubeMusicDownloader-Desktop-v2.1.1-win-x64.zip**, choose **Extract All**, and run **YouTubeMusicDownloader.Desktop.exe** from the extracted folder. Keep the entire folder together. Python, .NET, FFmpeg, and FFprobe are included.

Reuse your private YouTube `cookies.txt` and existing music folders. Cookies and downloaded music are not included. Some downloads require the optional Docker PO-token provider described in the README.

Windows x64; unsigned build. A SHA-256 checksum is provided as a separate release asset.

Validation: 44 Python tests, 57 desktop checks, and real header-button clicks with a 925-song sample playlist. A live YouTube download was not part of these checks.
