using System.Collections.ObjectModel;
using System.ComponentModel;
using System.IO;
using System.Reflection;
using System.Text.Json;
using System.Windows;
using System.Windows.Controls;
using System.Windows.Data;
using System.Windows.Controls.Primitives;
using System.Windows.Media;
using YouTubeMusicDownloader.Desktop;

internal static class Program
{
    private static int checks;
    private static void Check(bool condition, string message) {
        if (!condition) throw new Exception(message);
        checks++;
    }
    private static object? Call(MainWindow window, string name, params object[] args) =>
        typeof(MainWindow).GetMethod(name, BindingFlags.NonPublic | BindingFlags.Instance)!.Invoke(window, args);
    private static T Field<T>(MainWindow window, string name) =>
        (T)typeof(MainWindow).GetField(name, BindingFlags.NonPublic | BindingFlags.Instance)!.GetValue(window)!;
    private static IEnumerable<T> Visuals<T>(DependencyObject parent) where T : DependencyObject {
        for(int i=0;i<VisualTreeHelper.GetChildrenCount(parent);i++) {
            var child=VisualTreeHelper.GetChild(parent,i);
            if(child is T match) yield return match;
            foreach(var descendant in Visuals<T>(child)) yield return descendant;
        }
    }
    [STAThread]
    public static void Main(string[] args)
    {
        string report = Path.GetFullPath(args.FirstOrDefault() ?? "desktop-checks.txt");
        var app = new Application();
        app.Resources = new ResourceDictionary { Source = new Uri("/YouTubeMusicDownloader.Desktop;component/Resources.xaml",UriKind.Relative) };
        var window = new MainWindow();
        if (args.Contains("--compact")) { window.Width=window.MinWidth; window.Height=window.MinHeight; }
        window.Loaded += async (_, _) => {
            bool verified = false;
            string temp = Path.Combine(Path.GetTempPath(), "ytm-desktop-checks-" + Guid.NewGuid().ToString("N"));
            try {
                Directory.CreateDirectory(temp);
                // Two real local files and one missing song, deliberately sorted differently by each column.
                File.WriteAllBytes(Path.Combine(temp, "a.opus"), new byte[100]);
                File.WriteAllBytes(Path.Combine(temp, "b.opus"), new byte[20]);
                string cookieFile = Path.Combine(temp,"cookies.txt");
                string cookieHeader = "# Netscape HTTP Cookie File\n";
                string validCookies = cookieHeader+".youtube.com\tTRUE\t/\tTRUE\t0\tTEST_COOKIE\tfixture-only\n";
                File.WriteAllText(cookieFile,validCookies);
                Check(CookieFiles.Validate(cookieFile).IsValid,"Session cookies should validate");
                Check(CookieFiles.Discover(new[]{temp}).Path==cookieFile,"Existing cookies.txt should auto-detect without picker");
                Check(!CookieFiles.Validate(Path.Combine(temp,"absent.txt")).IsValid,"Missing cookie file rejected");
                File.WriteAllText(cookieFile,cookieHeader+".example.com\tTRUE\t/\tTRUE\t0\tTEST\tfixture-only\n");
                Check(!CookieFiles.Validate(cookieFile).IsValid,"Other website cookie file rejected");
                File.WriteAllText(cookieFile,cookieHeader+".youtube.com\tTRUE\t/\tTRUE\t1\tTEST\tfixture-only\n");
                Check(!CookieFiles.Validate(cookieFile).IsValid,"Expired cookie file rejected");
                File.WriteAllText(cookieFile,"{\"cookies\":[]}");
                Check(!CookieFiles.Validate(cookieFile).IsValid,"JSON cookie file rejected");
                File.WriteAllText(cookieFile,validCookies);
                string url = "https://music.youtube.com/playlist?list=PL-desktop-checks";
                var source = new[] {
                    new {video_id="a", title="Zulu", artists=new[]{"Beta"}, filename="a.opus", index=1, duration_seconds=(double?)600, genre=(string?)"Rock"},
                    new {video_id="b", title="Alpha", artists=new[]{"Alpha"}, filename="b.opus", index=2, duration_seconds=(double?)90, genre=(string?)"Jazz"},
                    new {video_id="c", title="日本語", artists=new[]{"Gamma"}, filename="c.opus", index=3, duration_seconds=(double?)null, genre=(string?)null}
                };
                var rows = source.Select(s => new {videoId=s.video_id, position=s.index, title=s.title, artist=s.artists[0], album=(string?)null,
                    genre=s.genre, duration=s.duration_seconds, fileSize=s.video_id == "c" ? (long?)null : new FileInfo(Path.Combine(temp,s.filename)).Length,
                    status=s.video_id == "c" ? "Missing" : "Downloaded"}).ToArray();
                var tracks = source.Select(s => new {s.index,s.video_id,set_video_id=(string?)null,s.title,s.artists,album=(string?)null,
                    thumbnail_url=(string?)null,s.filename,s.duration_seconds,s.genre}).ToArray();
                var snapshot = new { url,folder=temp,playlistId="PL-desktop-checks",title="Desktop verification",single=false,total=3,skipped=Array.Empty<int>(),tracks,rows };
                Call(window,"HandleEvent",JsonSerializer.SerializeToElement(new {type="scan", snapshot}));
                Field<Wpf.Ui.Controls.TextBox>(window,"UrlInput").Text = url;
                Field<Wpf.Ui.Controls.TextBox>(window,"CookiesInput").Text = cookieFile;
                typeof(MainWindow).GetField("cookiesManuallyChosen",BindingFlags.NonPublic|BindingFlags.Instance)!.SetValue(window,true);
                Check((bool)Call(window,"CheckCookies")!,"Valid selected file should enable download flow");
                Check(Field<TextBlock>(window,"CookieStatus").Text.Contains("checked"),"Cookie validation is visible");
                var songs = Field<ObservableCollection<SongRow>>(window,"songs");
                var view = Field<ListCollectionView>(window,"view");
                var grid = Field<Wpf.Ui.Controls.DataGrid>(window,"SongGrid");
                Check(songs.Count == 3,"Scan should load all rows");
                Check(songs[0].AlbumText=="None","Missing albums should display None");
                Check(songs[2].StatusText=="Not in selected playlist folder","Missing local audio should have an explicit status");
                Call(window,"HandleEvent",JsonSerializer.SerializeToElement(new {type="tracks",updates=new[]{new {videoId="a",status="Queued"},new {videoId="b",status="Not selected"}}}));
                Check(songs[0].Status=="Queued" && songs[1].Status=="Not selected","Initial download statuses should apply as a batch");
                Call(window,"HandleEvent",JsonSerializer.SerializeToElement(new {type="track_progress",videoId="a",percent=37.0,stage="Downloading"}));
                Check(songs[0].StatusText=="Downloading 37%","Downloading rows should show actual transfer percentages");
                Call(window,"HandleEvent",JsonSerializer.SerializeToElement(new {type="track_progress",videoId="a",percent=100.0,stage="Processing"}));
                Check(songs[0].StatusText=="Processing 100%","Transfer completion should distinguish audio processing from a finished song");
                Call(window,"HandleEvent",JsonSerializer.SerializeToElement(new {type="track_error",videoId="a",error="HTTP 403: fixture failure"}));
                Check(songs[0].Status=="Failed" && songs[0].StatusDescription.Contains("HTTP 403"),"Failed rows should retain the actionable reason in their tooltip");
                Call(window,"HandleEvent",JsonSerializer.SerializeToElement(new {type="tracks",updates=new[]{new {videoId="a",status="Downloaded"},new {videoId="b",status="Downloaded"}}}));
                Check(grid.Columns.Any(c=>c.Header as string=="Thumbnail") && !grid.Columns.Any(c=>c.SortMemberPath=="Genre"),"Thumbnail should replace genre in the table");
                Call(window,"HandleEvent",JsonSerializer.SerializeToElement(new {type="scan_progress",detected=120,unavailable=8}));
                Check(Field<TextBlock>(window,"StatusText").Text.Contains("120 songs detected") && Field<TextBlock>(window,"StatusText").Text.Contains("8 unavailable"),"Live scan counters should display real counts");
                window.UpdateLayout();
                Check(!Field<Expander>(window,"SetupSection").IsExpanded,"Scan should collapse setup to expand the song list");
                await Task.Delay(400); // Allow the setup section's collapse animation to finish.
                window.UpdateLayout();
                Check(grid.ActualHeight>=320,$"Song list should have room for many rows after scanning (height {grid.ActualHeight:0})");
                Call(window,"ShowPage",true);
                Check(Field<TextBlock>(window,"EmptyTitle").Text=="No downloads yet","Downloads tab should explain an empty queue");
                Check(grid.Columns.Single(c=>c.SortMemberPath=="Album").Visibility==Visibility.Collapsed && grid.Columns.Single(c=>c.SortMemberPath=="Status").Visibility==Visibility.Visible,"Downloads should prioritize status over album metadata");
                Call(window,"ShowPage",false);
                Check(grid.Columns.Single(c=>c.SortMemberPath=="Album").Visibility==Visibility.Visible,"Playlist tab should restore all metadata columns");
                Check(((ListCollectionView)grid.ItemsSource).Count==3,"Returning to Playlists should restore all songs");
                Call(window,"SetBusy",true);
                Check(grid.IsEnabled && !(bool)window.Tag,"During a download, browsing remains enabled and selection is locked");
                Call(window,"SetBusy",false);
                var titleColumn=grid.Columns.Single(c=>c.SortMemberPath=="Title");
                var titleHeader=Visuals<DataGridColumnHeader>(grid).Single(h=>h.Column==titleColumn);
                var resizeHandle=(Thumb)titleHeader.Template.FindName("PART_RightHeaderGripper",titleHeader);
                Check(resizeHandle.Visibility==Visibility.Visible && grid.CanUserResizeColumns,"Column resize handle should be usable");
                double oldWidth=titleColumn.ActualWidth;
                resizeHandle.RaiseEvent(new DragStartedEventArgs(0,0){RoutedEvent=Thumb.DragStartedEvent});
                resizeHandle.RaiseEvent(new DragDeltaEventArgs(40,0){RoutedEvent=Thumb.DragDeltaEvent});
                resizeHandle.RaiseEvent(new DragCompletedEventArgs(40,0,false){RoutedEvent=Thumb.DragCompletedEvent});
                window.UpdateLayout();
                Check(titleColumn.ActualWidth>oldWidth,"Dragging the header gripper should widen the column");
                var baseline=grid.Columns.Where(c=>c.Visibility==Visibility.Visible).ToDictionary(c=>c,c=>c.ActualWidth);
                double requestedWidth=oldWidth+2000;
                Call(window,"ResizeColumnTo",titleColumn,requestedWidth,baseline);
                window.UpdateLayout();
                Check(titleColumn.Width.Value>=requestedWidth,"Column widths should support expansion beyond the viewport");
                Call(window,"AutoFitColumn",titleColumn);
                window.UpdateLayout();
                Check(titleColumn.Width.Value<requestedWidth && titleColumn.Width.Value>=titleColumn.MinWidth,"Auto-fit should restore a content-sized column");
                foreach(var item in baseline) item.Key.Width=new DataGridLength(item.Value);
                foreach (string property in new[]{"Title","Artist","Album","Duration","Position","FileSize"}) {
                    var column = grid.Columns.Single(c=>c.SortMemberPath==property);
                    Call(window,"SetSort","Status",ListSortDirection.Ascending);
                    Call(window,"Grid_Sorting",grid,new DataGridSortingEventArgs(column));
                    Check(column.SortDirection==ListSortDirection.Ascending,property+" first click arrow");
                    Call(window,"Grid_Sorting",grid,new DataGridSortingEventArgs(column));
                    Check(column.SortDirection==ListSortDirection.Descending,property+" second click arrow");
                }
                Call(window,"SetSort","FileSize",ListSortDirection.Ascending);
                Check(view.Cast<SongRow>().Select(s=>s.VideoId).SequenceEqual(new[]{"b","a","c"}),"Numeric ascending file size; null last");
                Call(window,"SetSort","FileSize",ListSortDirection.Descending);
                Check(view.Cast<SongRow>().Select(s=>s.VideoId).SequenceEqual(new[]{"a","b","c"}),"Numeric descending file size; null last");
                Call(window,"SetSort","Duration",ListSortDirection.Ascending);
                Check(view.Cast<SongRow>().First().VideoId=="b","Duration sorts numerically");
                Call(window,"SetSort","Duration",ListSortDirection.Descending);
                Check(view.Cast<SongRow>().Last().VideoId=="c","Unknown duration stays last descending");
                songs[0].IsSelected=false;
                Call(window,"SetSort","Title",ListSortDirection.Ascending);
                Check(!songs.Single(s=>s.VideoId=="a").IsSelected,"Selection follows song after sorting");
                var search = Field<Wpf.Ui.Controls.TextBox>(window,"SearchInput");
                search.Text="alpha";
                Check(view.Cast<SongRow>().Count()==1 && view.Cast<SongRow>().Single().VideoId=="b","Search filters case insensitively");
                search.Clear();
                search.Text="no-such-song";
                Check(Field<StackPanel>(window,"EmptyState").Visibility==Visibility.Visible,"No-match search should show empty-state message");
                Check(Field<TextBlock>(window,"EmptyTitle").Text.Contains("No songs"),"No-match search should explain the blank table");
                search.Clear();
                Check(Field<StackPanel>(window,"EmptyState").Visibility==Visibility.Collapsed,"Clear search should dismiss no-match message");
                Call(window,"SetSelection",false);
                Check(songs.All(s=>!s.IsSelected),"Clear selection");
                var master=Field<Wpf.Ui.Controls.Button>(window,"HeaderSelectionButton");
                Check(System.Windows.Automation.AutomationProperties.GetName(master)=="Select all songs","Header button should describe selecting all");
                Call(window,"HeaderSelection_Click",master,new RoutedEventArgs());
                Check(songs.All(s=>s.IsSelected),"Header button should select all songs");
                Check(System.Windows.Automation.AutomationProperties.GetName(master)=="Deselect all songs","Header button should switch to deselect all");
                Call(window,"HeaderSelection_Click",master,new RoutedEventArgs());
                Check(songs.All(s=>!s.IsSelected),"Second header click should deselect all");
                songs[0].IsSelected=true;
                search.Text="alpha";
                Call(window,"HeaderSelection_Click",master,new RoutedEventArgs());
                Check(songs.All(s=>s.IsSelected),"Partial selection and filtering should still select the whole playlist");
                Call(window,"SetBusy",true);
                Check(!master.IsEnabled,"Header button should be disabled during a download");
                Call(window,"HeaderSelection_Click",master,new RoutedEventArgs());
                Check(songs.All(s=>s.IsSelected),"Busy header clicks must not alter download selection");
                Call(window,"SetBusy",false);
                search.Clear();
                Call(window,"SetSelection",true);
                Check(songs.All(s=>s.IsSelected),"Select all");
                Call(window,"SetSort","Position",ListSortDirection.Ascending);
                Call(window,"SetSelection",false);
                Call(window,"StartSelectionSweep",songs[1]);
                Call(window,"ApplySelectionSweep",songs[2]);
                Check(!songs[0].IsSelected && songs[1].IsSelected && songs[2].IsSelected,"Dragging from an unchecked box should select the contiguous displayed range");
                Call(window,"ApplySelectionSweep",songs[0]);
                Check(songs[0].IsSelected && songs[1].IsSelected && !songs[2].IsSelected,"Reversing a selection drag should restore rows outside the current range");
                Call(window,"EndSelectionSweep");
                Call(window,"SetSelection",true);
                Call(window,"StartSelectionSweep",songs[1]);
                Call(window,"ApplySelectionSweep",songs[2]);
                Call(window,"EndSelectionSweep");
                Check(songs[0].IsSelected && !songs[1].IsSelected && !songs[2].IsSelected,"Dragging from a checked box should deselect the range");
                search.Text="alpha";
                Call(window,"StartSelectionSweep",songs[1]);
                Call(window,"ApplySelectionSweep",songs[2]);
                Call(window,"EndSelectionSweep");
                Check(songs[0].IsSelected && songs[1].IsSelected && !songs[2].IsSelected,"Selection drags must leave filtered-out songs unchanged");
                search.Clear();
                Call(window,"SetBusy",true);
                Call(window,"StartSelectionSweep",songs[0]);
                Call(window,"ApplySelectionSweep",songs[2]);
                Check(songs[0].IsSelected && songs[1].IsSelected && !songs[2].IsSelected,"Selection drags must be disabled during downloads");
                Call(window,"SetBusy",false);
                Call(window,"SetSelection",true);
                songs.Single(s=>s.VideoId=="c").IsSelected=false;
                await (Task)Call(window,"DownloadAsync")!;
                Check(File.Exists(Path.Combine(temp,"Desktop verification.m3u8")),"JSON bridge should write M3U8");
                string[] playlist = File.ReadAllLines(Path.Combine(temp,"Desktop verification.m3u8")).Where(l=>l.Length>0 && !l.StartsWith('#')).ToArray();
                Check(playlist.SequenceEqual(new[]{"a.opus","b.opus"}),"Sorted display must not affect M3U8 order; missing unchecked excluded");
                Check(!File.Exists(Path.Combine(temp,"c.opus")),"Unchecked missing song must not download");
                Check(songs.Single(s=>s.VideoId=="c").Status=="Not selected","Progress updates unchecked row");
                Check(Field<bool>(window,"showingDownloads"),"Starting a download should open Downloads");
                Check(((ListCollectionView)grid.ItemsSource).Count==2,"Downloads should contain only songs from this download");
                Call(window,"ShowPage",false);
                Check(((ListCollectionView)grid.ItemsSource).Count==3,"Library should retain unchecked songs after viewing Downloads");
                Call(window,"SetSort","Title",ListSortDirection.Ascending);
                Field<CheckBox>(window,"CustomOrderToggle").IsChecked=true;
                Check(!grid.CanUserSortColumns && view.Cast<SongRow>().First().VideoId=="b","Custom order should start from the displayed arrangement and lock column sorting");
                await (Task)Call(window,"DownloadAsync")!;
                playlist=File.ReadAllLines(Path.Combine(temp,"Desktop verification.m3u8")).Where(l=>l.Length>0 && !l.StartsWith('#')).ToArray();
                Check(playlist.SequenceEqual(new[]{"b.opus","a.opus"}),"Custom display order must reach the frozen engine and saved M3U8");
                Call(window,"ShowPage",false);
                Field<CheckBox>(window,"CustomOrderToggle").IsChecked=false;
                Check(grid.CanUserSortColumns && view.Cast<SongRow>().First().VideoId=="a","Disabling custom order should restore YouTube order and column sorting");
                File.WriteAllText(report,$"PASS: {checks} WPF and bridge checks.");
                verified = true;
                if (args.Contains("--large")) {
                    var largeRows=Enumerable.Range(1,925).Select(i=>new {videoId=$"fixture-{i}",position=i,title=$"Song {i:000} · A longer song title for the playlist table",artist=$"Artist {(i%12)+1}",album=$"Album {(i%8)+1}",genre=i%3==0?(string?)null:"Pop",duration=(double?)(120+i%240),fileSize=(long?)null,status="Missing"}).ToArray();
                    var largeTracks=largeRows.Select(s=>new {index=s.position,video_id=s.videoId,set_video_id=(string?)null,title=s.title,artists=new[]{s.artist},album=s.album,thumbnail_url=(string?)null,filename=$"{s.videoId}.opus",duration_seconds=s.duration,genre=s.genre}).ToArray();
                    Call(window,"HandleEvent",JsonSerializer.SerializeToElement(new {type="scan",snapshot=new {url,folder=temp,playlistId="PL-desktop-checks",title="2026 download · 925 songs",single=false,total=925,skipped=Array.Empty<int>(),tracks=largeTracks,rows=largeRows}}));
                    if (args.Contains("--downloads")) {
                        var session=Field<HashSet<string>>(window,"downloadSession");
                        var pending=Field<HashSet<string>>(window,"pending");
                        foreach(var song in songs) {
                            session.Add(song.VideoId);
                            song.Status=song.Position<=6?"Downloading":song.Position<=46?"Downloaded":song.Position<=49?"Failed":"Queued";
                            if(song.Status is "Queued" or "Downloading") pending.Add(song.VideoId);
                        }
                        Call(window,"SetBusy",true);
                        Call(window,"ShowPage",true);
                        window.Closing+=(_,e)=>{Call(window,"SetBusy",false);e.Cancel=false;};
                    }
                }
                if (args.Contains("--preview")) return;
            } catch(Exception ex) { File.WriteAllText(report,"FAIL: "+ex); Environment.ExitCode=1; }
            finally { if (!args.Contains("--preview") || !verified) window.Close(); }
        };
        app.Run(window);
    }
}
