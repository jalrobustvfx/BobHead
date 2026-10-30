"""Exercise the local app against a real engine with a short, user-provided clip."""
import argparse
import asyncio
from pathlib import Path
import time
import aiohttp

async def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('clip', type=Path)
    parser.add_argument('--app', default='http://127.0.0.1:8787')
    parser.add_argument('--duration', type=int, default=1)
    args = parser.parse_args()
    async with aiohttp.ClientSession() as session:
        with args.clip.open('rb') as handle:
            form = aiohttp.FormData()
            form.add_field('video', handle, filename=args.clip.name, content_type='video/mp4')
            async with session.post(args.app + '/api/uploads', data=form) as response:
                upload = await response.json()
                if response.status >= 400: raise RuntimeError(upload)
        async with session.post(args.app + '/api/jobs', json={'upload_id': upload['upload_id'], 'duration': args.duration}) as response:
            job = await response.json()
            if response.status >= 400: raise RuntimeError(job)
        print('Job:', job['id'], flush=True)
        started = time.monotonic()
        while True:
            async with session.get(args.app + '/api/jobs/' + job['id']) as response:
                job = await response.json()
            print(round(time.monotonic()-started), job['status'], job.get('stage'), job.get('step'), flush=True)
            if job['status'] == 'error': raise RuntimeError(job['error'])
            if job['status'] == 'complete':
                async with session.get(args.app + '/api/jobs/' + job['id'] + '/video') as response:
                    content = await response.read()
                    if response.status != 200 or len(content) < 1024: raise RuntimeError('Final video download failed.')
                out = Path(__file__).resolve().parents[1] / '.data' / 'smoke-result.mp4'
                out.write_bytes(content)
                print('PASS: Final MP4 downloaded', len(content), 'bytes', str(out), flush=True)
                return
            await asyncio.sleep(15)

if __name__ == '__main__': asyncio.run(main())
