# YouTube Music Downloader v1.0

The first packaged Windows release.

## What is included

- A self-contained CMD downloader with its own private Python runtime
- Bundled FFmpeg and FFprobe, so no PATH setup is required
- Guided WSL 2 and Docker Desktop setup for the PO-token provider
- No Docker account or login required
- Optional guided `cookies.txt` setup; cookies are never included in the installer
- Stable OPUS filenames and Poweramp-compatible UTF-8 M3U8 playlists
- Playlist reordering without redownloading or renaming existing audio
- Single-song insertion at the top of an existing downloaded playlist
- Metadata, 1008px artwork, retries, automatic worker counts, URL validation, and failed-download reports

## Installation

1. Download `YouTube-Music-Downloader-Setup-v1.0.exe` and its `.sha256` file.
2. Because this is the free unsigned build, Windows may show SmartScreen. Verify the SHA-256 checksum, then choose **More info > Run anyway** only if it matches this release.
3. Complete the installer and leave prerequisite setup selected.
4. Approve WSL/Docker installation if needed. Setup may restart Windows once and resume automatically.
5. Docker login is not required.

The installer does not contain `cookies.txt` and does not access or remove existing music folders during installation or uninstallation.
