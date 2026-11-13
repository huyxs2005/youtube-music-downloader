# YouTube Music Downloader v2.2.6

- The first queued song now starts downloading immediately instead of waiting through the anti-hammering pauses. On a real download it began after about 8 seconds instead of about 53.
- Later songs are still paced to protect your account, with slightly shorter waits: 3 seconds between requests (was 5) and a random 10–25 second pause before each song (was 10–30).
- Adding a single song to a playlist also starts immediately.
- Scanning was never paced and is unchanged. Docker start-up behavior is unchanged.

If YouTube returns HTTP 429 or a bot check, wait before retrying.

Validation: 67 Python checks and the desktop checks, including new checks that only the first song skips the pauses.
