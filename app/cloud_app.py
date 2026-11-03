"""Password-protected web gateway for BobHead's Comfy API deployment."""
import asyncio
from collections import deque
import hashlib
import hmac
import html
import json
import os
from pathlib import Path
import secrets
import shutil
import time
from urllib.parse import urlsplit

from aiohttp import web
from cloud_backend import ComfyApiBackend, SubmissionUncertain
from server import ROOT, PUBLIC, build_prompt, prompt_target

ACTIVE = {'starting', 'queued', 'running', 'recovering', 'unknown', 'cancelling'}
TERMINAL = {'succeeded', 'failed', 'canceled', 'expired'}
UPLOAD_LIMIT = 64 * 1024**2
STORAGE_LIMIT = 512 * 1024**2
RETENTION = 24 * 3600


async def inspect_video(path):
    probe = shutil.which('ffprobe')
    if not probe:
        raise ValueError('Video validation is unavailable. Ask the app owner to install FFmpeg.')
    # The media parser has no reason to inherit cloud credentials.
    env = {k: os.environ[k] for k in ('PATH', 'SYSTEMROOT', 'WINDIR', 'TEMP', 'TMP') if k in os.environ}
    proc = await asyncio.create_subprocess_exec(probe, '-v', 'error', '-show_entries',
        'stream=codec_type,width,height:format=duration', '-of', 'json', str(path),
        stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.DEVNULL, env=env)
    try:
        output, _ = await asyncio.wait_for(proc.communicate(), 15)
    except asyncio.CancelledError:
        if proc.returncode is None:
            proc.kill()
        await proc.wait()
        raise
    except asyncio.TimeoutError:
        if proc.returncode is None:
            proc.kill()
        await proc.wait()
        raise ValueError('The video could not be inspected. Export a short H.264 MP4.') from None
    try:
        data = json.loads(output)
        video = next(s for s in data['streams'] if s['codec_type'] == 'video')
        duration = float(data['format']['duration'])
        if (proc.returncode or not 0 < duration <= 300 or not 0 < video['width'] <= 3840
                or not 0 < video['height'] <= 3840):
            raise ValueError()
    except (ValueError, KeyError, StopIteration, TypeError):
        raise ValueError('Use a valid video up to five minutes and 3840 pixels per side. A short H.264 MP4 works best.') from None


