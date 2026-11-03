# YouTube Music Downloader v2.2.4

- Downloaded files use readable `Artist - Title.opus` names. YouTube IDs remain in the manifest for reliable updates.
- Existing local files with ID suffixes are renamed on the next download; manifest and M3U8 references are updated together. Audio and artwork are not re-encoded.
- Different recordings with the same filename receive a numbered suffix; existing files are never overwritten during migration.
- Open an older M3U8 without a manifest to import its filenames before scanning the YouTube playlist. Matching names are remembered for future downloads. Different recordings and ambiguous names are not guessed.
- Full playlist order, duplicate entries, selection, per-song progress and Docker support remain available.

For phone libraries, copy newly renamed audio along with the updated M3U8 into the same music folder, then refresh the playlist in your player. Missing audio still cannot play until its matching file is present.

Validation: 63 Python checks and the desktop checks cover migration, collision handling, legacy names, full playlist order and existing download behavior.
