using System.Collections.ObjectModel;
using System.ComponentModel;
using System.Diagnostics;
using System.IO;
using System.Text.Json;
using System.Windows;
using System.Windows.Controls;
using System.Windows.Data;
using System.Windows.Controls.Primitives;
using System.Windows.Input;
using System.Windows.Media;
using Microsoft.Win32;

namespace YouTubeMusicDownloader.Desktop;

public partial class MainWindow : Wpf.Ui.Controls.FluentWindow
{
    private readonly ObservableCollection<SongRow> songs = [];
    private readonly BackendClient backend = new();
    private ListCollectionView? view;
    private ListCollectionView? downloadView;
    private readonly HashSet<string> downloadSession = [];
    private bool showingDownloads;
    private bool setupOpen = true;
    private JsonElement? snapshot;
    private bool busy;
    private readonly HashSet<string> pending = [];
    private int pendingTotal;
    private bool cookiesValid;
    private bool cookiesManuallyChosen;
    private bool updatingSelection;
    private string? sortProperty;
    private ListSortDirection sortDirection = ListSortDirection.Ascending;
    private DataGridColumn? resizingColumn;
    private Point resizeStart;
    private double resizeWidth;

    public MainWindow()
    {
        Wpf.Ui.Appearance.ApplicationAccentColorManager.Apply(
            Color.FromRgb(255, 0, 0), Color.FromRgb(255, 0, 0),
            Color.FromRgb(204, 0, 0), Color.FromRgb(255, 82, 82));
        InitializeComponent();
        view = new ListCollectionView(songs) { Filter = MatchesFilter };
        downloadView = new ListCollectionView(songs) { Filter = item => downloadSession.Contains(((SongRow)item).VideoId) && MatchesFilter(item) };
        Tag = true;
        SongGrid.ItemsSource = view;
        SongGrid.AddHandler(Thumb.DragDeltaEvent, new DragDeltaEventHandler(ResizeColumn), true);
        SongGrid.PreviewMouseLeftButtonDown += BeginColumnResize;
        SongGrid.PreviewMouseMove += ContinueColumnResize;
        SongGrid.PreviewMouseLeftButtonUp += EndColumnResize;
        SetSort("Position", ListSortDirection.Ascending);
        var music = Environment.GetFolderPath(Environment.SpecialFolder.MyMusic);
        if (Directory.Exists(music)) FolderInput.Text = music;
        CheckCookies();
    }

