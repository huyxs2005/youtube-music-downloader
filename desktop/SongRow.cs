using System.ComponentModel;
using System.Globalization;
using System.Runtime.CompilerServices;
using System.Text.Json;

namespace YouTubeMusicDownloader.Desktop;

public sealed class SongRow : INotifyPropertyChanged
{
    public string VideoId { get; set; } = "";
    public int Position { get; set; }
    public string Title { get; set; } = "";
    public string Artist { get; set; } = "";
    public string? Album { get; set; }
    public string? Genre { get; set; }
    public double? Duration { get; set; }
    public long? FileSize { get; set; }
    public string Status { get; set; } = "Missing";
    private bool selected = true;
    public bool IsSelected { get => selected; set { selected = value; Changed(); } }
    public string AlbumText => string.IsNullOrWhiteSpace(Album) ? "Unknown" : Album;
    public string GenreText => string.IsNullOrWhiteSpace(Genre) ? "Unknown" : Genre;
    public string DurationText => Duration is double seconds ?
        (seconds >= 3600 ? TimeSpan.FromSeconds(seconds).ToString(@"h\:mm\:ss") : TimeSpan.FromSeconds(seconds).ToString(@"m\:ss")) : "Unknown";
    public string SizeText => FileSize is long bytes ? bytes switch {
        >= 1073741824 => $"{bytes / 1073741824d:0.##} GB",
        >= 1048576 => $"{bytes / 1048576d:0.##} MB",
        >= 1024 => $"{bytes / 1024d:0.##} KB",
        _ => $"{bytes} B"
    } : "Unknown";
    public void Apply(JsonElement element)
    {
        var updated = element.Deserialize<SongRow>(BackendClient.JsonOptions)!;
        Status = updated.Status;
        FileSize = updated.FileSize;
        Duration = updated.Duration;
        Genre = updated.Genre;
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
            "Position" => song.Position, "Title" => song.Title, "Artist" => song.Artist,
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
