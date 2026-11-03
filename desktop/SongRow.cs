using System.ComponentModel;
using System.Globalization;
using System.Runtime.CompilerServices;
using System.Text.Json;
using System.Windows.Media.Imaging;

namespace YouTubeMusicDownloader.Desktop;

public sealed class SongRow : INotifyPropertyChanged
{
    public string VideoId { get; set; } = "";
    private int position;
    public int Position { get => position; set { position = value; Changed(); } }
    public int YouTubePosition { get; set; }
    public int CustomPosition { get; set; }
    public string Title { get; set; } = "";
    public string? ThumbnailUrl { get; set; }
    private BitmapImage? thumbnail;
    private bool thumbnailRequested;
    public BitmapImage? Thumbnail
    {
        get {
            if (thumbnailRequested) return thumbnail;
            thumbnailRequested = true;
            if (Uri.TryCreate(ThumbnailUrl, UriKind.Absolute, out var uri) && uri.Scheme == Uri.UriSchemeHttps) {
                try {
                    thumbnail = new BitmapImage();
                    thumbnail.BeginInit();
                    thumbnail.DecodePixelWidth = 72;
                    thumbnail.UriSource = uri;
                    thumbnail.EndInit();
                } catch (Exception) { thumbnail = null; }
            }
            return thumbnail;
        }
    }
    public string Artist { get; set; } = "";
    public string? Album { get; set; }
    public string? Genre { get; set; }
    public double? Duration { get; set; }
    public long? FileSize { get; set; }
    public bool SizeEstimated { get; set; }
    public bool MetadataFailed { get; set; }
    private bool metadataChecked;
    public bool MetadataChecked { get => metadataChecked; set { metadataChecked = value; Changed(nameof(GenreText)); Changed(nameof(SizeText)); } }
    public string Status { get; set; } = "Missing";
    public double? DownloadPercent { get; private set; }
    public string DownloadStage { get; private set; } = "Downloading";
    public string? ErrorMessage { get; private set; }
    public string StatusText => Status is "Missing" or "Not selected" ? "Not in selected playlist folder"
        : Status == "Downloading" ? DownloadPercent.HasValue ? $"{DownloadStage} {DownloadPercent.Value:0}%" : DownloadStage + "…"
        : Status;
    public string StatusDescription => ErrorMessage ?? StatusText;
    public void ApplyProgress(JsonElement element)
    {
        if (Status is "Downloaded" or "Failed") return;
        Status = "Downloading";
        DownloadPercent = element.TryGetProperty("percent", out var percent) && percent.ValueKind == JsonValueKind.Number
            ? Math.Clamp(percent.GetDouble(), 0, 100) : null;
        DownloadStage = element.TryGetProperty("stage", out var stage) ? stage.GetString() ?? "Downloading" : "Downloading";
        Changed(nameof(StatusText)); Changed(nameof(StatusDescription));
    }
    public void ApplyError(string error)
    {
        Status = "Failed";
        ErrorMessage = error;
        Changed(nameof(StatusText)); Changed(nameof(StatusDescription));
    }
    private bool selected = true;
    public bool IsSelected { get => selected; set { selected = value; Changed(); } }
    public string AlbumText => string.IsNullOrWhiteSpace(Album) || Album.Equals("Unknown", StringComparison.OrdinalIgnoreCase) ? "None" : Album;
    public string GenreText => string.IsNullOrWhiteSpace(Genre) ? (MetadataChecked ? (MetadataFailed ? "Unavailable" : "Not provided") : "Loading…") : Genre;
    public string DurationText => Duration is double seconds ?
        (seconds >= 3600 ? TimeSpan.FromSeconds(seconds).ToString(@"h\:mm\:ss") : TimeSpan.FromSeconds(seconds).ToString(@"m\:ss")) : "Unknown";
    public string SizeText => FileSize is long bytes ? (SizeEstimated ? "~" : "") + (bytes switch {
        >= 1073741824 => $"{bytes / 1073741824d:0.##} GB",
        >= 1048576 => $"{bytes / 1048576d:0.##} MB",
        >= 1024 => $"{bytes / 1024d:0.##} KB",
        _ => $"{bytes} B"
    }) : MetadataChecked ? "Unavailable" : "Loading…";
    public void ApplyMetadata(JsonElement element)
    {
        var updated = element.Deserialize<SongRow>(BackendClient.JsonOptions)!;
        Genre = updated.Genre ?? Genre;
        MetadataFailed = updated.MetadataFailed;
        Duration = updated.Duration ?? Duration;
        if (FileSize == null || SizeEstimated) {
            FileSize = updated.FileSize ?? FileSize;
            SizeEstimated = updated.FileSize != null ? updated.SizeEstimated : SizeEstimated;
        }
        MetadataChecked = true;
        Changed("");
    }
    public void Apply(JsonElement element)
    {
        var updated = element.Deserialize<SongRow>(BackendClient.JsonOptions)!;
        Status = updated.Status;
        if (Status == "Queued") { DownloadPercent = null; DownloadStage = "Downloading"; ErrorMessage = null; }
        if (Status == "Downloaded") { DownloadPercent = 100; ErrorMessage = null; }
        FileSize = updated.FileSize ?? FileSize;
        SizeEstimated = updated.FileSize != null ? updated.SizeEstimated : SizeEstimated;
        Duration = updated.Duration ?? Duration;
        Genre = updated.Genre ?? Genre;
        Changed("");
    }
    public event PropertyChangedEventHandler? PropertyChanged;
    private void Changed([CallerMemberName] string? name = null) => PropertyChanged?.Invoke(this, new(name));
}

// Sort raw values, not formatted strings. Null metadata stays last in both directions.
public sealed class SongComparer(string property, ListSortDirection direction) : System.Collections.IComparer
{
    public int Compare(object? x, object? y)
    {
        var a = (SongRow)x!;
        var b = (SongRow)y!;
        object? Value(SongRow song) => property switch {
            "Position" => song.Position, "CustomPosition" => song.CustomPosition, "Title" => song.Title, "Artist" => song.Artist,
            "Album" => song.Album, "Genre" => song.Genre, "Duration" => song.Duration,
            "FileSize" => song.FileSize, "Status" => song.Status, _ => song.Position
        };
        object? left = Value(a), right = Value(b);
        bool Missing(object? value) => value is null || value is string s && string.IsNullOrWhiteSpace(s);
        int result;
        if (Missing(left) || Missing(right))
            result = Missing(left) == Missing(right) ? 0 : Missing(left) ? 1 : -1;
        else {
            result = left is string text ? CultureInfo.CurrentCulture.CompareInfo.Compare(text, (string)right!, CompareOptions.IgnoreCase) : ((IComparable)left!).CompareTo(right);
            if (direction == ListSortDirection.Descending) result = -result;
        }
        return result != 0 ? result : a.Position.CompareTo(b.Position);
    }
}
