# Builds Kitchen-Sink-Windows.zip on the Desktop (portable, no dev junk).
$ErrorActionPreference = "Stop"

# This script lives in tools\, so the project root is one level up.
$root = Split-Path -Parent (Split-Path -Parent $MyInvocation.MyCommand.Path)
$destName = "Kitchen-Sink-Windows"
$stage = Join-Path $env:TEMP $destName
$zipPath = Join-Path ([Environment]::GetFolderPath("Desktop")) "$destName.zip"

if (Test-Path $stage) { Remove-Item $stage -Recurse -Force }
New-Item -ItemType Directory -Path $stage | Out-Null

# Everything the user sees at the top level.
foreach ($f in @("Kitchen Sink.bat", "setup.bat", "README.md")) {
    Copy-Item (Join-Path $root $f) (Join-Path $stage $f)
}

# bin\ and .venv\ are deliberately absent — setup.bat builds both, and
# together they weigh far more than the rest of the app.
foreach ($d in @("src", "docs", "tools")) {
    Copy-Item (Join-Path $root $d) (Join-Path $stage $d) -Recurse
}

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
Write-Host "  Copy this zip to your laptop, extract anywhere, read docs\START HERE.txt, run setup.bat once."
Write-Host ""
