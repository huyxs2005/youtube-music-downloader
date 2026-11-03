using System;
using System.Diagnostics;
using System.IO;
using System.Reflection;
using System.Runtime.InteropServices;

[assembly: AssemblyTitle("YouTube Music Downloader")]
[assembly: AssemblyDescription("Launch YouTube Music Downloader")]
[assembly: AssemblyVersion("2.2.2.0")]
[assembly: AssemblyFileVersion("2.2.2.0")]

internal static class DesktopLauncher
{
    [DllImport("user32.dll", CharSet = CharSet.Unicode)]
    private static extern int MessageBox(IntPtr owner, string text, string caption, uint type);

    [STAThread]
    private static void Main()
    {
        string folder = Path.Combine(AppDomain.CurrentDomain.BaseDirectory, "app");
        string executable = Path.Combine(folder, "YouTubeMusicDownloader.Desktop.exe");
        try {
            if (!File.Exists(executable))
                throw new FileNotFoundException("The app folder is missing. Keep this EXE and the app folder together, or extract the full download again.");
            using (Process process = Process.Start(new ProcessStartInfo(executable) {
                WorkingDirectory = folder, UseShellExecute = false, CreateNoWindow = true
            })) { }
        } catch (Exception error) {
            MessageBox(IntPtr.Zero, error.Message, "YouTube Music Downloader", 0x10);
        }
    }
}
