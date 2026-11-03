import asyncio
import json
from pathlib import Path
import sys
import tempfile
import unittest
from types import SimpleNamespace

from aiohttp import FormData
from aiohttp.test_utils import TestClient, TestServer

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'app'))
from cloud_app import create_cloud_app
from cloud_backend import ComfyApiBackend, SubmissionUncertain


class FakeBackend:
    configured = True
    def __init__(self):
        self.submissions = []
        self.remote = SimpleNamespace(id='remote-private-id', status='succeeded', refresh=self.refresh)
    async def start(self): pass
    async def close(self): pass
    async def check(self): return True, None
    async def refresh(self): pass
    async def submit(self, graph, path, job_id):
        self.submissions.append((graph, path, job_id))
        return self.remote
    async def get_job(self, remote_id): return self.remote
    async def save_output(self, remote, path, max_bytes): path.write_bytes(b'example-mp4')


async def fake_probe(path): pass


class GatewayTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.backend = FakeBackend()
        self.client = TestClient(TestServer(create_cloud_app(backend=self.backend,
            data_dir=self.temp.name, probe_video=fake_probe, poll_interval=.01)))
        await self.client.start_server()
    async def asyncTearDown(self):
        await self.client.close()
        self.temp.cleanup()
    async def upload(self, client=None):
        form = FormData()
        form.add_field('video', b'input-video', filename='before.mp4', content_type='video/mp4')
        response = await (client or self.client).post('/api/uploads', data=form)
        self.assertEqual(response.status, 200, await response.text())
        return await response.json()
    async def test_complete_generation_preserves_graph_and_serves_private_result(self):
        upload = await self.upload()
        response = await self.client.post('/api/jobs', json={'upload_id': upload['upload_id'], 'head_size': 1.9, 'duration': 3})
        self.assertEqual(response.status, 202)
        job = await response.json()
        for _ in range(100):
            response = await self.client.get('/api/jobs/' + job['id'])
            state = await response.json()
            if state['status'] == 'complete': break
            await asyncio.sleep(.01)
        self.assertEqual(state['status'], 'complete')
        self.assertNotIn('remote_id', state)
        self.assertNotIn('owner', state)
        graph = self.backend.submissions[0][0]
        self.assertEqual(graph['5116']['inputs']['strength'], 1.9)
        self.assertEqual(graph['5187']['inputs']['audio'], ['5060', 2])
        self.assertEqual(graph['5124']['inputs']['indexes'], '0')
        response = await self.client.get('/api/jobs/' + job['id'] + '/video?download=1')
        self.assertEqual(await response.read(), b'example-mp4')
        self.assertIn('attachment', response.headers['Content-Disposition'])
        response = await self.client.get('/api/models')
        self.assertFalse((await response.json())['enabled'])
    async def test_unknown_submission_blocks_duplicate_jobs_and_redacts_provider_error(self):
        async def broken(*args): raise RuntimeError('SECRET-API-KEY')
        self.backend.submit = broken
        upload = await self.upload()
        payload = {'upload_id': upload['upload_id']}
        response = await self.client.post('/api/jobs', json=payload)
        job = await response.json()
        await asyncio.sleep(.03)
        state = await (await self.client.get('/api/jobs/' + job['id'])).json()
        self.assertEqual(state['status'], 'unknown')
        self.assertNotIn('SECRET', json.dumps(state))
        response = await self.client.post('/api/jobs', json=payload)
        self.assertEqual(response.status, 400)
    async def test_wrong_origin_and_host_are_rejected(self):
        response = await self.client.post('/api/jobs', json={}, headers={'Origin':'https://attacker.example'})
        self.assertEqual(response.status, 403)
        response = await self.client.get('/api/preflight', headers={'Host':'attacker.example'})
        self.assertEqual(response.status, 403)
    async def test_public_login_cookie_and_private_uploads(self):
        client = TestClient(TestServer(create_cloud_app(backend=FakeBackend(),
            data_dir=Path(self.temp.name) / 'public', probe_video=fake_probe,
            public_origin='https://demo.example', password='jury-password-long', session_secret='s'*40)))
        await client.start_server()
        try:
            headers = {'Host':'demo.example'}
            response = await client.get('/api/preflight', headers=headers)
            self.assertEqual(response.status, 401)
            response = await client.post('/login', data={'password':'jury-password-long'}, headers=headers, allow_redirects=False)
            self.assertEqual(response.status, 302)
            cookie = response.cookies['bobhead_session']
            self.assertTrue(cookie['secure'])
            self.assertTrue(cookie['httponly'])
            self.assertEqual(cookie['samesite'], 'Strict')
            headers['Cookie'] = 'bobhead_session=' + cookie.value
            form = FormData()
            form.add_field('video', b'input', filename='mine.mp4')
            response = await client.post('/api/uploads', data=form, headers=headers)
            upload = await response.json()
            self.assertEqual(response.status, 200)
            response = await client.get(upload['url'], headers={'Host':'demo.example'})
            self.assertEqual(response.status, 401)
            response = await client.get(upload['url'], headers=headers)
            self.assertEqual(await response.read(), b'input')
        finally:
            await client.close()
    async def test_daily_quota(self):
        upload = await self.upload()
        for index in range(10):
            job = {'id':f'{index:032x}', 'status':'complete', 'created':__import__('time').time(), 'upload_id':upload['upload_id'], 'owner':'local-preview'}
            (Path(self.temp.name) / 'jobs' / (job['id']+'.json')).write_text(json.dumps(job))
        # Reload persisted job records into a new gateway.
        await self.client.close()
        self.client = TestClient(TestServer(create_cloud_app(backend=self.backend, data_dir=self.temp.name, probe_video=fake_probe)))
        await self.client.start_server()
        response = await self.client.post('/api/jobs', json={'upload_id':upload['upload_id']})
        self.assertEqual(response.status, 400)
        self.assertIn('24 hours', await response.text())
    async def test_restart_reattaches_existing_remote_job_without_resubmitting(self):
        self.backend.remote.status = 'running'
        upload = await self.upload()
        job = await (await self.client.post('/api/jobs', json={'upload_id':upload['upload_id']})).json()
        await asyncio.sleep(.04)
        self.assertEqual(len(self.backend.submissions), 1)
        await self.client.close()
        self.backend.remote.status = 'succeeded'
        self.client = TestClient(TestServer(create_cloud_app(backend=self.backend, data_dir=self.temp.name,
            probe_video=fake_probe, poll_interval=.01)))
        await self.client.start_server()
        await asyncio.sleep(.04)
        state = await (await self.client.get('/api/jobs/' + job['id'])).json()
        self.assertEqual(state['status'], 'complete')
        self.assertEqual(len(self.backend.submissions), 1)


