# YouTube Music Downloader

Download a YouTube Music playlist to ordered `.opus` files.

The script reads the playlist with `ytmusicapi`, then downloads each individual
`videoId` with `yt-dlp`. It does not use yt-dlp playlist parsing.

## Setup

1. Install Python for Windows from <https://www.python.org/downloads/windows/>.
2. Install the Python packages:

   ```powershell
   pip install ytmusicapi yt-dlp
   ```

3. Install ffmpeg and add it to `PATH`.

   One simple option is:

   ```powershell
   winget install --id Gyan.FFmpeg --exact
   ```

4. Verify the tools:

   ```powershell
   python --version
   ffmpeg -version
   ```

If YouTube starts failing on many tracks, update yt-dlp:

```powershell
python -m pip install -U yt-dlp
```

## Easy Usage

Double-click `Download Playlist.bat`.

It will ask for:

```text
Paste the YouTube Music playlist URL:
Output folder:
```

Paste your playlist link, then press Enter. For the output folder, paste a
folder like `D:\Music\My Playlist`, or press Enter to use the default
`downloads` folder next to the script.

If YouTube shows a message like `Sign in to confirm you're not a bot`, export
cookies with the browser extension `Get cookies.txt LOCALLY`. Save the exported
file as `cookies.txt` in the same folder as `ytmusic_downloader.py` and
`Download Playlist.bat`.

On the next run, the downloader automatically uses:

```text
cookies.txt
```

Missing songs download 10 at a time by default. Already downloaded songs are
still skipped, and renamed songs are handled before downloads start.

## PowerShell Usage

```powershell
python ytmusic_downloader.py "https://music.youtube.com/playlist?list=PLAYLIST_ID" --output "D:\Music\My Playlist"
```

To change how many songs download at the same time:

```powershell
python ytmusic_downloader.py "https://music.youtube.com/playlist?list=PLAYLIST_ID" --output "D:\Music\My Playlist" --workers 5
```

You can also choose a different cookies file path:

```powershell
python ytmusic_downloader.py "https://music.youtube.com/playlist?list=PLAYLIST_ID" --output "D:\Music\My Playlist" --cookies "C:\Users\Huy\Downloads\youtube-cookies.txt"
```

Files are named in playlist order:

```text
001 - Artist - Title.opus
002 - Artist - Title.opus
003 - Artist - Title.opus
```

The output folder also contains `playlist_manifest.json`. The manifest stores
the playlist id, stable YouTube `videoId`, optional `setVideoId`, title,
artists, playlist index, and output filename. On later runs, the script uses
the manifest to skip already downloaded songs and rename files when playlist
order or metadata changes.
