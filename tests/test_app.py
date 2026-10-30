import asyncio
import json
from pathlib import Path
import sys
import tempfile
import unittest

from aiohttp import FormData, web
from aiohttp.test_utils import TestClient, TestServer

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'app'))
from server import ancestors, build_prompt, create_app, DEFAULT_PROMPT, resolve_models


class WorkflowTests(unittest.TestCase):
    def setUp(self):
        self.graph = json.loads((ROOT / 'workflows/BobHead_API.json').read_text())

    def test_audio_reference_and_pose_guide_remain_connected(self):
        prompt = build_prompt(self.graph, 'uploaded.mp4', {'duration': 3, 'head_size': 2.1}, 'test-job')
        self.assertEqual(prompt['5060']['inputs']['video'], 'uploaded.mp4')
        self.assertEqual(prompt['5060']['inputs']['frame_load_cap'], 89)
        self.assertEqual(prompt['5164']['inputs']['num_frames'], ['5194', 2])
        self.assertEqual(prompt['5194']['inputs']['image'], ['5088', 0])
        self.assertEqual(prompt['5164']['inputs']['width'], ['5194', 0])
        self.assertEqual(prompt['5164']['inputs']['height'], ['5194', 1])
        self.assertEqual(prompt['5144']['inputs']['strength_1'], 1)
        self.assertEqual(prompt['5116']['inputs']['strength'], 1.5)
        self.assertEqual(prompt['5187']['inputs']['audio'], ['5060', 2])
        self.assertIn('5124', prompt)  # First processed frame is used as the reference.
        self.assertEqual(prompt['5124']['inputs']['indexes'], '0')
        self.assertEqual(prompt['5165']['inputs']['positive_prompt'], DEFAULT_PROMPT)
        self.assertNotIn('clown', DEFAULT_PROMPT)
        self.assertEqual(prompt['5136']['inputs']['attention_mode'], 'sdpa')
        outputs = [n for n in prompt.values() if n['class_type'] == 'VHS_VideoCombine']
        self.assertEqual(len(outputs), 1)
        self.assertNotIn('video/nvenc', json.dumps(prompt))

    def test_controls_reject_invalid_values(self):
        for options in [{'duration': 11}, {'duration': 0}]:
            with self.assertRaises(ValueError): build_prompt(self.graph, 'clip.mp4', options, 'test')

    def test_templates_are_not_mutated(self):
        before = json.dumps(self.graph, sort_keys=True)
        build_prompt(self.graph, 'different.mp4', {'head_size': 2}, 'test')
        self.assertEqual(before, json.dumps(self.graph, sort_keys=True))

    def test_model_folders_and_platform_separators(self):
        graph = {'1': {'class_type': 'Loader', 'inputs': {'model': 'Wan2.2\\model .safetensors'}}}
        info = {'Loader': {'input': {'required': {'model': [['other/model.safetensors']]}}}}
        self.assertEqual(resolve_models(graph, info), [])
        self.assertEqual(graph['1']['inputs']['model'], 'other/model.safetensors')
        info['Loader']['input']['required']['model'] = [['one/model.safetensors', 'two/model.safetensors']]
        self.assertTrue(resolve_models(graph, info))  # Ambiguous matches need attention.


class ApplicationTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.finished = False
        self.submitted = None
        self.uploaded = None
        template = json.loads((ROOT / 'workflows/BobHead_API.json').read_text())
        fake = web.Application()
        async def stats(r): return web.json_response({'system': {'comfyui_version': 'test'}, 'devices': []})
        async def info(r): return web.json_response({n['class_type']: {'input': {}} for n in template.values()})
        async def uploaded(r):
            form = await r.multipart()
            part = await form.next()
            self.uploaded = bytes(await part.read())
            return web.json_response({'name': part.filename, 'subfolder': '', 'type': 'input'})
        async def queued(r):
            self.submitted = await r.json()
            self.finished = True
            return web.json_response({'prompt_id': 'test-prompt'})
        async def history(r):
            return web.json_response({'test-prompt': {'status': {'status_str': 'success'}, 'outputs': {'5187': {'gifs': [{'filename': 'test.mp4', 'subfolder': 'BobHead', 'type': 'output'}]}}}} if self.finished else {})
        async def websocket(r):
            ws = web.WebSocketResponse()
            await ws.prepare(r)
            await ws.send_json({'type': 'status', 'data': {}})
            async for _ in ws: pass
            return ws
        async def view(r): return web.Response(body=b'fake-video', content_type='video/mp4')
        fake.router.add_get('/system_stats', stats)
        fake.router.add_get('/object_info', info)
        fake.router.add_post('/upload/image', uploaded)
        fake.router.add_post('/prompt', queued)
        fake.router.add_get('/history/{id}', history)
        fake.router.add_get('/ws', websocket)
        fake.router.add_get('/view', view)
        self.engine = TestServer(fake)
        await self.engine.start_server()
        self.client = TestClient(TestServer(create_app(str(self.engine.make_url('/')).rstrip('/'), self.tmp.name)))
        await self.client.start_server()

    async def asyncTearDown(self):
        await self.client.close()
        await self.engine.close()
        self.tmp.cleanup()

    async def test_upload_generate_status_download(self):
        response = await self.client.get('/api/preflight')
        self.assertTrue((await response.json())['ready'])
        form = FormData()
        form.add_field('video', b'example-video', filename='clip.mp4', content_type='video/mp4')
        response = await self.client.post('/api/uploads', data=form)
        upload = await response.json()
        self.assertEqual(self.uploaded, b'example-video')
        response = await self.client.post('/api/jobs', json={'upload_id': upload['upload_id'], 'head_size': 1.7, 'duration': 2})
        self.assertEqual(response.status, 202)
        job = await response.json()
        self.assertNotIn('head_size', job['options'])
        for _ in range(30):
            status = await (await self.client.get('/api/jobs/' + job['id'])).json()
            if status['status'] in ('complete', 'error'): break
            await asyncio.sleep(.1)
        self.assertEqual(status['status'], 'complete', status)
        self.assertEqual(self.submitted['prompt']['5060']['inputs']['frame_load_cap'], 57)
        response = await self.client.get('/api/jobs/' + job['id'] + '/video?download=1')
        self.assertEqual(await response.read(), b'fake-video')
        self.assertIn('attachment', response.headers['Content-Disposition'])

    async def test_cross_origin_submission_is_rejected(self):
        response = await self.client.post('/api/jobs', json={}, headers={'Origin': 'https://other.example'})
        self.assertEqual(response.status, 403)


if __name__ == '__main__': unittest.main()
