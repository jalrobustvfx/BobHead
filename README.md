# BobHead

[![BobHead interface](docs/screenshots/interface-v07-full.jpg)](docs/screenshots/interface-v07-full.jpg)

Turn a short video into a playful doll-style BobHead, preserving the performance and original dialogue.

**[Download Start-BobHead.cmd](https://github.com/jalrobustvfx/BobHead/releases/latest/download/Start-BobHead.cmd)** · **[Alternative: Google Drive runtime ZIP (3.41 GB)](https://drive.google.com/file/d/1AybkXAA47niFAuONsnjIE33zdB76Z3DU/view?usp=sharing)** · **[Installation guide](INSTALL.md)** · **[Before/after example files](example%20files)**

## Download and launch

1. Download **Start-BobHead.cmd** from the [latest Windows release](https://github.com/jalrobustvfx/BobHead/releases/latest) into a new, empty folder.
2. Double-click it. It downloads, verifies and extracts the bundled app, Python, ComfyUI and custom nodes, then opens the new interface. No separate ComfyUI installation is needed.
3. On first launch, click **Download required models**. The **15 main files total about 118.9 GB**, plus supporting downloads and working space. Downloads can pause and resume. Model weights are downloaded separately from their publishers.
4. Upload a clip, choose a short duration and a head size from **1.2× to 2.0×** (default **1.7×**), then click **Make me a bobhead**. Preview and download the result.

Keep the folder together and use the same starter for future launches. Completed setup is reused. If you have v07 installed, you can upgrade in place using the instructions below. Use a new installation folder when coming from v06. New installations use the model-free runtime base in `BobHead-Standalone-v07` and automatically apply the v08 app update.

**[Watch the narrated download, launch and use guide (1:56)](docs/media/download-launch-use.mp4)** — the current interface and one-file Windows installation (controls unchanged in v08), with Higgsfield's Archie voiceover.

[![BobHead v07 installation and usage walkthrough](docs/screenshots/v07-voiced-guide.jpg)](docs/media/download-launch-use.mp4)

## Alternative download: Google Drive

If the starter download fails or stalls, **[download the v07 runtime ZIP from Google Drive](https://drive.google.com/file/d/1AybkXAA47niFAuONsnjIE33zdB76Z3DU/view?usp=sharing)** (about **3.41 GB**).

1. Download `BobHead-Standalone-v07.zip` and choose **Extract All**.
2. Download [BobHead-App-v08.zip](https://github.com/jalrobustvfx/BobHead/releases/download/v0.8.0/BobHead-App-v08.zip), then extract its contents inside `BobHead-Standalone-v07`, replacing existing application files.
3. Double-click **Launch BobHead.cmd** in that folder. Python, ComfyUI and custom nodes are included.
4. In the app, click **Download required models** and wait for all 15 main files to show **Installed**. The ZIP excludes model weights, so model downloads still require Internet access.

Keep the extracted folder together and use **Launch BobHead.cmd** for future launches.

## What's new in v08

- Optimized image preparation with a dedicated 480×813 resize stage.
- Pose detection resolution reduced from 1024 to 512.
- VRAM cache cleanup and model unloading between image stages.
- Updated block-swap routing and the authored v08 sampling settings.
- The same head-size slider (1.2×–2.0×) and the same 15 main model files. **No new model downloads are required when upgrading from v07.**

**Already installed v07?** Download the new **Start-BobHead.cmd** into the parent folder containing `BobHead-Standalone-v07`, then run it. An installation previously completed through the starter reuses its runtime and models and applies a small v08 app update. The runtime folder keeps its existing name to preserve model paths. v08 launches on app port **8800** and engine port **8200**, separate from older versions.

For a manually extracted installation (including Google Drive), download **[BobHead-App-v08.zip](https://github.com/jalrobustvfx/BobHead/releases/download/v0.8.0/BobHead-App-v08.zip)**. Extract its contents **inside the existing app folder**, replacing application files, then run **Launch BobHead.cmd**. Existing models and user data are kept. [Update instructions](workflows/README-v08.md).

## See it in action

Original footage on the left; BobHead on the right. These silent previews loop automatically. Download each pair to try the source clip or inspect the full result.

### Props: the guitar stays in the performance

![Props: the guitar stays in the performance — before and after](docs/media/a-before-after.gif)

[Before MP4](example%20files/a_before.mp4) · [After MP4](example%20files/a_after.mp4)

### Body movement: keep the moves

![Body movement: keep the moves — before and after](docs/media/b-before-after.gif)

[Before MP4](example%20files/b_before.mp4) · [After MP4](example%20files/b_after.mp4)

### Facial expressions: big feelings

![Facial expressions: big feelings — before and after](docs/media/e-before-after.gif)

[Before MP4](example%20files/e_before.mp4) · [After MP4](example%20files/e_after.mp4)

### Accessories: hat and glasses

![Accessories: hat and glasses — before and after](docs/media/d-before-after.gif)

[Before MP4](example%20files/d_before.mp4) · [After MP4](example%20files/d_after.mp4)

### The BobHead transformation

![The BobHead transformation — before and after](docs/media/c-before-after.gif)

[Before MP4](example%20files/c_before.mp4) · [After MP4](example%20files/c_after.mp4)

## Troubleshooting

**Startup error about an older BobHead or a busy port?** Follow the [port-conflict troubleshooting steps](INSTALL.md#an-older-bobhead-v06-is-running-on-this-port).

## Requirements

Windows 10/11, an NVIDIA CUDA GPU with a compatible driver, reliable Internet for setup, and space for the runtime, 118.9 GB main models, supporting models, temporary files and outputs. The demonstrated setup uses an **RTX PRO 6000 Blackwell with 96 GiB VRAM**. Minimum VRAM is not established. A separate-machine installation and the complete fresh model download have not been validated.

GitHub's **Source code.zip** contains project source; the release starter installs the complete runtime. See the [source setup guide](docs/DEVELOPMENT.md) if you prefer to connect an existing ComfyUI installation.

## How it works

The first processed frame and enlarged OpenPose guide create the doll-style reference. The custom pose effect controls head size, while the animation follows the source movement. The final MP4 carries the original source dialogue. Optional direction edits the reference-image prompt.

## Optional cloud hosting

An optional Comfy API gateway keeps the same interface and runs generation on a remote GPU. The private jury deployment passed a real video generation, original-audio and download check. See [cloud hosting setup and limits](CLOUD-HOSTING.md) and [validation results](environment/cloud-validation.json). Access credentials are shared privately.

## Source and reproducibility

- [Editable v08 workflow](workflows/BobHead_Comfyui_v08.json) and [compiled app graph](workflows/BobHead_API.json)
- [Custom pose-effect node](custom_nodes/comfyui-pose-effects)
- [Required nodes](NODE_SETUP.md) and [model downloads](MODELS.md)
- [Developer setup and packaging](docs/DEVELOPMENT.md)
- [Recorded runtime versions](environment/installed-packages.txt) and [v07 generation checks](environment/v08-validation.json)

The app passes 41 automated checks covering graph compilation, prompt routing, head-size bounds, downloads and launch behavior. The exact release starter also passed a clean-folder test: checksum verification, archive joining/extraction, and the extracted Python, engine and app startup. The shared runtime with the v08 app exposes every required node type. A real v07 generation was checked for video decoding and source/result audio. Model weights are not packaged.

Built for the [ComfyUI open-source competition](https://comfy.org/open-source-higgsfield/).

## Credits and licensing

Application code and the custom pose effect use the [MIT license](LICENSE). ComfyUI, third-party nodes, Python packages and models retain their own licenses; see [node sources](NODE_SETUP.md) and [model sources](MODELS.md). Example footage is separate from the software license; see [media notes](docs/media/README.md). Use footage you have permission to process and share.
