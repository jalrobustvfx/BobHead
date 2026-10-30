"""BobHead local application. Run with the same Python used by ComfyUI."""
import argparse
import asyncio
import copy
import json
import math
import mimetypes
import os
import re
from pathlib import Path
import secrets
import time
import sys
from urllib.parse import urlparse

import aiohttp
from aiohttp import web
sys.path.insert(0, str(Path(__file__).resolve().parent))
from model_setup import ModelSetup

ROOT = Path(__file__).resolve().parents[1]
PUBLIC = ROOT / 'app' / 'static'
OUTPUT_NODE = '5187'
MAX_UPLOAD = 256 * 1024 * 1024
DEFAULT_PROMPT = ('character with a hugely enlarged oversized head,preserve the hair if its part of the identity, '
                  'head nearly as large as the torso, head-to-body ratio 1:1.5, only the head scale is exaggerated. '
                  'Maintaining the facial identity.')
MODEL_KEYS = {'unet_name', 'vae_name', 'clip_name', 'clip_name1', 'clip_name2',
              'lora_name', 'model', 'model_name', 'bbox_detector', 'pose_estimator', 'sam2_model', 'dino_model'}


def resolve_models(graph, info):
    """Allow the same filename in another folder or with platform path separators."""
    issues = []
    def normalized(name):
        return re.sub(r'\s+(?=\.[^.]+$)', '', name.replace('\\', '/').split('/')[-1]).casefold()
    for node in graph.values():
        kind = node['class_type']
        if kind not in info:
            issues.append(f'Missing node: {kind}')
            continue
        inputs = info[kind].get('input', {})
        specs = {**inputs.get('required', {}), **inputs.get('optional', {})}
        for name, value in list(node['inputs'].items()):
            if name not in MODEL_KEYS and not name.startswith('lora_'): continue
            spec = specs.get(name, [])
            if not spec or not isinstance(value, str) or value == 'none': continue
            choices = spec[0] if isinstance(spec[0], list) else (spec[1].get('options') if len(spec) > 1 and isinstance(spec[1], dict) else None)
            if choices is not None and value not in choices:
                matching = [c for c in choices if isinstance(c, str) and normalized(c) == normalized(value)]
                if len(matching) == 1:
                    node['inputs'][name] = matching[0]
                else:
                    issues.append(f'{kind}: select or install {value}')
    return list(dict.fromkeys(issues))


def ancestors(graph, root=OUTPUT_NODE):
    result = {}
    def visit(key):
        if key in result:
            return
        if key not in graph:
            raise ValueError(f'Workflow is missing node {key}.')
        result[key] = copy.deepcopy(graph[key])
        for value in graph[key]['inputs'].values():
            if isinstance(value, list) and len(value) == 2 and str(value[0]) in graph and isinstance(value[1], int):
                visit(str(value[0]))
    visit(root)
    return result