class AdapterTests(unittest.IsolatedAsyncioTestCase):
    async def test_ambiguous_submit_is_never_retried_and_input_uses_asset(self):
        calls = []
        class Asset:
            async def commit(self): calls.append('upload')
        class Workflow:
            def set_input(self, node, field, value): calls.append((node, field, value))
        async def submit(workflow, **kwargs):
            calls.append(kwargs)
            raise TimeoutError('private-key')
        client = SimpleNamespace(workflows=SimpleNamespace(from_json=lambda graph: Workflow()),
            assets=SimpleNamespace(from_file=lambda path: Asset()), submit=submit)
        with self.assertRaises(SubmissionUncertain):
            await ComfyApiBackend(client).submit({}, Path('input.mp4'), 'job1')
        self.assertEqual(calls[0], 'upload')
        self.assertEqual(calls[1][:2], ('5060','video'))
        self.assertEqual(calls[2]['idempotency_key'], 'bobhead-job1')
        self.assertEqual(len(calls), 3)
    async def test_output_size_bound_removes_partial_file(self):
        class Output:
            type, name, size_bytes = 'video', 'out.mp4', 1
            async def to_stream(self, target):
                target.write(b'123')
                target.write(b'456')
        remote = SimpleNamespace(get_outputs=lambda node: [Output()])
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / 'out.mp4'
            with self.assertRaises(ValueError):
                await ComfyApiBackend(object()).save_output(remote, path, max_bytes=4)
            self.assertFalse(path.exists())


if __name__ == '__main__': unittest.main()
