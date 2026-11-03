using System.Diagnostics;
using System.IO;
using System.Text;
using System.Text.Json;

namespace YouTubeMusicDownloader.Desktop;

public sealed class BackendClient
{
    public static readonly JsonSerializerOptions JsonOptions = new() { PropertyNameCaseInsensitive = true };
    public static string Root { get; } = FindRoot();
    public static string ApplicationFolder {
        get {
            var folder = new DirectoryInfo(AppContext.BaseDirectory);
            return folder.Name.Equals("app", StringComparison.OrdinalIgnoreCase) && folder.Parent != null &&
                File.Exists(Path.Combine(folder.Parent.FullName, "YouTubeMusicDownloader.Desktop.exe"))
                ? folder.Parent.FullName : AppContext.BaseDirectory;
        }
    }
    public static string BackendFolder => File.Exists(Path.Combine(AppContext.BaseDirectory, "backend", "desktop_bridge.py"))
        ? Path.Combine(AppContext.BaseDirectory, "backend") : Root;
    private static string FindRoot()
    {
        for (var folder = new DirectoryInfo(AppContext.BaseDirectory); folder != null; folder = folder.Parent)
            if (File.Exists(Path.Combine(folder.FullName, "ytmusic_downloader.py"))) return folder.FullName;
        return AppContext.BaseDirectory;
    }
    public async Task RunAsync(object request, Action<JsonElement> receive, Action<string> log, CancellationToken cancellationToken = default)
    {
        string? configured = Environment.GetEnvironmentVariable("YTM_DOWNLOADER_PYTHON");
        string local = Path.Combine(Root, ".venv", "Scripts", "python.exe");
        string bundled = Path.Combine(AppContext.BaseDirectory, "runtime", "python.exe");
        string python = configured ?? (File.Exists(bundled) ? bundled : File.Exists(local) ? local : "python");
        string packagedEngine = Path.Combine(AppContext.BaseDirectory, "engine", "YouTubeMusicEngine.exe");
        bool packaged = File.Exists(packagedEngine);
        var start = new ProcessStartInfo(packaged ? packagedEngine : python) {
            UseShellExecute = false, CreateNoWindow = true,
            RedirectStandardInput = true, RedirectStandardOutput = true, RedirectStandardError = true,
            StandardInputEncoding = new UTF8Encoding(false), StandardOutputEncoding = Encoding.UTF8,
            StandardErrorEncoding = Encoding.UTF8, WorkingDirectory = BackendFolder
        };
        if (!packaged) {
            start.ArgumentList.Add("-u");
            start.ArgumentList.Add(Path.Combine(BackendFolder, "desktop_bridge.py"));
        }
        start.Environment["PYTHONUTF8"] = "1";
        // Resolve bundled tools in portable desktop builds too.
        start.Environment["PATH"] = Path.Combine(AppContext.BaseDirectory, "tools") + Path.PathSeparator + start.Environment["PATH"];
        using var process = Process.Start(start) ?? throw new IOException("Could not start the download engine.");
        using var cancellation = cancellationToken.Register(() => {
            try { if (!process.HasExited) process.Kill(entireProcessTree: true); }
            catch (InvalidOperationException) { }
            catch (System.ComponentModel.Win32Exception) { }
        });
        await process.StandardInput.WriteLineAsync(JsonSerializer.Serialize(request));
        process.StandardInput.Close();
        var errors = new StringBuilder();
        async Task DrainErrors()
        {
            while (await process.StandardError.ReadLineAsync() is { } line) {
                if (errors.Length < 6000) errors.AppendLine(line);
                log(line);
            }
        }
        var errorTask = DrainErrors();
        bool received = false;
        while (await process.StandardOutput.ReadLineAsync() is { } line) {
            using var document = JsonDocument.Parse(line);
            received = true;
            receive(document.RootElement.Clone());
        }
        await errorTask;
        await process.WaitForExitAsync();
        cancellationToken.ThrowIfCancellationRequested();
        if (process.ExitCode != 0 && !received)
            throw new IOException("The download engine could not start. Check Python and requirements.txt. " + errors.ToString());
        if (!received) throw new IOException("The download engine returned no result.");
    }
}