def build_prompt(template, filename, options, job_id):
    duration = int(options.get('duration', 5))
    if not 1 <= duration <= 10:
        raise ValueError('Clip length must be between 1 and 10 seconds.')
    prompt_text = str(options.get('prompt') or DEFAULT_PROMPT).strip()
    if len(prompt_text) > 2000:
        raise ValueError('The description must be 2,000 characters or fewer.')
    prompt = copy.deepcopy(template)
    prompt['5060']['inputs']['video'] = filename
    prompt['5060']['inputs']['skip_first_frames'] = 0
    # LTX video latents use 8n+1 frames. Never ask Wan to animate the raw
    # source count after LTX has rounded it down during encode/decode.
    prompt['5060']['inputs']['frame_load_cap'] = ((duration * 30 - 1) // 8) * 8 + 1
    if prompt.get('5194', {}).get('class_type') == 'GetImageSize':
        # The workflow measures the processed batch. Its slots are width,
        # height, batch_size; GetImageSizeAndCount has a different layout.
        prompt['5164']['inputs']['num_frames'] = ['5194', 2]
    else:
        prompt['bobhead_frame_count'] = {'class_type': 'GetImageSizeAndCount', 'inputs': {'image': ['5088', 0]}}
        prompt['5164']['inputs']['num_frames'] = ['bobhead_frame_count', 3]
    # Keep the author's complete v06 pose settings, including fixed strength 1.5.
    prompt['5165']['inputs']['positive_prompt'] = prompt_text
    prompt[OUTPUT_NODE]['inputs'].update(filename_prefix=f'BobHead/{job_id}', format='video/h264-mp4',
                                        pix_fmt='yuv420p', crf=19, trim_to_audio=True, save_output=True)
    # Keep the workflow's seeds, attention mode, dynamic size and sampling settings.
    # Only the final encoder remains; debug GIFs and NVENC preview outputs are pruned.
    return ancestors(prompt)


def stage_for(node_id, graph):
    kind = graph.get(str(node_id), {}).get('class_type', '')
    if kind == 'VHS_LoadVideo': return 'Reading your clip'
    if kind in ('DWPreprocessor', 'OpenposeRenderNode'): return 'Tracking the movement'
    if kind == 'PE_PoseKeypointEffects': return 'Giving your head a little extra personality'
    if kind in ('SAM2Segment', 'InpaintCropImproved'): return 'Finding the face'
    if kind in ('WanVideoSampler', 'WanVideoDecode'): return 'Bringing your bobhead to life'
    if kind == 'VHS_VideoCombine': return 'Adding your original audio'
    if kind in ('SamplerCustomAdvanced', 'VAEDecodeTiled'): return 'Preparing the scene'
    return 'Preparing the video'


def readable_error(message):
    if 'could not be loaded with cv' in message or 'Could not find decoder' in message:
        return 'ComfyUI cannot decode this video. Export it as an H.264 MP4, then upload it again.'
    return message


def create_app(comfy_url='http://127.0.0.1:8188', data_dir=None):
    app = web.Application(client_max_size=MAX_UPLOAD)
    app['comfy_url'] = comfy_url.rstrip('/')
    app['data_dir'] = Path(data_dir or ROOT / '.data')
    app['data_dir'].mkdir(parents=True, exist_ok=True)
    app['jobs'] = {}
    app['uploads'] = {}
    app['tasks'] = set()
    setup = ModelSetup(ROOT)
    app['template'] = json.loads((ROOT / 'workflows' / 'BobHead_API.json').read_text(encoding='utf-8'))

    @web.middleware
    async def guard(request, handler):
        # The server is a local tool, with no cross-origin write API.
        if request.host.split(':')[0].lower() not in ('127.0.0.1', 'localhost', '[::1]'):
            return web.json_response({'error': 'Open BobHead using localhost.'}, status=403)
        origin = request.headers.get('Origin')
        if request.method != 'GET' and origin and urlparse(origin).netloc != request.host:
            return web.json_response({'error': 'Cross-origin requests are not allowed.'}, status=403)
        try:
            return await handler(request)
        except (ValueError, KeyError) as exc:
            return web.json_response({'error': str(exc)}, status=400)
        except (aiohttp.ClientError, asyncio.TimeoutError) as exc:
            return web.json_response({'error': f'Cannot reach ComfyUI. Start it and check the configured address. {exc}'}, status=503)
    app.middlewares.append(guard)

    async def startup(app):
        app['session'] = aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=90))
    async def cleanup(app):
        await setup.close()
        for task in app['tasks']: task.cancel()
        await asyncio.gather(*app['tasks'], return_exceptions=True)
        await app['session'].close()
    app.on_startup.append(startup)
    app.on_cleanup.append(cleanup)

    async def comfy(path, data=None):
        async with app['session'].request('POST' if data is not None else 'GET', app['comfy_url'] + path, json=data) as response:
            result = await response.json(content_type=None)
            if response.status >= 400:
                raise ValueError(json.dumps(result, ensure_ascii=False))
            return result

    async def preflight(request):
        try:
            stats, info = await asyncio.gather(comfy('/system_stats'), comfy('/object_info'))
        except (aiohttp.ClientError, asyncio.TimeoutError, ValueError) as exc:
            return web.json_response({'ready': False, 'connected': False, 'issues': [f'Start ComfyUI at {app["comfy_url"]}.'], 'details': str(exc)})
        issues = resolve_models(copy.deepcopy(app['template']), info)
        return web.json_response({'ready': not issues, 'connected': True, 'issues': issues,
            'workflow': 'BobHead_Comfyui_v06.json',
            'comfy_version': stats['system'].get('comfyui_version'),
            'device': next((d['name'] for d in stats.get('devices', [])), 'Unknown device'),
            'default_prompt': DEFAULT_PROMPT, 'node_count': len(app['template'])})

    async def upload(request):
        reader = await request.multipart()
        field = await reader.next()
        if not field or field.name != 'video' or not field.filename:
            raise ValueError('Choose a video file first.')
        ext = Path(field.filename).suffix.lower()
        if ext not in {'.mp4', '.mov', '.webm', '.mkv', '.avi'}:
            raise ValueError('Choose an MP4, MOV, WebM, MKV or AVI video.')
        upload_id = secrets.token_hex(16)
        path = app['data_dir'] / f'{upload_id}{ext}'
        size = 0
        try:
            with path.open('wb') as handle:
                while chunk := await field.read_chunk():
                    size += len(chunk)
                    if size > MAX_UPLOAD: raise ValueError('Videos must be smaller than 256 MB.')
                    handle.write(chunk)
            if not size: raise ValueError('That video is empty.')
            form = aiohttp.FormData()
            with path.open('rb') as handle:
                form.add_field('image', handle, filename=path.name, content_type='application/octet-stream')
                form.add_field('type', 'input')
                form.add_field('overwrite', 'false')
                async with app['session'].post(app['comfy_url'] + '/upload/image', data=form) as response:
                    result = await response.json(content_type=None)
                    if response.status >= 400 or 'name' not in result:
                        raise ValueError(f'ComfyUI could not accept the video: {result}')
            name = '/'.join(p for p in [result.get('subfolder', ''), result['name']] if p)
            app['uploads'][upload_id] = {'path': path, 'name': name, 'original_name': Path(field.filename).name}
            (app['data_dir'] / f'upload-{upload_id}.json').write_text(json.dumps({'file': path.name, 'name': name, 'original_name': Path(field.filename).name}), encoding='utf-8')
            return web.json_response({'upload_id': upload_id, 'name': Path(field.filename).name, 'size': size, 'url': f'/api/uploads/{upload_id}'})
        except BaseException:
            path.unlink(missing_ok=True)
            raise

    def save_job(job):
        (app['data_dir'] / f'job-{job["id"]}.json').write_text(json.dumps(job), encoding='utf-8')

    async def monitor(job, prompt):
        prompt_id = None
        try:
            # Connect first so rapid cached executions cannot race the listener.
            async with app['session'].ws_connect(app['comfy_url'] + '/ws?clientId=' + job['id'], heartbeat=30) as ws:
                result = await comfy('/prompt', {'prompt': prompt, 'client_id': job['id']})
                prompt_id = result['prompt_id']
                job.update(prompt_id=prompt_id, status='queued', stage='Waiting for the engine')
                save_job(job)
                while True:
                    try:
                        message = await ws.receive(timeout=2)
                        if message.type == aiohttp.WSMsgType.TEXT:
                            event = json.loads(message.data)
                            data = event.get('data', {})
                            if data.get('prompt_id') in (None, prompt_id):
                                if event['type'] == 'executing' and data.get('node'):
                                    node_id = str(data['node'])
                                    job.update(status='running', stage=stage_for(node_id, prompt), node=node_id, step=None)
                                elif event['type'] == 'progress':
                                    job['step'] = {'value': data.get('value'), 'max': data.get('max')}
                                elif event['type'] == 'execution_error':
                                    raise ValueError(readable_error(f'{data.get("node_type", "Generation")}: {data.get("exception_message", "Execution failed")}'))
                                elif event['type'] == 'execution_interrupted':
                                    job.update(status='cancelled', stage='Generation stopped')
                                    save_job(job)
                                    return
                        elif message.type in (aiohttp.WSMsgType.CLOSED, aiohttp.WSMsgType.ERROR):
                            raise ValueError('The engine disconnected. Check ComfyUI, then try again.')
                    except asyncio.TimeoutError:
                        pass
                    history = await comfy('/history/' + prompt_id)
                    record = history.get(prompt_id)
                    if record:
                        if record.get('status', {}).get('status_str') != 'success':
                            messages = record.get('status', {}).get('messages', [])
                            error = next((data.get('exception_message') for name, data in messages if name == 'execution_error'), 'The engine stopped before the final video was saved.')
                            raise ValueError(readable_error(error))
                        output = record.get('outputs', {}).get(OUTPUT_NODE, {})
                        video = next((item for group in ('gifs', 'videos', 'images') for item in output.get(group, []) if item.get('filename', '').lower().endswith('.mp4')), None)
                        if not video: raise ValueError('The workflow finished without a final MP4.')
                        job.update(status='complete', stage='Your bobhead is ready', output={k: video.get(k, '') for k in ('filename', 'subfolder', 'type')}, completed=time.time())
                        save_job(job)
                        return
                    save_job(job)
        except asyncio.CancelledError:
            raise
        except Exception as exc:
            job.update(status='error', stage='Generation needs attention', error=str(exc))
            save_job(job)

    async def generate(request):
        data = await request.json()
        if any(j['status'] in ('starting', 'queued', 'running') for j in app['jobs'].values()):
            raise ValueError('A BobHead video is already generating. Let it finish first.')
        upload_data = app['uploads'].get(data.get('upload_id'))
        if not upload_data: raise ValueError('Upload the clip again before generating.')
        job_id = secrets.token_hex(16)
        prompt = build_prompt(app['template'], upload_data['name'], data, job_id)
        issues = resolve_models(prompt, await comfy('/object_info'))
        if issues: raise ValueError('Setup needs attention: ' + '; '.join(issues))
        # Leave the user's existing ComfyUI work alone; new jobs join its queue.
        job = {'id': job_id, 'status': 'starting', 'stage': 'Connecting to the engine', 'created': time.time(), 'upload_id': data['upload_id'], 'options': {'duration': int(data.get('duration', 5)), 'prompt': data.get('prompt', '')}}
        app['jobs'][job_id] = job
        save_job(job)
        task = asyncio.create_task(monitor(job, prompt))
        app['tasks'].add(task)
        task.add_done_callback(app['tasks'].discard)
        return web.json_response(job, status=202)

    async def get_job(request):
        job_id = request.match_info['job_id']
        if not all(c in '0123456789abcdef' for c in job_id) or len(job_id) != 32: raise web.HTTPNotFound()
        job = app['jobs'].get(job_id)
        if not job:
            path = app['data_dir'] / f'job-{job_id}.json'
            if not path.exists(): raise web.HTTPNotFound()
            job = json.loads(path.read_text(encoding='utf-8'))
            if job['status'] not in ('complete', 'error', 'cancelled'):
                # Recover completion after a server restart through this job's history.
                record = (await comfy('/history/' + job['prompt_id'])).get(job['prompt_id']) if job.get('prompt_id') else None
                if record and record.get('status', {}).get('status_str') == 'success':
                    videos = record.get('outputs', {}).get(OUTPUT_NODE, {}).get('gifs', [])
                    video = next((v for v in videos if v.get('filename', '').endswith('.mp4')), None)
                    if video: job.update(status='complete', stage='Your bobhead is ready', output={k: video.get(k, '') for k in ('filename', 'subfolder', 'type')})
                if job['status'] != 'complete': job.update(status='error', error='BobHead restarted before monitoring finished. Check this generation in ComfyUI.')
                save_job(job)
            app['jobs'][job_id] = job
        payload = dict(job)
        original_data = app['uploads'].get(job.get('upload_id'))
        if not original_data:
            upload_id = job.get('upload_id', '')
            if len(upload_id) == 32 and all(c in '0123456789abcdef' for c in upload_id):
                meta_path = app['data_dir'] / f'upload-{upload_id}.json'
                if meta_path.exists():
                    meta = json.loads(meta_path.read_text(encoding='utf-8'))
                    path = app['data_dir'] / Path(meta['file']).name
                    if path.is_file():
                        original_data = {'path': path, 'name': meta['name'], 'original_name': meta['original_name']}
                else:
                    path = next((p for p in app['data_dir'].glob(upload_id + '.*') if p.suffix.lower() in {'.mp4', '.mov', '.mkv', '.webm', '.avi'}), None)
                    if path: original_data = {'path': path, 'name': path.name, 'original_name': 'Your clip'}
                if original_data: app['uploads'][upload_id] = original_data
        if original_data:
            payload.update(input_url=f'/api/uploads/{job["upload_id"]}', input_name=original_data['original_name'])
        return web.json_response(payload)

    async def video(request):
        job = app['jobs'].get(request.match_info['job_id'])
        if not job or job['status'] != 'complete': raise web.HTTPNotFound()
        headers = {'Range': request.headers['Range']} if 'Range' in request.headers else {}
        async with app['session'].get(app['comfy_url'] + '/view', params=job['output'], headers=headers) as upstream:
            response_headers = {k: v for k, v in upstream.headers.items() if k.lower() in ('content-type', 'content-length', 'content-range', 'accept-ranges')}
            if 'download' in request.query: response_headers['Content-Disposition'] = 'attachment; filename="bobhead.mp4"'
            response = web.StreamResponse(status=upstream.status, headers=response_headers)
            await response.prepare(request)
            async for chunk in upstream.content.iter_chunked(65536): await response.write(chunk)
            await response.write_eof()
            return response

    async def original(request):
        item = app['uploads'].get(request.match_info['upload_id'])
        if not item: raise web.HTTPNotFound()
        return web.FileResponse(item['path'])

    async def index(request): return web.FileResponse(PUBLIC / 'index.html', headers={'Cache-Control': 'no-store'})
    async def health(request):
        return web.json_response({'app': 'bobhead', 'workflow': 'v06', 'comfy_url': app['comfy_url']})
    async def model_status(request):
        return web.json_response(setup.status())
    async def model_download(request):
        setup.start()
        return web.json_response(setup.status(), status=202)
    async def model_pause(request):
        await setup.close()
        return web.json_response(setup.status())
    app.router.add_get('/', index)
    app.router.add_get('/api/health', health)
    app.router.add_get('/api/preflight', preflight)
    app.router.add_get('/api/models', model_status)
    app.router.add_post('/api/models/download', model_download)
    app.router.add_post('/api/models/pause', model_pause)
    app.router.add_post('/api/uploads', upload)
    app.router.add_get('/api/uploads/{upload_id}', original)
    app.router.add_post('/api/jobs', generate)
    app.router.add_get('/api/jobs/{job_id}', get_job)
    app.router.add_get('/api/jobs/{job_id}/video', video)
    app.router.add_static('/static/', PUBLIC)
    return app


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description='BobHead local video studio')
    parser.add_argument('--comfy-url', default=os.environ.get('COMFY_URL', 'http://127.0.0.1:8188'))
    parser.add_argument('--port', type=int, default=8787)
    args = parser.parse_args()
    print(f'BobHead: http://127.0.0.1:{args.port}  |  ComfyUI: {args.comfy_url}', flush=True)
    web.run_app(create_app(args.comfy_url), host='127.0.0.1', port=args.port)
