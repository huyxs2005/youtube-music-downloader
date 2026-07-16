[CmdletBinding()]
param(
    [switch]$Resume,
    [switch]$NoLaunch,
    [switch]$SkipCookies
)

$ErrorActionPreference = "Stop"
Set-StrictMode -Version Latest

$AppDir = $PSScriptRoot
$DownloaderExe = Join-Path $AppDir "YouTubeMusicDownloader.exe"
$CookiePath = Join-Path $AppDir "cookies.txt"
$ProviderImage = "brainicism/bgutil-ytdlp-pot-provider"
$ProviderContainer = "bgutil-provider"
$DockerDownloadUrl = "https://desktop.docker.com/win/main/amd64/Docker%20Desktop%20Installer.exe"
$CookieExtensionUrl = "https://chromewebstore.google.com/detail/get-cookiestxt-locally/cclelndahbckbenkjhflpdbgdldlbecc"
$YouTubeMusicUrl = "https://music.youtube.com/"
$DockerConfigDir = Join-Path $env:TEMP "youtube-music-downloader-docker-config"

# Pull the public image anonymously without depending on or changing the user's
# Docker Desktop credential helper configuration.
New-Item -ItemType Directory -Path $DockerConfigDir -Force | Out-Null
Set-Content -LiteralPath (Join-Path $DockerConfigDir "config.json") -Encoding Ascii -Value '{"auths":{}}'
$env:DOCKER_CONFIG = $DockerConfigDir

function Write-Step([string]$Message) {
    Write-Host ""
    Write-Host "==> $Message" -ForegroundColor Cyan
}

function Wait-ForUser([string]$Message = "Press Enter to close") {
    [void](Read-Host $Message)
}

function Get-DockerDesktopPath {
    $Candidates = @(
        (Join-Path $env:ProgramFiles "Docker\Docker\Docker Desktop.exe"),
        (Join-Path $env:LOCALAPPDATA "Programs\DockerDesktop\Docker Desktop.exe"),
        (Join-Path $env:LOCALAPPDATA "Docker\Docker Desktop.exe")
    )
    return $Candidates | Where-Object { Test-Path -LiteralPath $_ } | Select-Object -First 1
}

function Add-DockerToPath {
    $Candidates = @(
        (Join-Path $env:ProgramFiles "Docker\Docker\resources\bin"),
        (Join-Path $env:LOCALAPPDATA "Programs\DockerDesktop\resources\bin")
    )
    foreach ($Candidate in $Candidates) {
        if ((Test-Path -LiteralPath $Candidate) -and ($env:PATH -notlike "*$Candidate*")) {
            $env:PATH = "$Candidate;$env:PATH"
        }
    }
}

function Test-WslReady {
    if (-not (Get-Command "wsl.exe" -ErrorAction SilentlyContinue)) {
        return $false
    }
    & wsl.exe --status *> $null
    return $LASTEXITCODE -eq 0
}

function Register-ResumeAfterRestart {
    $RunOncePath = "HKCU:\Software\Microsoft\Windows\CurrentVersion\RunOnce"
    $Command = 'powershell.exe -NoProfile -ExecutionPolicy Bypass -File "{0}" -Resume' -f $PSCommandPath
    New-Item -Path $RunOncePath -Force | Out-Null
    New-ItemProperty -Path $RunOncePath -Name "YouTubeMusicDownloaderSetup" -Value $Command -PropertyType String -Force | Out-Null
}

function Install-Wsl {
    Write-Step "Installing or updating WSL 2"
    Write-Host "Windows may show an administrator approval prompt."
    $Install = Start-Process -FilePath "wsl.exe" -ArgumentList @("--install", "--no-distribution") -Verb RunAs -Wait -PassThru
    if ($Install.ExitCode -notin @(0, 3010)) {
        throw "WSL installation failed with exit code $($Install.ExitCode)."
    }

    Register-ResumeAfterRestart
    Write-Host ""
    Write-Host "Windows must restart before setup can continue." -ForegroundColor Yellow
    Write-Host "Setup will resume automatically after you sign back in."
    $Answer = Read-Host "Restart now? [Y/n]"
    if ([string]::IsNullOrWhiteSpace($Answer) -or $Answer -match '^(y|yes)$') {
        shutdown.exe /r /t 10 /c "Restarting to finish YouTube Music Downloader setup"
    }
    exit 3010
}

