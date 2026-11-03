# YouTube Music Downloader v2.2.1

- **Multiple select:** hold a song's checkbox and drag up or down to select a contiguous range. Start on a checked box to deselect the range. Drag back toward the first song to shorten the range. Hold near the table's top or bottom to scroll while selecting. Filtered-out songs stay unchanged, and selection remains locked during downloads.
- **Extract & open folder:** download **YouTubeMusicDownloader-Desktop-v2.2.1-win-x64-extract.exe** and press **Extract**. The inner `YouTubeMusicDownloader-Desktop` folder opens automatically afterward. Choose `D:\` with Browse to get `D:\YouTubeMusicDownloader-Desktop-v2.2.1-win-x64\YouTubeMusicDownloader-Desktop`.
- The regular **ZIP** is still available and contains the same portable app. Windows controls which folder opens when using its built-in Extract All.

Run `YouTubeMusicDownloader.Desktop.exe` in the inner folder, keeping its `app` subfolder alongside it. Place your own private `cookies.txt` beside the launcher. Existing music and cookies are not included in either download and are preserved when extracting over an existing copy.

Windows x64; unsigned downloads. SHA-256 files are supplied for both the ZIP and optional extractor. No app installation or BAT file is required. Optional Docker support is unchanged.

Validation: 49 Python tests, including extractor path protection and preservation of private files, and 69 WPF/bridge checks passed. No live YouTube download was performed.
