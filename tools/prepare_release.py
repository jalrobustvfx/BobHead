"""Split a model-free standalone ZIP and generate a verified Windows starter."""
import argparse
import hashlib
import json
from pathlib import Path
import zipfile

HEADER = r'''@echo off
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
'''


def prepare(archive, destination, repository, tag, part_bytes=1792 * 1024**2):
    archive = archive.resolve()
    destination = destination.resolve()
    destination.mkdir(parents=True, exist_ok=True)
    if not repository.startswith('https://github.com/'):
        raise ValueError('Expected an HTTPS GitHub repository URL')
    if not 0 < part_bytes < 2 * 1024**3:
        raise ValueError('Each part must be below 2 GiB')
    with zipfile.ZipFile(archive) as z:
        roots = {Path(n).parts[0] for n in z.namelist() if n}
        if len(roots) != 1:
            raise ValueError('Archive must contain one top-level app folder')
        for entry in z.infolist():
            if '/python_embeded/' not in entry.filename and Path(entry.filename).suffix.lower() in {'.safetensors', '.ckpt', '.gguf', '.onnx', '.pt', '.pth'}:
                raise ValueError(f'Model weight unexpectedly included: {entry.filename}')
        folder = roots.pop()
    digest = hashlib.sha256()
    parts = []
    with archive.open('rb') as reader:
        index = 1
        while True:
            first = reader.read(min(16 * 1024**2, part_bytes))
            if not first:
                break
            name = f'{archive.name}.part{index:02d}'
            part_hash = hashlib.sha256()
            count = 0
            with (destination / name).open('wb') as writer:
                chunk = first
                while chunk:
                    writer.write(chunk)
                    digest.update(chunk)
                    part_hash.update(chunk)
                    count += len(chunk)
                    if count == part_bytes:
                        break
                    chunk = reader.read(min(16 * 1024**2, part_bytes - count))
            parts.append({'name': name, 'bytes': count, 'sha256': part_hash.hexdigest()})
            print(f'Prepared {name}: {count:,} bytes', flush=True)
            index += 1
    manifest = {'archive': archive.name, 'folder': folder, 'bytes': archive.stat().st_size,
                'sha256': digest.hexdigest(), 'models_included': False, 'parts': parts}
    manifest_text = json.dumps(manifest, indent=2)
    (destination / 'runtime-manifest.json').write_text(manifest_text + '\n', encoding='utf-8')
    checksums = '\n'.join(f"{p['sha256']}  {p['name']}" for p in parts)
    checksums += f"\n{manifest['sha256']}  {archive.name}\n"
    (destination / 'SHA256SUMS.txt').write_text(checksums, encoding='ascii')
    template = Path(__file__).with_name('start_bobhead.ps1').read_text(encoding='utf-8')
    script = template.replace('__MANIFEST_JSON__', manifest_text).replace(
        '__RELEASE_URL__', repository.rstrip('/') + '/releases/download/' + tag)
    (destination / 'Start-BobHead.cmd').write_bytes((HEADER + script).replace('\r\n', '\n').replace('\n', '\r\n').encode('utf-8'))
    print(json.dumps(manifest, indent=2), flush=True)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--archive', type=Path, required=True)
    parser.add_argument('--destination', type=Path, required=True)
    parser.add_argument('--repository', required=True)
    parser.add_argument('--tag', default='v0.6.0')
    args = parser.parse_args()
    prepare(args.archive, args.destination, args.repository, args.tag)
