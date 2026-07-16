# YouTube Music Downloader

Download a YouTube Music playlist into stable `.opus` audio files and a
Poweramp-compatible `.m3u8` playlist.

WARNING: USE A THROWAWAY EMAIL IF YOU DECIDE TO USE THE cookie.txt SINCE YOU CAN GET A BAN FROM YOUTUBE, I WON'T HOLD RESONSIBLE 

This project uses:

* `ytmusicapi` to read the playlist order from YouTube Music
* `yt-dlp` to download each song
* `ffmpeg` to convert/extract audio to `.opus`
* `mutagen` to embed artist/title tags and cover thumbnails into `.opus`
* optional browser cookies for login/bot-check issues
* optional BgUtils PO-token provider through Docker for YouTube 403 errors

New downloads use filenames that do not depend on playlist position:

```text
Artist - Title [videoId].opus
```

The current YouTube Music order is stored in a title-based `.m3u8` file. The
`playlist_manifest.json` file permanently associates each YouTube `videoId`
with its audio filename, so reordering a playlist does not rename, redownload,
or modify existing audio. Existing numbered files such as
`001 - Artist - Title.opus` remain unchanged after migration.

---

## Features

* Downloads YouTube Music playlists as `.opus`
* Adds a single song to position 1 of an existing downloaded playlist
* Embeds title, artist, album, track number, and cover thumbnail metadata
* Generates a UTF-8 Poweramp `.m3u8` in current YouTube Music order
* Skips songs that were already downloaded
* Keeps every existing manifest filename unchanged when playlist order changes
* Uses stable, collision-resistant filenames containing `videoId` for new songs
* Writes `failed_downloads.txt` in the music folder when any tracks fail
* Skips unavailable playlist items that have no `videoId`
* Supports cookies with `cookies.txt`
* Supports PO-token provider through Docker for HTTP 403 issues
* Can be launched by double-clicking `Download Playlist.bat`

---

## Requirements

Install these first:

1. Python for Windows
   https://www.python.org/downloads/windows/

2. FFmpeg

   ```powershell
   winget install --id Gyan.FFmpeg --exact
   ```

3. Docker Desktop
   Required only if you want automatic PO-token support for YouTube 403 errors.

4. Python packages

   ```powershell
   python -m pip install -U ytmusicapi yt-dlp mutagen bgutil-ytdlp-pot-provider
   ```

Check that Python and FFmpeg work:

```powershell
python --version
ffmpeg -version
```

---

## Project Files

Keep these files in the same folder:

```text
Download Playlist.bat
ytmusic_downloader.py
cookies.txt
```

`cookies.txt` is optional, but recommended.

Do not upload `cookies.txt` to GitHub. It contains private login cookies.

---

## Easy Usage

Double-click:

```text
Download Playlist.bat
```

The program will ask:

```text
Paste a YouTube Music playlist or song URL:
```

Paste a playlist URL like:

```text
https://music.youtube.com/playlist?list=PLAYLIST_ID
```

After you enter the URL, a Windows folder-selection dialog opens. Select the
parent location where the playlist folder should be created, for example:

```text
D:\Music
```

The downloader reads the YouTube Music playlist title and automatically creates
or reuses a folder such as `D:\Music\My Playlist`. That folder contains the
songs, manifest, and M3U8 playlist. If the playlist title changes later, its
manifest ID is used to reuse the original folder instead of redownloading into
a duplicate folder.

Closing or cancelling the folder dialog stops the downloader and closes its
CMD window. The folder picker also appears when you choose to download another
playlist or song.

### Add One Song to the Top of an Existing Playlist

Double-click `Download Playlist.bat` and paste a song URL instead of a playlist
URL, for example:

```text
https://music.youtube.com/watch?v=VIDEO_ID
```

When the folder picker opens, choose the existing downloaded playlist folder.
It must contain `playlist_manifest.json`. The downloader will:

* download only that song, unless its audio already exists
* keep its existing filename if the song is already in the manifest
* move/insert it at playlist position 1
* update both `playlist_manifest.json` and the title-based `.m3u8`
* keep manually added songs at the top during future full-playlist syncs

