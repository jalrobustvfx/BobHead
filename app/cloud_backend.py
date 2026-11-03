"""Comfy API v2 adapter. Credentials and signed asset links stay server-side."""
import asyncio
import copy
import os
from pathlib import Path
from urllib.parse import urlsplit


class SubmissionUncertain(RuntimeError):
    """A submit may have reached the provider; never automatically submit again."""


class ComfyApiBackend:
    def __init__(self, client=None):
        self.client = client
        self.configured = client is not None
        self._owns_client = client is None

    async def start(self):
        if self.client is not None:
            return
        url = os.environ.get('COMFY_BASE_URL', '').strip().rstrip('/')
        key = os.environ.get('COMFY_API_KEY', '').strip()
        if not url or not key:
            return
        parsed = urlsplit(url)
        if (parsed.scheme != 'https' or not (parsed.hostname or '').endswith('.run.comfy.app')
                or parsed.username or parsed.password or parsed.query or parsed.fragment
                or parsed.path not in ('', '/')):
            raise ValueError('COMFY_BASE_URL must be your HTTPS Comfy deployment URL.')
        try:
            from comfy_sdk import AsyncComfy
        except ImportError:
            raise ValueError('Install requirements-cloud.txt to enable Comfy API mode.') from None
        self.client = AsyncComfy(api_key=key, client_info='bobhead', timeout=60)
        self.configured = True

    async def close(self):
        if self.client is not None and self._owns_client:
            await self.client.aclose()

    async def check(self):
        if not self.configured:
            return False, 'The app owner needs to configure the cloud deployment.'
        try:
            # A metadata read verifies access without submitting a GPU job.
            async for _ in self.client.list_jobs(limit=1):
                break
            return True, None
        except Exception:
            return False, 'The cloud connection could not be verified. Ask the app owner to check it.'

    async def submit(self, graph, path, job_id):
        workflow = self.client.workflows.from_json(copy.deepcopy(graph))
        asset = self.client.assets.from_file(path)
        await asset.commit()  # Upload failures happen before the paid job submit.
        workflow.set_input('5060', 'video', asset)
        try:
            return await self.client.submit(workflow, idempotency_key='bobhead-' + job_id,
                                            metadata={'app': 'bobhead', 'bobhead_job': job_id})
        except Exception as exc:
            # Known rejections did not create a job. Transport and unknown outcomes
            # stay locked and are recovered by metadata, not by repeating POST.
            code = getattr(exc, 'code', '')
            if code in {'unauthorized', 'forbidden', 'invalid_request', 'invalid_workflow',
                        'workflow_invalid', 'validation_error', 'queue_full'}:
                raise ValueError('The cloud rejected the job. Ask the app owner to check the deployment.') from None
            raise SubmissionUncertain('Checking whether the cloud received your job. Please do not submit it again.') from None

    async def recover(self, job_id):
        async for summary in self.client.list_jobs(metadata={'bobhead_job': job_id}, limit=10):
            if summary.metadata.get('bobhead_job') == job_id:
                return await self.client.jobs.get(summary.id)
        return None

    async def get_job(self, remote_id):
        return await self.client.jobs.get(remote_id)

    async def save_output(self, job, path, max_bytes=256 * 1024**2):
        outputs = job.get_outputs('5187')
        output = next((o for o in outputs if o.type == 'video' or o.name.lower().endswith('.mp4')), None)
        if output is None:
            raise ValueError('The cloud finished without a final MP4. Ask the app owner to inspect the run.')
        if output.size_bytes > max_bytes:
            raise ValueError('The result is too large for this demo. Try a shorter clip.')

        class LimitedWriter:
            def __init__(self, handle):
                self.handle, self.total = handle, 0

            def write(self, data):
                if self.total + len(data) > max_bytes:
                    raise ValueError('The result exceeds the demo download limit.')
                written = self.handle.write(data)
                self.total += written
                return written

        path = Path(path)
        try:
            with path.open('wb') as handle:
                writer = LimitedWriter(handle)
                await output.to_stream(writer)
                if writer.total == 0:
                    raise ValueError('The cloud returned an empty video.')
        except BaseException:
            path.unlink(missing_ok=True)
            raise
