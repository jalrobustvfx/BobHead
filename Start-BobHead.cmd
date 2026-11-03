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
        $request.UserAgent = 'BobHead-Setup-v08'
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

function Install-BobHeadAppUpdate {
    if (-not $appUpdate) { return }
    New-Item -ItemType Directory -Force -Path $cache | Out-Null
    $updateMarker = Join-Path $appRoot '.app-update-installed'
    if ((Test-Path -LiteralPath $updateMarker) -and
        ((Get-Content -LiteralPath $updateMarker -Raw).Trim() -eq $appUpdate.sha256) -and
        (Test-Path -LiteralPath (Join-Path $appRoot ('workflows\' + $appUpdate.workflow)))) { return }
    Write-Host ('Updating BobHead to ' + $appUpdate.version + '. Existing models are kept.')
    $updateZip = Join-Path $cache $appUpdate.archive
    $updateValid = (Test-Path -LiteralPath $updateZip) -and
        ((Get-Item -LiteralPath $updateZip).Length -eq $appUpdate.bytes) -and
        ((Get-BobHeadHash $updateZip) -eq $appUpdate.sha256)
    if (-not $updateValid) {
        $updatePartial = $updateZip + '.partial'
        Save-BobHeadDownload ($appUpdateBaseUrl + '/' + $appUpdate.archive) $updatePartial $appUpdate.bytes 0 $appUpdate.bytes
        if ((Get-BobHeadHash $updatePartial) -ne $appUpdate.sha256) {
            [IO.File]::Delete($updatePartial)
            throw 'The app update checksum did not match. Run this starter again.'
        }
        Move-Item -LiteralPath $updatePartial -Destination $updateZip -Force
    }
    Add-Type -AssemblyName System.IO.Compression.FileSystem
    $stage = Join-Path $cache ('app-update-' + $appUpdate.sha256.Substring(0, 12))
    New-Item -ItemType Directory -Force -Path $stage | Out-Null
    $stageRoot = [IO.Path]::GetFullPath($stage).TrimEnd('\') + '\'
    $installRoot = [IO.Path]::GetFullPath($appRoot).TrimEnd('\') + '\'
    $expected = @{}
    foreach ($file in $appUpdate.files) { $expected[$file.path] = $file }
    $zip = [IO.Compression.ZipFile]::OpenRead($updateZip)
    try {
        if ($zip.Entries.Count -ne $expected.Count) { throw 'Unexpected files in the app update.' }
        foreach ($entry in $zip.Entries) {
            $name = $entry.FullName
            if (-not $expected.ContainsKey($name)) { throw 'An unlisted file was found in the app update.' }
            if ($name.Contains(':') -or $name.StartsWith('/') -or $name.StartsWith('\') -or
                (($name.Replace('\', '/').Split('/')) -contains '..') -or
                (@('runtime','cache','.data') -contains ($name.Replace('\', '/').Split('/')[0]))) { throw 'Unsafe app update path.' }
            $target = [IO.Path]::GetFullPath($stageRoot + $name.Replace('/', '\'))
            $destination = [IO.Path]::GetFullPath($installRoot + $name.Replace('/', '\'))
            if ((-not $target.StartsWith($stageRoot, [StringComparison]::OrdinalIgnoreCase)) -or
                (-not $destination.StartsWith($installRoot, [StringComparison]::OrdinalIgnoreCase))) {
                throw 'An app update path is outside the installation folder.'
            }
            [IO.Directory]::CreateDirectory([IO.Path]::GetDirectoryName($target)) | Out-Null
            [IO.Compression.ZipFileExtensions]::ExtractToFile($entry, $target, $true)
            $file = $expected[$name]
            if (((Get-Item -LiteralPath $target).Length -ne $file.bytes) -or
                ((Get-BobHeadHash $target) -ne $file.sha256)) { throw ('App update verification failed: ' + $name) }
        }
    } finally { $zip.Dispose() }
    # Copy only verified application files. Runtime/model and user-data folders are excluded.
    foreach ($file in $appUpdate.files) {
        $source = Join-Path $stage $file.path
        $target = Join-Path $appRoot $file.path
        [IO.Directory]::CreateDirectory([IO.Path]::GetDirectoryName($target)) | Out-Null
        [IO.File]::Copy($source, $target, $true)
    }
    Set-Content -LiteralPath $updateMarker -Value $appUpdate.sha256 -Encoding ASCII
    Write-Host ('BobHead ' + $appUpdate.version + ' is installed.')
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
$appUpdate = ConvertFrom-Json @'
{
  "version": "v0.8.0",
  "workflow": "BobHead_Comfyui_v08.json",
  "archive": "BobHead-App-v08.zip",
  "bytes": 198385,
  "sha256": "cbc21e7033ff6b2266dd3d37b103d85b2ac9a30ffcd71d38c583aec6ebc335ab",
  "files": [
    {
      "path": "INSTALL.md",
      "bytes": 6963,
      "sha256": "4a1cbc817654a5b453cb447c8aab93c381cfadd32aa46b40e107428fa7f7a079"
    },
    {
      "path": "LICENSE",
      "bytes": 1274,
      "sha256": "ef73531f4ffb27268c6cb5c1a5cba46c11f9c38b002b6107d7a9b28298d62edf"
    },
    {
      "path": "Launch BobHead.cmd",
      "bytes": 549,
      "sha256": "a37312dab0fe438cf97bee2bccb44a496203375d7f51e29e0f354d8c7704e337"
    },
    {
      "path": "MODELS.md",
      "bytes": 4311,
      "sha256": "4283556a7edff4c60ee686f4aa89c39d3a64c687f653e8d31fcf91330d444bb6"
    },
    {
      "path": "NODE_SETUP.md",
      "bytes": 2118,
      "sha256": "992f09604469acc8160c4a27a0c69ea99cc3b70a9a0ec1811559ac8e0ed15590"
    },
    {
      "path": "README.md",
      "bytes": 8082,
      "sha256": "185a63cabbf7040b182f35ed0f7735881c324b3722ee7b36083d3f8636233244"
    },
    {
      "path": "SOURCE_README.md",
      "bytes": 8082,
      "sha256": "185a63cabbf7040b182f35ed0f7735881c324b3722ee7b36083d3f8636233244"
    },
    {
      "path": "app/launcher.py",
      "bytes": 8012,
      "sha256": "ebe152ff15685ec6656bfe561eaac928c857df42b564c799b49d63fd0f916f1b"
    },
    {
      "path": "app/model_setup.py",
      "bytes": 5304,
      "sha256": "6e99a50b87d6e51a5852a8042fdee6806fcc795ce309da56e7d65d34fdb69a37"
    },
    {
      "path": "app/server.py",
      "bytes": 22983,
      "sha256": "811bee67fb999aab84b4e48e196a01cc755684486b57f5ef866fccdd7ad43ae3"
    },
    {
      "path": "app/static/app.js",
      "bytes": 13037,
      "sha256": "9b2c91249300dc5400b7eb14c900371d4a300c68040d29f74e44e558ac46d684"
    },
    {
      "path": "app/static/index.html",
      "bytes": 12093,
      "sha256": "3e37e4e5667bf275442e281a943bcc4a52f13f702e25eae9add1df94b4024ac0"
    },
    {
      "path": "app/static/style.css",
      "bytes": 18653,
      "sha256": "fb09db084bb61b5ce7a0132e8b0d4e08487dc620d9b5eb81b2d46a8bc89e42b5"
    },
    {
      "path": "docs/DEVELOPMENT.md",
      "bytes": 3796,
      "sha256": "26cd3753b6b615d1b6d11ae4665542704781e5c6520910a78ffd0898207d07d6"
    },
    {
      "path": "docs/QUICKSTART.md",
      "bytes": 6956,
      "sha256": "709802f865ebde6dae7deceb486d52a7ee79a5e4a4ebab2351d7d67da6b752dd"
    },
    {
      "path": "environment/app-workflow.json",
      "bytes": 293,
      "sha256": "f8db9d81b39cb0b210206d9d21d3e14844181c9d9844edec88d94b82695489e9"
    },
    {
      "path": "environment/model-downloads.json",
      "bytes": 7210,
      "sha256": "6ae7b459f33ad54581270c123b8c5915b229df4b83bc42e1845d24f1ba14a48e"
    },
    {
      "path": "environment/v08-validation.json",
      "bytes": 417,
      "sha256": "e49c855a7ebfac3883cdddf2aa96dbd024fbb325f5223baa6902d1c9c3fe0335"
    },
    {
      "path": "requirements-app.txt",
      "bytes": 16,
      "sha256": "9ff2177e763edd4e9724ffbd5a78794aa24e8492245e2f9e2b3f521fdf956b74"
    },
    {
      "path": "tests/test_app.py",
      "bytes": 10107,
      "sha256": "0d636d9c45927c92d5a4c5c4280ad28e79398b7fc169f225f3c152a4eadf5e5c"
    },
    {
      "path": "tests/test_app_update.py",
      "bytes": 4091,
      "sha256": "38abe305c74b4522dc6f77aebbc7ffd6f34fa083d9e4f27dc2ab0ad42c5a35e1"
    },
    {
      "path": "tests/test_compile_workflow.py",
      "bytes": 3112,
      "sha256": "ba1b8386234032ed1a6bf83019807f8a60cd5e131e826d4ad19b3352072f1398"
    },
    {
      "path": "tests/test_launcher.py",
      "bytes": 4599,
      "sha256": "a92546f0d78dadd65dd57b5c88b86f517514e84d3fb59a3b2c8ed90b8cb6e465"
    },
    {
      "path": "tests/test_model_setup.py",
      "bytes": 3561,
      "sha256": "ce9d5d59c6a118c93ef806abb7244e564bf60ad341f95a06cbf6b769e626d340"
    },
    {
      "path": "tests/test_starter_download.py",
      "bytes": 5397,
      "sha256": "377288843280275c5c5a9d7c7d2112653afa590409bdc18bba160901be619d70"
    },
    {
      "path": "tools/archive_standalone.py",
      "bytes": 2439,
      "sha256": "f2898b40aef78f71c570003bd67ef1d62bcdbf03dae0ad766783ac25b037d0d9"
    },
    {
      "path": "tools/build_app_update.py",
      "bytes": 3590,
      "sha256": "99d00f4a8f43ad5c5031e3a0ef7556e8777cbddbbcf3f771ce71a7aca4b22f52"
    },
    {
      "path": "tools/build_standalone.py",
      "bytes": 8294,
      "sha256": "743915183bd8fb63344a5965fc395f9b3dc4bf97ad93a018edfcf31d0f2f7af2"
    },
    {
      "path": "tools/compile_workflow.py",
      "bytes": 7363,
      "sha256": "1b73a33962f42d4f66c40606acfebafe16a7563eabbf3276b61f20842ff30ce7"
    },
    {
      "path": "tools/prepare_api.py",
      "bytes": 330,
      "sha256": "89f2d61bb3864b7060f877791113326c26967141b2f7cc1711d9e8e01d03b9a7"
    },
    {
      "path": "tools/prepare_release.py",
      "bytes": 4097,
      "sha256": "164bfee2943fd4486d7ddf48bb3728bb481720d3aa08b38ebffa5069683d99d2"
    },
    {
      "path": "tools/smoke_test.py",
      "bytes": 2206,
      "sha256": "3f65f72eec9983fef6265801a8e03d978f3e88f42e470dca139344962c756779"
    },
    {
      "path": "tools/start_bobhead.ps1",
      "bytes": 14409,
      "sha256": "176d57fabca53a1000b63f2e1487d389b5fdcdc6a3aaf7fcb4f482ffdeecf09c"
    },
    {
      "path": "tools/verify_model_links.py",
      "bytes": 3012,
      "sha256": "5f3bfabb2b3f3662c1a7698f5a454b80e7f596ffa6e896972bdd9f98bfe72537"
    },
    {
      "path": "workflows/BobHead_API.json",
      "bytes": 24019,
      "sha256": "235672b03524307ac53b6b7b6149dcc04c7934d44dd8dc51dc28d546c850eb09"
    },
    {
      "path": "workflows/BobHead_Comfyui_v06.json",
      "bytes": 173072,
      "sha256": "d907c97de538474e05783741e26b486babc90d87974709c45398fdc86c6c0128"
    },
    {
      "path": "workflows/BobHead_Comfyui_v06_API_source.json",
      "bytes": 17436,
      "sha256": "d1fb7a6478122c175287384cafc80985ce0ea703bc441f6b911aa58f63766b84"
    },
    {
      "path": "workflows/BobHead_Comfyui_v07.json",
      "bytes": 282931,
      "sha256": "a3a8643c5f6a8149574434d5bf9f89adc81c05d959013458b87b3c9f4dece7bb"
    },
    {
      "path": "workflows/BobHead_Comfyui_v07_API_source.json",
      "bytes": 22960,
      "sha256": "d28b38f7cad2933f4c717adfae257e37dcf0f9209e0ae4769d189c2ff2bd3f1a"
    },
    {
      "path": "workflows/BobHead_Comfyui_v08.json",
      "bytes": 287493,
      "sha256": "b32abab9be7950e2d301bf34fb8a64ae747dfcc65f6f198cd558778dc141db0e"
    },
    {
      "path": "workflows/BobHead_Comfyui_v08_API_source.json",
      "bytes": 24328,
      "sha256": "8e47aa30b73f7a425d1d2aa48fa89ad61f196619dfa2e025c85b4f6f91d4cf0d"
    },
    {
      "path": "workflows/README-v07.md",
      "bytes": 2479,
      "sha256": "ad6628c943aa052ba9e9d92ade3795abcebfc9a455d69c6d01cc93bc3d33dea5"
    },
    {
      "path": "workflows/README-v08.md",
      "bytes": 1918,
      "sha256": "30b0432f6c8ec32abcc14388f8ea310e712ca0e47a472d5914ea9e64c79a69e1"
    }
  ]
}
'@
$appUpdateBaseUrl = 'https://github.com/jalrobustvfx/BobHead/releases/download/v0.8.0'
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
    Install-BobHeadAppUpdate
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
Install-BobHeadAppUpdate
Write-Host 'Setup complete. Starting BobHead...'
& $launch
exit $LASTEXITCODE
