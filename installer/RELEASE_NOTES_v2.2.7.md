# YouTube Music Downloader v2.2.7

- **No more request bursts after scanning.** The app used to inspect every song with yt-dlp right after a scan, with no pauses, just to refine the File Size column. On a 940-song playlist that meant hundreds of requests within minutes, and most were refused. File sizes before download are now estimated from the song's duration, so scanning sends no extra requests.
- **Faster song preparation.** If Deno or Node is installed, it is used to solve YouTube's challenges, about twice as fast as the bundled QuickJS (around 3.5 s instead of 6.5 s per song). PCs without them keep using the bundled runtime.
- **Tags and cover art are written in parallel**, so a slow cover image no longer holds up other songs from finishing.
- **No pause after scanning large playlists.** The song table updates once instead of once per song (about 0.05 s instead of 0.4 s for 940 songs).

Download pacing between songs and Docker start-up are unchanged.

Validation: 70 Python checks and 76 desktop checks.
