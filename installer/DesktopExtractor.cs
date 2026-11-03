using System;
using System.ComponentModel;
using System.Diagnostics;
using System.Drawing;
using System.IO;
using System.IO.Compression;
using System.Reflection;
using System.Windows.Forms;

[assembly: AssemblyTitle("YouTube Music Downloader Extractor")]
[assembly: AssemblyVersion("2.2.4.0")]
[assembly: AssemblyFileVersion("2.2.4.0")]

internal static class DesktopExtractor
{
    internal const string InnerFolder = "YouTubeMusicDownloader-Desktop";

    internal static void ExtractPayload(string destination, Action<int> report)
    {
        string root = Path.GetFullPath(destination).TrimEnd(Path.DirectorySeparatorChar) + Path.DirectorySeparatorChar;
        string appPath = Path.Combine(root, InnerFolder, "app", "YouTubeMusicDownloader.Desktop.exe");
        foreach (Process process in Process.GetProcessesByName("YouTubeMusicDownloader.Desktop")) {
            using (process) {
                string runningPath = null;
                try { runningPath = process.MainModule.FileName; } catch (Win32Exception) { }
                if (String.Equals(runningPath, appPath, StringComparison.OrdinalIgnoreCase))
                    throw new IOException("Close YouTube Music Downloader before extracting over this copy.");
            }
        }
        using (Stream payload = Assembly.GetExecutingAssembly().GetManifestResourceStream("ReleaseArchive"))
        using (ZipArchive archive = new ZipArchive(payload, ZipArchiveMode.Read)) {
            long total = 0, written = 0;
            foreach (ZipArchiveEntry entry in archive.Entries) {
                string target = Path.GetFullPath(Path.Combine(root, entry.FullName));
                if (!target.StartsWith(root, StringComparison.OrdinalIgnoreCase)) throw new IOException("The archive contains an invalid path.");
                total += entry.Length;
            }
            Directory.CreateDirectory(root);
            byte[] buffer = new byte[1024 * 1024];
            int previous = -1;
            foreach (ZipArchiveEntry entry in archive.Entries) {
                string target = Path.GetFullPath(Path.Combine(root, entry.FullName));
                if (entry.FullName.EndsWith("/")) { Directory.CreateDirectory(target); continue; }
                Directory.CreateDirectory(Path.GetDirectoryName(target));
                using (Stream source = entry.Open())
                using (FileStream output = new FileStream(target, FileMode.Create, FileAccess.Write, FileShare.None)) {
                    int count;
                    while ((count = source.Read(buffer, 0, buffer.Length)) > 0) {
                        output.Write(buffer, 0, count);
                        written += count;
                        int progress = total == 0 ? 1000 : (int)(written * 1000 / total);
                        if (progress != previous) { report(progress); previous = progress; }
                    }
                }
            }
        }
    }

    [STAThread]
    private static int Main(string[] args)
    {
        // Exercise the same extraction path in automated packaging checks without opening windows.
        if (args.Length == 2 && args[0] == "--extract-only") {
            try { ExtractPayload(args[1], delegate(int progress) { }); return 0; }
            catch { return 1; }
        }
        Application.EnableVisualStyles();
        Application.SetCompatibleTextRenderingDefault(false);
        Application.Run(new ExtractWindow());
        return 0;
    }

    private sealed class ExtractWindow : Form
    {
        private readonly TextBox destination;
        private readonly Button browse;
        private readonly Button extract;
        private readonly Label status;
        private readonly ProgressBar progress;
        private readonly BackgroundWorker worker = new BackgroundWorker { WorkerReportsProgress = true };
        private string selectedDestination;

        internal ExtractWindow()
        {
            Text = "YouTube Music Downloader — Extract";
            Font = new Font("Segoe UI", 10);
            ClientSize = new Size(650, 230);
            FormBorderStyle = FormBorderStyle.FixedDialog;
            MaximizeBox = false;
            StartPosition = FormStartPosition.CenterScreen;
            Icon = System.Drawing.Icon.ExtractAssociatedIcon(Assembly.GetExecutingAssembly().Location);
            Controls.Add(new Label { Text = "Extract to:", AutoSize = true, Location = new Point(20, 20) });
            string name = "YouTubeMusicDownloader-Desktop-v" + Assembly.GetExecutingAssembly().GetName().Version.ToString(3) + "-win-x64";
            destination = new TextBox { Text = Path.Combine(AppDomain.CurrentDomain.BaseDirectory, name), Location = new Point(20, 50), Size = new Size(510, 30) };
            browse = new Button { Text = "Browse…", Location = new Point(540, 49), Size = new Size(90, 31) };
            browse.Click += delegate {
                using (FolderBrowserDialog picker = new FolderBrowserDialog { Description = "Choose where to create the extracted version folder" }) {
                    if (picker.ShowDialog(this) == DialogResult.OK) destination.Text = Path.Combine(picker.SelectedPath, name);
                }
            };
            status = new Label { Text = "After extraction, the app folder will open automatically.", Location = new Point(20, 98), Size = new Size(610, 42) };
            progress = new ProgressBar { Location = new Point(20, 148), Size = new Size(610, 12), Maximum = 1000 };
            extract = new Button { Text = "Extract", Location = new Point(520, 180), Size = new Size(110, 32) };
            Controls.AddRange(new Control[] { destination, browse, status, progress, extract });
            AcceptButton = extract;
            extract.Click += delegate {
                if (String.IsNullOrWhiteSpace(destination.Text)) return;
                try { selectedDestination = Path.GetFullPath(destination.Text); }
                catch (Exception error) { MessageBox.Show(this, error.Message, Text, MessageBoxButtons.OK, MessageBoxIcon.Warning); return; }
                destination.Enabled = browse.Enabled = extract.Enabled = false;
                status.Text = "Extracting files…";
                worker.RunWorkerAsync(selectedDestination);
            };
            worker.DoWork += delegate(object sender, DoWorkEventArgs e) {
                ExtractPayload((string)e.Argument, delegate(int percent) { worker.ReportProgress(percent); });
            };
            worker.ProgressChanged += delegate(object sender, ProgressChangedEventArgs e) { progress.Value = Math.Min(1000, e.ProgressPercentage); };
            worker.RunWorkerCompleted += delegate(object sender, RunWorkerCompletedEventArgs e) {
                destination.Enabled = browse.Enabled = extract.Enabled = true;
                if (e.Error != null) { status.Text = "Extraction could not finish."; MessageBox.Show(this, e.Error.Message, Text, MessageBoxButtons.OK, MessageBoxIcon.Warning); return; }
                try {
                    Process.Start(new ProcessStartInfo("explorer.exe", "\"" + Path.Combine(selectedDestination, InnerFolder) + "\"") { UseShellExecute = true });
                    Close();
                } catch (Exception error) {
                    status.Text = "Extracted to " + Path.Combine(selectedDestination, InnerFolder);
                    MessageBox.Show(this, error.Message, "Files extracted — open the folder manually", MessageBoxButtons.OK, MessageBoxIcon.Information);
                }
            };
            FormClosing += delegate(object sender, FormClosingEventArgs e) { if (worker.IsBusy) e.Cancel = true; };
        }
    }
}
