"""Display metadata built from scan data only; never contacts YouTube.

An earlier version ran yt-dlp on every playlist song after each scan, unpaced, just to
refine the size column. That burst hundreds of requests with the user's cookies and was
mostly refused, so the duration-based estimate below is used for every song instead.
"""
import math


def positive_number(value):
    return value if isinstance(value, (int, float)) and math.isfinite(value) and value > 0 else None


def estimated_size(duration):
    seconds = positive_number(duration)
    return round(seconds * 160_000 / 8) if seconds else None


def describe(track):
    duration = positive_number(track.get("duration_seconds"))
    return dict(videoId=track["video_id"], genre=track.get("genre"), duration=duration,
                fileSize=estimated_size(duration), sizeEstimated=True,
                metadataChecked=True, metadataFailed=False)


def stream(request, emit):
    unique = {track["video_id"]: track for track in request["snapshot"]["tracks"]}
    for track in unique.values():
        emit("metadata", **describe(track))
