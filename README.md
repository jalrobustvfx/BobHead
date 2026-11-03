# BobHead

[![Complete BobHead app interface, including header, video panels, controls, and footer](docs/screenshots/interface-v07-full.jpg)](docs/screenshots/interface-v07-full.jpg)

Turn a short video of someone talking into a bobhead video, with an enlarged head, the original head movement, and the original dialogue.

**Latest: [v07 workflow](workflows/BobHead_Comfyui_v07.json) · [Run the current app from source](docs/DEVELOPMENT.md) · [v07 setup guide](workflows/README-v07.md)**

## V07 app update

The current source app uses **v07**, including a Qwen Image 2.1 stage that creates a doll-style reference from the first processed frame and the enlarged OpenPose guide. Head size is adjustable from **1.2× to 2.0×**, defaulting to **1.7×**. Optional direction edits the doll reference prompt; the animation prompt stays as authored.

Model setup now lists **15 files, approximately 118.9 GB** total. The three new Qwen files add approximately **17.3 GB**. See [model downloads](MODELS.md).

The interface shown above and the source app are v07. The downloadable Windows **v0.6.0 release** and the older installation walkthrough describe v06. To use the latest interface and workflow, follow the [v07 source setup](docs/DEVELOPMENT.md).

## See it in action

Original footage on the left; BobHead on the right. These silent previews loop automatically. Download each pair to try the source clip or inspect the full result.

### Props: the guitar stays in the performance

![Props: the guitar stays in the performance — before and after](docs/media/a-before-after.gif)

[Before MP4](exmaples%20files/a_before.mp4) · [After MP4](exmaples%20files/a_after.mp4)

### Body movement: keep the moves

![Body movement: keep the moves — before and after](docs/media/b-before-after.gif)

[Before MP4](exmaples%20files/b_before.mp4) · [After MP4](exmaples%20files/b_after.mp4)

### Facial expressions: big feelings

![Facial expressions: big feelings — before and after](docs/media/e-before-after.gif)

[Before MP4](exmaples%20files/e_before.mp4) · [After MP4](exmaples%20files/e_after.mp4)

### Accessories: hat and glasses

![Accessories: hat and glasses — before and after](docs/media/d-before-after.gif)

[Before MP4](exmaples%20files/d_before.mp4) · [After MP4](exmaples%20files/d_after.mp4)

### The BobHead transformation

![The BobHead transformation — before and after](docs/media/c-before-after.gif)

[Before MP4](exmaples%20files/c_before.mp4) · [After MP4](exmaples%20files/c_after.mp4)

**[Download the Windows app](https://github.com/jalrobustvfx/BobHead/releases/latest)** · **[Download before and after example files](exmaples%20files)** · **[Watch the tutorial on YouTube](https://youtu.be/cc84p_qUgdo)**

The tutorial covers downloading BobHead, model setup, uploading your clip, generating, and saving the result. [Download the walkthrough MP4](docs/media/how-to-use-me.mp4).

Built for the [ComfyUI open-source competition](https://comfy.org/open-source-higgsfield/). This repository includes the app, v07 workflow, custom pose effect, setup instructions, and actual input/output examples.

## Run the latest app (v07)

Download this repository using **Code → Download ZIP**, or clone it. Follow the [developer setup](docs/DEVELOPMENT.md) to connect the app to a working ComfyUI installation with the [v07 models](MODELS.md) and [required nodes](NODE_SETUP.md). The current app includes the redesigned interface and the **1.2×–2.0× head-size slider**.

## Packaged Windows app (v0.6.0)

The starter instructions below install the older v06 package.

**[Example files: before.mp4 and after.mp4](exmaples%20files)** — download the source footage to test BobHead and compare it with the enlarged-head result.

**Jury test clip: [Download the original talking video with audio (MP4, 1.1 MB)](https://raw.githubusercontent.com/jalrobustvfx/BobHead/main/docs/media/before.mp4).** This is the supplied `Me01.mp4`, stored here as `before.mp4`. Save the video to your computer, upload it in BobHead, choose **5 seconds**, and click **Make me a bobhead**. Compare your output with the [included result](docs/media/after.mp4).

**New to GitHub? Follow the [download and installation guide](INSTALL.md)** for exactly which file to click and how to set up the app.

1. Open the [latest release](https://github.com/jalrobustvfx/BobHead/releases/latest) and download **Start-BobHead.cmd** into an empty folder on a drive with plenty of space.
2. Double-click **Start-BobHead.cmd**. It downloads and extracts the bundled Windows runtime, verifies the download, and launches BobHead. Python, ComfyUI, and the required custom nodes are included.
3. On the first launch, click **Download required models** in the app. The 12 main model files total approximately **101.6 GB**, with additional supporting downloads on the first generation. Model weights are downloaded from their publishers; they are not included in the app download.
4. Upload a talking-person clip, choose a short duration, and click **Make me a bobhead**. When it finishes, preview and download the result.

Keep the installation folder for future launches. Run the same starter again; completed setup is reused. You do not need your own ComfyUI installation or a folder picker.

**Requirements:** Windows 10/11, an NVIDIA CUDA GPU with a compatible driver, a reliable Internet connection for setup, and space for the runtime, model files, temporary files, and outputs. The demonstrated setup uses an **RTX PRO 6000 Blackwell with 96 GiB VRAM**. The minimum VRAM requirement has not been established; this is a large LTX/Wan workflow. A separate-machine installation has not yet been validated.

See the [illustrated quick start and troubleshooting guide](docs/QUICKSTART.md). GitHub's **Source code.zip** contains the project source; the release starter installs the complete runtime.

## Test with the creator's footage

| Original talking clip | Generated BobHead |
| --- | --- |
| [Download before.mp4](exmaples%20files/before.mp4) | [Download after.mp4](exmaples%20files/after.mp4) |

The source is the creator's own `Me01.mp4`. Upload `before.mp4` in BobHead and choose **5 seconds**. The result uses the original source audio.

## How it works

The workflow takes the first video frame as its reference image. A custom OpenPose effect enlarges the head in the pose guidance, while the video pipeline uses the source motion to animate the result. The final video combines the generated frames with the original source audio.

The current source app uses workflow **v07**. The head-size slider drives the custom pose node from **1.2× to 2.0×**, defaulting to **1.7×**. The interface handles uploads, model setup, progress, previews, and downloads locally through ComfyUI.

## Source and reproducibility

- [Editable ComfyUI v07 workflow](workflows/BobHead_Comfyui_v07.json)
- [Compiled API workflow](workflows/BobHead_API.json)
- [Custom pose-effect node](custom_nodes/comfyui-pose-effects)
- [Required node packs and sources](NODE_SETUP.md)
- [Model download locations and licenses](MODELS.md)
- [Developer setup, validation, and packaging](docs/DEVELOPMENT.md)
- [Recorded dependency versions](environment/installed-packages.txt) and [source inventory](environment/source-versions.json)

The app's automated checks cover v07 prompt routing, graph connections, downloads, and launch behavior. The five example pairs above were supplied for this update. A real v07 generation was also validated; see `environment/v07-validation.json`. The complete first-time model download has not been rerun from an empty model folder.

## Credits and licensing

BobHead's application code and custom pose effect are provided under the [MIT license](LICENSE). ComfyUI, the third-party custom nodes, Python packages, and model weights retain their own licenses; see [node sources](NODE_SETUP.md) and [model sources](MODELS.md). The bundled runtime preserves third-party license files.

The example footage and demonstration media are separate from the software license; see [media notes](docs/media/README.md). Use footage you have permission to process and share.
