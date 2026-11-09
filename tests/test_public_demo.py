import asyncio
from pathlib import Path
import sys
import tempfile
import unittest
from aiohttp import FormData
from aiohttp.test_utils import TestClient, TestServer

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'app'))
from cloud_app import create_cloud_app
from test_cloud import FakeBackend, fake_probe


class PublicDemoTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.settings = dict(backend=FakeBackend(), data_dir=self.temp.name,
            public_origin='https://demo.example', session_secret='s'*40,
            probe_video=fake_probe, poll_interval=.01, max_jobs=1)
        self.client = TestClient(TestServer(create_cloud_app(**self.settings, public_demo=True)))
        await self.client.start_server()
    async def asyncTearDown(self):
        await self.client.close()
        self.temp.cleanup()
    async def visitor(self):
        response = await self.client.get('/', headers={'Host':'demo.example'})
        self.assertEqual(response.status, 200)
        self.assertIn('id="generate"', await response.text())
        cookie = response.cookies['bobhead_session']
        self.assertTrue(cookie['secure'])
        self.assertTrue(cookie['httponly'])
        self.assertEqual(cookie['samesite'], 'Strict')
        self.assertEqual(cookie.value.split('.')[2], 'public')
        return {'Host':'demo.example', 'Origin':'https://demo.example', 'Cookie':'bobhead_session='+cookie.value}
    async def upload(self, headers):
        form = FormData()
        form.add_field('video', b'video', filename='clip.mp4')
        response = await self.client.post('/api/uploads', data=form, headers=headers)
        self.assertEqual(response.status, 200)
        return await response.json()
    async def test_passwordless_entry_still_requires_a_visitor_session(self):
        response = await self.client.get('/api/preflight', headers={'Host':'demo.example'})
        self.assertEqual(response.status, 401)
        headers = await self.visitor()
        response = await self.client.get('/api/preflight', headers=headers)
        self.assertEqual(response.status, 200)
        response = await self.client.get('/login', headers=headers, allow_redirects=False)
        self.assertEqual(response.status, 302)
        self.assertEqual(response.headers['Location'], '/')
    async def test_visitors_cannot_read_each_others_files_or_bypass_global_quota(self):
        first, second = await self.visitor(), await self.visitor()
        self.assertNotEqual(first['Cookie'], second['Cookie'])
        upload = await self.upload(first)
        response = await self.client.post('/api/jobs', json={'upload_id':upload['upload_id'], 'duration':1}, headers=first)
        self.assertEqual(response.status, 202)
        job = await response.json()
        for _ in range(100):
            state = await (await self.client.get('/api/jobs/'+job['id'], headers=first)).json()
            if state['status']=='complete': break
            await asyncio.sleep(.01)
        self.assertEqual(state['status'], 'complete')
        for path in [upload['url'], '/api/jobs/'+job['id'], '/api/jobs/'+job['id']+'/video']:
            self.assertEqual((await self.client.get(path, headers=second)).status, 404)
        response = await self.client.get('/api/jobs/'+job['id']+'/video', headers=first)
        self.assertEqual(await response.read(), b'example-mp4')
        another = await self.upload(second)
        response = await self.client.post('/api/jobs', json={'upload_id':another['upload_id']}, headers=second)
        self.assertEqual(response.status, 400)
        self.assertIn('24 hours', await response.text())
    async def test_restoring_password_mode_rejects_anonymous_cookies(self):
        headers = await self.visitor()
        await self.client.close()
        self.client = TestClient(TestServer(create_cloud_app(**self.settings, public_demo=False,
            password='restored-password-long')))
        await self.client.start_server()
        response = await self.client.get('/api/preflight', headers=headers)
        self.assertEqual(response.status, 401)
        response = await self.client.get('/', headers=headers, allow_redirects=False)
        self.assertEqual(response.headers['Location'], '/login')
    def test_public_mode_still_requires_a_private_session_secret(self):
        settings = {**self.settings, 'session_secret':None}
        with self.assertRaises(ValueError):
            create_cloud_app(**settings, public_demo=True)


if __name__ == '__main__': unittest.main()
