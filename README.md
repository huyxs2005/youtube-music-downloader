# YouTube Music Downloader

Download YouTube Music playlists as stable `.opus` files and generate UTF-8
`.m3u8` playlists that preserve the current YouTube Music order.

> **Cookie security:** `cookies.txt` contains private browser session data.
> Never share it, upload it, or commit it to Git. Cookies are optional; consider
> using a secondary YouTube account if you decide to export them.

## Installation Options

### Windows installer

Download the latest installer from
[GitHub Releases](https://github.com/huyxs2005/youtube-music-downloader/releases).

The installer:

- requests administrator approval through Windows UAC
- installs to `C:\Program Files\YouTube Music Downloader` by default
- lets the user choose a different installation folder
- includes a private Python runtime, FFmpeg, and FFprobe
- guides the user through WSL 2, Docker Desktop, and PO-token setup
- offers optional guided `cookies.txt` selection
- does not require a Docker account or Docker login

The free installer is unsigned, so Windows may show an **Unknown publisher** or
SmartScreen warning. Download it only from the official release page and verify
the published SHA-256 checksum before choosing **More info > Run anyway**.

For a completely manual installation, follow the single **Manual Setup** section
below.

## Features

- Downloads YouTube Music playlists as `.opus` audio
- Downloads only new or missing tracks during later playlist syncs
- Never renames an existing audio file when playlist order changes
- Keeps legacy numbered files such as `001 - Artist - Song.opus`
- Uses stable `Artist - Title [videoId].opus` filenames for new tracks
- Stores permanent filename mappings in `playlist_manifest.json`
- Generates an atomic, Unicode UTF-8 `.m3u8` in current playlist order
- Includes only audio files that actually exist in the M3U8
- Adds an individually downloaded song to position 1 of an existing playlist
- Embeds title, artist, album, track number, and artwork metadata
- Requests artwork up to 1008px
- Uses automatic worker counts, pacing, and retries
- Supports optional browser cookies and a Docker PO-token provider
- Keeps Docker/provider diagnostic noise out of the normal CMD output
- Writes readable failed-track reports without Python tracebacks
- Opens a native Windows folder picker instead of requiring typed paths
- Supports downloading another playlist or song without reopening the program

## Manual Setup

Everything required for a source installation—including cookies, Docker,
PO-token testing, updates, and troubleshooting—is contained in this section.

### 1. Download the project

With Git:

```powershell
git clone https://github.com/huyxs2005/youtube-music-downloader.git
cd youtube-music-downloader
```

Without Git, open the repository on GitHub and select **Code > Download ZIP**,
then extract the ZIP to a normal writable folder.

### 2. Install Python

Install a current 64-bit Python release from
[python.org](https://www.python.org/downloads/windows/). Ensure the `python`
command is available, then close and reopen PowerShell or CMD.

Verify it:

```powershell
python --version
python -m pip --version
```

### 3. Install FFmpeg

Using Windows Package Manager:

```powershell
winget install --id Gyan.FFmpeg --exact
```

Close and reopen the terminal, then verify it:

```powershell
ffmpeg -version
ffprobe -version
```

### 4. Install the Python packages

Run this from the extracted project folder:

```powershell
python -m pip install -r requirements.txt
```

The requirements file installs the tested versions of `ytmusicapi`, `yt-dlp`,
`mutagen`, `Pillow`, and `bgutil-ytdlp-pot-provider`.

Verify the imports:

```powershell
python -c "import ytmusicapi, yt_dlp, mutagen, PIL; print('Python packages OK')"
```

### 5. Set up Docker and the PO-token provider

Docker is optional, but strongly recommended for tracks that require a YouTube
GVS PO token or otherwise fail with HTTP 403.

1. Install [Docker Desktop](https://docs.docker.com/desktop/setup/install/windows-install/).
2. Use the WSL 2 backend when prompted.
3. Restart Windows if WSL requests it.
4. Open Docker Desktop and accept its terms.

A Docker account and Docker login are **not required**.

From PowerShell, verify Docker and pull the public provider image:

```powershell
docker info
docker pull brainicism/bgutil-ytdlp-pot-provider
```

Create the provider container the first time:

```powershell
docker run -d --name bgutil-provider -p 4416:4416 brainicism/bgutil-ytdlp-pot-provider
```

If the container already exists, start it instead:

```powershell
docker start bgutil-provider
```

Test the provider:

```powershell
Invoke-WebRequest http://127.0.0.1:4416/ping
```

The downloader will later open Docker Desktop when needed, wait for its engine,
and start the existing `bgutil-provider` container automatically.

### 6. Set up cookies (optional)

Cookies may help when YouTube displays **Sign in to confirm you're not a bot**
or requires a logged-in session.

1. Install
   [Get cookies.txt LOCALLY](https://chromewebstore.google.com/detail/get-cookiestxt-locally/cclelndahbckbenkjhflpdbgdldlbecc).
2. Open YouTube or YouTube Music in the same browser and sign in.
3. While on that YouTube page, use the extension to export `cookies.txt`.
4. Place `cookies.txt` beside `ytmusic_downloader.py` and
   `Download Playlist.bat`.

The file should begin with something similar to:

```text
# Netscape HTTP Cookie File
```

The downloader automatically detects the file. You can also pass a different
path with `--cookies`.

### 7. Verify PO-token support (optional)

Replace `PLAYLIST_ID` and run:

```powershell
python -m yt_dlp -v --cookies ".\cookies.txt" --yes-playlist --playlist-items 1 -f "bestaudio[ext=webm]/bestaudio/best" -x --audio-format opus "https://music.youtube.com/playlist?list=PLAYLIST_ID"
```

Omit `--cookies ".\cookies.txt"` if you are not using cookies.

Good signs include:

```text
PO Token Providers: bgutil:http
Generating a gvs PO Token
Retrieved a gvs PO Token
Downloading 1 format(s): 251
```

### 8. Run the automated tests (optional)

```powershell
python -m py_compile ytmusic_downloader.py
python -m unittest discover -s tests -v
```

### 9. Update a manual installation

If installed with Git:

```powershell
git pull
python -m pip install -r requirements.txt
```

If installed from a ZIP, download and extract the new release, then copy your
private `cookies.txt` into the new project folder. Do not replace or delete your
downloaded music folders.

If YouTube changes and only yt-dlp needs updating:

```powershell
python -m pip install -U yt-dlp
```

### 10. Manual setup troubleshooting

#### `python` is not recognized

Reinstall Python with command-line support enabled, then reopen the terminal.
The batch launcher also checks `%LocalAppData%\Python\bin\python.exe`,
`python.exe`, and `py.exe`.

#### `ffmpeg` is not recognized

Reopen the terminal after installing FFmpeg. If it still fails, reinstall it
with Winget and confirm its `bin` directory is on `PATH`.

#### Docker is installed but unavailable

Open Docker Desktop, wait until it reports that the engine is running, then
check:

```powershell
docker info
docker ps
```

#### The provider container name already exists

Do not run `docker run` again. Start the existing container:

```powershell
docker start bgutil-provider
```

#### Docker reports `docker-credential-desktop` not found

Avoid overwriting your normal Docker configuration. Pull the public image with
a temporary anonymous configuration:

```powershell
$dockerConfig = Join-Path $env:TEMP "youtube-music-downloader-docker-config"
New-Item -ItemType Directory -Path $dockerConfig -Force | Out-Null
Set-Content -Path (Join-Path $dockerConfig "config.json") -Value '{"auths":{}}'
docker --config $dockerConfig pull brainicism/bgutil-ytdlp-pot-provider
```

#### Docker pull returns `EOF`

This is normally a temporary network or Docker DNS problem. Restart Docker
Desktop and retry the pull before changing Docker settings.

#### Downloads return HTTP 403

Check the provider, then retry the downloader:

```powershell
docker start bgutil-provider
Invoke-WebRequest http://127.0.0.1:4416/ping
```

#### Downloads return HTTP 429

Wait before retrying. The downloader already uses request sleeps, limited
retries, and reduced worker counts for large playlists. You can also run with
fewer workers, such as `--workers 1`.

#### Cookies are rejected

Re-export them from a YouTube or YouTube Music page using the recommended
extension. Confirm that the file uses Netscape cookie format and is named
`cookies.txt`, not `cookies.txt.txt`.

## Usage

All normal workflows—playlist downloads, individual songs, resyncing, command
line options, and transferring to a phone—are contained in this section.

### Easy CMD usage

Double-click:

```text
Download Playlist.bat
```

Paste either a YouTube Music/YouTube playlist URL or an individual song URL.
A native folder picker opens after the URL is validated. Closing the picker
cancels the process and closes the launcher.

### Download or update a playlist

1. Paste a playlist URL such as:

   ```text
   https://music.youtube.com/playlist?list=PLAYLIST_ID
   ```

2. Choose the parent location where the playlist folder should live, such as
   `D:\Music`.
3. The downloader creates a subfolder using the playlist title, such as
   `D:\Music\My Playlist`.

Running the same playlist again:

- reuses the folder by playlist ID, even if its title changed
- skips audio files that already exist
- downloads only new or missing tracks
- preserves every existing filename
- refreshes manifest indexes
- regenerates the title-based M3U8 in current YouTube Music order

### Add one song to the top of an existing playlist

1. Paste a song URL such as:

   ```text
   https://music.youtube.com/watch?v=VIDEO_ID
   ```

2. Select an existing downloaded playlist folder containing
   `playlist_manifest.json`.

The downloader downloads the song only if needed, preserves any existing
filename, moves/inserts it at position 1, and updates both the manifest and
M3U8. The newest manually added song becomes first.

### Download another playlist or song

After a sync finishes, answer **Yes** when asked whether to download another
playlist or song. The URL prompt and folder picker open again.

### PowerShell usage

Download a playlist:

```powershell
python ytmusic_downloader.py "https://music.youtube.com/playlist?list=PLAYLIST_ID" --output "D:\Music\My Playlist"
```

For command-line usage, `--output` is the exact playlist folder. The
double-click flow is recommended when you want the program to create a
playlist-title subfolder automatically beneath a selected parent location.

Add one song to an existing playlist:

```powershell
python ytmusic_downloader.py "https://music.youtube.com/watch?v=VIDEO_ID" --output "D:\Music\My Playlist"
```

Use a specific cookie file:

```powershell
python ytmusic_downloader.py "https://music.youtube.com/playlist?list=PLAYLIST_ID" --output "D:\Music\My Playlist" --cookies ".\cookies.txt"
```

Override the automatic worker count:

```powershell
python ytmusic_downloader.py "https://music.youtube.com/playlist?list=PLAYLIST_ID" --output "D:\Music\My Playlist" --workers 2
```

Automatic worker counts are:

```text
10 tracks or fewer: 4 workers
11-99 tracks:       3 workers
100+ tracks:        2 workers
```

### Output files

A playlist folder can contain:

```text
Artist - Title [videoId].opus
Playlist Title.m3u8
playlist_manifest.json
failed_downloads.txt
download_errors.log
```

- `.opus` files contain the audio, metadata, and embedded artwork.
- `.m3u8` stores the current playlist order using exact relative filenames.
- `playlist_manifest.json` permanently maps each `videoId` to its filename.
- `failed_downloads.txt` lists tracks that should be retried.
- `download_errors.log` contains only readable failed-song entries and is
  removed after a fully successful retry.

Missing audio files are not added to the M3U8. Retrying the sync regenerates the
playlist so newly successful tracks appear automatically.

### Transfer updates to a phone

After a playlist sync:

1. Copy only newly downloaded `.opus` files to the existing playlist folder on
   the phone.
2. Replace the old `.m3u8` with the updated one.
3. Keep the `.m3u8` in the same folder as the audio files.
4. Let the music player rescan its library.

In Poweramp, open **Library > Playlists** and select the playlist named after
the M3U8. The **Folder Songs** view can remain sorted by filename because that
does not affect playlist order. Turn playback shuffle **off** for sequential
top-to-bottom playback.

## Repository Safety

Never commit private cookies or downloaded media. If you download into the
repository, add rules such as these to your local Git exclusions:

```gitignore
cookies.txt
*.opus
*.m3u8
playlist_manifest.json
failed_downloads.txt
download_errors.log
downloads/
```

## Legal Note

Use this project only for content you are permitted to download. You are
responsible for following YouTube's terms and the copyright laws that apply in
your region.
