$ErrorActionPreference = 'Stop'
function Get-BobHeadHash([string]$path) {
    $stream = [IO.File]::OpenRead($path)
    $sha = [Security.Cryptography.SHA256]::Create()
    try { return [BitConverter]::ToString($sha.ComputeHash($stream)).Replace('-', '').ToLowerInvariant() }
    finally { $stream.Dispose(); $sha.Dispose() }
}
function Save-BobHeadDownload([string]$url, [string]$destination, [long]$expectedBytes,
    [long]$completedBytes, [long]$totalBytes) {
    $request = [Net.HttpWebRequest]::Create($url)
    $request.UserAgent = 'BobHead-Setup-v07'
    $request.Timeout = 60000
    $request.ReadWriteTimeout = 120000
    $response = $null
    $inputStream = $null
    $outputStream = $null
    $received = [long]0
    $timer = [Diagnostics.Stopwatch]::StartNew()
    $lastUpdate = -1.0
    try {
        $response = $request.GetResponse()
        $inputStream = $response.GetResponseStream()
        $outputStream = [IO.File]::Create($destination)
        $buffer = New-Object byte[] 65536
        do {
            $count = $inputStream.Read($buffer, 0, $buffer.Length)
            if ($count -gt 0) {
                $received += $count
                if ($received -gt $expectedBytes) { throw 'Download is larger than expected.' }
                $outputStream.Write($buffer, 0, $count)
            }
            $seconds = $timer.Elapsed.TotalSeconds
            if (($seconds - $lastUpdate -ge 0.2) -or ($count -eq 0)) {
                $done = $completedBytes + $received
                $fraction = [Math]::Min(1.0, $done / [double]$totalBytes)
                $filled = [int][Math]::Floor($fraction * 20)
                $bar = ('#' * $filled) + ('-' * (20 - $filled))
                $speed = $received / 1MB / [Math]::Max(0.01, $seconds)
                $line = '[{0}] {1,5:N1}%  {2:N0}/{3:N0} MiB  {4:N1} MiB/s' -f $bar, ($fraction * 100), ($done / 1MB), ($totalBytes / 1MB), $speed
                [Console]::Write("`r" + $line + '    ')
                $lastUpdate = $seconds
            }
        } while ($count -gt 0)
    } finally {
        if ($outputStream) { $outputStream.Dispose() }
        if ($inputStream) { $inputStream.Dispose() }
        if ($response) { $response.Dispose() }
        [Console]::WriteLine()
    }
}
$manifest = ConvertFrom-Json @'
__MANIFEST_JSON__
'@
$baseUrl = '__RELEASE_URL__'
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
