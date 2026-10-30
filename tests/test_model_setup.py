import hashlib
import json
from pathlib import Path
import sys
import tempfile
import unittest

import aiohttp
from aiohttp import web
from aiohttp.test_utils import TestServer

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'app'))
from model_setup import ModelSetup


class DownloadTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        (self.root / 'environment').mkdir()
        (self.root / 'environment/model-downloads.json').write_text('[]')
        self.setup = ModelSetup(self.root)
        self.content = b'model-test-content' * 100
        self.mode = 'range'
        self.seen_range = None
        async def get(request):
            self.seen_range = request.headers.get('Range')
            if self.mode == 'error': return web.Response(status=403)
            if self.seen_range and self.mode != 'ignore':
                offset = int(self.seen_range.split('=')[1].split('-')[0])
                return web.Response(status=206, body=self.content[offset:], headers={'Content-Range': f'bytes {offset}-{len(self.content)-1}/{len(self.content)}'})
            return web.Response(body=self.content)
        app = web.Application()
        app.router.add_get('/model', get)
        self.server = TestServer(app)
        await self.server.start_server()
        self.model = {'path': 'vae/test.safetensors', 'url': str(self.server.make_url('/model')),
                      'bytes': len(self.content), 'sha256': hashlib.sha256(self.content).hexdigest()}
        self.session = aiohttp.ClientSession()

    async def asyncTearDown(self):
        await self.session.close()
        await self.server.close()
        self.tmp.cleanup()

    def partial(self):
        target = self.setup.target(self.model)
        target.parent.mkdir(parents=True, exist_ok=True)
        return target.with_suffix('.safetensors.part')

    async def test_resume_and_atomic_install(self):
        partial = self.partial()
        partial.write_bytes(self.content[:117])
        await self.setup.download(self.session, self.model)
        self.assertEqual(self.seen_range, 'bytes=117-')
        self.assertEqual(self.setup.target(self.model).read_bytes(), self.content)
        self.assertFalse(partial.exists())

    async def test_server_ignoring_range_restarts(self):
        self.mode = 'ignore'
        self.partial().write_bytes(self.content[:117])
        await self.setup.download(self.session, self.model)
        self.assertEqual(self.setup.target(self.model).read_bytes(), self.content)

    async def test_failure_preserves_partial_for_retry(self):
        self.mode = 'error'
        self.partial().write_bytes(self.content[:117])
        with self.assertRaisesRegex(ValueError, '403'):
            await self.setup.download(self.session, self.model)
        self.assertEqual(self.partial().stat().st_size, 117)
        self.assertFalse(self.setup.target(self.model).exists())

    async def test_bad_hash_is_never_installed(self):
        self.model['sha256'] = '0' * 64
        with self.assertRaisesRegex(ValueError, 'Checksum'):
            await self.setup.download(self.session, self.model)
        self.assertFalse(self.setup.target(self.model).exists())
        self.assertFalse(self.partial().exists())

    async def test_destination_cannot_escape(self):
        with self.assertRaisesRegex(ValueError, 'Invalid'):
            self.setup.target({'path': '../../../elsewhere'})


if __name__ == '__main__': unittest.main()
