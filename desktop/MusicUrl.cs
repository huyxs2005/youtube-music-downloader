using System.Text.RegularExpressions;

namespace YouTubeMusicDownloader.Desktop;

internal static class MusicUrl
{
    public static bool TryValidate(string input, out string normalized, out string error)
    {
        normalized = input.Trim().Trim('"');
        error = "Paste a playlist or song link from YouTube or YouTube Music.\n\nPlaylist:\nhttps://www.youtube.com/playlist?list=PLAYLIST_ID\n\nSong:\nhttps://www.youtube.com/watch?v=VIDEO_ID\n\nYouTube Music links and youtu.be Share links work too.";
        if (!Uri.TryCreate(normalized, UriKind.Absolute, out var uri) ||
            uri.Scheme is not ("http" or "https") || normalized.Any(char.IsWhiteSpace) ||
            !uri.IsDefaultPort || uri.UserInfo.Length > 0 ||
            uri.Host.ToLowerInvariant() is not ("music.youtube.com" or "youtube.com" or "www.youtube.com" or "m.youtube.com" or "youtu.be"))
            return false;
        try {
            var query = uri.Query.TrimStart('?').Split('&', StringSplitOptions.RemoveEmptyEntries)
                .Select(part => part.Split('=', 2))
                .Select(part => (Key: Uri.UnescapeDataString(part[0]), Value: part.Length == 2 ? Uri.UnescapeDataString(part[1].Replace('+', ' ')) : ""))
                .ToLookup(part => part.Key, part => part.Value, StringComparer.Ordinal);
            if (query["v"].Count() > 1 || query["list"].Count() > 1) {
                error = "This link contains conflicting song or playlist IDs. Copy a fresh link using Share on YouTube Music.";
                return false;
            }
            string path = uri.AbsolutePath.TrimEnd('/');
            if (uri.Host.Equals("youtu.be", StringComparison.OrdinalIgnoreCase)) {
                if (Regex.IsMatch(path, @"^/[A-Za-z0-9_-]{11}$")) return true;
                error = "This shortened song link has an invalid video ID. Copy the complete Share link from YouTube Music.";
                return false;
            }
            if (path == "/watch") {
                if (Regex.IsMatch(query["v"].FirstOrDefault() ?? "", @"^[A-Za-z0-9_-]{11}$")) return true;
                error = "The song link needs a valid 11-character video ID after v=. Copy the full song link from YouTube Music.";
                return false;
            }
            if (path == "/playlist") {
                if (Regex.IsMatch(query["list"].FirstOrDefault() ?? "", @"^[A-Za-z0-9_-]+$")) return true;
                error = "The playlist link needs a playlist ID after list=. Copy the full playlist link from YouTube Music.";
                return false;
            }
            error = "This YouTube page is not a song or playlist link. Open a song or playlist, then use Share to copy its link.";
            return false;
        } catch (UriFormatException) { return false; }
    }
}
