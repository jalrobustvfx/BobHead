@echo off
setlocal
title BobHead Setup
set "BOBHEAD_BOOTSTRAP=%~f0"
powershell.exe -NoProfile -Command "try { $sections=(Get-Content -LiteralPath $env:BOBHEAD_BOOTSTRAP -Raw) -split '(?m)^# BOBHEAD_POWERSHELL_START\r?$',2; if($sections.Length -ne 2){throw 'Starter is incomplete'}; & ([scriptblock]::Create($sections[1])) } catch { Write-Host $_ -ForegroundColor Red; exit 1 }"
if errorlevel 1 (
  pause
  exit /b 1
)
exit /b
# BOBHEAD_POWERSHELL_START
$ErrorActionPreference = 'Stop'
function Get-BobHeadHash([string]$path) {
    $stream = [IO.File]::OpenRead($path)
    $sha = [Security.Cryptography.SHA256]::Create()
    try { return [BitConverter]::ToString($sha.ComputeHash($stream)).Replace('-', '').ToLowerInvariant() }
    finally { $stream.Dispose(); $sha.Dispose() }
}
$manifest = ConvertFrom-Json @'
{
  "archive": "BobHead-Standalone-v06.zip",
  "folder": "BobHead-Standalone-v06",
  "bytes": 3345284431,
  "sha256": "08dfc6523bc0eac63a752013b332eb5b6b37683d4c759bf8082cf06be2ec6a57",
  "models_included": false,
  "parts": [
    {
      "name": "BobHead-Standalone-v06.zip.part01",
      "bytes": 1879048192,
      "sha256": "d9948178ee2fc73af064362ed49b84d2db958e1a42741c3487eb3129ec72d98a"
    },
    {
      "name": "BobHead-Standalone-v06.zip.part02",
      "bytes": 1466236239,
      "sha256": "6dae0f0310c8910c6fd4bb446f6d07114f95bbbc7d14c22052369f127ef0b075"
    }
  ]
}
'@
$baseUrl = 'https://github.com/jalrobustvfx/BobHead/releases/download/v0.6.0'
$installParent = Split-Path -Parent $env:BOBHEAD_BOOTSTRAP
$cache = Join-Path $installParent 'BobHead-downloads'
$appRoot = Join-Path $installParent $manifest.folder
$launch = Join-Path $appRoot 'Launch BobHead.cmd'
$marker = Join-Path $appRoot '.release-installed'
$runtimePython = Join-Path $appRoot 'runtime\ComfyUI_windows_portable\python_embeded\python.exe'
$runtimeMain = Join-Path $appRoot 'runtime\ComfyUI_windows_portable\ComfyUI\main.py'

if ((Test-Path -LiteralPath $marker) -and (Test-Path -LiteralPath $launch) -and
    (Test-Path -LiteralPath $runtimePython) -and (Test-Path -LiteralPath $runtimeMain) -and
    ((Get-Content -LiteralPath $marker -Raw).Trim() -eq $manifest.sha256)) {
    Write-Host 'Starting your installed BobHead app...'
    & $launch
    exit $LASTEXITCODE
}

New-Item -ItemType Directory -Force -Path $cache | Out-Null
[Net.ServicePointManager]::SecurityProtocol = [Net.SecurityProtocolType]::Tls12
Write-Host 'BobHead first-time setup. Keep this window open.'
Write-Host 'Downloading the bundled app. Model downloads happen inside the app afterward.'

foreach ($part in $manifest.parts) {
    $target = Join-Path $cache $part.name
    $valid = (Test-Path -LiteralPath $target) -and
        ((Get-Item -LiteralPath $target).Length -eq $part.bytes) -and
        ((Get-BobHeadHash $target) -eq $part.sha256)
    if ($valid) { Write-Host ('Reusing verified download: ' + $part.name); continue }
    $partial = $target + '.partial'
    Write-Host ('Downloading ' + $part.name + ' (' + [Math]::Round($part.bytes / 1GB, 2) + ' GiB)...')
    $client = New-Object Net.WebClient
    try {
        $client.Headers.Add('User-Agent', 'BobHead-Setup-v06')
        $client.DownloadFile($baseUrl + '/' + $part.name, $partial)
    } finally { $client.Dispose() }
    if (((Get-Item -LiteralPath $partial).Length -ne $part.bytes) -or
        ((Get-BobHeadHash $partial) -ne $part.sha256)) {
        throw ('Download verification failed: ' + $part.name + '. Run this starter again to retry.')
    }
    # These paths are fixed filenames inside the starter's own download directory.
    Move-Item -LiteralPath $partial -Destination $target -Force
}

$archive = Join-Path $cache $manifest.archive
$archiveValid = (Test-Path -LiteralPath $archive) -and
    ((Get-Item -LiteralPath $archive).Length -eq $manifest.bytes) -and
    ((Get-BobHeadHash $archive) -eq $manifest.sha256)
if (-not $archiveValid) {
    Write-Host 'Joining and checking the runtime archive...'
    $writer = [IO.File]::Create($archive)
    try {
        foreach ($part in $manifest.parts) {
            $reader = [IO.File]::OpenRead((Join-Path $cache $part.name))
            try { $reader.CopyTo($writer) } finally { $reader.Dispose() }
        }
    } finally { $writer.Dispose() }
    if (((Get-Item -LiteralPath $archive).Length -ne $manifest.bytes) -or
        ((Get-BobHeadHash $archive) -ne $manifest.sha256)) {
        throw 'The archive checksum did not match. Run the starter again to retry.'
    }
}

Write-Host 'Extracting the bundled runtime. This can take several minutes...'
Add-Type -AssemblyName System.IO.Compression.FileSystem
$root = [IO.Path]::GetFullPath($installParent).TrimEnd('\') + '\'
$zip = [IO.Compression.ZipFile]::OpenRead($archive)
try {
    foreach ($entry in $zip.Entries) {
        $path = [IO.Path]::GetFullPath((Join-Path $installParent $entry.FullName))
        if (-not $path.StartsWith($root, [StringComparison]::OrdinalIgnoreCase)) {
            throw 'The archive contains a path outside the installation folder.'
        }
        if ($entry.FullName.EndsWith('/')) {
            [IO.Directory]::CreateDirectory($path) | Out-Null
        } else {
            [IO.Directory]::CreateDirectory([IO.Path]::GetDirectoryName($path)) | Out-Null
            [IO.Compression.ZipFileExtensions]::ExtractToFile($entry, $path, $true)
        }
    }
} finally { $zip.Dispose() }
if (-not ((Test-Path -LiteralPath $launch) -and (Test-Path -LiteralPath $runtimePython) -and
    (Test-Path -LiteralPath $runtimeMain))) { throw 'The extracted runtime is incomplete.' }
Set-Content -LiteralPath $marker -Value $manifest.sha256 -Encoding ASCII
Write-Host 'Setup complete. Starting BobHead...'
& $launch
exit $LASTEXITCODE
