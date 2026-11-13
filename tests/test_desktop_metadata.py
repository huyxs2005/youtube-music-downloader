import unittest
from unittest.mock import patch

import desktop_metadata
import ytmusic_downloader as engine


class DesktopMetadataTests(unittest.TestCase):
    def test_metadata_uses_scan_data_and_never_contacts_youtube(self):
        tracks = [
            dict(video_id="a", duration_seconds=200, genre="Pop"),
            dict(video_id="b", duration_seconds=None, genre=None),
            dict(video_id="a", duration_seconds=200, genre="Pop"),  # repeated playlist entry
        ]
        events = []
        with patch.object(engine, "YoutubeDL", side_effect=AssertionError("must not contact YouTube")):
            desktop_metadata.stream(dict(snapshot=dict(tracks=tracks), cookies="cookies.txt"),
                                    lambda kind, **values: events.append((kind, values)))
        self.assertEqual([kind for kind, _ in events], ["metadata", "metadata"])
        rows = {values["videoId"]: values for _, values in events}
        self.assertEqual(rows["a"], dict(videoId="a", genre="Pop", duration=200, fileSize=4_000_000,
                                         sizeEstimated=True, metadataChecked=True, metadataFailed=False))
        self.assertEqual(rows["b"]["fileSize"], None)
        self.assertTrue(rows["b"]["metadataChecked"])


if __name__ == "__main__":
    unittest.main()
