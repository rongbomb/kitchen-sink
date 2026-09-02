# Builds Kitchen-Sink-Windows.zip on the Desktop (portable, no dev junk).
$ErrorActionPreference = "Stop"
$root = Split-Path -Parent $MyInvocation.MyCommand.Path
$destName = "Kitchen-Sink-Windows"
$stage = Join-Path $env:TEMP $destName
$zipPath = Join-Path ([Environment]::GetFolderPath("Desktop")) "$destName.zip"

if (Test-Path $stage) { Remove-Item $stage -Recurse -Force }
New-Item -ItemType Directory -Path $stage | Out-Null

$include = @(
    "Kitchen Sink.bat",
    "Kitchen Sink (Debug).bat",
    "KitchenSink.pyw",
    "setup.bat",
    "update.bat",
    "requirements.txt",
    "README.md",
    "START HERE.txt"
)

foreach ($f in $include) {
    Copy-Item (Join-Path $root $f) (Join-Path $stage $f)
}

Copy-Item (Join-Path $root "app") (Join-Path $stage "app") -Recurse
Copy-Item (Join-Path $root "web") (Join-Path $stage "web") -Recurse

# Strip caches if any slipped in
Get-ChildItem $stage -Recurse -Directory -Filter "__pycache__" -ErrorAction SilentlyContinue |
    Remove-Item -Recurse -Force

if (Test-Path $zipPath) { Remove-Item $zipPath -Force }
Compress-Archive -Path (Join-Path $stage "*") -DestinationPath $zipPath -CompressionLevel Optimal

Remove-Item $stage -Recurse -Force

$sizeMb = [math]::Round((Get-Item $zipPath).Length / 1MB, 2)
Write-Host ""
Write-Host "  Created: $zipPath"
Write-Host "  Size:    $sizeMb MB"
Write-Host ""
Write-Host "  Copy this zip to your laptop, extract anywhere, read START HERE.txt, run setup.bat once."
Write-Host ""
