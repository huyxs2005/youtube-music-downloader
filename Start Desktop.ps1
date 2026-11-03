$ErrorActionPreference = "Stop"
$ProjectRoot = $PSScriptRoot
$Dotnet = Get-Command dotnet -ErrorAction SilentlyContinue
$LocalSdk = Join-Path $env:LOCALAPPDATA "ytm-dotnet\dotnet.exe"
if (Test-Path -LiteralPath $LocalSdk) { $DotnetPath = $LocalSdk }
elseif ($Dotnet) { $DotnetPath = $Dotnet.Source }
else { throw "Install the .NET 10 SDK to build the desktop app." }
$DesktopPython = Join-Path $ProjectRoot ".venv\Scripts\python.exe"
if (-not (Test-Path -LiteralPath $DesktopPython)) {
    & python -m venv (Join-Path $ProjectRoot ".venv")
    if ($LASTEXITCODE -ne 0) { throw "Install Python 3.11 or newer first." }
}
& $DesktopPython -m pip install -r (Join-Path $ProjectRoot "requirements.txt")
if ($LASTEXITCODE -ne 0) { throw "Installing Python dependencies failed." }
& $DotnetPath build (Join-Path $ProjectRoot "desktop") -c Release
if ($LASTEXITCODE -ne 0) { throw "Building the desktop app failed." }
Start-Process -FilePath (Join-Path $ProjectRoot "desktop\bin\Release\net10.0-windows\YouTubeMusicDownloader.Desktop.exe") -WindowStyle Hidden
