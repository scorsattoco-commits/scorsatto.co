$ErrorActionPreference = "Stop"

$Root = "C:\Users\aliss\OneDrive\Documentos\SCORSATTO\site-scorsatto"
$Date = Get-Date -Format "yyyy-MM-dd-HHmmss"
$BackupRoot = Join-Path $Root "previews\backups\site-critical"
$BackupDir = Join-Path $BackupRoot $Date
$ZipPath = "$BackupDir.zip"

New-Item -ItemType Directory -Force -Path $BackupDir | Out-Null

$Items = @(
  "index.html",
  "beta-kit-scorsatto.html",
  "privacidade.html",
  "termos.html",
  "exclusao-dados.html",
  "robots.txt",
  "sitemap.xml",
  "CNAME",
  ".nojekyll",
  "supabase",
  "scripts",
  "data"
)

foreach ($Item in $Items) {
  $Source = Join-Path $Root $Item
  if (Test-Path $Source) {
    Copy-Item -LiteralPath $Source -Destination $BackupDir -Recurse -Force
  }
}

Compress-Archive -Path (Join-Path $BackupDir "*") -DestinationPath $ZipPath -Force

Get-ChildItem $BackupRoot -Filter "*.zip" | Sort-Object LastWriteTime -Descending | Select-Object -Skip 14 | Remove-Item -Force

Write-Output $ZipPath
