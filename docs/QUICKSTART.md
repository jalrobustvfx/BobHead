# Download and install BobHead v0.7.0

**[Watch the 1:56 narrated walkthrough](media/download-launch-use.mp4)** — the new interface, one-file installation, model setup and first video.

## 1. Get the starter

Open the [latest Windows release](https://github.com/jalrobustvfx/BobHead/releases/latest). Under **Assets**, download **Start-BobHead.cmd** into a new, empty folder on the drive where you want to install BobHead. The starter downloads the large `.part` files automatically; you only download the starter yourself.

Windows 10/11 and an NVIDIA CUDA GPU with a compatible driver are required. Allow room for the runtime, about **118.9 GB of main models**, supporting downloads and output files. The validated GPU has 96 GiB VRAM; the minimum has not been established.

## 2. Launch

Double-click **Start-BobHead.cmd**. Its live progress bar shows the overall percentage, downloaded MiB and speed. Keep its window open while it downloads, verifies and extracts `BobHead-Standalone-v07`. The app opens in your browser automatically. Python, ComfyUI and the required custom nodes are included; no separate installation or folder picker is needed.

If you previously installed v06, put the new v07 starter in a new folder. The old starter is pinned to the old package. For a fresh launch later, reuse the new starter or open **Launch BobHead.cmd** inside the v07 folder.

## 3. Download models once

Click **Download required models** in the app. All **15 main files** must show **Installed**. The total is approximately **118.9 GB**, including the three Qwen Image 2.1 files. Downloads can pause and resume. Keep Internet access available for supporting models that may download during the first generation. Then close setup.

Model weights are downloaded directly from their publishers; they are not included in the app download. See the [model list](../MODELS.md).

## 4. Choose a source clip

Open [example files](https://github.com/jalrobustvfx/BobHead/tree/main/example%20files) in the repository. Choose a file ending in `_before.mp4`, then click **Download raw file**. The corresponding `_after.mp4` is the supplied result for comparison.

In the app, click the upload panel or drag in your clip. Use footage you have permission to share.

## 5. Choose the effect

Start with a **5-second** clip. Set **Head size** between **1.2× and 2.0×**; the default is **1.7× / Big mood**. The choice applies to the next generation. Optional direction changes the doll reference prompt.

## 6. Generate and save

Click **Make me a bobhead**. Leave the app and engine running. Generation can take several minutes, depending on your GPU and clip. When the result is ready, play it back and click **Download MP4**. Use **Replace** for another clip.

Keep the installation folder together. Completed setup is reused on later launches.

## Troubleshooting

- **The interface looks old:** get the new starter from the latest release and install it in a new folder. The old v06 starter stays pinned to v06.
- **Models are missing:** reopen model setup and wait for all 15 files to show Installed.
- **A runtime download stops:** run the same starter again; verified complete parts are reused.
- **The engine does not start:** check the startup logs under the app's `.data/logs` folder and confirm your NVIDIA driver is compatible.

The exact starter passed a clean-folder installation test on this computer, including checksum verification, extraction and startup of the freshly extracted app and engine. A separate-machine installation and the complete fresh model download have not been rerun.

## Source code

**Code → Download ZIP** contains source only. To use your own ComfyUI, follow the [developer guide](DEVELOPMENT.md). For the self-contained Windows app, use **Start-BobHead.cmd** above.