The newest manually added song becomes first. Previously added manual songs
remain immediately below it. Copy the new `.opus` file and updated `.m3u8` to
the same playlist folder on the phone, then let Poweramp rescan its library.

---

## PowerShell Usage

Run from the project folder:

```powershell
cd "D:\Youtube Music Downloader"

python ytmusic_downloader.py "https://music.youtube.com/playlist?list=PLAYLIST_ID" --output "D:\Music\My Playlist"
```

Add one song to the top of an existing downloaded playlist:

```powershell
python ytmusic_downloader.py "https://music.youtube.com/watch?v=VIDEO_ID" --output "D:\Music\My Playlist"
```

Use a specific cookies file:

```powershell
python ytmusic_downloader.py "https://music.youtube.com/playlist?list=PLAYLIST_ID" --output "D:\Music\My Playlist" --cookies ".\cookies.txt"
```

Change how many songs download at the same time:

```powershell
python ytmusic_downloader.py "https://music.youtube.com/playlist?list=PLAYLIST_ID" --output "D:\Music\My Playlist" --workers 5
```

By default, worker count is automatic:

```text
10 songs or fewer: 4 workers
11-99 songs:       3 workers
100+ songs:        2 workers
```

Downloads are also paced with yt-dlp request/download sleeps and limited retries to reduce 403/429 failures:

```text
sleep requests:    5 seconds
sleep interval:    10-30 seconds before each download
retries:           3
fragment retries:  3
```

---

## Cookies Setup

If YouTube gives errors like:

```text
Sign in to confirm you're not a bot
```

or downloads fail because YouTube needs your logged-in session, export cookies from your browser.

Recommended browser extension:

```text
Get cookies.txt LOCALLY
```

Export cookies from the browser where you are logged into YouTube Music.

Save the file as:

```text
cookies.txt
```

Place it in the same folder as:

```text
ytmusic_downloader.py
Download Playlist.bat
```

The script will automatically use it.

---

## PO Token / HTTP 403 Setup

Some YouTube Music tracks may fail with:

```text
HTTP Error 403: Forbidden
```

This can happen when YouTube requires a GVS PO token.

This project can use `bgutil-ytdlp-pot-provider` with Docker to generate PO tokens automatically.

Install the plugin:

```powershell
python -m pip install -U bgutil-ytdlp-pot-provider
```

Pull the Docker image:

```powershell
docker pull brainicism/bgutil-ytdlp-pot-provider
```

Create/start the provider container:

```powershell
docker run -d --name bgutil-provider -p 4416:4416 brainicism/bgutil-ytdlp-pot-provider
```

Check that it works:

```powershell
Invoke-WebRequest http://127.0.0.1:4416/ping
```

After this setup, the Python script can automatically:

1. Open Docker Desktop if needed
2. Wait for Docker engine to be ready
3. Start the `bgutil-provider` container
4. Download with PO-token support

The normal downloader keeps optional Docker/PO-token provider diagnostics
silent. If the provider is unavailable, it continues with the regular download
flow without filling the CMD window with token errors.

After restarting your PC, you should usually only need to run the `.bat` file again.

---

## Testing PO Token Support

Run this test:

```powershell
cd "D:\Youtube Music Downloader"

python -m yt_dlp -v --cookies ".\cookies.txt" --yes-playlist --playlist-items 1 -f "bestaudio[ext=webm]/bestaudio/best" -x --audio-format opus "https://music.youtube.com/playlist?list=PLAYLIST_ID"
```

Good signs in the log:

```text
PO Token Providers: bgutil:http
Generating a gvs PO Token
Retrieved a gvs PO Token
Downloading 1 format(s): 251
```

Format `251` is the good Opus audio-only format.

Bad signs:

```text
PO Token Providers: none
HTTP Error 403: Forbidden
```

If that happens, make sure Docker Desktop is running and the `bgutil-provider` container is started.

---

## Output Files

