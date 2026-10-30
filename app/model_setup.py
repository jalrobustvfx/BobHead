"""Explicit first-launch model downloads; fixed manifest, local destinations only."""
import asyncio
import hashlib
import json
import shutil
from pathlib import Path

import aiohttp


class ModelSetup:
    def __init__(self, root):
        self.root = Path(root)
        self.comfy = self.root / 'runtime/ComfyUI_windows_portable/ComfyUI'
        self.enabled = (self.comfy / 'main.py').is_file()
        self.models = json.loads((self.root / 'environment/model-downloads.json').read_text())
        self.task = None
        self.current = None
        self.downloaded = 0
        self.error = None

    def target(self, model):
        target = (self.comfy / 'models' / model['path']).resolve()
        if not target.is_relative_to((self.comfy / 'models').resolve()):
            raise ValueError('Invalid model destination.')
        return target

    def installed(self, model):
        target = self.target(model)
        return target.is_file() and target.stat().st_size == model['bytes']

    def status(self):
        rows = []
        for model in self.models:
            partial = self.target(model).with_suffix('.safetensors.part')
            rows.append({**model, 'installed': self.installed(model),
                         'partial_bytes': partial.stat().st_size if partial.is_file() else 0})
        return {'enabled': self.enabled, 'models': rows,
                'complete': all(m['installed'] for m in rows),
                'running': bool(self.task and not self.task.done()),
                'current': self.current, 'downloaded': self.downloaded, 'error': self.error,
                'remaining_bytes': sum(m['bytes'] - min(m['partial_bytes'], m['bytes']) for m in rows if not m['installed'])}

    def start(self):
        if not self.enabled:
            raise ValueError('Downloads are available in the standalone edition.')
        if self.task and not self.task.done():
            return
        self.error = None
        self.task = asyncio.create_task(self.run())

    async def close(self):
        if self.task and not self.task.done():
            self.task.cancel()
            await asyncio.gather(self.task, return_exceptions=True)
        self.current = None

    async def run(self):
        try:
            missing = [m for m in self.models if not self.installed(m)]
            remaining = self.status()['remaining_bytes']
            if shutil.disk_usage(self.root).free < remaining + 5 * 1024**3:
                raise ValueError('There is not enough free disk space. Allow the remaining download size plus 5 GB for working space.')
            timeout = aiohttp.ClientTimeout(total=None, sock_connect=60, sock_read=120)
            async with aiohttp.ClientSession(timeout=timeout, auto_decompress=False) as session:
                for model in missing:
                    self.current = model['path']
                    await self.download(session, model)
        except asyncio.CancelledError:
            raise
        except Exception as exc:
            self.error = str(exc)
        finally:
            self.current = None

    async def download(self, session, model):
        target = self.target(model)
        target.parent.mkdir(parents=True, exist_ok=True)
        partial = target.with_suffix('.safetensors.part')
        offset = partial.stat().st_size if partial.exists() else 0
        if offset > model['bytes']:
            partial.unlink()
            offset = 0
        self.downloaded = offset
        if offset < model['bytes']:
            headers = {'Range': f'bytes={offset}-'} if offset else {}
            async with session.get(model['url'], headers=headers) as response:
                if response.status not in (200, 206):
                    raise ValueError(f"Download failed ({response.status}): {target.name}. Check your connection and the model's source link, then retry.")
                if response.status == 206:
                    expected = f'bytes {offset}-'
                    if not response.headers.get('Content-Range', '').startswith(expected):
                        raise ValueError(f'Unexpected resume response for {target.name}.')
                elif offset:
                    offset = 0  # Server ignored Range; safely restart this file.
                self.downloaded = offset
                with partial.open('ab' if offset else 'wb') as handle:
                    async for chunk in response.content.iter_chunked(1024**2):
                        if self.downloaded + len(chunk) > model['bytes']:
                            raise ValueError(f'Download size changed for {target.name}.')
                        handle.write(chunk)
                        self.downloaded += len(chunk)
        if partial.stat().st_size != model['bytes']:
            raise ValueError(f'Incomplete download: {target.name}. Click Resume to continue.')
        # Hash in a worker so the browser keeps receiving progress during verification.
        def checksum():
            with partial.open('rb') as handle:
                return hashlib.file_digest(handle, 'sha256').hexdigest()
        if await asyncio.to_thread(checksum) != model['sha256']:
            partial.unlink()
            raise ValueError(f'Checksum mismatch: {target.name}. Retry to download a fresh copy.')
        partial.replace(target)
