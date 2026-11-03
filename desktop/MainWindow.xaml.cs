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
using System.Windows.Media.Imaging;
using System.Windows.Media.Animation;
using Microsoft.Win32;

namespace YouTubeMusicDownloader.Desktop;

public partial class MainWindow : Wpf.Ui.Controls.FluentWindow
{
    private readonly ObservableCollection<SongRow> songs = [];
    private readonly BackendClient backend = new();
    private readonly Wpf.Ui.SnackbarService notifications = new();
    private ListCollectionView? view;
    private ListCollectionView? downloadView;
    private readonly HashSet<string> downloadSession = [];
    private bool showingDownloads;
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
    private Dictionary<DataGridColumn, double>? resizeBaseline;
    private CancellationTokenSource? metadataCancellation;
    private SongRow? draggedSong;
    private Point rowDragStart;
    private bool loadingOrder;
    private bool sidebarExpanded = true;
    private CancellationTokenSource? previewCancellation;

    public MainWindow()
    {
        Wpf.Ui.Appearance.ApplicationAccentColorManager.Apply(
            Color.FromRgb(255, 0, 0), Color.FromRgb(255, 0, 0),
            Color.FromRgb(204, 0, 0), Color.FromRgb(255, 82, 82));
        InitializeComponent();
        notifications.SetSnackbarPresenter(Notifications);
        UrlInput.TextChanged += (_, _) => UrlInput.ClearValue(Control.BorderBrushProperty);
        PreviewKeyDown += (_, e) => {
            if (e.Key == Key.Escape && ThumbnailPreview.Visibility == Visibility.Visible) {
                CloseThumbnailPreview();
                e.Handled = true;
            }
        };
        view = new ListCollectionView(songs) { Filter = MatchesFilter };
        downloadView = new ListCollectionView(songs) { Filter = item => downloadSession.Contains(((SongRow)item).VideoId) && MatchesFilter(item) };
        Tag = true;
        SongGrid.ItemsSource = view;
        SongGrid.AddHandler(Thumb.DragDeltaEvent, new DragDeltaEventHandler(ResizeColumn), true);
        SongGrid.PreviewMouseLeftButtonDown += BeginColumnResize;
        SongGrid.PreviewMouseMove += ContinueColumnResize;
        SongGrid.PreviewMouseLeftButtonUp += EndColumnResize;
        SongGrid.PreviewMouseLeftButtonDown += BeginRowDrag;
        SongGrid.PreviewMouseMove += ContinueRowDrag;
        SongGrid.AllowDrop = true;
        SongGrid.DragOver += RowDragOver;
        SongGrid.Drop += DropRow;
        SetSort("Position", ListSortDirection.Ascending);
        FolderInput.Text = BackendClient.ApplicationFolder;
        CheckCookies();
    }

