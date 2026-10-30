# Developer setup

The standalone release is the easiest way to reproduce the demonstrated environment. This source checkout can also connect to an existing, working ComfyUI server.

## Use an existing ComfyUI

1. Install the 13 required packs in [NODE_SETUP.md](../NODE_SETUP.md), including the bundled `custom_nodes/comfyui-pose-effects` source. Install their requirements into ComfyUI's Python environment.
2. Obtain the files in [MODELS.md](../MODELS.md) and place them in the indicated ComfyUI model folders. Supporting nodes fetch their own auxiliary models on first use.
3. Open `workflows/BobHead_Comfyui_v06.json` in ComfyUI, select a local input video, and verify the workflow runs. This is the editable GUI workflow.
4. With ComfyUI running at `http://127.0.0.1:8188`, install the small app dependency and start the app:

```powershell
python -m pip install -r requirements-app.txt
python app/server.py --comfy-url http://127.0.0.1:8188 --port 8787
```

Open `http://127.0.0.1:8787`. Use the same Python environment if running the app with ComfyUI's portable Python. Source mode expects you to manage ComfyUI and model installation; the automatic model setup panel targets a bundled runtime.

The recorded runtime uses Python 3.13, ComfyUI 0.43.0, PyTorch 2.14.1+cu130, Transformers 4.57.6, Diffusers 0.35.2, and huggingface-hub 0.36.2. Full package versions and node source records are under `environment/`. These are records of a working environment rather than a guarantee for every CUDA/GPU combination.

## Workflow mapping

`workflows/BobHead_API.json` is the active compiled API graph. `environment/app-workflow.json` records the active workflow configuration. The app replaces the input filename and duration for each job, preserves the first-frame reference path, and connects original audio to the final video output. It does not override the head scale.

The original v06 API source is retained beside the editable GUI workflow. The custom OpenPose effect has a fixed head scale of 1.5 in this submission.

## Validation

```powershell
python -m unittest discover -s tests -v
```

These checks cover app behavior without loading the GPU models. A real v06 generation was also completed with the included talking clip on an RTX PRO 6000 Blackwell (96 GiB VRAM). The output and input audio correlation was approximately 0.995. See `environment/media-validation.json` for the saved media checks.

## Package a standalone runtime

The packaging tool copies a working Windows portable ComfyUI environment and the required node packs, while excluding model weights, user settings, histories, input/output folders, caches, and unrelated node packs.

```powershell
python tools/build_standalone.py --help
python tools/archive_standalone.py --help
python tools/prepare_release.py --help
```

Build from a known working portable install. Review the output inventory and included third-party licenses before distribution. Never package an installation containing credentials or personal footage. Keep model weights out of Git and release runtime assets.

`prepare_release.py` splits the model-free archive into assets below GitHub's per-file release limit and creates a checksum-verifying Windows starter. The starter downloads only the pinned release assets; the app separately offers the model downloads.
