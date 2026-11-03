# YouTube Music Downloader v2.2.2

- Fixed a download compatibility fault: the old token-provider plugin was version 1.3.1 while current Docker servers use 2.0.2. This release bundles plugin 2.0.2 and updated yt-dlp.
- Bundled QuickJS-NG and YouTube's JavaScript challenge-solver scripts. No separate host JavaScript runtime installation is needed.
- Removed forced YouTube client settings so yt-dlp can choose supported clients.
- The Status column now shows actual per-song transfer percentages and distinguishes processing from completed downloads.
- Failed downloads show actionable reasons in Activity, their status tooltip, and `download_errors.log`. Sensitive headers and signed URL queries are removed from diagnostics.
- Fixed large-playlist startup pauses by batching manifest writes and initial row updates instead of rewriting and refreshing the entire playlist for each unchecked song.
- Pauses background metadata requests during downloads and keeps the user's cookie export read-only across workers.
- Newly created Docker providers publish their port to localhost only. Existing running containers are left alone.
- Reuses an already-running token provider immediately instead of waiting on a redundant Docker startup check.

Close the old app before extracting over it. Keep your `cookies.txt`, playlist folders, audio, and manifests. The existing playlist folder is reused; **Retry failed** can retry missing songs.

Both the regular ZIP and optional **…-extract.exe** contain the same portable app. The extractor opens the inner app folder after extraction. Windows x64; unsigned downloads, with separate SHA-256 checksums.

Validation: 54 Python tests and 73 WPF/bridge checks passed. A real song was downloaded, converted and added to an M3U8 by the packaged engine with only bundled tools available; real percentage events were verified. A 1,000-song/two-selection fixture verified four manifest writes and batched row updates.