    private bool MatchesFilter(object item)
    {
        var song = (SongRow)item;
        string search = SearchInput.Text.Trim();
        string filter = (StatusFilter.SelectedItem as ComboBoxItem)?.Content?.ToString() ?? "All songs";
        bool missing = song.Status is "Missing" or "Not selected";
        return (filter == "All songs" || (filter == "Not in selected playlist folder" ? missing : song.Status == filter)) &&
            (search.Length == 0 || string.Join(" ", song.Title, song.Artist, song.Album).Contains(search, StringComparison.CurrentCultureIgnoreCase));
    }
    private ListCollectionView? ActiveView => showingDownloads ? downloadView : view;
    private void Filter_Changed(object sender, RoutedEventArgs e) { view?.Refresh(); downloadView?.Refresh(); UpdateCounts(); }
    private void Playlists_Click(object sender, RoutedEventArgs e) => ShowPage(false);
    private void SidebarToggle_Click(object sender, RoutedEventArgs e)
    {
        bool show = sidebarExpanded = !sidebarExpanded;
        double width = Sidebar.ActualWidth, opacity = SidebarContent.Opacity, offset = SidebarContentOffset.X;
        double targetWidth = show ? 190 : 74;
        double targetOpacity = show ? 1 : 0;
        double targetOffset = show ? 0 : -16;
        Sidebar.Width = targetWidth;
        SidebarContent.Opacity = targetOpacity;
        SidebarContentOffset.X = targetOffset;
        SidebarContent.IsHitTestVisible = show;
        SidebarContent.IsEnabled = show;
        var duration = TimeSpan.FromMilliseconds(SystemParameters.ClientAreaAnimation ? 240 : 0);
        DoubleAnimation Slide(double from, double to) => new(from, to, duration) {
            EasingFunction = new CubicEase { EasingMode = EasingMode.EaseInOut }, FillBehavior = FillBehavior.Stop
        };
        Sidebar.BeginAnimation(WidthProperty, Slide(width, targetWidth));
        SidebarContent.BeginAnimation(OpacityProperty, Slide(opacity, targetOpacity));
        SidebarContentOffset.BeginAnimation(TranslateTransform.XProperty, Slide(offset, targetOffset));
        string label = show ? "Hide sidebar" : "Show sidebar";
        SidebarToggle.ToolTip = label;
        System.Windows.Automation.AutomationProperties.SetName(SidebarToggle, label);
    }
    private void Downloads_Click(object sender, RoutedEventArgs e) => ShowPage(true);
    private void ShowPage(bool downloads)
    {
        showingDownloads = downloads;
        SongGrid.ItemsSource = ActiveView;
        SongGrid.Columns[0].Visibility = downloads ? Visibility.Collapsed : Visibility.Visible;
        // Keep progress visible in a narrow Downloads view; metadata remains in Playlists.
        foreach (var column in SongGrid.Columns.Where(column => column.SortMemberPath is "Album" or "Duration"))
            column.Visibility = downloads ? Visibility.Collapsed : Visibility.Visible;
        SetupSection.Visibility = downloads ? Visibility.Collapsed : Visibility.Visible;
        CustomOrderToggle.Visibility = downloads ? Visibility.Collapsed : Visibility.Visible;
        DownloadButton.Visibility = downloads ? Visibility.Collapsed : Visibility.Visible;
        BackToPlaylistButton.Visibility = downloads ? Visibility.Visible : Visibility.Collapsed;
        ActivityPanel.Visibility = downloads ? Visibility.Visible : Visibility.Collapsed;
        PageLabel.Text = downloads ? "CURRENT PLAYLIST · DOWNLOADS" : "Playlist";
        PlaylistNav.Appearance = downloads ? Wpf.Ui.Controls.ControlAppearance.Secondary : Wpf.Ui.Controls.ControlAppearance.Primary;
        DownloadsNav.Appearance = downloads ? Wpf.Ui.Controls.ControlAppearance.Primary : Wpf.Ui.Controls.ControlAppearance.Secondary;
        if (downloads && sortProperty is "Album" or "Duration") SetSort("Position", ListSortDirection.Ascending);
        if (ActiveView != null) ActiveView.CustomSort = new SongComparer(CustomOrderToggle.IsChecked == true && !downloads ? "CustomPosition" : sortProperty ?? "Position", sortDirection);
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
        HeaderSelectionButton.Content = allSelected ? "✓" : selectedCount > 0 ? "−" : "+";
        HeaderSelectionButton.ToolTip = allSelected ? "Deselect all songs (including hidden songs)" : "Select all songs (including hidden songs)";
        System.Windows.Automation.AutomationProperties.SetName(HeaderSelectionButton, allSelected ? "Deselect all songs" : "Select all songs");
        HeaderSelectionButton.IsEnabled = !busy && songs.Count > 0;
        SelectionText.Text = showingDownloads ? $"{completed} of {session.Count} downloaded · {failed} failed" : $"{selectedCount} of {songs.Count} songs selected";
        SelectionHint.Text = CustomOrderToggle.IsChecked == true
            ? "Drag songs to arrange them. Download & sync saves this order to the M3U8; existing audio stays included."
            : "Existing audio stays in the M3U8 in YouTube order. Missing unchecked songs are skipped.";
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
    private async void VerifyCookies_Click(object sender, RoutedEventArgs e)
    {
        bool valid = CheckCookies();
        StatusText.Text = $"Cookie check {(valid ? "passed" : "failed")} at {DateTime.Now:T}. {CookieStatus.Text}";
        if (valid)
        {
            notifications.Show("Cookie file verified", "Format and local expiry checks passed.",
                Wpf.Ui.Controls.ControlAppearance.Secondary, null, TimeSpan.FromSeconds(4));
            return;
        }
        var resultDialog = new Wpf.Ui.Controls.MessageBox
        {
            Owner = this,
            Title = "Cookie file needs attention",
            Content = CookieStatus.Text + "\n\nChoose Add cookies.txt to select a fresh export from YouTube.",
            CloseButtonText = "OK"
        };
        await resultDialog.ShowDialogAsync();
    }
    private bool CheckCookies()
    {
        CookieCheck result;
        if (cookiesManuallyChosen) result = CookieFiles.Validate(CookiesInput.Text);
        else {
            string? target = snapshot?.GetProperty("folder").GetString();
            result = CookieFiles.Discover(new[] { BackendClient.ApplicationFolder, AppContext.BaseDirectory, BackendClient.Root, FolderInput.Text, target ?? "" }, CookieFiles.RememberedPath());
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
    private async Task ShowFetchErrorAsync(string message, bool invalidUrl = false)
    {
        StatusText.Text = "Fetch error · " + message;
        if (invalidUrl) {
            SetupSection.IsExpanded = true;
            UrlInput.BorderBrush = new SolidColorBrush(Color.FromRgb(255, 82, 82));
            UrlInput.Focus();
        }
        var warning = new Wpf.Ui.Controls.MessageBox {
            Owner = this, Title = invalidUrl ? "Invalid music URL" : "Could not fetch playlist or song",
            Content = new TextBlock {
                Text = message, TextWrapping = TextWrapping.Wrap, TextAlignment = TextAlignment.Left,
                HorizontalAlignment = HorizontalAlignment.Stretch, MaxWidth = 440
            }, CloseButtonText = "OK"
        };
        await warning.ShowDialogAsync();
    }
    private async void Scan_Click(object sender, RoutedEventArgs e)
    {
        if (busy) return;
        if (!MusicUrl.TryValidate(UrlInput.Text, out string url, out string error)) {
            InvalidateScan();
            await ShowFetchErrorAsync(error, invalidUrl: true);
            return;
        }
        UrlInput.Text = url;
        UrlInput.ClearValue(Control.BorderBrushProperty);
        if (!Directory.Exists(FolderInput.Text)) {
            await ShowFetchErrorAsync("Choose an existing music folder before scanning.");
            return;
        }
        InvalidateScan();
        metadataCancellation?.Cancel();
        SetBusy(true);
        StatusText.Text = "Scanning YouTube… 0 songs detected · 0 unavailable items";
        Progress.IsIndeterminate = true;
        Activity.Clear();
        string? fetchError = null;
        try {
            await backend.RunAsync(new { action = "scan", url, folder = FolderInput.Text }, element => {
                if (element.GetProperty("type").GetString() == "error") fetchError = element.GetProperty("message").GetString();
                else if (element.GetProperty("type").GetString() == "scan" &&
                    element.GetProperty("snapshot").GetProperty("rows").GetArrayLength() == 0)
                    fetchError = "No playable songs were found. The playlist may be empty, private, deleted, or unavailable. Check that the link opens in YouTube Music.";
                else HandleEvent(element);
            }, Log);
        } catch (Exception ex) { fetchError = ex.Message; }
        finally { SetBusy(false); Progress.IsIndeterminate = false; }
        if (fetchError != null) {
            Log(fetchError);
            await ShowFetchErrorAsync(fetchError + "\n\nCheck your internet connection and make sure the playlist or song is accessible. You can copy a fresh link using Share on YouTube Music, then try again.");
            return;
        }
        if (snapshot.HasValue) _ = FetchMetadataAsync();
    }
    private void HandleEvent(JsonElement element)
    {
        switch (element.GetProperty("type").GetString()) {
            case "scan_progress":
                int detected = element.GetProperty("detected").GetInt32();
                int unavailable = element.GetProperty("unavailable").GetInt32();
                string checking = element.TryGetProperty("checked", out var checkedFiles)
                    ? $" · Checking local files {checkedFiles.GetInt32():N0}/{element.GetProperty("total").GetInt32():N0}" : "";
                StatusText.Text = $"Scanning… {detected:N0} songs detected · {unavailable:N0} unavailable items{checking}";
                break;
            case "scan":
                snapshot = element.GetProperty("snapshot").Clone();
                CheckCookies();
                foreach (var song in songs) song.PropertyChanged -= SongChanged;
                songs.Clear();
                downloadSession.Clear();
                foreach (var item in snapshot.Value.GetProperty("rows").EnumerateArray()) {
                    var song = item.Deserialize<SongRow>(BackendClient.JsonOptions)!;
                    song.YouTubePosition = song.Position;
                    song.CustomPosition = song.Position;
                    song.PropertyChanged += SongChanged;
                    songs.Add(song);
                }
                PlaylistTitle.Text = snapshot.Value.GetProperty("title").GetString();
                loadingOrder = true;
                bool custom = snapshot.Value.TryGetProperty("customOrder", out var savedOrder) && savedOrder.GetArrayLength() > 0;
                if (custom) {
                    var ranks = savedOrder.EnumerateArray().Select((id, index) => (Id: id.GetString()!, Rank: index + 1)).ToDictionary(x => x.Id, x => x.Rank);
                    foreach (var song in songs) song.CustomPosition = ranks.GetValueOrDefault(song.VideoId, ranks.Count + song.YouTubePosition);
                }
                CustomOrderToggle.IsChecked = custom;
                loadingOrder = false;
                ApplyCustomOrder();
                SetupSection.IsExpanded = false;
                ShowPage(false);
                SetSort(custom ? "CustomPosition" : "Position", ListSortDirection.Ascending);
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
        SetupSection.IsEnabled = !value;
        CustomOrderToggle.IsEnabled = !value;
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
            string[]? customOrder = CustomOrderToggle.IsChecked == true
                ? songs.OrderBy(song => song.CustomPosition).Select(song => song.VideoId).ToArray() : null;
            await backend.RunAsync(new { action = "download", snapshot = snapshot.Value, selected, cookies, customOrder }, HandleEvent, Log);
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
    private async Task FetchMetadataAsync()
    {
        metadataCancellation?.Cancel();
        var cancellation = new CancellationTokenSource();
        metadataCancellation = cancellation;
        var currentSnapshot = snapshot!.Value;
        try {
            await new BackendClient().RunAsync(new { action = "metadata", snapshot = currentSnapshot, cookies = cookiesValid ? CookiesInput.Text : null }, element => {
                if (cancellation.IsCancellationRequested || element.GetProperty("type").GetString() != "metadata") return;
                string? id = element.GetProperty("videoId").GetString();
                foreach (var song in songs.Where(s => s.VideoId == id)) song.ApplyMetadata(element);
                view?.Refresh(); downloadView?.Refresh();
            }, _ => { }, cancellation.Token);
        } catch (OperationCanceledException) { }
        catch (Exception) {
            if (!cancellation.IsCancellationRequested)
                foreach (var song in songs) { song.MetadataFailed = true; song.MetadataChecked = true; }
        } finally {
            if (metadataCancellation == cancellation) metadataCancellation = null;
            cancellation.Dispose();
        }
    }
    private void CustomOrder_Changed(object sender, RoutedEventArgs e)
    {
        if (loadingOrder || view == null) return;
        if (CustomOrderToggle.IsChecked == true) {
            int rank = 1;
            // Start from the current display, keeping filtered-out songs in the arrangement.
            var visible = view.Cast<SongRow>().ToList();
            foreach (var song in visible.Concat(songs.Except(visible))) song.CustomPosition = rank++;
        }
        ApplyCustomOrder();
        SetSort(CustomOrderToggle.IsChecked == true ? "CustomPosition" : "Position", ListSortDirection.Ascending);
        UpdateCounts();
    }
    private void ApplyCustomOrder()
    {
        bool custom = CustomOrderToggle.IsChecked == true;
        SongGrid.CanUserSortColumns = !custom;
        int rank = 1;
        foreach (var song in songs.OrderBy(s => s.CustomPosition)) song.Position = custom ? rank++ : song.YouTubePosition;
    }
    private static T? ParentOf<T>(DependencyObject? source) where T : DependencyObject
    {
        while (source != null) {
            if (source is T result) return result;
            source = source is Visual || source is System.Windows.Media.Media3D.Visual3D
                ? VisualTreeHelper.GetParent(source) : LogicalTreeHelper.GetParent(source);
        }
        return null;
    }
    private async void Thumbnail_Click(object sender, RoutedEventArgs e)
    {
        if ((sender as FrameworkElement)?.DataContext is not SongRow song) return;
        PreviewTitle.Text = song.Title + " · " + song.Artist;
        previewCancellation?.Cancel();
        using var cancellation = new CancellationTokenSource();
        previewCancellation = cancellation;
        PreviewImage.Source = null;
        PreviewMessage.Text = "Loading...";
        PreviewMessage.Visibility = Visibility.Visible;
        ThumbnailPreview.Visibility = Visibility.Visible;
        try {
            var image = await PreviewImages.LoadAsync(song, cancellation.Token);
            cancellation.Token.ThrowIfCancellationRequested();
            PreviewImage.Source = image;
            if (image != null) PreviewMessage.Visibility = Visibility.Collapsed;
            else PreviewMessage.Text = "Could not load this thumbnail. Close and click it to try again.";
        } catch (OperationCanceledException) { }
        catch (Exception) {
            PreviewMessage.Text = "Could not load this thumbnail. Close and click it to try again.";
        } finally {
            if (previewCancellation == cancellation) previewCancellation = null;
        }
    }
    private void CloseThumbnailPreview()
    {
        previewCancellation?.Cancel();
        ThumbnailPreview.Visibility = Visibility.Collapsed;
        PreviewImage.Source = null;
    }
    private void ClosePreview_Click(object sender, RoutedEventArgs e) => CloseThumbnailPreview();
    private void PreviewBackdrop_MouseDown(object sender, MouseButtonEventArgs e)
    {
        if (ReferenceEquals(e.OriginalSource, sender)) CloseThumbnailPreview();
    }
    private void BeginRowDrag(object sender, MouseButtonEventArgs e)
    {
        draggedSong = null;
        if (busy || showingDownloads || CustomOrderToggle.IsChecked != true || e.Handled) return;
        var source = e.OriginalSource as DependencyObject;
        if (ParentOf<ButtonBase>(source) != null || ParentOf<Thumb>(source) != null) return;
        draggedSong = ParentOf<DataGridRow>(source)?.Item as SongRow;
        rowDragStart = e.GetPosition(SongGrid);
    }
    private void ContinueRowDrag(object sender, MouseEventArgs e)
    {
        if (draggedSong == null || busy || showingDownloads || e.LeftButton != MouseButtonState.Pressed) return;
        var point = e.GetPosition(SongGrid);
        if (Math.Abs(point.X - rowDragStart.X) < SystemParameters.MinimumHorizontalDragDistance &&
            Math.Abs(point.Y - rowDragStart.Y) < SystemParameters.MinimumVerticalDragDistance) return;
        var song = draggedSong;
        draggedSong = null;
        DragDrop.DoDragDrop(SongGrid, new DataObject("PlaylistSong", song.VideoId), DragDropEffects.Move);
    }
    private void RowDragOver(object sender, DragEventArgs e)
    {
        bool allowed = !busy && !showingDownloads && CustomOrderToggle.IsChecked == true && e.Data.GetDataPresent("PlaylistSong");
        e.Effects = allowed ? DragDropEffects.Move : DragDropEffects.None;
        e.Handled = true;
        if (!allowed || view == null) return;
        var visible = view.Cast<SongRow>().ToList();
        var row = ParentOf<DataGridRow>(e.OriginalSource as DependencyObject);
        if (row?.Item is not SongRow target) return;
        int index = visible.IndexOf(target);
        double y = e.GetPosition(SongGrid).Y;
        if (y < 85 && index > 0) SongGrid.ScrollIntoView(visible[index - 1]);
        else if (y > SongGrid.ActualHeight - 60 && index + 1 < visible.Count) SongGrid.ScrollIntoView(visible[index + 1]);
    }
    private void DropRow(object sender, DragEventArgs e)
    {
        if (busy || showingDownloads || CustomOrderToggle.IsChecked != true || !e.Data.GetDataPresent("PlaylistSong")) return;
        var source = songs.FirstOrDefault(s => s.VideoId == e.Data.GetData("PlaylistSong") as string);
        var row = ParentOf<DataGridRow>(e.OriginalSource as DependencyObject);
        var target = row?.Item as SongRow;
        if (source == null || target == null || source == target) return;
        var ordered = songs.OrderBy(s => s.CustomPosition).ToList();
        ordered.Remove(source);
        int index = ordered.IndexOf(target);
        if (e.GetPosition(row!).Y >= row!.ActualHeight / 2) index++;
        ordered.Insert(index, source);
        for (int i = 0; i < ordered.Count; i++) ordered[i].CustomPosition = i + 1;
        ApplyCustomOrder();
        SetSort("CustomPosition", ListSortDirection.Ascending);
        SongGrid.SelectedItem = source;
        e.Handled = true;
    }
    private void ResizeColumn(object sender, DragDeltaEventArgs e)
    {
        if (e.OriginalSource is not Thumb thumb || thumb.TemplatedParent is not DataGridColumnHeader header || header.Column == null) return;
        var column = header.Column;
        if (thumb.Name == "PART_LeftHeaderGripper")
            column = SongGrid.Columns.FirstOrDefault(c => c.DisplayIndex == column.DisplayIndex - 1);
        if (column == null || !column.CanUserResize) return;
        if (resizingColumn == null) ResizeColumnTo(column, column.ActualWidth + e.HorizontalChange, ColumnWidths());
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
        var clickedButton = ParentOf<ButtonBase>(e.OriginalSource as DependencyObject);
        if (e.ClickCount == 2 && (clickedButton == null || ReferenceEquals(clickedButton, header))) {
            AutoFitColumn(column ?? header.Column);
            e.Handled = true;
            return;
        }
        if (column == null || !column.CanUserResize) return;
        resizingColumn = column;
        resizeStart = e.GetPosition(SongGrid);
        resizeWidth = column.ActualWidth;
        resizeBaseline = ColumnWidths();
        Mouse.Capture(SongGrid, CaptureMode.SubTree);
        e.Handled = true;
    }
    private void ContinueColumnResize(object sender, MouseEventArgs e)
    {
        if (resizingColumn == null || e.LeftButton != MouseButtonState.Pressed) return;
        ResizeColumnTo(resizingColumn, resizeWidth + e.GetPosition(SongGrid).X - resizeStart.X, resizeBaseline!);
        e.Handled = true;
    }
    private void EndColumnResize(object sender, MouseButtonEventArgs e)
    {
        if (resizingColumn == null) return;
        resizingColumn = null;
        resizeBaseline = null;
        Mouse.Capture(null);
        e.Handled = true;
    }
    private Dictionary<DataGridColumn, double> ColumnWidths() => SongGrid.Columns
        .Where(column => column.Visibility == Visibility.Visible).ToDictionary(column => column, column => column.ActualWidth);
    private void ResizeColumnTo(DataGridColumn column, double requested, Dictionary<DataGridColumn, double> baseline)
    {
        if (!double.IsFinite(requested) || !baseline.ContainsKey(column)) return;
        double width = Math.Clamp(requested, column.MinWidth, column.MaxWidth);
        double remaining = width - baseline[column];
        foreach (var item in baseline) item.Key.Width = new DataGridLength(item.Value);
        column.Width = new DataGridLength(width);
        var right = baseline.Keys.Where(other => other.DisplayIndex > column.DisplayIndex && other.CanUserResize)
            .OrderBy(other => other.DisplayIndex).ToList();
        foreach (var other in right) {
            if (remaining <= 0) break;
            double shrink = Math.Min(remaining, Math.Max(0, baseline[other] - other.MinWidth));
            other.Width = new DataGridLength(baseline[other] - shrink);
            remaining -= shrink;
        }
        if (remaining < 0 && right.Count > 0)
            right[0].Width = new DataGridLength(baseline[right[0]] - remaining);
        // Once the columns on the right reach minimum width, extra width scrolls horizontally.
    }
    private void AutoFitColumn(DataGridColumn column)
    {
        if (!column.CanUserResize) return;
        var font = new Typeface(SongGrid.FontFamily, SongGrid.FontStyle, SongGrid.FontWeight, SongGrid.FontStretch);
        double pixelsPerDip = VisualTreeHelper.GetDpi(SongGrid).PixelsPerDip;
        double Measure(string text) => new FormattedText(text, System.Globalization.CultureInfo.CurrentCulture,
            FlowDirection.LeftToRight, font, SongGrid.FontSize, Brushes.White, pixelsPerDip).WidthIncludingTrailingWhitespace;
        double width = column.Header is string header ? Measure(header) + 44 : 44;
        if (column is DataGridTextColumn textColumn && textColumn.Binding is Binding binding) {
            var property = typeof(SongRow).GetProperty(binding.Path.Path);
            var rows = showingDownloads ? songs.Where(song => downloadSession.Contains(song.VideoId)) : songs;
            foreach (string text in rows.Select(song => property?.GetValue(song)?.ToString() ?? "").Distinct())
                width = Math.Max(width, Measure(text) + 30);
        }
        ResizeColumnTo(column, width, ColumnWidths());
    }
    private void SetSort(string property, ListSortDirection direction)
    {
        if (ActiveView == null) return;
        sortProperty = property;
        sortDirection = direction;
        ActiveView.CustomSort = new SongComparer(property, direction);
        foreach (var column in SongGrid.Columns)
            column.SortDirection = column.SortMemberPath == (property == "CustomPosition" ? "Position" : property) ? direction : null;
    }
    private void ResetSort_Click(object sender, RoutedEventArgs e) => SetSort("Position", ListSortDirection.Ascending);
    private void Window_Closing(object? sender, CancelEventArgs e)
    {
        if (!busy) metadataCancellation?.Cancel();
        if (!busy) return;
        e.Cancel = true;
        StatusText.Text = "Please wait for the current scan or sync to finish before closing.";
    }
}
