"""Single-entry local launcher. Uses only the portable Python standard library."""
import argparse
import json
import os
from pathlib import Path
import socket
import subprocess
import sys
import time
from urllib.error import HTTPError, URLError
from urllib.request import urlopen
import webbrowser

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / '.data'


def portable_folder(path):
    base = Path(path).expanduser().resolve()
    candidates = [base, base / 'ComfyUI_windows_portable',
                  base / 'ComfyUI_windows_portable_nvidia' / 'ComfyUI_windows_portable']
    for candidate in candidates:
        if (candidate / 'python_embeded' / 'python.exe').is_file() and (candidate / 'ComfyUI' / 'main.py').is_file():
            return candidate
    raise ValueError('Select the portable folder containing python_embeded and ComfyUI.')


def read_json(url, timeout=3):
    try:
        with urlopen(url, timeout=timeout) as response:
            return json.load(response)
    except (OSError, ValueError, URLError, HTTPError):
        return None


def port_in_use(port):
    with socket.socket() as sock:
        sock.settimeout(.5)
        return sock.connect_ex(('127.0.0.1', port)) == 0


def start_background(command, cwd, log_file, env=None):
    flags = (subprocess.CREATE_NO_WINDOW | subprocess.CREATE_NEW_PROCESS_GROUP) if os.name == 'nt' else 0
    with log_file.open('ab') as log:
        log.write(f'\n--- BobHead launch {time.strftime("%Y-%m-%d %H:%M:%S")} ---\n'.encode())
        return subprocess.Popen(command, cwd=str(cwd), stdin=subprocess.DEVNULL,
                                stdout=log, stderr=subprocess.STDOUT, creationflags=flags, env=env)


def wait_until(url, predicate, process, log_path, timeout):
    deadline = time.monotonic() + timeout
    next_update = 0
    while time.monotonic() < deadline:
        result = read_json(url)
        if result is not None and predicate(result): return result
        if process is not None and process.poll() is not None:
            raise RuntimeError(f'A startup process exited. Read {log_path} for the reason.')
        if time.monotonic() >= next_update:
            print('  Waiting for startup...', flush=True)
            next_update = time.monotonic() + 10
        time.sleep(.5)
    raise RuntimeError(f'Startup timed out. Read {log_path}, then run the launcher again.')


def launch(portable, app_port=8787, engine_port=8188, open_browser=True, timeout=240, bundled=False):
    portable = portable_folder(portable)
    python = portable / 'python_embeded' / 'python.exe'
    comfy_url = f'http://127.0.0.1:{engine_port}'
    app_url = f'http://127.0.0.1:{app_port}'
    logs = DATA / 'logs'
    logs.mkdir(parents=True, exist_ok=True)
    child_env = None
    if bundled:
        if not portable.is_relative_to(ROOT):
            raise ValueError('Bundled mode requires the runtime inside the BobHead folder.')
        child_env = os.environ.copy()
        for name in ('PYTHONPATH', 'PYTHONHOME', 'HF_TOKEN', 'HUGGING_FACE_HUB_TOKEN', 'HF_HUB_OFFLINE', 'TRANSFORMERS_OFFLINE'):
            child_env.pop(name, None)
        child_env.update(HF_HOME=str(ROOT / 'cache/huggingface'),
                         HF_HUB_CACHE=str(ROOT / 'cache/huggingface/hub'),
                         HF_HUB_DISABLE_TELEMETRY='1', PYTHONNOUSERSITE='1',
                         TORCH_HOME=str(ROOT / 'cache/torch'),
                         TORCHINDUCTOR_CACHE_DIR=str(ROOT / 'cache/torchinductor'),
                         TRITON_CACHE_DIR=str(ROOT / 'cache/triton'),
                         XDG_CACHE_HOME=str(ROOT / 'cache'), NO_ALBUMENTATIONS_UPDATE='1')

    if child_env is not None:
        child_env['BOBHEAD_COMFY_ROOT'] = str(portable / 'ComfyUI')

    # Reuse an app only if its identity and engine address match.
    health = read_json(app_url + '/api/health')
    if health and health.get('app') == 'bobhead':
        if health.get('comfy_url') != comfy_url:
            raise RuntimeError('BobHead is already running with a different engine address. Close that instance or choose another app port.')
    elif port_in_use(app_port):
        raise RuntimeError(f'Port {app_port} is in use. Close the older BobHead instance or use --app-port with another port.')

    engine = read_json(comfy_url + '/system_stats')
    if engine and isinstance(engine.get('system'), dict):
        print('  ComfyUI is already running; using it.', flush=True)
    else:
        if port_in_use(engine_port):
            raise RuntimeError(f'Port {engine_port} is occupied but is not responding as ComfyUI. Close that service or choose another engine port.')
        print('  Starting ComfyUI...', flush=True)
        command = [str(python), '-s', 'ComfyUI/main.py', '--windows-standalone-build', '--disable-auto-launch', '--port', str(engine_port)]
        process = start_background(command, portable, logs / 'comfyui.log', **({'env': child_env} if child_env else {}))
        wait_until(comfy_url + '/system_stats', lambda result: isinstance(result.get('system'), dict),
                   process, logs / 'comfyui.log', timeout)

    if not health:
        check = subprocess.run([str(python), '-s', '-c', 'import aiohttp'], capture_output=True)
        if check.returncode:
            if bundled:
                raise RuntimeError('The bundled app dependency is missing. Re-extract the complete bundle.')
            print('  Installing the small BobHead app dependency from PyPI...', flush=True)
            subprocess.run([str(python), '-s', '-m', 'pip', 'install', '-r', str(ROOT / 'requirements-app.txt')], check=True)
        print('  Starting BobHead...', flush=True)
        process = start_background([str(python), '-s', str(ROOT / 'app' / 'server.py'), '--comfy-url', comfy_url, '--port', str(app_port)],
                                   ROOT, logs / 'bobhead.log', **({'env': child_env} if child_env else {}))
        wait_until(app_url + '/api/health', lambda result: result.get('app') == 'bobhead',
                   process, logs / 'bobhead.log', timeout)
    else:
        print('  BobHead is already running; using it.', flush=True)

    (DATA / 'launcher.json').write_text(json.dumps({'portable_path': str(portable)}, indent=2), encoding='utf-8')
    print(f'\n  Ready: {app_url}\n  Startup logs: {logs}\n', flush=True)
    print('  If setup is incomplete, use "Setup & workflow" in the app.', flush=True)
    if open_browser: webbrowser.open(app_url)
    return {'app_url': app_url, 'comfy_url': comfy_url, 'portable_path': str(portable)}


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description='Launch ComfyUI and BobHead together')
    parser.add_argument('--portable', required=True)
    parser.add_argument('--app-port', type=int, default=8787)
    parser.add_argument('--engine-port', type=int, default=8188)
    parser.add_argument('--no-browser', action='store_true')
    parser.add_argument('--timeout', type=int, default=240)
    parser.add_argument('--bundled', action='store_true')
    args = parser.parse_args()
    try:
        launch(args.portable, args.app_port, args.engine_port,
               not args.no_browser and os.environ.get('BOBHEAD_NO_BROWSER') != '1', args.timeout, args.bundled)
    except (ValueError, RuntimeError, OSError, subprocess.CalledProcessError) as exc:
        print(f'\n  Startup needs attention: {exc}', file=sys.stderr, flush=True)
        sys.exit(1)