function Install-DockerDesktop {
    Write-Step "Installing Docker Desktop"
    Write-Host "Docker Desktop is used only for the YouTube PO-token provider."
    Write-Host "A Docker account or login is not required."
    Write-Host "Docker Desktop terms: https://www.docker.com/legal/docker-subscription-service-agreement/"
    $Consent = Read-Host "Install Docker Desktop and accept its terms? [Y/n]"
    if ($Consent -match '^(n|no)$') {
        throw "Docker installation was declined. Run 'Finish Setup' from the Start menu later."
    }

    $InstallerPath = Join-Path $env:TEMP "DockerDesktopInstaller.exe"
    Write-Host "Downloading Docker Desktop from Docker..."
    Invoke-WebRequest -Uri $DockerDownloadUrl -OutFile $InstallerPath -UseBasicParsing

    $Signature = Get-AuthenticodeSignature -FilePath $InstallerPath
    if ($Signature.Status -ne "Valid" -or $Signature.SignerCertificate.Subject -notmatch "Docker Inc") {
        Remove-Item -LiteralPath $InstallerPath -Force -ErrorAction SilentlyContinue
        throw "The Docker installer signature could not be verified."
    }

    $Install = Start-Process -FilePath $InstallerPath -ArgumentList @(
        "install",
        "--user",
        "--accept-license",
        "--backend=wsl-2"
    ) -Wait -PassThru
    Remove-Item -LiteralPath $InstallerPath -Force -ErrorAction SilentlyContinue
    if ($Install.ExitCode -notin @(0, 3010)) {
        throw "Docker Desktop installation failed with exit code $($Install.ExitCode)."
    }
}

function Wait-ForDocker {
    Add-DockerToPath
    & docker.exe info *> $null
    if ($LASTEXITCODE -eq 0) {
        return
    }

    $DockerDesktop = Get-DockerDesktopPath
    if (-not $DockerDesktop) {
        throw "Docker Desktop was installed, but its executable could not be found."
    }

    Write-Step "Starting Docker Desktop"
    Start-Process -FilePath $DockerDesktop | Out-Null
    for ($Attempt = 0; $Attempt -lt 90; $Attempt++) {
        Start-Sleep -Seconds 2
        & docker.exe info *> $null
        if ($LASTEXITCODE -eq 0) {
            return
        }
        if (($Attempt + 1) % 10 -eq 0) {
            Write-Host "Still waiting for Docker Desktop..."
        }
    }
    throw "Docker Desktop did not become ready within three minutes. Run Finish Setup again after Docker starts."
}

function Install-PoProvider {
    Write-Step "Downloading the PO-token provider"
    & docker.exe pull $ProviderImage
    if ($LASTEXITCODE -ne 0) {
        throw "The PO-token provider image could not be downloaded."
    }

    & docker.exe inspect $ProviderContainer *> $null
    if ($LASTEXITCODE -eq 0) {
        & docker.exe start $ProviderContainer *> $null
    }
    else {
        & docker.exe run -d --name $ProviderContainer -p 4416:4416 $ProviderImage *> $null
    }
    if ($LASTEXITCODE -ne 0) {
        throw "The PO-token provider container could not be started."
    }
}

function Configure-Cookies {
    if (Test-Path -LiteralPath $CookiePath) {
        Write-Host "cookies.txt is already configured."
        return
    }

    Write-Step "Optional YouTube cookie setup"
    Write-Host "Cookies help when YouTube asks for login or bot verification."
    $Answer = Read-Host "Open YouTube Music and the cookie-export extension now? [Y/n]"
    if ($Answer -match '^(n|no)$') {
        Write-Host "Skipped. The downloader can run without cookies."
        return
    }

    Start-Process $CookieExtensionUrl
    Start-Process $YouTubeMusicUrl
    Write-Host ""
    Write-Host "1. Install the extension."
    Write-Host "2. Sign in at YouTube Music."
    Write-Host "3. Use the extension on the YouTube Music page to export cookies.txt."
    Wait-ForUser "Press Enter after cookies.txt has been exported"

    Add-Type -AssemblyName System.Windows.Forms
    $Dialog = New-Object System.Windows.Forms.OpenFileDialog
    $Dialog.Title = "Select the exported cookies.txt"
    $Dialog.Filter = "Netscape cookies file (cookies.txt)|cookies.txt|Text files (*.txt)|*.txt"
    $Dialog.CheckFileExists = $true
    if ($Dialog.ShowDialog() -eq [System.Windows.Forms.DialogResult]::OK) {
        Copy-Item -LiteralPath $Dialog.FileName -Destination $CookiePath -Force
        Write-Host "Saved cookies.txt to the application folder."
    }
    else {
        Write-Host "No cookie file selected. You can add it later."
    }
}

try {
    Write-Host "YouTube Music Downloader v1.0 - first-time setup" -ForegroundColor Green

    if (-not (Test-WslReady)) {
        Install-Wsl
    }

    if (-not (Get-DockerDesktopPath)) {
        Install-DockerDesktop
    }

    Wait-ForDocker
    Install-PoProvider
    if (-not $SkipCookies) {
        Configure-Cookies
    }

    Write-Step "Setup complete"
    Write-Host "Python and FFmpeg are bundled with the downloader."
    Write-Host "Docker login is not required."

    if (-not $NoLaunch) {
        Wait-ForUser "Press Enter to open YouTube Music Downloader"
        Start-Process -FilePath $DownloaderExe -WorkingDirectory $AppDir
    }
}
catch {
    Write-Host ""
    Write-Host "Setup could not finish:" -ForegroundColor Red
    Write-Host $_.Exception.Message -ForegroundColor Red
    Write-Host ""
    Write-Host "Nothing in your music folders was changed."
    Write-Host "Run 'Finish Setup' from the Start menu to try again."
    Wait-ForUser
    exit 1
}
