import hashlib
import json
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest
import zipfile

ROOT = Path(__file__).resolve().parents[1]


@unittest.skipUnless(shutil.which('powershell.exe'), 'Windows PowerShell required')
class AppUpdateTests(unittest.TestCase):
    def run_update(self, payload, bad_hash=False):
        with tempfile.TemporaryDirectory(prefix='BobHead app update ') as temp:
            root = Path(temp)
            app = root / 'installed app'
            cache = root / 'downloads'
            cache.mkdir()
            (app / 'app').mkdir(parents=True)
            (app / 'app/server.py').write_text('old app')
            model = app / 'runtime/ComfyUI_windows_portable/ComfyUI/models/example.safetensors'
            model.parent.mkdir(parents=True)
            model.write_bytes(b'existing model - never overwrite')
            zip_path = cache / 'BobHead-App-v08.zip'
            files = []
            with zipfile.ZipFile(zip_path, 'w') as z:
                for name, data in payload.items():
                    z.writestr(name, data)
                    files.append({'path': name, 'bytes': len(data),
                                  'sha256': '0' * 64 if bad_hash else hashlib.sha256(data).hexdigest()})
            manifest = {'archive': zip_path.name, 'bytes': zip_path.stat().st_size,
                        'sha256': hashlib.sha256(zip_path.read_bytes()).hexdigest(),
                        'workflow': 'BobHead_Comfyui_v08.json', 'version': 'v0.8.0', 'files': files}
            functions = (ROOT / 'tools/start_bobhead.ps1').read_text().split("$manifest = ConvertFrom-Json @'", 1)[0]
            script = root / 'run.ps1'
            script.write_text(functions + "\n$appUpdate = ConvertFrom-Json @'\n" + json.dumps(manifest) +
                              "\n'@\n$cache = '" + str(cache).replace("'", "''") +
                              "'\n$appRoot = '" + str(app).replace("'", "''") +
                              "'\nInstall-BobHeadAppUpdate\nInstall-BobHeadAppUpdate\n")
            result = subprocess.run(['powershell.exe', '-NoProfile', '-ExecutionPolicy', 'Bypass', '-File', str(script)],
                                    capture_output=True, text=True, timeout=30)
            self.assertEqual(model.read_bytes(), b'existing model - never overwrite')
            self.assertFalse((root / 'outside.txt').exists())
            return result, (app / 'app/server.py').read_text(), (app / '.app-update-installed').exists()

    def test_update_preserves_models_and_reuses_verified_install(self):
        result, app, marker = self.run_update({'app/server.py': b'new v08 app',
                                             'workflows/BobHead_Comfyui_v08.json': b'{}'})
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(app, 'new v08 app')
        self.assertTrue(marker)
        self.assertEqual(result.stdout.count('is installed.'), 1)

    def test_bad_file_hash_does_not_overwrite_app(self):
        result, app, marker = self.run_update({'app/server.py': b'bad data'}, bad_hash=True)
        self.assertNotEqual(result.returncode, 0)
        self.assertNotIn('running scripts is disabled', result.stderr)
        self.assertEqual(app, 'old app')
        self.assertFalse(marker)

    def test_parent_traversal_is_rejected(self):
        result, app, marker = self.run_update({'../outside.txt': b'unsafe'})
        self.assertNotEqual(result.returncode, 0)
        self.assertNotIn('running scripts is disabled', result.stderr)
        self.assertEqual(app, 'old app')
        self.assertFalse(marker)

    def test_runtime_files_cannot_be_overwritten(self):
        result, app, marker = self.run_update({'runtime/ComfyUI_windows_portable/ComfyUI/models/example.safetensors': b'unsafe'})
        self.assertNotEqual(result.returncode, 0)
        self.assertNotIn('running scripts is disabled', result.stderr)
        self.assertEqual(app, 'old app')
        self.assertFalse(marker)
