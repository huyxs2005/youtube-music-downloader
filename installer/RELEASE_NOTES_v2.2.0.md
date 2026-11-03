# YouTube Music Downloader v2.2.0

Download **YouTubeMusicDownloader-Desktop-v2.2.0-win-x64.zip**, choose **Extract All**, and open **YouTubeMusicDownloader.Desktop.exe**. Keep the `app` folder beside it. No BAT file, CMD commands, or separate Python/.NET/FFmpeg installation is needed for normal use.

- Clean portable layout: a launcher EXE beside one `app` support folder.
- Downloads default beside the launcher, with a named folder for each playlist.
- Custom order checkbox and drag-to-reorder songs; sync saves the arrangement in the M3U8. YouTube order remains the default.
- Small song thumbnails, with clickable higher-resolution previews.
- Smooth sidebar toggle, a simpler Playlist page, and clearer local-file status.
- Flexible column resizing, ellipsis for narrow cells, and double-click auto-fit.
- Live detected-song and unavailable-item counters while scanning.
- Clear URL/fetch warnings and brief successful cookie-verification notifications.
- Background file-size estimates marked with `~`; downloaded songs show their actual file size. Missing albums show None.
- Smaller package using shared FFmpeg libraries, English-only framework resources, and only the image features this app uses.

Reuse your own private `cookies.txt` beside the launcher or choose it in the app. Keep existing music and its playlist manifest together. Cookies and downloaded music are excluded from the release.

Windows x64; unsigned build. A separate SHA-256 checksum is supplied. Some YouTube downloads need the optional Docker token provider described in the README.

Validation: 47 Python tests and 64 WPF/bridge checks passed. The extracted release engine, shared FFmpeg/FFprobe, bundled runtimes, icon, playlist order, and cookie exclusion passed an isolated package check. No live YouTube download was performed.
