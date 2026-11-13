A Windows desktop app for downloading YouTube and YouTube Music playlists as OPUS audio, with selectable songs and optional custom playlist order.

## Installation

### 1. Download the Windows app

**[Download YouTube Music Downloader v2.2.6 — Extract & open folder](https://github.com/huyxs2005/youtube-music-downloader/releases/download/v2.2.6/YouTubeMusicDownloader-Desktop-v2.2.6-win-x64-extract.exe)**

Prefer a regular archive? Download the **[portable ZIP](https://github.com/huyxs2005/youtube-music-downloader/releases/download/v2.2.6/YouTubeMusicDownloader-Desktop-v2.2.6-win-x64.zip)** instead. Both downloads contain the same app.

Choose a Windows app download from [Releases](https://github.com/huyxs2005/youtube-music-downloader/releases/latest), not the automatically generated **Source code** downloads.

The package includes the app, .NET runtime, Python download engine, FFmpeg, and FFprobe. **You do not need to install Python, .NET, Git, or FFmpeg separately. No CMD commands or BAT files are needed to open the app.**

This package is for 64-bit Windows. The older v1.0 installer is the command-line edition; v2.2.6 is the WPF-UI desktop edition.

### 2. Extract and open it

1. Open the downloaded **…-extract.exe**.
2. Choose where to extract it. **Browse** lets you choose a drive or parent folder.
3. Press **Extract**. When it finishes, the inner **YouTubeMusicDownloader-Desktop** folder opens automatically.
4. Double-click **YouTubeMusicDownloader.Desktop.exe** inside that folder.

For example, choosing `D:\` extracts to `D:\YouTubeMusicDownloader-Desktop-v2.2.6-win-x64\YouTubeMusicDownloader-Desktop` and opens that inner folder directly. The extractor does not start the app automatically.

**Using the ZIP instead:** right-click it, choose **Extract All**, then open **YouTubeMusicDownloader-Desktop** inside the destination. Windows decides which folder opens after ZIP extraction; the optional extractor above opens the inner app folder for you.

**Keep the whole extracted folder together.** Do not move only the EXE, delete its supporting files, or run it from inside the ZIP. You can create a desktop shortcut to the EXE instead.

The app folder is organized like this:

```text
YouTubeMusicDownloader-Desktop/
├── YouTubeMusicDownloader.Desktop.exe  ← open this
└── app/                              ← supporting files
```

Keep the `app` subfolder beside the EXE. The root EXE is a small launcher using the .NET Framework included with supported Windows versions. The app's own runtime, download engine, tools, licenses, and this guide stay inside `app`. Your private `cookies.txt` can stay beside the launcher.

The app is unsigned, so Windows may show an unknown-publisher warning. Download it from this repository's official release page. A [SHA-256 checksum](https://github.com/huyxs2005/youtube-music-downloader/releases/download/v2.2.6/YouTubeMusicDownloader-Desktop-v2.2.6-win-x64.zip.sha256) is provided with the release.

### 3. Add your cookies.txt file

**The app requires an exported YouTube cookie file before downloading.**

1. Install [Get cookies.txt LOCALLY](https://chromewebstore.google.com/detail/get-cookiestxt-locally/cclelndahbckbenkjhflpdbgdldlbecc) in a compatible browser.
2. Open [YouTube Music](https://music.youtube.com/) or [YouTube](https://www.youtube.com/) and sign in.
3. While on that website, use the extension to export cookies in **Netscape cookies.txt format**.
4. Save the file as `cookies.txt` beside **YouTubeMusicDownloader.Desktop.exe**.

The file should begin with:

```text
# Netscape HTTP Cookie File
```

The app automatically detects an existing `cookies.txt` beside the EXE or in the selected music/playlist folder. You do not need to browse for it again. **Add cookies.txt** lets you choose a file elsewhere, and a valid manually chosen path is remembered. **Verify** checks it again without opening a file picker.

Validation checks the format, YouTube domains, and expiry. These local checks cannot prove that YouTube still accepts a signed-out or revoked session. Export fresh cookies if YouTube rejects them.

**Keep cookies.txt private. It contains browser session data. Never share it, upload it to GitHub, or include it in a release.**

### 4. Scan and download

1. On **Playlists**, paste a YouTube Music or YouTube playlist URL.
2. Downloads default to the folder beside the launcher EXE. Each playlist gets its own subfolder named after the playlist. Use **Choose folder** to select another parent folder or an existing playlist folder.
3. Click **Scan playlist**.
4. Tick the songs you want to download, or use the button in the table's top-left corner to select all.
5. Click **Download selected**.

The **Downloads** tab opens automatically so you can follow the current playlist's progress.

### Optional: Docker for downloads that need a PO token

Some YouTube downloads need an additional token and may fail with HTTP 403 without it. The app supports a local Docker service that provides this token. Try downloading first; complete this section if needed.

If WSL 2 is missing, open **Command Prompt (CMD) as administrator** and paste:

```cmd
wsl --install --no-distribution
wsl --update
```

Restart Windows if requested. See Microsoft's [WSL installation guide](https://learn.microsoft.com/en-us/windows/wsl/install) if setup fails.

Install [Docker Desktop for Windows](https://docs.docker.com/desktop/setup/install/windows-install/), choose the **WSL 2 backend**, and open Docker Desktop. Wait for its engine to start.

In a new CMD window, paste these commands one at a time:

```cmd
docker info
docker pull brainicism/bgutil-ytdlp-pot-provider
docker run -d --name bgutil-provider -p 127.0.0.1:4416:4416 brainicism/bgutil-ytdlp-pot-provider
curl http://127.0.0.1:4416/ping
```

Create the container only once. If CMD says `bgutil-provider` already exists, start it instead:

```cmd
docker start bgutil-provider
```

Once configured, the app can open Docker Desktop and start the existing provider when preparing downloads.

## Using the app

The app uses a YouTube-style black-and-red theme. Its red icon has a white triangle pointing down to represent downloading.

Use **☰** to expand or collapse the sidebar. The scan status counts detected songs and unavailable items as results arrive. Invalid links and fetch failures show an explanation. Cookie verification shows a brief success notification, with a warning dialog if the file needs attention.

Click a song thumbnail to open a larger preview. Close it with **Close**, **Esc**, or by clicking outside. Missing albums show **None**.

### Larger song list and Downloads tab

After scanning, setup collapses so the song table has more room. Click the **Playlist setup** section heading to open or close the setup form.

The **Downloads** tab shows the current queue, remaining count, and downloaded/failed totals. Use its status filter to focus on **Downloading**, **Queued**, or **Failed** songs. You can browse, scroll, and sort while downloads run. Song selection is locked until the download finishes.

The Status column shows real transfer percentages, such as **Downloading 37%**. **Processing 100%** means the audio transfer is complete and conversion/tagging is still finishing; the row changes to **Downloaded** afterward. Hover over a failed status for its reason, or read Activity and the playlist folder's `download_errors.log`.

After downloading, click **Open download folder** to open the actual playlist folder in File Explorer. The button is also available when you scan a folder that already contains downloaded songs, and after a download finishes with some failures.

Large playlists prepare their manifest and initial statuses in batches. Unchecked songs are not downloaded, and background metadata fetching pauses when a download starts.

The first queued song starts downloading immediately. Later songs are paced (a few seconds between requests and a random 10–25 second pause before each song) so long downloads do not hammer YouTube with your account. If YouTube still returns HTTP 429 or a bot check, wait before retrying.

### Updating a playlist

For a new playlist, the app creates a subfolder using its title. Later downloads find the same playlist by its saved YouTube ID, even if the title changes. Existing audio is reused. Filenames use `Artist - Title.opus`; YouTube IDs stay inside the manifest. The first download with v2.2.4 removes older ID suffixes from local filenames and updates the playlist references together, without re-encoding audio. Different videos with the same name get `(2)`, `(3)`, and so on rather than overwriting each other. **Retry failed** selects and retries failed songs.

Keep the audio, M3U8, and `playlist_manifest.json` together in the original playlist folder so the app can recognize existing songs.

### What do the checkboxes change?

**Checkboxes control downloading. The M3U8 keeps every song in the complete playlist order, including unchecked songs and audio that has not been downloaded yet.**

The button in the table's top-left corner selects all scanned songs. Click it again to deselect all. Its icon shows whether none, some, or all songs are selected. It includes songs hidden by your current filter and is disabled while downloading.

**Multiple select:** press and hold a song's checkbox, then drag up or down across more songs. Starting on an unchecked box selects the range; starting on a checked box clears the range. Hold near the top or bottom of the table to scroll while selecting. Only displayed songs are affected, and releasing the mouse finishes the selection. It also works with Custom order enabled, without dragging the songs themselves.

Example: a playlist has 10 songs. The last 7 are already downloaded, and you select only the first 3. The app downloads those 3 and writes an M3U8 containing **all 10 in YouTube order**.

Unchecked songs that are missing locally are not downloaded, but their filenames remain in the M3U8 as references. They become playable once their audio is downloaded into the same folder. Some players skip or hide missing-file entries until you import or refresh the playlist again. These references are not online streams. Downloading with nothing selected still saves the complete playlist order. Repeated songs keep their separate positions in the playlist.

### Sorting and search

Click a column header once for ascending **▲** order and again for descending **▼** order:

| Column | Ascending | Descending |
| --- | --- | --- |
| Title, Artist, Album | A to Z | Z to A |
| Duration | Shortest first | Longest first |
| No. | Lowest playlist number first | Highest first |
| File Size | Smallest first | Largest first |

Duration, number, and size sort numerically. Missing values stay at the bottom. File Size shows actual local audio sizes after download. Before download, **~** marks an estimate from the available audio stream or, as a fallback, duration at 160 kbps. Metadata loads in the background and is cached. A small song thumbnail appears to the left of Title. Hover over shortened titles or artist names to see the full text. **Not in selected playlist folder** means the local audio file was not found; it does not mean the song is unavailable on YouTube.

With **Custom order** off, column sorting changes only the display and the saved playlist uses YouTube order. Check **Custom order** to start from the current table arrangement, then drag individual songs up or down. Column sorting is disabled while arranging songs. **Download selected** saves the complete custom order to the M3U8, including songs not yet downloaded. The next scan restores your saved arrangement and appends new songs. Turn Custom order off to return to YouTube order.

Search by title, artist, or album. Checkboxes stay attached to songs as rows move. The corner button selects or deselects every scanned song, including songs hidden by filters. Scroll the table horizontally to reach more columns in a narrow window.

Drag a column edge to resize it. Columns on the right shrink and shorten overflowing text with **…**. Double-click an edge or heading to fit that column to its longest value. Very wide columns can be reached with horizontal scrolling.

### Open an existing M3U8

Click **Open M3U8** in playlist setup and choose a playlist previously created by the app. Its companion `playlist_manifest.json` identifies the YouTube playlist. Click **Scan playlist** to check for changes and new songs.

An arbitrary M3U8 without that manifest cannot identify its original YouTube playlist automatically.

### Add a single song

Paste a song URL and choose an existing downloaded playlist folder containing `playlist_manifest.json`. Scan, select the song, and download it. It is inserted at position 1. Manually added songs stay at the top during later playlist downloads.

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

To reuse filenames from an older phone playlist, choose **Open M3U8**, select that old playlist without a companion manifest, then paste its YouTube URL and scan. The app reuses matching filenames and remembers them for later updates. It only matches the same artist and title, allowing punctuation and accent differences; it does not guess between different recordings or versions.

Old audio copied straight into a playlist folder is matched the same way, even without its old M3U8. For example, `Chevy & City Girl - Daydreaming.opus` is recognized as the song the app would name `Chevy, City Girl - Daydreaming.opus`, and its existing filename is kept. Files that already belong to another song in the manifest are never reused.

To update a phone, copy the new audio into its existing playlist folder and replace the old M3U8. If you previously copied files with ID brackets, copy the newly renamed audio too; replacing an M3U8 alone cannot rename files already on the phone. Keep the M3U8 beside the audio. In Poweramp, open it under **Library > Playlists** and turn shuffle off for playlist order.

## Update to a newer release

1. Let any download finish, then close the app.
2. Download the new desktop ZIP from [Releases](https://github.com/huyxs2005/youtube-music-downloader/releases/latest).
3. Extract it into a new folder.
4. Copy your private `cookies.txt` beside the new EXE, or reuse your remembered cookie-file location.
5. Open the new EXE and choose your existing music folder when scanning.

Keep your existing music folders and manifests. You do not need to clone the repository, install development tools, or redownload existing songs.

## Troubleshooting

| Problem | What to do |
| --- | --- |
| The app will not open or reports missing DLL files | Use **Extract All** on the complete ZIP. Keep the EXE and all supporting folders together. |
| Download button is disabled | Scan a playlist and check the cookies message. Add or refresh the cookie file if needed. |
| Cookies are rejected | Export a fresh Netscape-format file while signed in on YouTube. Check that its name is `cookies.txt`, not `cookies.txt.txt`. |
| HTTP 403 or token errors | Set up the optional Docker provider above, open Docker Desktop, and run `docker start bgutil-provider`. |
| HTTP 429 | Wait before retrying. YouTube is limiting requests. |
| Container name already exists | Use `docker start bgutil-provider` instead of creating it again. |
| Docker is unavailable | Open Docker Desktop, wait for its engine, and check `docker info`. |
| Existing songs appear missing | Choose the original playlist folder and keep its audio and manifest together. |
| Older releases fail with Docker server 2.x | Upgrade to v2.2.4 or later. The token-provider plugin must match the server's major version; v2.2.4 bundles plugin 2.0.2 and a JavaScript runtime for YouTube. |
| Files cannot be written | Extract the app and choose a music folder in a writable location outside `Program Files`. |

To check the ZIP's checksum, open CMD in the folder containing your download and run:

```cmd
certutil -hashfile YouTubeMusicDownloader-Desktop-v2.2.6-win-x64.zip SHA256
```

Compare the result with the release's `.sha256` file.

## For developers: build from source

Normal users can use the portable release above. To develop the app, install Git, Python 3.13, the .NET 10 SDK, and FFmpeg/FFprobe. These commands can be pasted into CMD:

```cmd
winget install --id Git.Git --exact --source winget
winget install --id Python.Python.3.13 --exact --source winget
winget install --id Microsoft.DotNet.SDK.10 --exact --source winget
winget install --id Gyan.FFmpeg --exact --source winget
```

Close CMD and open a new window after installation, then run:

```cmd
cd /d "%USERPROFILE%"
git clone https://github.com/huyxs2005/youtube-music-downloader.git
cd youtube-music-downloader
powershell -NoProfile -ExecutionPolicy Bypass -File ".\Start Desktop.ps1"
```

The interface uses **C#/WPF and [WPF-UI](https://github.com/lepoco/wpfui)**. The Python engine handles downloading, metadata, manifests, and M3U8 generation. The old BAT launcher remains available for command-line use.

### Build the portable ZIP

Close the source-build app and run these commands from the project folder in CMD:

```cmd
powershell -NoProfile -ExecutionPolicy Bypass -File ".\installer\build-desktop.ps1" -Python ".\.venv\Scripts\python.exe"
.venv\Scripts\python.exe installer\package-desktop.py dist\YouTubeMusicDownloader-Desktop --version 2.2.6
powershell -NoProfile -ExecutionPolicy Bypass -File ".\installer\build-extractor.ps1" -ArchivePath ".\dist\releases\YouTubeMusicDownloader-Desktop-v2.2.6-win-x64.zip"
```

FFmpeg and FFprobe must be on `PATH`. A shared FFmpeg build reduces the installed size; its DLLs are copied with the tools. Alternatively, add `-FfmpegDirectory "C:\ffmpeg\bin"` to the build command, using your actual FFmpeg folder. The ZIP and checksum are written to `dist\releases`. Packaging includes only the launcher and `app` subfolder; private cookies and downloaded playlist folders beside the EXE are excluded. It refuses private files inside `app`.

The older `build-installer.ps1` builds the legacy command-line installer.

### Tests

Run from the project folder in CMD:

```cmd
.venv\Scripts\python.exe -m unittest discover -s tests -v
dotnet build tests\desktop -c Release
start "" /wait "tests\desktop\bin\Release\net10.0-windows\DesktopChecks.exe" "%CD%\desktop-checks.txt"
type desktop-checks.txt
```

The desktop checks use local fixtures without downloading from YouTube or using private cookies. For UI changes, also use the app and inspect screenshots at default and minimum sizes, including large playlists. Check both tabs, sorting, checkboxes, empty search results, filters, cookie controls, picker cancellation, and scrolling.

## Responsible use

Download only content you have permission to save, and follow applicable copyright laws and YouTube's terms. Never commit private cookies or downloaded media to this repository.
