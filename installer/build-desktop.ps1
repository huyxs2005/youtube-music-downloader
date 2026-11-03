[CmdletBinding()]
param(
    [string]$Dotnet = "dotnet",
    [string]$Python = "python",
    [string]$FfmpegDirectory = ""
)
$ErrorActionPreference = "Stop"
$ProjectRoot = Split-Path -Parent $PSScriptRoot
$Package = Join-Path $ProjectRoot "dist\YouTubeMusicDownloader-Desktop"
$EngineDist = Join-Path $ProjectRoot "build\desktop-engine-dist"

& $Python -m pip install -r (Join-Path $ProjectRoot "requirements-build.txt")
if ($LASTEXITCODE -ne 0) { throw "Installing the engine build dependencies failed." }
& $Python -m PyInstaller --noconfirm --distpath $EngineDist --workpath (Join-Path $ProjectRoot "build\desktop-engine") (Join-Path $PSScriptRoot "YouTubeMusicEngine.spec")
if ($LASTEXITCODE -ne 0) { throw "Building the download engine failed." }
& $Dotnet publish (Join-Path $ProjectRoot "desktop\YouTubeMusicDownloader.Desktop.csproj") -c Release -r win-x64 --self-contained true -o $Package
if ($LASTEXITCODE -ne 0) { throw "Building the desktop app failed." }
$EngineTarget = Join-Path $Package "engine"
New-Item -ItemType Directory -Path $EngineTarget -Force | Out-Null
Copy-Item -Path (Join-Path $EngineDist "YouTubeMusicEngine\*") -Destination $EngineTarget -Recurse -Force

if (-not $FfmpegDirectory) {
    $FfmpegCommand = Get-Command ffmpeg.exe -ErrorAction SilentlyContinue
    if ($FfmpegCommand) { $FfmpegDirectory = Split-Path $FfmpegCommand.Source }
}
if (-not $FfmpegDirectory -or -not (Test-Path (Join-Path $FfmpegDirectory "ffmpeg.exe")) -or -not (Test-Path (Join-Path $FfmpegDirectory "ffprobe.exe"))) {
    throw "Pass -FfmpegDirectory with the folder containing ffmpeg.exe and ffprobe.exe to finish the portable package."
}
$ToolsTarget = Join-Path $Package "tools"
New-Item -ItemType Directory -Path $ToolsTarget -Force | Out-Null
foreach ($File in @("ffmpeg.exe", "ffprobe.exe")) {
    Copy-Item -LiteralPath (Join-Path $FfmpegDirectory $File) -Destination $ToolsTarget -Force
}
$FfmpegRoot = Split-Path $FfmpegDirectory
foreach ($File in @("LICENSE", "README.txt")) {
    $LicensePath = Join-Path $FfmpegRoot $File
    if (Test-Path -LiteralPath $LicensePath) { Copy-Item -LiteralPath $LicensePath -Destination $ToolsTarget -Force }
}
$WpfLicense = Join-Path $ProjectRoot "desktop\THIRD_PARTY_NOTICES.txt"
Copy-Item -LiteralPath $WpfLicense -Destination (Join-Path $Package "DESKTOP_THIRD_PARTY_NOTICES.txt") -Force
# Preserve the exact runtime and UI licenses from the packages used by restore.
$Assets = Get-Content -LiteralPath (Join-Path $ProjectRoot "desktop\obj\project.assets.json") -Raw | ConvertFrom-Json
foreach ($Library in $Assets.libraries.PSObject.Properties.Name) {
    if ($Library -notlike "Microsoft.NETCore.App.Runtime.win-x64/*" -and $Library -notlike "Microsoft.WindowsDesktop.App.Runtime.win-x64/*" -and $Library -notlike "WPF-UI/*") { continue }
    foreach ($CacheRoot in $Assets.packageFolders.PSObject.Properties.Name) {
        $LibraryFolder = Join-Path $CacheRoot $Library.ToLowerInvariant()
        if (-not (Test-Path -LiteralPath $LibraryFolder)) { continue }
        $LicenseTarget = Join-Path $Package ("licenses\" + $Library.Replace('/', '-'))
        New-Item -ItemType Directory -Path $LicenseTarget -Force | Out-Null
        Get-ChildItem -LiteralPath $LibraryFolder -File | Where-Object { $_.Name -match 'license|notice' } | Copy-Item -Destination $LicenseTarget -Force
    }
}
Copy-Item -LiteralPath (Join-Path $PSScriptRoot "THIRD_PARTY_NOTICES.txt") -Destination $Package -Force
Copy-Item -LiteralPath (Join-Path $ProjectRoot "README.md") -Destination $Package -Force
Write-Host "Desktop app ready: $(Join-Path $Package 'YouTubeMusicDownloader.Desktop.exe')"
