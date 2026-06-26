# YouTube Music Downloader

Download a YouTube Music playlist into ordered `.opus` audio files.

This project uses:

* `ytmusicapi` to read the playlist order from YouTube Music
* `yt-dlp` to download each song
* `ffmpeg` to convert/extract audio to `.opus`
* optional browser cookies for login/bot-check issues
* optional BgUtils PO-token provider through Docker for YouTube 403 errors

The downloader is designed to keep playlist order like this:

```text
001 - Artist - Title.opus
002 - Artist - Title.opus
003 - Artist - Title.opus
```

It also keeps a `playlist_manifest.json` file so already-downloaded songs can be skipped and renamed correctly if the playlist order changes.

---

## Features

* Downloads YouTube Music playlists as `.opus`
* Keeps playlist order in filenames
* Skips songs that were already downloaded
* Renames existing files if playlist order or metadata changes
* Avoids numbering gaps when unavailable playlist items have no `videoId`
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
   python -m pip install -U ytmusicapi yt-dlp bgutil-ytdlp-pot-provider
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
Paste the YouTube Music playlist URL:
Output folder:
```

Paste a playlist URL like:

```text
https://music.youtube.com/playlist?list=PLAYLIST_ID
```

For the output folder, you can either type a folder path:

```text
D:\Music\My Playlist
```

or press Enter to use the default `downloads` folder.

---

## PowerShell Usage

Run from the project folder:

```powershell
cd "D:\Youtube Music Downloader"

python ytmusic_downloader.py "https://music.youtube.com/playlist?list=PLAYLIST_ID" --output "D:\Music\My Playlist"
```

Use a specific cookies file:

```powershell
python ytmusic_downloader.py "https://music.youtube.com/playlist?list=PLAYLIST_ID" --output "D:\Music\My Playlist" --cookies ".\cookies.txt"
```

Change how many songs download at the same time:

```powershell
python ytmusic_downloader.py "https://music.youtube.com/playlist?list=PLAYLIST_ID" --output "D:\Music\My Playlist" --workers 5
```

Default worker count is `10`.

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

Downloaded songs are saved as:

```text
001 - Artist - Title.opus
002 - Artist - Title.opus
003 - Artist - Title.opus
```

The output folder also contains:

```text
playlist_manifest.json
download_errors.log
```

`playlist_manifest.json` stores downloaded track info so the script can skip already downloaded songs on later runs.

`download_errors.log` appears if some tracks fail.

---

## Redownloading the Same Playlist

If you run the same playlist again:

* already-downloaded songs are skipped
* new songs are downloaded
* old files are renamed if the playlist order changed
* numbering is recalculated from valid downloadable tracks

Example:

Old playlist:

```text
001 - Song A.opus
002 - Song B.opus
003 - Song C.opus
```

New playlist with a song added at the top:

```text
001 - Song D.opus
002 - Song A.opus
003 - Song B.opus
004 - Song C.opus
```

The script uses the manifest to rename and keep order.

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