Newly downloaded songs are saved as:

```text
Artist - Title [videoId].opus
```

The output folder also contains:

```text
Playlist Title.m3u8
playlist_manifest.json
download_errors.log
```

`Playlist Title.m3u8` contains relative paths to the existing audio files in
the current YouTube Music playlist order. Tracks with missing or failed audio
are omitted until a later retry succeeds.

`playlist_manifest.json` stores track information, the permanent filename for
each `videoId`, the current playlist index, and the generated M3U8 filename.
This lets the script skip already downloaded songs on later runs.

`download_errors.log` appears only when tracks fail. It contains one readable
song entry per current failure, without Docker/token diagnostics or Python
tracebacks. Each run replaces the old report, and a fully successful retry
removes it automatically.

---

## Redownloading the Same Playlist

If you run the same playlist again:

* already-downloaded songs are skipped
* new songs are downloaded
* existing audio filenames remain unchanged
* the manifest playlist indexes are refreshed
* the `.m3u8` is regenerated in the current playlist order

Example:

Existing files:

```text
001 - Artist - Song A.opus
002 - Artist - Song B.opus
Artist - Song C [c-video-id].opus
```

If YouTube Music changes from A, B, C to C, A, B, those filenames stay exactly
the same. Only the M3U8 order changes:

```text
#EXTM3U
#EXTINF:-1,Artist - Song C
Artist - Song C [c-video-id].opus
#EXTINF:-1,Artist - Song A
001 - Artist - Song A.opus
#EXTINF:-1,Artist - Song B
002 - Artist - Song B.opus
```

The script migrates existing downloaded folders from their manifests without
redownloading or renaming audio.

---

## Using the Playlist in Poweramp

After each sync, copy only the new `.opus` files and the updated `.m3u8` file
to the same folder on your Android device. Existing `.opus` files do not need
to be copied again just because the playlist order changed.

In Poweramp, open **Library > Playlists** and select the playlist named after
the generated M3U8. The M3U8 references exact audio filenames in the same
folder and supplies the current YouTube Music order.

The **Folder Songs** view can remain sorted by filename; that sorting does not
control the order inside the playlist. Turn playback shuffle **off** when you
want Poweramp to play the playlist sequentially from top to bottom.

---

## Updating yt-dlp

If downloads suddenly fail, update yt-dlp:

```powershell
python -m pip install -U yt-dlp
```

You can also update all required Python packages:

```powershell
python -m pip install -U ytmusicapi yt-dlp bgutil-ytdlp-pot-provider
```

---

## Troubleshooting

### `HTTP Error 403: Forbidden`

Use the PO-token setup.

Check Docker:

```powershell
docker ps
Invoke-WebRequest http://127.0.0.1:4416/ping
```

Then rerun the downloader.

### `cookies.txt does not look like a Netscape format cookies file`

Re-export cookies using `Get cookies.txt LOCALLY`.

The first line should look like:

```text
# Netscape HTTP Cookie File
```

### Docker pull gives `EOF`

This is usually a network issue.

Try again a few times:

```powershell
docker pull brainicism/bgutil-ytdlp-pot-provider
```

If it keeps failing, open Docker Desktop settings and add this to Docker Engine config:

```json
{
  "dns": ["8.8.8.8", "1.1.1.1"],
  "max-concurrent-downloads": 1
}
```

Then click **Apply & Restart**.

### Docker says `docker-credential-desktop` not found

Reset Docker config:

```powershell
Set-Content "$env:USERPROFILE\.docker\config.json" '{ "auths": {}, "currentContext": "desktop-linux" }'
docker logout
```

Then try pulling again.

---

## GitHub Safety

Do not commit these files:

```text
cookies.txt
.env
downloads/
playlist_manifest.json
download_errors.log
```

Recommended `.gitignore`:

```gitignore
cookies.txt
.env
downloads/
playlist_manifest.json
download_errors.log
*.log
```

---

## Notes

This tool is for personal playlist backup/downloading workflows. You are responsible for following YouTube’s terms and copyright laws in your region.
