# BobHead jury demo on Comfy API

Status: the Render gateway and Comfy v2 Linux deployment are live. A real one-second creator sample completed in 138 seconds, and its MP4, original audio, password login, upload and unauthenticated API rejection were verified. See [cloud validation](environment/cloud-validation.json). Passwordless access is enabled on the hosted jury demo, with separate visitor sessions and a shared ten-generation limit per rolling 24 hours. API keys remain in private server settings. See [public-access validation](environment/public-access-validation.json). The Windows launcher continues to use the local engine.

## Two services

1. Comfy API hosts the GPU engine: the v08 workflow, model files, custom nodes and their dependencies.
2. A small web service hosts BobHead's existing interface and password-protected gateway. It uploads clips to the engine, submits jobs, retrieves MP4 outputs and serves them to the jury. The GPU endpoint alone does not host the BobHead interface.

## Prepare the engine

Use the Comfy Developer Platform Build wizard or official comfy-cli with the working installation. Review every custom node and model source against the local installation. Include `custom_nodes/comfyui-pose-effects` as a node pack, not the entire BobHead repository. Preserve `environment/model-downloads.json` model filenames and folders. Include auxiliary detection, segmentation and pose weights that node packs fetch separately. A workflow import can miss custom classes or choose newer pack versions; importing successfully is not evidence that the graph executes.

Pin the tested dependencies before publishing a release. Test the build on Linux, including Qwen, Wan, LTX, DWPose, video encoding and the custom pose node. Keep the v08 first-frame reference, head effect and original-audio connections. Start with one maximum GPU worker and zero minimum workers. Confirm rates and storage charges in Comfy before deployment. Scale-to-zero stops idle GPU usage; it does not remove model storage charges. Daily app limits are not a currency spending cap.

## Host the interface

Use a Docker web service with `Dockerfile.cloud`, one instance and one Python process. Provide HTTPS and a persistent writable volume mounted at `/data`, The container initializes the disk directory, then drops to UID 10001 before starting the app. In-memory locks are deliberately limited to a single gateway process; do not run multiple replicas.

Use `.env.example` as a configuration checklist for the host's private environment settings. On Render, leave `BOBHEAD_PUBLIC_ORIGIN` unset unless using a custom domain; `RENDER_EXTERNAL_URL` supplies the default origin. `COMFY_BASE_URL` is the HTTPS deployment origin provided by Comfy. `COMFY_API_KEY` stays on this server. Never put it in browser JavaScript, URLs, screenshots or Git. Choose a demo password of at least 12 characters and a random session secret of at least 32 characters. Changing the session secret invalidates existing sessions. On Render, the app uses the platform-provided `RENDER_EXTERNAL_URL` automatically. For another host or a custom domain, set `BOBHEAD_PUBLIC_ORIGIN` to the exact public HTTPS origin, without a path. The reverse proxy must preserve that Host header. Use `/healthz` as the health check.

The service listens on `PORT` (default 8787). The app does not load `.env` automatically. Install `requirements-cloud.txt` and FFmpeg if hosting without Docker, then run `python app/server.py --backend comfy-api` with the same environment settings.

## Verify before sharing

Check the password page, unauthenticated API rejection, a short video upload, one completed GPU job, playback, original audio and download. Reopen the job page after a gateway restart to confirm it reconnects to the same remote job. Confirm the deployment scales down, and check the actual credits consumed. Share the web-service URL and jury password privately. Users do not need their own Comfy account or model downloads.

The gateway permits 64 MB uploads, clips up to five minutes and 3840 pixels per side; generation uses the existing 1–10 second control and 1.2–2.0 head scale. It queues one job at a time, limits requests to the configured rolling 24-hour count (default 10), and requests cancellation after 30 minutes. Cancellation depends on provider acknowledgement and is not a guaranteed cost cutoff. Unknown submission outcomes block new jobs instead of retrying a potentially paid request.

Gateway uploads and results are cleaned approximately every ten minutes once they are 24 hours old. Active or uncertain jobs are retained for recovery. Comfy's asset retention and storage are separate; this gateway does not delete provider assets. Sessions expire after 12 hours, so save results promptly. Each browser session can access only its own uploads and jobs. A shared password protects this small demo, not a public multi-user production service.

## Troubleshooting

- **Cloud unavailable:** check the deployment URL, key permissions and installed cloud requirements in private host settings. The app deliberately returns generic errors rather than provider credentials or signed links.
- **Generation paused / uncertain job:** inspect Comfy Activity and the persisted `/data/jobs/<id>.json` record. Do not submit the same clip again until its outcome is known. Restarting reattaches using the remote ID or metadata, without repeating job submission. If no remote job exists, the owner must resolve the record after checking provider activity; do not delete records while paid work may still be running.
- **No final video:** inspect output node `5187` in Comfy Activity. Keep it as a video output.
- **Long first generation:** a worker may need to start and load models after inactivity. Cold-start time is part of GPU usage.
- **Disk limit:** download needed results and remove completed, expired demo records. Keep active records and the persistent volume across deployments.

References: [Comfy API deployment and billing](https://support.comfy.org/articles/2703236295-comfy-api-deploy-your-comfyui-workflow-as-an-api), [official Python SDK](https://github.com/Comfy-Org/comfy-python-sdk), [current pricing](https://comfy.org/pricing).

## Prepared Render settings

Use the public Git repository `https://github.com/jalrobustvfx/BobHead`, branch `main`, Docker runtime and Dockerfile path `./Dockerfile.cloud`, with the repository root as the build context. Choose one `0.5c-512mb` instance, a 1 GB persistent disk mounted at `/data`, and health check `/healthz`. Disable automatic deploys for this jury demo. No database or separate worker service is needed.

Configure `COMFY_BASE_URL`, `COMFY_API_KEY`, `BOBHEAD_DEMO_PASSWORD` and `BOBHEAD_SESSION_SECRET` privately before deployment. The Docker image sets the backend, host, data directory and default port. `PORT` supplied by Render takes precedence. The hosted jury demo uses `BOBHEAD_MAX_JOBS_PER_DAY=10`, shared across visitors per rolling 24 hours. App limits do not enforce a dollar spending cap.

The Comfy deployment proposal uses the v2 Linux artifact, an RTX PRO 6000 96 GB, zero always-warm workers, a maximum of one worker, a one-minute idle timeout and United States location. These settings were used for the validated deployment, after the owner approved recurring costs and an initial GPU test budget.

## Optional passwordless access

`BOBHEAD_PUBLIC_DEMO=true` opens the studio without a password. This is public access: anyone who discovers the URL can use the shared paid-generation quota. Self-hosted copies remain password-protected by default. The owner explicitly enabled this setting on the hosted jury demo. A session secret is still required. Visitors receive separate signed cookies, so one visitor cannot view another visitor's uploads or results. Original signed-in sessions keep their existing files. Restoring `BOBHEAD_PUBLIC_DEMO=false` rejects anonymous sessions immediately. The rolling global generation limit and single-active-job limit continue to apply; the daily limit is not a dollar spending cap.
