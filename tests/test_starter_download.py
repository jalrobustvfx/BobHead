import http.server
import shutil
from pathlib import Path
import subprocess
import tempfile
import threading
import time
import unittest

ROOT = Path(__file__).resolve().parents[1]
PAYLOAD = b'BobHead-download-test\x00' * 50000


class Handler(http.server.BaseHTTPRequestHandler):
    def do_GET(self):
        if self.path == '/missing':
            self.send_error(404)
            return
        self.send_response(200)
        self.send_header('Content-Length', str(len(PAYLOAD)))
        self.end_headers()
        try:
            for pos in range(0, len(PAYLOAD), 32768):
                self.wfile.write(PAYLOAD[pos:pos + 32768])
                self.wfile.flush()
                time.sleep(.025)
        except (BrokenPipeError, ConnectionResetError):
            pass

    def log_message(self, *_):
        pass


@unittest.skipUnless(shutil.which('powershell.exe'), 'Windows PowerShell is required')
class StarterDownloadTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.server = http.server.ThreadingHTTPServer(('127.0.0.1', 0), Handler)
        threading.Thread(target=cls.server.serve_forever, daemon=True).start()

    @classmethod
    def tearDownClass(cls):
        cls.server.shutdown()
        cls.server.server_close()

    def run_download(self, path='/file', expected=None):
        with tempfile.TemporaryDirectory(prefix='BobHead progress test ') as temp:
            temp = Path(temp)
            destination = temp / 'runtime.part.partial'
            template = (ROOT / 'tools/start_bobhead.ps1').read_text()
            functions = template.split("$manifest = ConvertFrom-Json @'", 1)[0]
            expected = len(PAYLOAD) if expected is None else expected
            # A verified cached first part counts toward the overall progress.
            call = "Save-BobHeadDownload '%s' '%s' %d %d %d\n" % (
                f'http://127.0.0.1:{self.server.server_port}{path}',
                str(destination).replace("'", "''"), expected,
                len(PAYLOAD), len(PAYLOAD) + expected)
            script = temp / 'test.ps1'
            script.write_text(functions + call)
            result = subprocess.run(['powershell.exe', '-NoProfile', '-ExecutionPolicy', 'Bypass', '-File', str(script)],
                                    capture_output=True, timeout=30)
            data = destination.read_bytes() if destination.exists() else None
            return result.returncode, result.stdout.decode(errors='replace'), data

    def test_progress_and_cached_part_total(self):
        code, output, data = self.run_download()
        self.assertEqual(code, 0, output)
        self.assertEqual(data, PAYLOAD)
        self.assertGreater(output.count('%'), 2)
        self.assertIn('100.0%', output)
        self.assertIn('MiB/s', output)
        self.assertIn('[##########', output)

    def test_http_failure_is_reported(self):
        code, output, data = self.run_download('/missing')
        self.assertNotEqual(code, 0)
        self.assertIsNone(data)

    def test_oversized_response_is_rejected_and_file_closed(self):
        code, output, data = self.run_download(expected=32)
        self.assertNotEqual(code, 0)
        self.assertEqual(data, b'')


if __name__ == '__main__':
    unittest.main(verbosity=2)