    private bool MatchesFilter(object item)
    {
        var song = (SongRow)item;
        string search = SearchInput.Text.Trim();
        string filter = (StatusFilter.SelectedItem as ComboBoxItem)?.Content?.ToString() ?? "All songs";
        bool missing = song.Status is "Missing" or "Not selected";
        return (filter == "All songs" || (filter == "Missing" ? missing : song.Status == filter)) &&
            (search.Length == 0 || string.Join(" ", song.Title, song.Artist, song.Album, song.Genre).Contains(search, StringComparison.CurrentCultureIgnoreCase));
    }
    private ListCollectionView? ActiveView => showingDownloads ? downloadView : view;
    private void Filter_Changed(object sender, RoutedEventArgs e) { view?.Refresh(); downloadView?.Refresh(); UpdateCounts(); }
    private void Setup_Click(object sender, RoutedEventArgs e)
    {
        setupOpen = !setupOpen;
        SetupPanel.Visibility = !showingDownloads && setupOpen ? Visibility.Visible : Visibility.Collapsed;
        SetupButton.Content = setupOpen ? "Hide setup · expand list" : "Playlist setup";
    }
    private void Playlists_Click(object sender, RoutedEventArgs e) => ShowPage(false);
    private void Downloads_Click(object sender, RoutedEventArgs e) => ShowPage(true);
    private void ShowPage(bool downloads)
    {
        showingDownloads = downloads;
        SongGrid.ItemsSource = ActiveView;
        SongGrid.Columns[0].Visibility = downloads ? Visibility.Collapsed : Visibility.Visible;
        // Keep progress visible in a narrow Downloads view; metadata remains in Playlists.
        foreach (int index in new[] { 4, 5, 6 }) SongGrid.Columns[index].Visibility = downloads ? Visibility.Collapsed : Visibility.Visible;
        SetupPanel.Visibility = !downloads && setupOpen ? Visibility.Visible : Visibility.Collapsed;
        SetupButton.Visibility = downloads ? Visibility.Collapsed : Visibility.Visible;
        SelectAllButton.Visibility = ClearSelectionButton.Visibility = downloads ? Visibility.Collapsed : Visibility.Visible;
        DownloadButton.Visibility = downloads ? Visibility.Collapsed : Visibility.Visible;
        BackToPlaylistButton.Visibility = downloads ? Visibility.Visible : Visibility.Collapsed;
        ActivityPanel.Visibility = downloads ? Visibility.Visible : Visibility.Collapsed;
        PageLabel.Text = downloads ? "CURRENT PLAYLIST · DOWNLOADS" : "PLAYLIST WORKSPACE";
        PlaylistNav.Appearance = downloads ? Wpf.Ui.Controls.ControlAppearance.Secondary : Wpf.Ui.Controls.ControlAppearance.Primary;
        DownloadsNav.Appearance = downloads ? Wpf.Ui.Controls.ControlAppearance.Primary : Wpf.Ui.Controls.ControlAppearance.Secondary;
        if (downloads && sortProperty is "Album" or "Genre" or "Duration") SetSort("Position", ListSortDirection.Ascending);
        if (ActiveView != null) ActiveView.CustomSort = new SongComparer(sortProperty ?? "Position", sortDirection);
        UpdateCounts();
    }
    private void UpdateCounts()
    {
        if (Counts == null || view == null) return;
        var session = songs.Where(s => downloadSession.Contains(s.VideoId)).ToList();
        int completed = session.Count(s => s.Status == "Downloaded"), failed = session.Count(s => s.Status == "Failed");
        Counts.Text = showingDownloads
            ? $"{session.Count} in this download  ·  {completed} downloaded  ·  {failed} failed  ·  {ActiveView?.Cast<SongRow>().Count()} shown"
            : $"{songs.Count} songs  ·  {songs.Count(s => s.Status == "Downloaded")} downloaded  ·  {view.Cast<SongRow>().Count()} shown";
        int selectedCount = songs.Count(s => s.IsSelected);
        bool allSelected = songs.Count > 0 && selectedCount == songs.Count;
        HeaderSelectionButton.Content = allSelected ? "☑" : selectedCount > 0 ? "▣" : "☐";
        HeaderSelectionButton.Appearance = allSelected ? Wpf.Ui.Controls.ControlAppearance.Primary : Wpf.Ui.Controls.ControlAppearance.Secondary;
        HeaderSelectionButton.ToolTip = allSelected ? "Deselect all songs (including hidden songs)" : "Select all songs (including hidden songs)";
        System.Windows.Automation.AutomationProperties.SetName(HeaderSelectionButton, allSelected ? "Deselect all songs" : "Select all songs");
        HeaderSelectionButton.IsEnabled = !busy && songs.Count > 0;
        SelectionText.Text = showingDownloads ? $"{completed} of {session.Count} downloaded · {failed} failed" : $"{selectedCount} of {songs.Count} songs selected";
        SelectionHint.Text = showingDownloads ? "Follow the current playlist here. Sorting changes the display only." : "Existing audio stays in the M3U8. Missing unchecked songs are skipped.";
        DownloadBadge.Text = session.Count == 0 ? "No active downloads" : busy ? $"{pending.Count} remaining" : $"{completed} downloaded · {failed} failed";
        bool noMatches = (showingDownloads ? session.Count : songs.Count) > 0 && ActiveView?.IsEmpty == true;
        EmptyState.Visibility = ActiveView?.IsEmpty == true ? Visibility.Visible : Visibility.Collapsed;
        EmptyTitle.Text = noMatches ? "No songs match your filters" : showingDownloads ? "No downloads yet" : "Your next listening session starts here";
        EmptyHint.Text = noMatches ? "Try another search or choose All songs." : showingDownloads ? "Choose songs in Playlists and start a download." : "Add a playlist URL and choose a folder to begin.";
        RetryButton.IsEnabled = !busy && cookiesValid && songs.Any(s => s.Status == "Failed");
    }
    private void Folder_Click(object sender, RoutedEventArgs e)
    {
        var picker = new OpenFolderDialog { Title = "Choose a music parent folder or an existing playlist folder" };
        if (picker.ShowDialog(this) == true) { FolderInput.Text = picker.FolderName; InvalidateScan(); CheckCookies(); }
    }
    private void Cookies_Click(object sender, RoutedEventArgs e)
    {
        var picker = new OpenFileDialog { Title = "Choose exported YouTube cookies.txt", Filter = "Cookie files (*.txt)|*.txt|All files|*.*" };
        if (picker.ShowDialog(this) != true) return;
        CookiesInput.Text = picker.FileName;
        cookiesManuallyChosen = true;
        if (CheckCookies()) CookieFiles.Remember(CookiesInput.Text);
    }
    private void VerifyCookies_Click(object sender, RoutedEventArgs e) => CheckCookies();
    private bool CheckCookies()
    {
        CookieCheck result;
        if (cookiesManuallyChosen) result = CookieFiles.Validate(CookiesInput.Text);
        else {
            string? target = snapshot?.GetProperty("folder").GetString();
            result = CookieFiles.Discover(new[] { AppContext.BaseDirectory, BackendClient.Root, FolderInput.Text, target ?? "" }, CookieFiles.RememberedPath());
        }
        CookiesInput.Text = result.Path;
        cookiesValid = result.IsValid;
        CookieStatus.Text = (result.IsValid && !cookiesManuallyChosen ? "Auto-detected · " : "") + result.Message;
        CookieStatus.Foreground = new System.Windows.Media.SolidColorBrush(result.IsValid
            ? System.Windows.Media.Color.FromRgb(229,229,229) : System.Windows.Media.Color.FromRgb(255,146,146));
        DownloadButton.IsEnabled = !busy && snapshot.HasValue && cookiesValid;
        RetryButton.IsEnabled = !busy && cookiesValid && songs.Any(s => s.Status == "Failed");
        return cookiesValid;
    }
    private void M3u_Click(object sender, RoutedEventArgs e)
    {
        var picker = new OpenFileDialog { Filter = "M3U8 playlists (*.m3u8)|*.m3u8" };
        if (picker.ShowDialog(this) != true) return;
        try {
            string folder = Path.GetDirectoryName(picker.FileName)!;
            using var doc = JsonDocument.Parse(File.ReadAllText(Path.Combine(folder, "playlist_manifest.json")));
            string id = doc.RootElement.GetProperty("playlist_id").GetString() ?? throw new IOException("Missing playlist ID.");
            UrlInput.Text = "https://music.youtube.com/playlist?list=" + Uri.EscapeDataString(id);
            FolderInput.Text = folder;
            InvalidateScan();
            CheckCookies();
            StatusText.Text = "Existing playlist loaded. Select Scan playlist to check YouTube for new songs.";
        } catch (Exception) {
            StatusText.Text = "This M3U8 needs its companion playlist_manifest.json to identify the YouTube playlist. Paste its URL and choose its music folder.";
        }
    }
    private void InvalidateScan() { snapshot = null; DownloadButton.IsEnabled = false; }
    private async void Scan_Click(object sender, RoutedEventArgs e)
    {
        if (busy) return;
        if (string.IsNullOrWhiteSpace(UrlInput.Text) || !Directory.Exists(FolderInput.Text)) {
            StatusText.Text = "Enter a YouTube URL and choose an existing music folder first."; return;
        }
        InvalidateScan();
        SetBusy(true);
        StatusText.Text = "Scanning YouTube and checking your local music files…";
        Progress.IsIndeterminate = true;
        Activity.Clear();
        try {
            await backend.RunAsync(new { action = "scan", url = UrlInput.Text.Trim(), folder = FolderInput.Text }, HandleEvent, Log);
        } catch (Exception ex) { StatusText.Text = ex.Message; }
        finally { SetBusy(false); Progress.IsIndeterminate = false; }
    }
    private void HandleEvent(JsonElement element)
    {
        switch (element.GetProperty("type").GetString()) {
            case "scan":
                snapshot = element.GetProperty("snapshot").Clone();
                CheckCookies();
                foreach (var song in songs) song.PropertyChanged -= SongChanged;
                songs.Clear();
                downloadSession.Clear();
                foreach (var item in snapshot.Value.GetProperty("rows").EnumerateArray()) {
                    var song = item.Deserialize<SongRow>(BackendClient.JsonOptions)!;
                    song.PropertyChanged += SongChanged;
                    songs.Add(song);
                }
                PlaylistTitle.Text = snapshot.Value.GetProperty("title").GetString();
                setupOpen = false;
                SetupButton.Content = "Playlist setup";
                ShowPage(false);
                SetSort("Position", ListSortDirection.Ascending);
                string note = snapshot.Value.GetProperty("single").GetBoolean() ? " This song will be inserted at position 1." : "";
                StatusText.Text = $"Scan complete. {snapshot.Value.GetProperty("skipped").GetArrayLength()} unavailable items skipped. Choose the songs to download.{note}";
                Progress.Value = 0;
                UpdateCounts();
                break;
            case "track":
                var id = element.GetProperty("videoId").GetString()!;
                foreach (var song in songs.Where(song => song.VideoId == id)) song.Apply(element);
                string status = element.GetProperty("status").GetString()!;
                if (status is "Downloaded" or "Failed" or "Not selected") pending.Remove(id);
                Progress.Value = pendingTotal == 0 ? 100 : 100d * (pendingTotal - pending.Count) / pendingTotal;
                view?.Refresh();
                downloadView?.Refresh();
                UpdateCounts();
                break;
            case "done":
                Progress.Value = 100;
                StatusText.Text = element.GetProperty("message").GetString();
                view?.Refresh(); downloadView?.Refresh(); UpdateCounts();
                break;
            case "error":
                StatusText.Text = element.GetProperty("message").GetString();
                Log(StatusText.Text ?? "Download error");
                break;
            case "log": StatusText.Text = element.GetProperty("message").GetString(); break;
        }
    }
    private void SongChanged(object? sender, PropertyChangedEventArgs e) { if (!updatingSelection) UpdateCounts(); }
    private void Log(string text)
    {
        // Keep long sessions responsive without growing an unbounded log.
        if (Activity.Text.Length > 18000) Activity.Text = Activity.Text[^12000..];
        Activity.AppendText(text + Environment.NewLine);
        Activity.ScrollToEnd();
    }
    private void SetBusy(bool value)
    {
        busy = value;
        Tag = !value;
        Inputs.IsEnabled = !value;
        SetupButton.IsEnabled = !value;
        SelectAllButton.IsEnabled = ClearSelectionButton.IsEnabled = !value;
        HeaderSelectionButton.IsEnabled = !value && songs.Count > 0;
        DownloadButton.IsEnabled = !value && snapshot.HasValue && cookiesValid;
        RetryButton.IsEnabled = !value && cookiesValid && songs.Any(s => s.Status == "Failed");
    }
    private async void Download_Click(object sender, RoutedEventArgs e) => await DownloadAsync();
    private async Task DownloadAsync()
    {
        if (busy || snapshot == null) return;
        if (UrlInput.Text.Trim() != snapshot.Value.GetProperty("url").GetString()) {
            InvalidateScan(); StatusText.Text = "The URL changed. Scan the playlist again before downloading."; return;
        }
        if (!CheckCookies()) { StatusText.Text = CookieStatus.Text; return; }
        string cookies = CookiesInput.Text;
        string[] selected = songs.Where(song => song.IsSelected).Select(song => song.VideoId).Distinct().ToArray();
        downloadSession.Clear();
        foreach (string id in selected) downloadSession.Add(id);
        SetBusy(true);
        pending.Clear();
        foreach (var song in songs.Where(s => s.IsSelected && s.Status != "Downloaded")) pending.Add(song.VideoId);
        pendingTotal = pending.Count;
        foreach (var song in songs.Where(s => pending.Contains(s.VideoId))) song.Status = "Queued";
        SearchInput.Clear();
        StatusFilter.SelectedIndex = 0;
        ShowPage(true);
        Progress.Value = 0;
        StatusText.Text = selected.Length == 0 ? "Updating the playlist using existing audio…" : "Downloading selected songs and syncing the playlist…";
        try {
            await backend.RunAsync(new { action = "download", snapshot = snapshot.Value, selected, cookies }, HandleEvent, Log);
        } catch (Exception ex) { StatusText.Text = ex.Message; }
        finally { SetBusy(false); view?.Refresh(); downloadView?.Refresh(); UpdateCounts(); }
    }
    private void SetSelection(bool selected)
    {
        if (busy) return;
        updatingSelection = true;
        try { foreach (var song in songs) song.IsSelected = selected; }
        finally { updatingSelection = false; UpdateCounts(); }
    }
    private void HeaderSelection_Click(object sender, RoutedEventArgs e)
    {
        if (!busy && songs.Count > 0) SetSelection(!songs.All(song => song.IsSelected));
    }
    private void SelectAll_Click(object sender, RoutedEventArgs e) => SetSelection(true);
    private void Clear_Click(object sender, RoutedEventArgs e) => SetSelection(false);
    private async void Retry_Click(object sender, RoutedEventArgs e)
    {
        if (busy) return;
        foreach (var song in songs) song.IsSelected = song.Status == "Failed";
        await DownloadAsync();
    }
    private void Grid_Sorting(object sender, DataGridSortingEventArgs e)
    {
        e.Handled = true;
        var direction = sortProperty == e.Column.SortMemberPath && sortDirection == ListSortDirection.Ascending
            ? ListSortDirection.Descending : ListSortDirection.Ascending;
        SetSort(e.Column.SortMemberPath, direction);
    }
    private void ResizeColumn(object sender, DragDeltaEventArgs e)
    {
        if (e.OriginalSource is not Thumb thumb || thumb.TemplatedParent is not DataGridColumnHeader header || header.Column == null) return;
        var column = header.Column;
        if (thumb.Name == "PART_LeftHeaderGripper")
            column = SongGrid.Columns.FirstOrDefault(c => c.DisplayIndex == column.DisplayIndex - 1);
        if (column == null || !column.CanUserResize) return;
        column.Width = new DataGridLength(Math.Clamp(column.ActualWidth + e.HorizontalChange, column.MinWidth, column.MaxWidth));
        e.Handled = true;
    }
    private void BeginColumnResize(object sender, MouseButtonEventArgs e)
    {
        DependencyObject? source = e.OriginalSource as DependencyObject;
        while (source != null && source is not DataGridColumnHeader) source = VisualTreeHelper.GetParent(source);
        if (source is not DataGridColumnHeader header || header.Column == null) return;
        double x = e.GetPosition(header).X;
        DataGridColumn? column = x >= header.ActualWidth - 6 ? header.Column : x <= 6
            ? SongGrid.Columns.FirstOrDefault(c => c.DisplayIndex == header.Column.DisplayIndex - 1) : null;
        if (column == null || !column.CanUserResize) return;
        resizingColumn = column;
        resizeStart = e.GetPosition(SongGrid);
        resizeWidth = column.ActualWidth;
        Mouse.Capture(SongGrid, CaptureMode.SubTree);
        e.Handled = true;
    }
    private void ContinueColumnResize(object sender, MouseEventArgs e)
    {
        if (resizingColumn == null || e.LeftButton != MouseButtonState.Pressed) return;
        resizingColumn.Width = new DataGridLength(Math.Clamp(resizeWidth + e.GetPosition(SongGrid).X - resizeStart.X,
            resizingColumn.MinWidth, resizingColumn.MaxWidth));
        e.Handled = true;
    }
    private void EndColumnResize(object sender, MouseButtonEventArgs e)
    {
        if (resizingColumn == null) return;
        resizingColumn = null;
        Mouse.Capture(null);
        e.Handled = true;
    }
    private void SetSort(string property, ListSortDirection direction)
    {
        if (ActiveView == null) return;
        sortProperty = property;
        sortDirection = direction;
        ActiveView.CustomSort = new SongComparer(property, direction);
        foreach (var column in SongGrid.Columns)
            column.SortDirection = column.SortMemberPath == property ? direction : null;
    }
    private void ResetSort_Click(object sender, RoutedEventArgs e) => SetSort("Position", ListSortDirection.Ascending);
    private void Window_Closing(object? sender, CancelEventArgs e)
    {
        if (!busy) return;
        e.Cancel = true;
        StatusText.Text = "Please wait for the current scan or sync to finish before closing.";
    }
}
