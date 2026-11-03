"""Report playlist rows as each real YouTube response arrives."""
from ytmusicapi import YTMusic
from ytmusicapi.parsers.playlists import parse_playlist_items


class ProgressYTMusic(YTMusic):
    def __init__(self, report):
        self.report = report
        self.progress_items = []
        self.progress_reliable = True
        self.detected = 0
        self.unavailable = 0
        super().__init__()

    @staticmethod
    def playlist_pages(value):
        if isinstance(value, dict):
            for key in ("musicPlaylistShelfRenderer", "musicPlaylistShelfContinuation"):
                if key in value:
                    yield value[key].get("contents", [])
                    return
            if "appendContinuationItemsAction" in value:
                yield value["appendContinuationItemsAction"].get("continuationItems", [])
                return
            for child in value.values():
                yield from ProgressYTMusic.playlist_pages(child)
        elif isinstance(value, list):
            for child in value:
                yield from ProgressYTMusic.playlist_pages(child)

    def _send_request(self, endpoint, body, additionalParams=""):
        response = super()._send_request(endpoint, body, additionalParams)
        for page in self.playlist_pages(response):
            for item in page:
                if "musicResponsiveListItemRenderer" not in item:
                    continue  # Continuation buttons and headings are not songs.
                try:
                    parsed = parse_playlist_items([item])
                except (KeyError, TypeError, IndexError, ValueError):
                    self.progress_reliable = False
                    continue  # Let the normal library parser handle unfamiliar responses.
                song = parsed[0] if parsed else {"videoId": None}
                self.progress_items.append(song)
                if song.get("videoId") and song.get("isAvailable") is not False:
                    self.detected += 1
                else:
                    self.unavailable += 1
                self.report(self.detected, self.unavailable)
        return response
