[CmdletBinding()]
param([Parameter(Mandatory=$true)][string]$PackageDirectory)
$ErrorActionPreference = "Stop"
$PackageRoot = [IO.Path]::GetFullPath($PackageDirectory).TrimEnd('\')
$AppRoot = Join-Path $PackageRoot 'app'
if (-not (Test-Path -LiteralPath (Join-Path $AppRoot 'engine\YouTubeMusicEngine.exe'))) {
    throw 'Only optimize a complete portable package with its bundled engine.'
}
function Remove-PackageItem([string]$Path) {
    $Resolved = [IO.Path]::GetFullPath($Path)
    if (-not $Resolved.StartsWith($AppRoot + '\', [StringComparison]::OrdinalIgnoreCase)) {
        throw "Refusing to remove anything outside the app support folder: $Resolved"
    }
    if (Test-Path -LiteralPath $Resolved) { Remove-Item -LiteralPath $Resolved -Recurse -Force }
}
$Before = (Get-ChildItem -LiteralPath $AppRoot -File -Recurse | Measure-Object Length -Sum).Sum
Get-ChildItem -LiteralPath $AppRoot -File -Recurse -Filter '*.pdb' | ForEach-Object { Remove-PackageItem $_.FullName }
# The frozen engine is shipped, so duplicate source fallback files are unnecessary.
Remove-PackageItem (Join-Path $AppRoot 'backend')
# The app is English; remove unused framework translation assemblies, retaining all other resources.
Get-ChildItem -LiteralPath $AppRoot -Directory | Where-Object { $_.Name -match '^[a-z]{2}(?:-[A-Za-z]{2,4})?$' -and $_.Name -ne 'en' } | ForEach-Object {
    $Files = @(Get-ChildItem -LiteralPath $_.FullName -File -Recurse)
    if ($Files.Count -gt 0 -and @($Files | Where-Object { $_.Name -notlike '*.resources.dll' }).Count -eq 0) {
        Remove-PackageItem $_.FullName
    }
}
$After = (Get-ChildItem -LiteralPath $AppRoot -File -Recurse | Measure-Object Length -Sum).Sum
Write-Host "Portable package cleanup saved $($Before - $After) bytes."
