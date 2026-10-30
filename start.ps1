param(
    [string]$ComfyPortable,
    [string]$ComfyUrl = 'http://127.0.0.1:8188',
    [int]$Port = 8787
)
$ErrorActionPreference = 'Stop'
if ($ComfyPortable) {
    $BobHeadPython = Join-Path $ComfyPortable 'python_embeded\python.exe'
    if (-not (Test-Path -LiteralPath $BobHeadPython)) {
        throw 'ComfyPortable must point to the folder containing python_embeded and ComfyUI.'
    }
} else {
    $BobHeadPython = 'python'
}
& $BobHeadPython (Join-Path $PSScriptRoot 'app\server.py') --comfy-url $ComfyUrl --port $Port