def create_cloud_app(backend=None, data_dir=None, public_origin=None, password=None,
                     session_secret=None, max_jobs=10, probe_video=inspect_video,
                     poll_interval=2, public_demo=False):
    origin = (public_origin or '').rstrip('/')
    if origin:
        parsed = urlsplit(origin)
        if (parsed.scheme != 'https' or not parsed.hostname or parsed.username or parsed.password
                or parsed.path or parsed.query or parsed.fragment):
            raise ValueError('BOBHEAD_PUBLIC_ORIGIN must be the HTTPS origin of your web app.')
        if not session_secret or len(session_secret) < 32:
            raise ValueError('Public cloud hosting requires a session secret (32+ characters).')
        if not public_demo and (not password or len(password) < 12):
            raise ValueError('Password-protected cloud hosting requires a demo password (12+ characters).')
    if not 1 <= max_jobs <= 100:
        raise ValueError('The demo job limit must be between 1 and 100 per 24 hours.')
    password = password or ''
    secret = (session_secret or secrets.token_hex(32)).encode()
    backend = backend or ComfyApiBackend()
    data_dir = Path(data_dir or ROOT / '.data/cloud')
    data_dir.mkdir(parents=True, exist_ok=True)
    for directory in ['uploads', 'results', 'jobs']:
        (data_dir / directory).mkdir(exist_ok=True)
    template = json.loads((ROOT / 'workflows/BobHead_API.json').read_text())
    workflow = json.loads((ROOT / 'environment/app-workflow.json').read_text())['workflow']
    app = web.Application(client_max_size=UPLOAD_LIMIT)
    jobs, uploads, tasks = {}, {}, set()
    storage_lock, submit_lock = asyncio.Lock(), asyncio.Lock()
    failed_logins = deque(maxlen=100)

    def write_job(job):
        path = data_dir / 'jobs' / (job['id'] + '.json')
        temp = path.with_suffix('.tmp')
        temp.write_text(json.dumps(job))
        temp.replace(path)

    def storage_used():
        return sum(p.stat().st_size for p in data_dir.rglob('*') if p.is_file())

    def owner(request):
        if request.get('public_visitor'):
            return request['public_visitor']
        if not password and not public_demo:
            return 'local-preview'
        value = request.cookies.get('bobhead_session', '')
        try:
            parts = value.split('.')
            if len(parts) == 4:
                # Anonymous cookies stop working immediately if password mode is restored.
                if not public_demo or parts[2] != 'public':
                    return None
            elif len(parts) != 3:
                return None
            identity, expiry, signature = parts[0], parts[1], parts[-1]
            body = '.'.join(parts[:-1]).encode()
            if (len(identity) != 32 or not all(c in '0123456789abcdef' for c in identity)
                    or int(expiry) < time.time() or
                    not hmac.compare_digest(signature, hmac.new(secret, body, hashlib.sha256).hexdigest())):
                return None
            return identity
        except (ValueError, TypeError):
            return None

    @web.middleware
    async def guard(request, handler):
        if request.path == '/healthz' and request.method == 'GET':
            return web.json_response({'status': 'ok'})
        allowed_host = urlsplit(origin).netloc.lower() if origin else None
        if allowed_host:
            valid_host = request.host.lower() == allowed_host
        else:
            valid_host = request.url.host in {'127.0.0.1', 'localhost', '::1'}
        if not valid_host:
            return web.json_response({'error': 'Open BobHead at its configured address.'}, status=403)
        expected_origin = origin or f'{request.scheme}://{request.host}'
        if request.method != 'GET' and request.headers.get('Origin', expected_origin) != expected_origin:
            return web.json_response({'error': 'This request came from another website.'}, status=403)
        new_visitor_cookie = None
        if public_demo and not owner(request) and request.method == 'GET' and request.path == '/':
            # Each visitor gets private uploads/results, even without a password.
            request['public_visitor'] = secrets.token_hex(16)
            body = request['public_visitor'] + '.' + str(int(time.time() + 12 * 3600)) + '.public'
            new_visitor_cookie = body + '.' + hmac.new(secret, body.encode(), hashlib.sha256).hexdigest()
        public = request.path in {'/login', '/static/style.css'}
        if not public and not owner(request):
            if request.path.startswith('/api/'):
                return web.json_response({'error': 'Open BobHead to start your session.' if public_demo else 'Please sign in to continue.'}, status=401)
            raise web.HTTPFound('/' if public_demo else '/login')
        try:
            result = await handler(request)
            if new_visitor_cookie:
                result.set_cookie('bobhead_session', new_visitor_cookie, httponly=True,
                                  secure=bool(origin), samesite='Strict', max_age=12 * 3600)
            result.headers.setdefault('Cache-Control', 'no-store')
            result.headers['X-Content-Type-Options'] = 'nosniff'
            result.headers['Referrer-Policy'] = 'same-origin'
            result.headers['X-Frame-Options'] = 'DENY'
            return result
        except web.HTTPException:
            raise
        except ValueError as exc:
            return web.json_response({'error': str(exc)}, status=400)
        except Exception:
            return web.json_response({'error': 'The cloud service needs attention. Please ask the app owner.'}, status=503)
    app.middlewares.append(guard)

    def add_task(coro):
        task = asyncio.create_task(coro)
        tasks.add(task)
        task.add_done_callback(tasks.discard)

    async def monitor(job):
        remote = None
        try:
            if job.get('remote_id'):
                remote = await backend.get_job(job['remote_id'])
            elif job.get('submit_attempted'):
                job.update(status='recovering', stage='Checking the cloud job; please wait')
            else:
                job['submit_attempted'] = True
                write_job(job)
                graph = build_prompt(template, job['upload_id'] + '.mp4', job['options'], job['id'])
                try:
                    remote = await backend.submit(graph, uploads[job['upload_id']]['path'], job['id'])
                except SubmissionUncertain:
                    job.update(status='recovering', stage='Checking the cloud job; please do not resubmit')
            recovery_deadline = time.monotonic() + 180
            while remote is None:
                try:
                    remote = await backend.recover(job['id'])
                except Exception:
                    pass
                if remote is None and time.monotonic() >= recovery_deadline:
                    job.update(status='unknown', stage='The app owner needs to check this cloud job',
                               error='Your job could not be confirmed. New submissions are paused to avoid duplicate charges.')
                    write_job(job)
                    return
                if remote is None:
                    await asyncio.sleep(max(poll_interval, 2))
            job['remote_id'] = remote.id
            write_job(job)
            deadline = job['created'] + 1800
            while True:
                try:
                    await remote.refresh()
                except Exception:
                    job.update(status='recovering', stage='Reconnecting to your cloud job')
                    write_job(job)
                    await asyncio.sleep(max(poll_interval, 2))
                    continue
                if remote.status in TERMINAL:
                    break
                if job.get('cancel_requested') or time.time() >= deadline:
                    try:
                        await remote.cancel()
                    except Exception:
                        pass
                    job.update(status='cancelling', stage='Waiting for the cloud to stop generation')
                else:
                    running = remote.status in {'running', 'executing'}
                    job.update(status='running' if running else 'queued',
                               stage='Creating your bobhead' if running else 'Starting the cloud engine / waiting for a worker')
                write_job(job)
                await asyncio.sleep(poll_interval)
            if remote.status == 'succeeded':
                job.update(status='running', stage='Saving your finished video')
                write_job(job)
                async with storage_lock:
                    available = STORAGE_LIMIT - storage_used()
                    if available <= 0:
                        raise ValueError('This demo has reached its storage limit. Ask the app owner to clear old files.')
                    await backend.save_output(remote, data_dir / 'results' / (job['id'] + '.mp4'), min(256 * 1024**2, available))
                job.update(status='complete', stage='Your bobhead is ready', completed=time.time())
            elif remote.status == 'canceled':
                job.update(status='cancelled', stage='Generation stopped', completed=time.time())
            else:
                job.update(status='error', stage='Generation needs attention', completed=time.time(),
                           error='The cloud could not finish this video. Ask the app owner to inspect the run before retrying.')
            write_job(job)
        except asyncio.CancelledError:
            # Persisted cloud jobs are reattached on restart, never resubmitted.
            write_job(job)
            raise
        except ValueError as exc:
            job.update(status='error', stage='Generation needs attention', error=str(exc), completed=time.time())
            write_job(job)
        except Exception:
            job.update(status='unknown' if job.get('submit_attempted') else 'error',
                       stage='The app owner needs to check the cloud job',
                       error='The cloud connection needs attention. Please do not submit this video again yet.')
            write_job(job)

    async def collect_old_files():
        while True:
            async with storage_lock:
                cutoff = time.time() - RETENTION
                referenced = {j['upload_id'] for j in jobs.values() if j['status'] in ACTIVE}
                for identity, item in list(uploads.items()):
                    if item['created'] < cutoff and identity not in referenced:
                        item['path'].unlink(missing_ok=True)
                        (data_dir / 'uploads' / (identity + '.json')).unlink(missing_ok=True)
                        uploads.pop(identity, None)
                for identity, job in list(jobs.items()):
                    if job['status'] not in ACTIVE and job.get('completed', job['created']) < cutoff:
                        (data_dir / 'results' / (identity + '.mp4')).unlink(missing_ok=True)
                        (data_dir / 'jobs' / (identity + '.json')).unlink(missing_ok=True)
                        jobs.pop(identity, None)
            await asyncio.sleep(600)

    async def startup(_):
        await backend.start()
        for p in (data_dir / 'uploads').glob('*.json'):
            item = json.loads(p.read_text())
            item['path'] = data_dir / 'uploads' / item['file']
            if item['path'].is_file():
                uploads[p.stem] = item
        for p in (data_dir / 'jobs').glob('*.json'):
            job = json.loads(p.read_text())
            jobs[job['id']] = job
            if job['status'] in ACTIVE and backend.configured:
                add_task(monitor(job))
        add_task(collect_old_files())

    async def cleanup(_):
        for task in list(tasks):
            task.cancel()
        await asyncio.gather(*tasks, return_exceptions=True)
        await backend.close()
    app.on_startup.append(startup)
    app.on_cleanup.append(cleanup)

    async def login(request):
        if public_demo:
            raise web.HTTPFound('/')
        message = ''
        if request.method == 'POST':
            if request.content_length and request.content_length > 4096:
                raise web.HTTPRequestEntityTooLarge(max_size=4096, actual_size=request.content_length)
            now = time.time()
            while failed_logins and failed_logins[0] < now - 60:
                failed_logins.popleft()
            if len(failed_logins) >= 10:
                return web.Response(text='Too many attempts. Try again in a minute.', status=429)
            data = await request.post()
            if hmac.compare_digest(str(data.get('password', '')).encode(), password.encode()):
                body = secrets.token_hex(16) + '.' + str(int(now + 12 * 3600))
                value = body + '.' + hmac.new(secret, body.encode(), hashlib.sha256).hexdigest()
                response = web.HTTPFound('/')
                response.set_cookie('bobhead_session', value, httponly=True, secure=bool(origin),
                                    samesite='Strict', max_age=12 * 3600)
                raise response
            failed_logins.append(now)
            message = 'That password did not match. Try again.'
        return web.Response(content_type='text/html', text='''<!doctype html><html lang="en"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>BobHead — Jury demo</title><style>body{background:#f3ecdf;color:#320913;font:18px Arial;display:grid;place-items:center;min-height:90vh}main{max-width:420px;padding:35px}h1{font-size:64px;line-height:1;margin:24px 0}input,button{box-sizing:border-box;width:100%;padding:16px;border-radius:12px;margin:10px 0;border:1px solid #320913;font:inherit}button{background:#e5f344;font-weight:bold}small{line-height:1.5}p{color:#6c3542}</style><main><strong>bobhead ✳</strong><h1>Big head.<br>Private demo.</h1><small>Enter the jury password to try BobHead. Your clip is processed on Comfy's cloud GPU. This demo keeps local uploads and results for up to 24 hours; cloud-provider retention is separate.</small><form method="post" action="/login"><label for="password">Demo password</label><input id="password" name="password" type="password" autocomplete="current-password" required maxlength="256"><button>Enter the studio ↗</button></form><p>''' + html.escape(message) + '</p></main></html>')

    async def preflight(_):
        ready, issue = await backend.check()
        return web.json_response({'backend': 'comfy-api', 'ready': ready, 'connected': ready,
            'issues': [issue] if issue else [], 'workflow': workflow, 'comfy_version': 'Comfy API v2',
            'device': 'Cloud GPU', 'node_count': len(template), 'max_upload_bytes': UPLOAD_LIMIT,
            'default_prompt': template[prompt_target(template)[0]]['inputs'][prompt_target(template)[1]],
            'head_size': {'min': 1.2, 'max': 2.0, 'default': template['5116']['inputs']['strength']}})

    async def upload(request):
        async with storage_lock:
            reader = await request.multipart()
            field = await reader.next()
            if not field or field.name != 'video' or not field.filename:
                raise ValueError('Choose a video first.')
            name = field.filename.replace('\\', '/').rsplit('/', 1)[-1]
            ext = Path(name).suffix.lower()
            if ext not in {'.mp4', '.mov', '.webm', '.mkv', '.avi'}:
                raise ValueError('Choose an MP4, MOV, WEBM, MKV or AVI video.')
            identity = secrets.token_hex(16)
            path = data_dir / 'uploads' / (identity + ext)
            available, size = STORAGE_LIMIT - storage_used(), 0
            try:
                with path.open('wb') as handle:
                    while chunk := await field.read_chunk():
                        size += len(chunk)
                        if size > UPLOAD_LIMIT or size > available:
                            raise ValueError('This demo accepts clips under 64 MB and has limited storage. Try a shorter clip.')
                        handle.write(chunk)
                if not size:
                    raise ValueError('That video is empty.')
                await probe_video(path)
                item = {'file': path.name, 'name': name, 'owner': owner(request), 'created': time.time()}
                (data_dir / 'uploads' / (identity + '.json')).write_text(json.dumps(item))
                uploads[identity] = {**item, 'path': path}
                return web.json_response({'upload_id': identity, 'name': name, 'size': size,
                                          'url': '/api/uploads/' + identity})
            except BaseException:
                path.unlink(missing_ok=True)
                raise

    async def generate(request):
        data = await request.json()
        async with submit_lock:
            if not backend.configured:
                raise ValueError('The cloud deployment is not configured yet.')
            if any(j['status'] in ACTIVE for j in jobs.values()):
                raise ValueError('A video is already generating or being checked. Please wait for it to finish.')
            if sum(j['created'] > time.time() - 86400 for j in jobs.values()) >= max_jobs:
                raise ValueError('This demo has reached its generation limit for 24 hours. Please contact the app owner.')
            item = uploads.get(data.get('upload_id'))
            if not item or item['owner'] != owner(request):
                raise ValueError('Upload your clip again before generating.')
            identity = secrets.token_hex(16)
            prompt = build_prompt(template, item['file'], data, identity)
            job = {'id': identity, 'upload_id': data['upload_id'], 'owner': owner(request),
                'status': 'starting', 'stage': 'Sending your clip to the cloud', 'created': time.time(),
                'options': {'duration': int(data.get('duration', 5)), 'head_size': prompt['5116']['inputs']['strength'],
                            'prompt': data.get('prompt', '')}}
            jobs[identity] = job
            write_job(job)
            add_task(monitor(job))
            return web.json_response({k: v for k, v in job.items() if k != 'owner'}, status=202)

    def owned_job(request):
        job = jobs.get(request.match_info['job_id'])
        if not job or job['owner'] != owner(request):
            raise web.HTTPNotFound()
        return job

    async def get_job(request):
        job = owned_job(request)
        payload = {k: v for k, v in job.items() if k not in {'owner', 'remote_id', 'submit_attempted'}}
        item = uploads.get(job['upload_id'])
        if item:
            payload.update(input_url='/api/uploads/' + job['upload_id'], input_name=item['name'])
        return web.json_response(payload)

    async def video(request):
        job = owned_job(request)
        path = data_dir / 'results' / (job['id'] + '.mp4')
        if job['status'] != 'complete' or not path.is_file():
            raise web.HTTPNotFound()
        headers = {'Content-Type': 'video/mp4'}
        if 'download' in request.query:
            headers['Content-Disposition'] = 'attachment; filename="bobhead.mp4"'
        return web.FileResponse(path, headers=headers)

    async def original(request):
        item = uploads.get(request.match_info['upload_id'])
        if not item or item['owner'] != owner(request) or not item['path'].is_file():
            raise web.HTTPNotFound()
        return web.FileResponse(item['path'])

    async def cancel(request):
        job = owned_job(request)
        job['cancel_requested'] = True
        write_job(job)
        return web.json_response({'status': 'cancelling'}, status=202)

    async def models(_):
        return web.json_response({'enabled': False, 'complete': True, 'models': [], 'backend': 'comfy-api'})

    async def index(_):
        return web.FileResponse(PUBLIC / 'index.html')

    async def health(_):
        return web.json_response({'app': 'bobhead', 'workflow': Path(workflow).stem.rsplit('_', 1)[-1], 'backend': 'comfy-api'})

    app.router.add_get('/login', login)
    app.router.add_post('/login', login)
    app.router.add_get('/healthz', health)
    app.router.add_get('/', index)
    app.router.add_get('/api/health', health)
    app.router.add_get('/api/preflight', preflight)
    app.router.add_get('/api/models', models)
    app.router.add_post('/api/uploads', upload)
    app.router.add_get('/api/uploads/{upload_id}', original)
    app.router.add_post('/api/jobs', generate)
    app.router.add_get('/api/jobs/{job_id}', get_job)
    app.router.add_get('/api/jobs/{job_id}/video', video)
    app.router.add_post('/api/jobs/{job_id}/cancel', cancel)
    app.router.add_static('/static/', PUBLIC)
    return app
