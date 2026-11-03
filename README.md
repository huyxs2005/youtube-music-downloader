A Windows desktop app that downloads YouTube Music songs as OPUS audio and keeps your M3U8 playlists in YouTube order.

## Installation

These steps install the **WPF-UI desktop app** on 64-bit Windows. Paste the commands into **Command Prompt (CMD)**.

### 1. Install the required programs

| Download | Why you need it |
| --- | --- |
| [Git](https://git-scm.com/downloads/win) | Downloads this project and gets updates. |
| [Python 3.13, 64-bit](https://www.python.org/downloads/windows/) | Runs the download engine. |
| [.NET 10 SDK](https://dotnet.microsoft.com/en-us/download/dotnet/10.0) | Builds the interface. Install the **SDK**, not only the runtime. |
| [FFmpeg](https://www.gyan.dev/ffmpeg/builds/) | Processes audio. You need both `ffmpeg.exe` and `ffprobe.exe`. |

You can install all four through CMD. Paste these commands one at a time and follow the prompts:

```cmd
winget install --id Git.Git --exact --source winget
winget install --id Python.Python.3.13 --exact --source winget
winget install --id Microsoft.DotNet.SDK.10 --exact --source winget
winget install --id Gyan.FFmpeg --exact --source winget
```

Skip programs you already have. **Close CMD and open a new CMD window after installation.** Check the installations:

```cmd
git --version
python --version
dotnet --list-sdks
ffmpeg -version
ffprobe -version
```

Each command should show version information. The SDK list must include a `10.x` version.

If `winget` is unavailable, install or update **App Installer** from the Microsoft Store, or use the download links above. For manual installation, enable **Add python.exe to PATH** in Python's installer and add FFmpeg's `bin` folder to your Windows `PATH`.

### 2. Download the project

Paste into CMD:

```cmd
cd /d "%USERPROFILE%"
git clone https://github.com/huyxs2005/youtube-music-downloader.git
cd youtube-music-downloader
```

This creates a `youtube-music-downloader` folder inside your Windows user folder. Keep CMD open in that project folder for the next steps. If you already cloned the project, open CMD in your existing project folder instead of cloning again.

### 3. Get cookies.txt

**The desktop app requires an exported YouTube cookie file before downloading.**

1. Install [Get cookies.txt LOCALLY](https://chromewebstore.google.com/detail/get-cookiestxt-locally/cclelndahbckbenkjhflpdbgdldlbecc) in a compatible browser.
2. Open [YouTube Music](https://music.youtube.com/) or [YouTube](https://www.youtube.com/) and sign in.
3. While on that website, export cookies in **Netscape cookies.txt format** using the extension.
4. Save the file as `cookies.txt` in the project folder, beside `README.md` and `ytmusic_downloader.py`.

The file should begin with:

```text
# Netscape HTTP Cookie File
```

The app automatically detects an existing `cookies.txt` beside the app, in the project folder, or in the selected music/playlist folder. You do not need to browse for it again. **Add cookies.txt** lets you choose a file elsewhere, and a valid manually chosen path is remembered. **Verify** checks it again without opening a file picker.

Validation checks the format, YouTube domains, and expiry. These are local checks; YouTube can still reject a signed-out or revoked session. Export a fresh file if that happens.

**Keep cookies.txt private. It contains browser session data. Never share it, upload it to GitHub, or include it in a release.**

### 4. Build and open the app

In CMD, while inside the project folder, paste:

```cmd
powershell -NoProfile -ExecutionPolicy Bypass -File ".\Start Desktop.ps1"
```

This runs the included setup script. It creates a private Python environment, installs the Python packages, builds the interface, and opens the app. The first run may take a few minutes. You do not need Visual Studio.

### 5. Open the app next time

In File Explorer, open this folder inside the project:

```text
desktop\bin\Release\net10.0-windows
```

Double-click **YouTubeMusicDownloader.Desktop.exe**. You can create a desktop shortcut to it.

**No BAT file or open CMD window is needed for normal use.** Keep the project folder and its `.venv` folder together, because this source build uses them.

The older v1.0 installer in [Releases](https://github.com/huyxs2005/youtube-music-downloader/releases) installs the command-line edition. Use the steps above for the WPF-UI desktop app.

### 6. Optional: Docker and the PO-token provider

Some YouTube downloads need an additional token and may fail with HTTP 403 without it. The app supports a local Docker service that provides this token. You can try downloading first and return here if needed.

If WSL 2 is missing, open **CMD as administrator** and run:

```cmd
wsl --install --no-distribution
wsl --update
```

Restart Windows if requested. See Microsoft's [WSL installation guide](https://learn.microsoft.com/en-us/windows/wsl/install) if setup fails.

Install [Docker Desktop for Windows](https://docs.docker.com/desktop/setup/install/windows-install/), choose the **WSL 2 backend**, and open Docker Desktop. Wait for its engine to start.

In a new CMD window, paste:

```cmd
docker info
docker pull brainicism/bgutil-ytdlp-pot-provider
docker run -d --name bgutil-provider -p 127.0.0.1:4416:4416 brainicism/bgutil-ytdlp-pot-provider
curl http://127.0.0.1:4416/ping
```

Create the container only once. If `bgutil-provider` already exists, start it instead:

```cmd
docker start bgutil-provider
```

Once configured, the app can open Docker Desktop and start the existing provider when preparing downloads.

## Use the app

### Download or update a playlist

1. On **Playlists**, paste a playlist URL and click **Choose folder**.
2. Choose your music parent folder, such as `D:\Music`, or the playlist's existing downloaded folder.
3. Check that the cookies row shows a valid file, then click **Scan playlist**.
4. Tick the songs you want to download, or click **Select all**.
5. Click **Download selected & sync**.

After scanning, setup collapses so the song list has more room. **Playlist setup** reopens it; **Hide setup · expand list** closes it again.

The **Downloads** tab on the left shows the current playlist's download queue and progress. It opens automatically when you start downloading. You can switch between tabs while downloads run. Song selection is locked during a sync, but browsing, scrolling, and display sorting remain available. Use the status filter to focus on **Downloading**, **Queued**, or **Failed** songs.

For a new playlist, the app creates a subfolder using its title. Later syncs find the same playlist by its saved YouTube ID, even if the title changes. Existing audio is reused and filenames stay the same. **Retry failed** retries failed songs.

### What do the checkboxes change?

**Checkboxes control downloading. Existing songs stay in the M3U8 even when unchecked.**

Example: a playlist has 10 songs. The last 7 are already downloaded, and you select only the first 3. The app downloads those 3 and writes an M3U8 containing **all 10 in YouTube order**.

Unchecked songs that are missing locally are not downloaded and get no broken entries. A sync with nothing selected still refreshes the M3U8 using existing audio.

Keep the audio, M3U8, and `playlist_manifest.json` together in the original playlist folder so the app can recognize existing songs.

### Sort and find songs

Click a header once for ascending **▲** order and again for descending **▼** order:

| Column | Ascending | Descending |
| --- | --- | --- |
| Title, Artist, Album, Genre | A to Z | Z to A |
| Duration | Shortest first | Longest first |
| Position | Lowest playlist number first | Highest first |
| File Size | Smallest first | Largest first |

Duration, position, and size sort numerically. Unknown values stay at the bottom. File Size shows actual local audio sizes; undownloaded files show **Unknown**. Unavailable genre and other metadata also show **Unknown**. Hover over shortened titles or artist names to see the full text.

**Table sorting never changes the saved playlist order.** Click **YouTube order** to restore the table's original order.

Search by title, artist, album, or genre. Checkboxes stay attached to their songs as rows move. **Select all** and **Clear** apply to every scanned song, including songs hidden by filters. Scroll the table horizontally to reach more columns in a narrow window.

### Open an existing M3U8

Click **Open M3U8** in playlist setup and choose a playlist previously created by the app. Its companion `playlist_manifest.json` identifies the YouTube playlist. Click **Scan playlist** to check for changes and new songs.

An arbitrary M3U8 without that manifest cannot identify its original YouTube playlist automatically.

### Add a single song

Paste a song URL and choose an existing downloaded playlist folder containing `playlist_manifest.json`. Scan, select the song, and download it. It is inserted at position 1. Manually added songs stay at the top during later playlist syncs.

## Output files

```text
My Playlist\
  Artist - Title [videoId].opus
  My Playlist.m3u8
  playlist_manifest.json
  failed_downloads.txt
  download_errors.log
```

- **OPUS:** audio with title, artist, album, track number, and artwork when available.
- **M3U8:** playlist entries pointing to audio files that exist locally.
- **Manifest:** the playlist ID and permanent filename mappings. Keep it for future updates.
- **Failure reports:** songs that need another attempt. Reports are cleared after a successful retry.

To update a phone, copy the new audio into its existing playlist folder and replace the old M3U8. Keep the M3U8 beside the audio. In Poweramp, open it under **Library > Playlists** and turn shuffle off for playlist order.

## Update the app

Close the app first. If you followed the installation path above, paste into CMD:

```cmd
cd /d "%USERPROFILE%\youtube-music-downloader"
git pull --ff-only
powershell -NoProfile -ExecutionPolicy Bypass -File ".\Start Desktop.ps1"
```

If installed elsewhere, change the first line to your project folder. Keep your cookies and downloaded music.

## Troubleshooting

| Problem | What to do |
| --- | --- |
| A command is not recognized | Reopen CMD after installation. Check the program's installation and `PATH`. |
| No SDK is found | Install the **.NET 10 SDK** and check `dotnet --list-sdks`. A runtime alone cannot build the app. |
| Download button is disabled | Scan a playlist and check the cookies message. Add or refresh the cookie file if needed. |
| Cookies are rejected | Export a fresh Netscape-format file while signed in on YouTube. Check that its name is `cookies.txt`, not `cookies.txt.txt`. |
| HTTP 403 or token errors | Set up the optional Docker provider, open Docker Desktop, and run `docker start bgutil-provider`. |
| HTTP 429 | Wait before retrying. YouTube is limiting requests. |
| Container name already exists | Use `docker start bgutil-provider` instead of creating it again. |
| Docker is unavailable | Open Docker Desktop, wait for its engine, and check `docker info`. |
| Existing songs appear missing | Choose the original playlist folder and keep its audio and manifest together. |
| Building an update says files are in use | Close the app and test previews, then retry. |

## Build a portable package

For maintainers: complete the source installation, close the app, and run this from the project folder in CMD:

```cmd
powershell -NoProfile -ExecutionPolicy Bypass -File ".\installer\build-desktop.ps1" -Python ".\.venv\Scripts\python.exe"
```

FFmpeg and FFprobe must be on `PATH`. Alternatively, add `-FfmpegDirectory "C:\ffmpeg\bin"`, replacing that path with your actual FFmpeg folder.

The output is `dist\YouTubeMusicDownloader-Desktop`. Distribute **the entire folder**, not just the EXE. It contains the .NET runtime, Python engine, FFmpeg, and FFprobe, so users of the complete package do not need to install Python or .NET separately. They need their own cookies and, when required, the optional token provider.

Never include private cookies or downloaded music in the package. The older `build-installer.ps1` builds the legacy command-line installer.

## Development and testing

The interface uses **C#/WPF and [WPF-UI](https://github.com/lepoco/wpfui)**. The Python engine handles downloads, metadata, manifests, and M3U8 generation. The old `Download Playlist.bat` remains available for command-line use.

Run from the project folder in CMD:

```cmd
.venv\Scripts\python.exe -m unittest discover -s tests -v
dotnet build tests\desktop -c Release
start "" /wait "tests\desktop\bin\Release\net10.0-windows\DesktopChecks.exe" "%CD%\desktop-checks.txt"
type desktop-checks.txt
```

The desktop checks use local fixtures without downloading from YouTube or using private cookies. For UI changes, also use the app and inspect screenshots at default and minimum window sizes, including large playlists. Check both tabs, sorting, checkboxes, search with no matches, filters, cookie controls, picker cancellation, and scrolling.

## Responsible use

Download only content you have permission to save, and follow applicable copyright laws and YouTube's terms. Never commit private cookies or downloaded media to this repository.
