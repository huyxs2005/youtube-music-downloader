# YouTube Music Downloader v2.2.5

- Old audio copied straight into a playlist folder (for example from a phone) is now recognized during scanning, even without importing its old M3U8.
- Artist separators no longer matter: `Chevy & City Girl - Daydreaming.opus` is matched to the song the app names `Chevy, City Girl - Daydreaming.opus`. Matching ignores punctuation and accents, the same rules used for imported M3U8 names.
- The existing filename is kept and written into the manifest and M3U8 on the next download, so phone playlists keep pointing at files already on the phone.
- A file that already belongs to another song in the manifest is never reused, and ambiguous matches are still not guessed.

Validation: Python checks cover the new folder matching alongside the existing migration, collision and legacy-name tests.
