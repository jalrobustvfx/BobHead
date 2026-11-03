"""Package a small app update that reuses a verified, model-free runtime."""
import argparse
import hashlib
import importlib.util
import json
from pathlib import Path
import zipfile

ROOT = Path(__file__).resolve().parents[1]


def build(destination, base_manifest, base_url, release_url):
    destination.mkdir(parents=True, exist_ok=True)
    sources = {}
    for folder in ['app', 'workflows', 'tests', 'tools']:
        for path in (ROOT / folder).rglob('*'):
            if path.is_file() and '__pycache__' not in path.parts:
                sources[path.relative_to(ROOT).as_posix()] = path
    for relative in ['environment/app-workflow.json', 'environment/model-downloads.json',
                     'environment/v08-validation.json', 'Launch BobHead.cmd', 'README.md',
                     'INSTALL.md', 'MODELS.md', 'NODE_SETUP.md', 'LICENSE', 'requirements-app.txt',
                     'docs/QUICKSTART.md', 'docs/DEVELOPMENT.md']:
        sources[relative] = ROOT / relative
    sources['SOURCE_README.md'] = ROOT / 'README.md'
    archive = destination / 'BobHead-App-v08.zip'
    records = []
    with zipfile.ZipFile(archive, 'w', compression=zipfile.ZIP_DEFLATED, compresslevel=6) as z:
        for relative, path in sorted(sources.items()):
            assert relative.split('/')[0] not in ('runtime', 'cache', '.data')
            data = path.read_bytes()
            z.writestr(relative, data)
            records.append({'path': relative, 'bytes': len(data),
                            'sha256': hashlib.sha256(data).hexdigest()})
    update = {'version': 'v0.8.0', 'workflow': 'BobHead_Comfyui_v08.json',
              'archive': archive.name, 'bytes': archive.stat().st_size,
              'sha256': hashlib.sha256(archive.read_bytes()).hexdigest(), 'files': records}
    (destination / 'app-update-manifest.json').write_text(json.dumps(update, indent=2))
    base = json.loads(base_manifest.read_text())
    template = (ROOT / 'tools/start_bobhead.ps1').read_text()
    script = template.replace('__MANIFEST_JSON__', json.dumps(base, indent=2)).replace(
        '__RELEASE_URL__', base_url).replace('__APP_UPDATE_JSON__', json.dumps(update, indent=2)).replace(
        '__APP_UPDATE_URL__', release_url)
    spec = importlib.util.spec_from_file_location('prepare_release', ROOT / 'tools/prepare_release.py')
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    starter = (module.HEADER + script).replace('\r\n', '\n').replace('\n', '\r\n').encode('utf-8')
    (destination / 'Start-BobHead.cmd').write_bytes(starter)
    checksums = '\n'.join(hashlib.sha256((destination / name).read_bytes()).hexdigest() + '  ' + name
                          for name in [archive.name, 'Start-BobHead.cmd', 'app-update-manifest.json'])
    (destination / 'SHA256SUMS.txt').write_text(checksums + '\n')
    print(json.dumps({'version': update['version'], 'update_bytes': update['bytes'],
                      'application_files': len(records), 'base_runtime': base['folder'],
                      'main_model_files_changed': False, 'starter_bytes': len(starter)}), flush=True)
    return update


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--destination', type=Path, required=True)
    parser.add_argument('--base-manifest', type=Path, required=True)
    parser.add_argument('--base-url', required=True)
    parser.add_argument('--release-url', required=True)
    args = parser.parse_args()
    build(args.destination, args.base_manifest, args.base_url, args.release_url)
