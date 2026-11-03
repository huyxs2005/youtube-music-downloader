using System.IO;
using System.Net.Http;
using System.Text.RegularExpressions;
using System.Windows.Media.Imaging;

namespace YouTubeMusicDownloader.Desktop;

internal static class PreviewImages
{
    private static readonly HttpClient Client = new() {
        Timeout = TimeSpan.FromSeconds(10), MaxResponseContentBufferSize = 20 * 1024 * 1024
    };

    private static IEnumerable<string> Candidates(SongRow song)
    {
        string original = song.ThumbnailUrl ?? "";
        if (Uri.TryCreate(original, UriKind.Absolute, out var source)) {
            if (source.Host.EndsWith(".ytimg.com", StringComparison.OrdinalIgnoreCase) &&
                Regex.IsMatch(song.VideoId, @"^[A-Za-z0-9_-]{11}$")) {
                foreach (string name in new[] { "maxresdefault", "sddefault", "hqdefault" })
                    yield return $"https://i.ytimg.com/vi/{song.VideoId}/{name}.jpg";
            } else {
                foreach (int size in new[] { 2048, 1600, 1200, 1008, 800 }) {
                    string larger = Regex.Replace(original, @"=w\d+-h\d+", $"=w{size}-h{size}");
                    larger = Regex.Replace(larger, @"=s\d+", $"=s{size}");
                    if (larger != original) yield return larger;
                }
            }
        }
        yield return original;
    }

    public static async Task<BitmapImage?> LoadAsync(SongRow song, CancellationToken cancellationToken)
    {
        BitmapImage? best = null;
        foreach (string candidate in Candidates(song).Distinct()) {
            cancellationToken.ThrowIfCancellationRequested();
            if (!Uri.TryCreate(candidate, UriKind.Absolute, out var uri) || uri.Scheme != Uri.UriSchemeHttps) continue;
            try {
                byte[] bytes = await Client.GetByteArrayAsync(uri, cancellationToken).ConfigureAwait(false);
                using var stream = new MemoryStream(bytes);
                var frame = BitmapFrame.Create(stream, BitmapCreateOptions.None, BitmapCacheOption.OnLoad);
                int originalWidth = frame.PixelWidth;
                stream.Position = 0;
                var image = new BitmapImage();
                image.BeginInit();
                image.CacheOption = BitmapCacheOption.OnLoad;
                image.DecodePixelWidth = Math.Min(1600, originalWidth);
                image.StreamSource = stream;
                image.EndInit();
                image.Freeze();
                if (best == null || image.PixelWidth > best.PixelWidth) best = image;
                // YouTube can return a tiny placeholder with HTTP 200 for missing artwork.
                if (originalWidth >= 640) return image;
            } catch (OperationCanceledException) when (cancellationToken.IsCancellationRequested) { throw; }
            catch (Exception) { /* Try the next available resolution. */ }
        }
        return best;
    }
}
