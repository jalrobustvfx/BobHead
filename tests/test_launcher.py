import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import Mock, patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'app'))
import launcher


class LauncherTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        self.portable = self.root / 'folder with spaces' / 'ComfyUI_windows_portable'
        (self.portable / 'python_embeded').mkdir(parents=True)
        (self.portable / 'python_embeded/python.exe').touch()
        (self.portable / 'ComfyUI').mkdir()
        (self.portable / 'ComfyUI/main.py').touch()

    def tearDown(self): self.tmp.cleanup()

    def test_parent_folder_is_resolved(self):
        self.assertEqual(launcher.portable_folder(self.portable.parent), self.portable)

    def test_repeated_launch_reuses_services(self):
        def response(url):
            if url.endswith('/api/health'): return {'app': 'bobhead', 'comfy_url': 'http://127.0.0.1:8188'}
            return {'system': {'comfyui_version': 'test'}}
        with patch.object(launcher, 'DATA', self.root / 'data'), patch.object(launcher, 'read_json', side_effect=response), patch.object(launcher, 'start_background') as start, patch.object(launcher.webbrowser, 'open') as browser:
            result = launcher.launch(self.portable, open_browser=False)
            start.assert_not_called()
            browser.assert_not_called()
            saved = json.loads((self.root / 'data/launcher.json').read_text())
            self.assertEqual(saved['portable_path'], str(self.portable))
            self.assertEqual(result['app_url'], 'http://127.0.0.1:8787')

    def test_starts_both_services_when_missing(self):
        with patch.object(launcher, 'DATA', self.root / 'data'), patch.object(launcher, 'read_json', return_value=None), patch.object(launcher, 'port_in_use', return_value=False), patch.object(launcher, 'wait_until'), patch.object(launcher, 'start_background', return_value=Mock()) as start, patch.object(launcher.subprocess, 'run', return_value=Mock(returncode=0)):
            launcher.launch(self.portable, open_browser=False)
            self.assertEqual(start.call_count, 2)
            engine_command, cwd, log = start.call_args_list[0].args
            self.assertIn('ComfyUI/main.py', engine_command)
            self.assertEqual(cwd, self.portable)
            self.assertEqual(log.name, 'comfyui.log')
            self.assertEqual(start.call_args_list[1].args[2].name, 'bobhead.log')

    def test_unrelated_port_is_not_replaced(self):
        with patch.object(launcher, 'DATA', self.root / 'data'), patch.object(launcher, 'read_json', return_value=None), patch.object(launcher, 'port_in_use', return_value=True), patch.object(launcher, 'start_background') as start:
            with self.assertRaisesRegex(RuntimeError, 'Port 8787 is in use'):
                launcher.launch(self.portable, open_browser=False)
            start.assert_not_called()

    def test_bundled_start_uses_private_offline_cache(self):
        with patch.object(launcher, 'ROOT', self.root), patch.object(launcher, 'DATA', self.root / 'data'), patch.object(launcher, 'read_json', return_value=None), patch.object(launcher, 'port_in_use', return_value=False), patch.object(launcher, 'wait_until'), patch.object(launcher, 'start_background', return_value=Mock()) as start, patch.object(launcher.subprocess, 'run', return_value=Mock(returncode=0)), patch.dict(launcher.os.environ, {'HF_TOKEN': 'test-token', 'PYTHONPATH': 'outside-path'}):
            launcher.launch(self.portable, app_port=8790, engine_port=8190, open_browser=False, bundled=True)
            env = start.call_args_list[0].kwargs['env']
            self.assertNotIn('HF_HUB_OFFLINE', env)
            self.assertEqual(env['PYTHONNOUSERSITE'], '1')
            self.assertEqual(env['HF_HOME'], str(self.root / 'cache/huggingface'))
            self.assertNotIn('HF_TOKEN', env)
            self.assertNotIn('PYTHONPATH', env)


if __name__ == '__main__': unittest.main()
