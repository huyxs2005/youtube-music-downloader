using System.Globalization;
using System.IO;
using System.Text.RegularExpressions;

namespace YouTubeMusicDownloader.Desktop;

public sealed record CookieCheck(bool IsValid, string Path, string Message);

public static class CookieFiles
{
    public static CookieCheck Validate(string? path)
    {
        if (string.IsNullOrWhiteSpace(path)) return new(false, "", "Cookies required. Add a YouTube cookies.txt file to continue.");
        try {
            string fullPath = System.IO.Path.GetFullPath(path);
            string[] lines = File.ReadAllLines(fullPath);
            if (lines.Length == 0 || !Regex.IsMatch(lines[0].TrimStart('\uFEFF'), @"^#(?: Netscape)? HTTP Cookie File"))
                return new(false, fullPath, "Invalid cookie format. Export a Netscape cookies.txt file from YouTube.");
            int usable = 0, youtube = 0;
            double now = DateTimeOffset.UtcNow.ToUnixTimeSeconds();
            foreach (string raw in lines.Skip(1)) {
                string line = raw.StartsWith("#HttpOnly_", StringComparison.Ordinal) ? raw[10..] : raw;
                if (string.IsNullOrWhiteSpace(line) || line.StartsWith('#')) continue;
                string[] fields = line.Split('\t');
                if (fields.Length != 7 || fields[0].Length == 0 || fields[0].Any(char.IsWhiteSpace) ||
                    fields[1] is not ("TRUE" or "FALSE") || fields[3] is not ("TRUE" or "FALSE") ||
                    fields[0].StartsWith('.') != (fields[1] == "TRUE") || !fields[2].StartsWith('/') ||
                    (fields[4].Length != 0 && !Regex.IsMatch(fields[4], @"^[0-9]+(?:\.[0-9]+)?$")))
                    return new(false, fullPath, "Malformed cookie entries. Export a fresh Netscape cookies.txt file from YouTube.");
                double expires = 0;
                if (fields[4].Length != 0 && (!double.TryParse(fields[4], NumberStyles.AllowDecimalPoint, CultureInfo.InvariantCulture, out expires) || !double.IsFinite(expires)))
                    return new(false, fullPath, "Invalid cookie expiry values. Export a fresh cookies.txt file.");
                string domain = fields[0].TrimStart('.').ToLowerInvariant();
                if (domain != "youtube.com" && !domain.EndsWith(".youtube.com", StringComparison.Ordinal)) continue;
                youtube++;
                if ((expires == 0 || expires > now) && fields[5].Length > 0 && fields[6].Length > 0) usable++;
            }
            if (usable == 0) return new(false, fullPath, youtube == 0
                ? "No YouTube cookies found. Export cookies while on youtube.com or music.youtube.com."
                : "No usable YouTube cookies remain. Export fresh cookies from YouTube.");
            return new(true, fullPath, "Cookie file checked · YouTube cookies present and not expired.");
        } catch (Exception ex) when (ex is IOException or UnauthorizedAccessException or ArgumentException or NotSupportedException) {
            return new(false, path, "Cannot read this cookie file. Add an accessible cookies.txt file.");
        }
    }

    public static CookieCheck Discover(IEnumerable<string> folders, string? remembered = null)
    {
        CookieCheck? firstInvalid = null;
        var candidates = folders.Where(f => !string.IsNullOrWhiteSpace(f)).Select(f => System.IO.Path.Combine(f, "cookies.txt"));
        if (!string.IsNullOrWhiteSpace(remembered)) candidates = candidates.Append(remembered);
        foreach (string path in candidates.Distinct(StringComparer.OrdinalIgnoreCase)) {
            if (!File.Exists(path)) continue;
            var result = Validate(path);
            if (result.IsValid) return result;
            firstInvalid ??= result;
        }
        return firstInvalid ?? Validate(null);
    }

    private static string PreferencePath => System.IO.Path.Combine(Environment.GetFolderPath(Environment.SpecialFolder.LocalApplicationData), "YouTubeMusicDownloader", "cookie-path.txt");
    public static string? RememberedPath()
    {
        try { return File.Exists(PreferencePath) ? File.ReadAllText(PreferencePath).Trim() : null; }
        catch (IOException) { return null; }
        catch (UnauthorizedAccessException) { return null; }
    }
    public static void Remember(string path)
    {
        try { Directory.CreateDirectory(System.IO.Path.GetDirectoryName(PreferencePath)!); File.WriteAllText(PreferencePath, path); }
        catch (IOException) { }
        catch (UnauthorizedAccessException) { }
    }
}
