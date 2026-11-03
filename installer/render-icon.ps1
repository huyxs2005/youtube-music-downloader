[CmdletBinding()]
param([string]$Python = "python")
$ErrorActionPreference = "Stop"
Add-Type -AssemblyName WindowsBase, PresentationCore
$ProjectRoot = Split-Path -Parent $PSScriptRoot
$Assets = Join-Path $ProjectRoot "desktop\Assets"
[xml]$Svg = Get-Content -LiteralPath (Join-Path $Assets "app-icon.svg") -Raw
$Shape = $Svg.svg.rect
$Visual = New-Object System.Windows.Media.DrawingVisual
$Drawing = $Visual.RenderOpen()
$Drawing.PushTransform([System.Windows.Media.ScaleTransform]::new(4, 4))
$Rectangle = [System.Windows.Rect]::new([double]$Shape.x, [double]$Shape.y, [double]$Shape.width, [double]$Shape.height)
$Drawing.DrawRoundedRectangle([System.Windows.Media.Brushes]::Red, $null, $Rectangle, [double]$Shape.rx, [double]$Shape.rx)
$Triangle = [System.Windows.Media.Geometry]::Parse("M" + ($Svg.svg.polygon.points -replace " ", " L") + " Z")
$Drawing.DrawGeometry([System.Windows.Media.Brushes]::White, $null, $Triangle)
$Drawing.Pop()
$Drawing.Close()
$Bitmap = [System.Windows.Media.Imaging.RenderTargetBitmap]::new(1024, 1024, 96, 96, [System.Windows.Media.PixelFormats]::Pbgra32)
$Bitmap.Render($Visual)
$Encoder = New-Object System.Windows.Media.Imaging.PngBitmapEncoder
$Encoder.Frames.Add([System.Windows.Media.Imaging.BitmapFrame]::Create($Bitmap))
$Stream = [IO.File]::Create((Join-Path $Assets "app-icon.png"))
try { $Encoder.Save($Stream) } finally { $Stream.Dispose() }
Push-Location $ProjectRoot
try {
    & $Python -c "from PIL import Image; Image.open('desktop/Assets/app-icon.png').save('desktop/Assets/app-icon.ico',format='ICO',sizes=[(16,16),(24,24),(32,32),(48,48),(64,64),(128,128),(256,256)])"
    if ($LASTEXITCODE -ne 0) { throw "Creating the Windows ICO failed." }
} finally { Pop-Location }
Write-Host "Rendered app-icon.svg as PNG and a multi-resolution Windows ICO."
