# YouTube Music Downloader v2.1.0 — Black & Red

## New look

- YouTube-style black and charcoal surfaces with red buttons, selection accents, progress indicators, and sort arrows.
- A new red rounded-rectangle app icon with a white triangle pointing down, suggesting download.
- Updated EXE, taskbar/window icon, title bar, and sidebar branding.
- The large playlist table, Downloads tab, cookie checks, and YouTube-order M3U8 sync work as before.

## Download and run

1. Download **YouTubeMusicDownloader-Desktop-v2.1.0-win-x64.zip** below. Choose this desktop ZIP rather than the automatically generated Source code archives.
2. Right-click the ZIP and choose **Extract All**.
3. Open the extracted **YouTubeMusicDownloader-Desktop** folder and double-click **YouTubeMusicDownloader.Desktop.exe**.
4. Put your exported YouTube **cookies.txt** beside the EXE, or use your remembered cookie-file location.

Keep the whole extracted folder together. The package includes .NET, the Python download engine, FFmpeg, and FFprobe. No separate Python/.NET installation or BAT launcher is required.

When upgrading, close the old app, extract this release into a new folder, and keep using your existing music folders and playlist manifests. Existing valid cookies can be reused.

## Notes

- Windows x64; unsigned build.
- Cookies and downloaded music are not included. Some downloads require the optional Docker PO-token provider described in the README.
- A SHA-256 checksum is included as a separate release asset.
- Validation: 44 Python tests, 50 desktop checks, screenshot checks at normal and compact sizes, and a portable engine check outside the source folder. No live YouTube download was performed.
