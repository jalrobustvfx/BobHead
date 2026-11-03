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
function Show-BobHeadDownloadProgress([long]$received, [long]$completedBytes, [long]$totalBytes, [double]$speed, [string]$state) {
    $done = $completedBytes + $received
    $fraction = [Math]::Min(1.0, $done / [double]$totalBytes)
    $filled = [int][Math]::Floor($fraction * 20)
    $bar = ('#' * $filled) + ('-' * (20 - $filled))
    $line = '[{0}] {1,5:N1}% {2:N0}/{3:N0} MiB {4:N1} MiB/s {5}' -f $bar, ($fraction * 100), ($done / 1MB), ($totalBytes / 1MB), $speed, $state
    [Console]::Write("`r" + $line.PadRight(95))
}
function Save-BobHeadDownload([string]$url, [string]$destination, [long]$expectedBytes,
    [long]$completedBytes, [long]$totalBytes, [int]$idleTimeoutSeconds = 30,
    [int]$retryDelaySeconds = 3, [int]$maxAttempts = 5) {
    for ($attempt = 1; $attempt -le $maxAttempts; $attempt++) {
        $received = [long]0
        if (Test-Path -LiteralPath $destination) { $received = (Get-Item -LiteralPath $destination).Length }
        if ($received -eq $expectedBytes) { return } # Caller verifies SHA256 before installation.
        if ($received -gt $expectedBytes) { $received = 0 }
        $offset = $received
        $request = [Net.HttpWebRequest]::Create($url)
        $request.UserAgent = 'BobHead-Setup-v07'
        $request.CachePolicy = New-Object Net.Cache.RequestCachePolicy([Net.Cache.RequestCacheLevel]::NoCacheNoStore)
        $request.Timeout = 30000
        $request.ReadWriteTimeout = 30000
        if ($offset -gt 0) { $request.AddRange($offset); Write-Host ('Resuming at ' + [Math]::Round($offset / 1MB, 1) + ' MiB...') }
        $response = $null; $inputStream = $null; $outputStream = $null
        $retryable = $true
        $timer = [Diagnostics.Stopwatch]::StartNew()
        $lastUpdate = -1.0
        try {
            $response = $request.GetResponse()
            if ([int]$response.StatusCode -eq 206) {
                $range = $response.Headers['Content-Range']
                if ($range -notmatch ('^bytes ' + $offset + '-\d+/' + $expectedBytes + '$')) {
                    $retryable = $false; throw 'The server returned an incorrect download range.'
                }
                $mode = [IO.FileMode]::Append
            } else {
                # A server ignoring Range must restart, never append a full response.
                $received = 0; $offset = 0; $mode = [IO.FileMode]::Create
            }
            $inputStream = $response.GetResponseStream()
            $outputStream = [IO.File]::Open($destination, $mode, [IO.FileAccess]::Write, [IO.FileShare]::Read)
            $buffer = New-Object byte[] 65536
            do {
                $idle = [Diagnostics.Stopwatch]::StartNew()
                $pending = $inputStream.ReadAsync($buffer, 0, $buffer.Length)
                while (-not $pending.Wait(250)) {
                    Show-BobHeadDownloadProgress $received $completedBytes $totalBytes 0 ('Waiting ' + [int]$idle.Elapsed.TotalSeconds + 's...')
                    if ($idle.Elapsed.TotalSeconds -ge $idleTimeoutSeconds) {
                        $request.Abort(); throw 'No download data received; reconnecting.'
                    }
                }
                $count = $pending.GetAwaiter().GetResult()
                if ($count -gt 0) {
                    $received += $count
                    if ($received -gt $expectedBytes) { $retryable = $false; throw 'Download is larger than expected.' }
                    $outputStream.Write($buffer, 0, $count)
                }
                $seconds = $timer.Elapsed.TotalSeconds
                if (($seconds - $lastUpdate -ge 0.2) -or ($count -eq 0)) {
                    $speed = ($received - $offset) / 1MB / [Math]::Max(0.01, $seconds)
                    Show-BobHeadDownloadProgress $received $completedBytes $totalBytes $speed ''
                    $lastUpdate = $seconds
                }
            } while ($count -gt 0)
            if ($received -ne $expectedBytes) { throw 'The connection ended before the file finished.' }
            return
        } catch {
            $message = $_.Exception.Message
            $errorResponse = $_.Exception.Response
            if ($errorResponse -and ([int]$errorResponse.StatusCode -in @(401,404))) { $retryable = $false }
            if ((-not $retryable) -or ($attempt -eq $maxAttempts)) {
                throw ('Download stopped: ' + $message + ' Your partial download is saved. Run this starter again to resume.')
            }
        } finally {
            if ($outputStream) { $outputStream.Dispose() }
            if ($inputStream) { $inputStream.Dispose() }
            if ($response) { $response.Dispose() }
            [Console]::WriteLine()
        }
        Write-Host ('Connection interrupted. Reconnecting (' + $attempt + '/' + $maxAttempts + ')...')
        if ($retryDelaySeconds -gt 0) { Start-Sleep -Seconds ([Math]::Min(15, $retryDelaySeconds * $attempt)) }
    }
}

