@echo off
setlocal
set "BOBHEAD_PY=python"
if not "%~1"=="" set "BOBHEAD_PY=%~1\python_embeded\python.exe"
"%BOBHEAD_PY%" "%~dp0app\server.py"
if errorlevel 1 pause
