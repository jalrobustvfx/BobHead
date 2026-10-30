"""Assemble a private Windows runtime copy without model weights."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import shutil
import time
import threading
from concurrent.futures import ThreadPoolExecutor, as_completed

APP = Path(__file__).resolve().parents[1]
WEIGHTS = {'.safetensors', '.pt', '.pth', '.onnx', '.ckpt', '.gguf', '.bin'}
SKIP_DIRS = {'.git', '__pycache__', '.data', '.venv', 'node_modules'}


def inventory(portable, shared_models=None, hf_cache=None):
    items = {}
    runtime = Path('runtime/ComfyUI_windows_portable')
    comfy = portable / 'ComfyUI'
    def add(source, target, kind):
        source = Path(source)
        if not source.is_file(): raise FileNotFoundError(source)
        items[Path(target).as_posix()] = {'source': str(source), 'target': Path(target).as_posix(), 'bytes': source.stat().st_size, 'kind': kind}
    def tree(source, target, kind, skip=(), root_skip=(), exclude_weights=False):
        for folder, directories, files in os.walk(source, followlinks=False):
            relative = Path(folder).relative_to(source)
            directories[:] = [n for n in directories if n not in SKIP_DIRS and n not in skip and not (relative == Path('.') and n in root_skip)]
            for name in files:
                path = Path(folder) / name
                if path.suffix == '.pyc' or (exclude_weights and path.suffix.lower() in WEIGHTS): continue
                if path.is_file(): add(path, Path(target) / relative / name, kind)

    tree(APP, Path('.'), 'app', skip=('runtime',))
    tree(portable / 'python_embeded', runtime / 'python_embeded', 'python')
    tree(comfy, runtime / 'ComfyUI', 'comfy', root_skip=('models', 'custom_nodes', 'input', 'output', 'temp', 'user', 'logs'))
    for name in ('ffmpeg.exe', 'ffprobe.exe'):
        if (portable / name).is_file(): add(portable / name, runtime / name, 'ffmpeg')
    # No user settings, histories, credentials or unrelated node packs.
    required = json.loads((APP / 'environment/required-node-packs.json').read_text())
    for pack in required:
        source = comfy / 'custom_nodes' / pack['folder']
        tree(source, runtime / 'ComfyUI/custom_nodes' / pack['folder'], 'custom-node',
             skip=('ckpts', 'cache', '.cache'), exclude_weights=True)

    # v06 ships code/runtime only. All checkpoints are first-launch downloads.
    return sorted(items.values(), key=lambda item: item['target'])



def assemble(items, destination):
    destination = destination.resolve()
    destination.mkdir(parents=True, exist_ok=True)
    marker = destination / 'standalone-build.json'
    if any(destination.iterdir()) and not marker.exists():
        raise RuntimeError('Destination must be empty or an earlier standalone build from this tool.')
    total = sum(item['bytes'] for item in items)
    free = shutil.disk_usage(destination).free
    checkpoint_path = destination / 'standalone-copy-checkpoint.json'
    completed = json.loads(checkpoint_path.read_text()) if checkpoint_path.exists() else {}
    remaining = sum(i['bytes'] for i in items if i['target'] not in completed)
    if remaining + 8 * 1024**3 > free: raise RuntimeError('Not enough disk space, including an 8 GiB reserve.')
    marker.write_text(json.dumps({'status': 'copying', 'total_bytes': total, 'files': len(items)}, indent=2))
    copied = 0
    tick = time.monotonic()
    lock = threading.Lock()
    def copy_one(item):
        nonlocal copied, tick
        source = Path(item['source'])
        relative_target = Path(item['target'])
        if relative_target.is_absolute() or relative_target.drive or '..' in relative_target.parts:
            raise RuntimeError(f'Target escapes bundle: {relative_target}')
        target = destination / relative_target
        if item['target'] in completed and target.is_file() and target.stat().st_size == item['bytes']:
            with lock: copied += item['bytes']
            return item['target'], completed[item['target']]
        if target.is_file() and target.stat().st_size == item['bytes']:
            with source.open('rb') as handle: source_hash = hashlib.file_digest(handle, 'sha256').hexdigest()
            with target.open('rb') as handle: target_hash = hashlib.file_digest(handle, 'sha256').hexdigest()
            if source_hash == target_hash:
                with lock: copied += item['bytes']
                return item['target'], {'bytes': item['bytes'], 'sha256': source_hash, 'kind': item['kind']}
        target.parent.mkdir(parents=True, exist_ok=True)
        partial = target.with_name(target.name + '.bobhead-partial')
        digest = hashlib.sha256()
        with source.open('rb') as reader, partial.open('wb') as writer:
            while chunk := reader.read(16 * 1024**2):
                writer.write(chunk)
                digest.update(chunk)
                with lock:
                    copied += len(chunk)
                    if time.monotonic() - tick > 15:
                        print(f'{copied / 1024**3:.1f}/{total / 1024**3:.1f} GiB | {target.name}', flush=True)
                        tick = time.monotonic()
        if partial.stat().st_size != item['bytes']: raise RuntimeError(f'Size mismatch: {target}')
        partial.replace(target)
        return item['target'], {'bytes': item['bytes'], 'sha256': digest.hexdigest(), 'kind': item['kind']}
    small = [i for i in items if i['bytes'] < 64 * 1024**2]
    large = [i for i in items if i['bytes'] >= 64 * 1024**2]
    with ThreadPoolExecutor(max_workers=16) as pool:
        futures = [pool.submit(copy_one, item) for item in small]
        for index, future in enumerate(as_completed(futures)):
            key, record = future.result()
            completed[key] = record
            if index % 500 == 0: checkpoint_path.write_text(json.dumps(completed))
    for item in large:
        key, record = copy_one(item)
        completed[key] = record
        checkpoint_path.write_text(json.dumps(completed))
    checkpoint_path.write_text(json.dumps(completed, indent=2))
    # The default local model categories now contain every required checkpoint.
    (destination / 'runtime/ComfyUI_windows_portable/ComfyUI/extra_model_paths.yaml').write_text('{}\n')
    for name in ('input', 'output', 'temp', 'user'):
        (destination / 'runtime/ComfyUI_windows_portable/ComfyUI' / name).mkdir(exist_ok=True)
    (destination / 'Launch BobHead.cmd').write_text('@echo off\nsetlocal\ntitle BobHead Standalone\necho Starting BobHead and its bundled engine...\n"%~dp0runtime\\ComfyUI_windows_portable\\python_embeded\\python.exe" -s "%~dp0app\\launcher.py" --portable "%~dp0runtime\\ComfyUI_windows_portable" --app-port 8790 --engine-port 8190 --bundled\nif errorlevel 1 pause\n', encoding='utf-8')
    shutil.copy2(destination / 'README.md', destination / 'SOURCE_README.md')
    shutil.copy2(APP / 'README.md', destination / 'README.md')
    marker.write_text(json.dumps({'status': 'copied', 'total_bytes': total, 'files': len(items), 'models_included': False, 'startup_test': 'pending'}, indent=2))
    print(f'Copied {total / 1024**3:.2f} GiB to {destination}', flush=True)


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--portable', type=Path, required=True)
    parser.add_argument('--models', type=Path, help='Legacy option; models are not packaged')
    parser.add_argument('--hf-cache', type=Path, help='Legacy option; caches are not packaged')
    parser.add_argument('--destination', type=Path, required=True)
    parser.add_argument('--copy', action='store_true')
    args = parser.parse_args()
    items = inventory(args.portable, args.models, args.hf_cache)
    plan = APP / '.data/standalone-plan.json'
    plan.parent.mkdir(exist_ok=True)
    plan.write_text(json.dumps(items, indent=2))
    kinds = {kind: round(sum(i['bytes'] for i in items if i['kind'] == kind) / 1024**3, 3) for kind in sorted({i['kind'] for i in items})}
    print(json.dumps({'files': len(items), 'GiB_by_kind': kinds, 'total_GiB': sum(i['bytes'] for i in items)/1024**3, 'plan': str(plan)}, indent=2), flush=True)
    if args.copy: assemble(items, args.destination)
