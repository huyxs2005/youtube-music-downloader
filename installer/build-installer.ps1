[CmdletBinding()]
param(
    [string]$Python = "python",
    [string]$IsccPath = ""
)

$ErrorActionPreference = "Stop"
Set-StrictMode -Version Latest

$Root = Split-Path -Parent $PSScriptRoot
$Venv = Join-Path $Root ".venv-build"
$VenvPython = Join-Path $Venv "Scripts\python.exe"
$DistDir = Join-Path $Root "dist\YouTubeMusicDownloader"
$ToolsDir = Join-Path $DistDir "tools"

Set-Location $Root

if (-not (Test-Path -LiteralPath $VenvPython)) {
    & $Python -m venv $Venv
    if ($LASTEXITCODE -ne 0) {
        throw "Creating the build environment failed with exit code $LASTEXITCODE."
    }
}

& $VenvPython -m pip install --upgrade pip
if ($LASTEXITCODE -ne 0) {
    throw "Updating pip failed with exit code $LASTEXITCODE."
}
& $VenvPython -m pip install --requirement (Join-Path $Root "requirements-build.txt")
if ($LASTEXITCODE -ne 0) {
    throw "Installing build requirements failed with exit code $LASTEXITCODE."
}

Remove-Item -LiteralPath (Join-Path $Root "build") -Recurse -Force -ErrorAction SilentlyContinue
Remove-Item -LiteralPath (Join-Path $Root "dist") -Recurse -Force -ErrorAction SilentlyContinue
Remove-Item -LiteralPath (Join-Path $PSScriptRoot "output") -Recurse -Force -ErrorAction SilentlyContinue

& $VenvPython -m PyInstaller --noconfirm --clean (Join-Path $PSScriptRoot "YouTubeMusicDownloader.spec")
if ($LASTEXITCODE -ne 0) {
    throw "PyInstaller failed with exit code $LASTEXITCODE."
}

$PackagedExe = Join-Path $DistDir "YouTubeMusicDownloader.exe"
if (-not (Test-Path -LiteralPath $PackagedExe)) {
    throw "PyInstaller did not create the expected executable: $PackagedExe"
}

$Ffmpeg = Get-Command "ffmpeg.exe" -ErrorAction Stop
$FfprobePath = Join-Path (Split-Path $Ffmpeg.Source) "ffprobe.exe"
if (-not (Test-Path -LiteralPath $FfprobePath)) {
    throw "ffprobe.exe was not found beside ffmpeg.exe."
}

New-Item -ItemType Directory -Path $ToolsDir -Force | Out-Null
Copy-Item -LiteralPath $Ffmpeg.Source -Destination (Join-Path $ToolsDir "ffmpeg.exe")
Copy-Item -LiteralPath $FfprobePath -Destination (Join-Path $ToolsDir "ffprobe.exe")

$FfmpegRoot = Split-Path (Split-Path $Ffmpeg.Source)
foreach ($Name in @("LICENSE", "README.txt")) {
    $Source = Join-Path $FfmpegRoot $Name
    if (Test-Path -LiteralPath $Source) {
        Copy-Item -LiteralPath $Source -Destination $ToolsDir
    }
}

if (-not $IsccPath) {
    $IsccCandidates = @(
        (Join-Path ${env:ProgramFiles(x86)} "Inno Setup 6\ISCC.exe"),
        (Join-Path $env:ProgramFiles "Inno Setup 6\ISCC.exe"),
        (Join-Path $env:LOCALAPPDATA "Programs\Inno Setup 6\ISCC.exe")
    )
    $IsccPath = $IsccCandidates | Where-Object { $_ -and (Test-Path -LiteralPath $_) } | Select-Object -First 1
}
if (-not $IsccPath -or -not (Test-Path -LiteralPath $IsccPath)) {
    throw "Inno Setup 6 was not found. Install it with: winget install --id JRSoftware.InnoSetup -e"
}

& $IsccPath (Join-Path $PSScriptRoot "YouTubeMusicDownloader.iss")
if ($LASTEXITCODE -ne 0) {
    throw "Inno Setup failed with exit code $LASTEXITCODE."
}

$Installer = Join-Path $PSScriptRoot "output\YouTube-Music-Downloader-Setup-v1.0.exe"
if (-not (Test-Path -LiteralPath $Installer)) {
    throw "The expected installer was not created: $Installer"
}

$Hash = Get-FileHash -Algorithm SHA256 -LiteralPath $Installer
Set-Content -LiteralPath "$Installer.sha256" -Encoding ascii -Value "$($Hash.Hash.ToLowerInvariant())  $([IO.Path]::GetFileName($Installer))"
Write-Host ""
Write-Host "Installer: $Installer" -ForegroundColor Green
Write-Host "SHA256:    $($Hash.Hash.ToLowerInvariant())" -ForegroundColor Green
