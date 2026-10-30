"""Archive a validated standalone folder without personal test inputs or outputs."""
import argparse
import json
from pathlib import Path
import shutil
import time
from zipfile import ZipFile, ZIP_DEFLATED

parser = argparse.ArgumentParser()
parser.add_argument('folder', type=Path)
args = parser.parse_args()
root = args.folder.resolve()
report = root / 'environment/standalone-validation.json'
if not report.exists() or json.loads(report.read_text()).get('status') != 'passed':
    raise RuntimeError('The standalone bundle must pass its runtime test before archiving.')
archive = root.parent / (root.name + '.zip')
partial = archive.with_suffix('.zip.partial')
files = []
for path in root.rglob('*'):
    if not path.is_file(): continue
    relative = path.relative_to(root)
    if '.data' in relative.parts or '__pycache__' in relative.parts: continue
    if relative.parts[0] == 'cache': continue
    if path.suffix.lower() in {'.safetensors', '.gguf', '.ckpt', '.onnx', '.pt', '.pth'} and 'python_embeded' not in relative.parts:
        raise RuntimeError(f'Model weight must not be packaged: {relative}')
    if path.name == 'standalone-copy-checkpoint.json': continue
    if relative.parts[:3] == ('runtime', 'ComfyUI_windows_portable', 'ComfyUI') and len(relative.parts) > 3 and relative.parts[3] in ('input', 'output', 'temp', 'user'):
        continue
    if path.name.endswith('.bobhead-partial'): continue
    files.append(path)
total = sum(path.stat().st_size for path in files)
if shutil.disk_usage(root.parent).free < total + 8 * 1024**3:
    raise RuntimeError('Not enough disk space for an archive plus an 8 GiB reserve. The unpacked bundle remains usable.')
copied = 0
tick = time.monotonic()
with ZipFile(partial, 'w', compression=ZIP_DEFLATED, compresslevel=1, allowZip64=True) as output:
    for path in files:
        relative = path.relative_to(root)
        with path.open('rb') as source, output.open((Path(root.name) / relative).as_posix(), 'w', force_zip64=True) as target:
            while chunk := source.read(16 * 1024**2):
                target.write(chunk)
                copied += len(chunk)
                if time.monotonic() - tick > 15:
                    print(f'Archive: {copied / 1024**3:.1f}/{total / 1024**3:.1f} GiB', flush=True)
                    tick = time.monotonic()
partial.replace(archive)
print(f'Archive ready: {archive} ({archive.stat().st_size / 1024**3:.2f} GiB)', flush=True)