$manifest = ConvertFrom-Json @'
{
  "archive": "BobHead-Standalone-v07.zip",
  "folder": "BobHead-Standalone-v07",
  "bytes": 3411983646,
  "sha256": "9aec987a468262a60eb649a75a12ba46904dacc814a7dce6da43a4ed9a5c2f10",
  "models_included": false,
  "parts": [
    {
      "name": "BobHead-Standalone-v07.zip.part01",
      "bytes": 1879048192,
      "sha256": "24cd384941d3f7920f5674defb8adda53dee045c1da1cb89dad18a23e3e16f05"
    },
    {
      "name": "BobHead-Standalone-v07.zip.part02",
      "bytes": 1532935454,
      "sha256": "c51845c95ce4b8795df70a2b9bd213abe2124e8c3d581f6b0630a14c46afba6b"
    }
  ]
}
'@
$baseUrl = 'https://github.com/jalrobustvfx/BobHead/releases/download/v0.7.0'
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

$completedDownloadBytes = [long]0
foreach ($part in $manifest.parts) {
    $target = Join-Path $cache $part.name
    $valid = (Test-Path -LiteralPath $target) -and
        ((Get-Item -LiteralPath $target).Length -eq $part.bytes) -and
        ((Get-BobHeadHash $target) -eq $part.sha256)
    if ($valid) { Write-Host ('Reusing verified download: ' + $part.name); $completedDownloadBytes += $part.bytes; continue }
    $partial = $target + '.partial'
    Write-Host ('Downloading ' + $part.name + ' (' + [Math]::Round($part.bytes / 1GB, 2) + ' GiB)...')
    Save-BobHeadDownload ($baseUrl + '/' + $part.name) $partial $part.bytes $completedDownloadBytes $manifest.bytes
    Write-Host 'Checking downloaded file...'
    if (((Get-Item -LiteralPath $partial).Length -ne $part.bytes) -or
        ((Get-BobHeadHash $partial) -ne $part.sha256)) {
        [IO.File]::Delete($partial) # A corrupt generated download cannot be resumed safely.
        throw ('Download verification failed: ' + $part.name + '. Run this starter again to retry.')
    }
    # These paths are fixed filenames inside the starter's own download directory.
    Move-Item -LiteralPath $partial -Destination $target -Force
    $completedDownloadBytes += $part.bytes
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
# Use extended Windows paths so the included package license paths extract
# correctly even when the installation folder is nested inside Downloads.
if ($root.StartsWith('\\')) { $root = '\\?\UNC\' + $root.Substring(2) }
else { $root = '\\?\' + $root }
$zip = [IO.Compression.ZipFile]::OpenRead($archive)
try {
    foreach ($entry in $zip.Entries) {
        $entryName = $entry.FullName.Replace('/', '\')
        if ($entryName.StartsWith('\') -or $entryName.Contains(':') -or
            ($entryName.Split('\') -contains '..')) {
            throw 'The archive contains an unsafe path.'
        }
        $path = [IO.Path]::GetFullPath($root + $entryName)
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
