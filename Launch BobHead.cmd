@echo off
setlocal
if not exist "%~dp0runtime\ComfyUI_windows_portable\python_embeded\python.exe" (
  echo This is the BobHead source checkout. Download Start-BobHead.cmd from:
  echo https://github.com/jalrobustvfx/BobHead/releases/latest
  echo That starter installs the bundled app and ComfyUI runtime.
  pause
  exit /b 1
)
"%~dp0runtime\ComfyUI_windows_portable\python_embeded\python.exe" -s "%~dp0app\launcher.py" --portable "%~dp0runtime\ComfyUI_windows_portable" --app-port 8790 --engine-port 8190 --bundled
if errorlevel 1 pause
