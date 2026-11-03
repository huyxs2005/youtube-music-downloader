[CmdletBinding()]
param([Parameter(Mandatory=$true)][string]$ArchivePath)
$ErrorActionPreference = 'Stop'
$Archive = [IO.Path]::GetFullPath($ArchivePath)
if (-not (Test-Path -LiteralPath $Archive)) { throw 'Create the portable ZIP first.' }
$ProjectRoot = Split-Path -Parent $PSScriptRoot
$Compiler = Join-Path $env:WINDIR 'Microsoft.NET\Framework64\v4.0.30319\csc.exe'
if (-not (Test-Path -LiteralPath $Compiler)) { $Compiler = Join-Path $env:WINDIR 'Microsoft.NET\Framework\v4.0.30319\csc.exe' }
$Output = [IO.Path]::Combine([IO.Path]::GetDirectoryName($Archive), [IO.Path]::GetFileNameWithoutExtension($Archive) + '-extract.exe')
& $Compiler /nologo /target:winexe /platform:anycpu /optimize+ /reference:System.Windows.Forms.dll /reference:System.Drawing.dll /reference:System.IO.Compression.dll /reference:System.IO.Compression.FileSystem.dll "/win32icon:$(Join-Path $ProjectRoot 'desktop\Assets\app-icon.ico')" "/resource:$Archive,ReleaseArchive" "/out:$Output" (Join-Path $PSScriptRoot 'DesktopExtractor.cs')
if ($LASTEXITCODE -ne 0) { throw 'Building the self-extracting download failed.' }
$Hash = (Get-FileHash -LiteralPath $Output -Algorithm SHA256).Hash.ToLowerInvariant()
[IO.File]::WriteAllText($Output + '.sha256', "$Hash  $([IO.Path]::GetFileName($Output))`n", [Text.Encoding]::ASCII)
Write-Host "Self-extracting download ready: $Output"
