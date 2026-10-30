# BobHead

Turn a short video of someone talking into a bobhead video, with an enlarged head, the original head movement, and the original dialogue.

![Original footage and BobHead result](docs/screenshots/before-after.jpg)

**[Watch the before/after comparison](docs/media/before-after.mp4)** · **[Watch the 1:54 walkthrough](docs/media/how-to-use.mp4)** · **[Download the Windows app](https://github.com/jalrobustvfx/BobHead/releases/latest)**

Built for the [ComfyUI open-source competition](https://comfy.org/open-source-higgsfield/). This repository includes the app, v06 workflow, custom pose effect, setup instructions, and actual input/output examples.

## Run the app

1. Open the [latest release](https://github.com/jalrobustvfx/BobHead/releases/latest) and download **Start-BobHead.cmd** into an empty folder on a drive with plenty of space.
2. Double-click **Start-BobHead.cmd**. It downloads and extracts the bundled Windows runtime, verifies the download, and launches BobHead. Python, ComfyUI, and the required custom nodes are included.
3. On the first launch, click **Download models** in the app. The 12 main model files total approximately **101.6 GB**, with additional supporting downloads on the first generation. Model weights are downloaded from their publishers; they are not included in the app download.
4. Upload a talking-person clip, choose a short duration, and click **Make BobHead**. When it finishes, preview and download the result.

Keep the installation folder for future launches. Run the same starter again; completed setup is reused. You do not need your own ComfyUI installation or a folder picker.

**Requirements:** Windows 10/11, an NVIDIA CUDA GPU with a compatible driver, a reliable Internet connection for setup, and space for the runtime, model files, temporary files, and outputs. The demonstrated setup uses an **RTX PRO 6000 Blackwell with 96 GiB VRAM**. The minimum VRAM requirement has not been established; this is a large LTX/Wan workflow. A separate-machine installation has not yet been validated.

See the [illustrated quick start and troubleshooting guide](docs/QUICKSTART.md). GitHub's **Source code.zip** contains the project source; the release starter installs the complete runtime.

## See it in action

| Original talking clip | Generated BobHead |
| --- | --- |
| [Play before.mp4](docs/media/before.mp4) | [Play after.mp4](docs/media/after.mp4) |

The example uses the supplied `Tonigh_v003.mp4` clip with audible dialogue. The generated result keeps that dialogue. The [walkthrough](docs/media/how-to-use.mp4) is 1 minute 54 seconds, with narration and captions. [Transcript](docs/media/how-to-use-transcript.txt) · [Subtitles](docs/media/how-to-use.srt).

![BobHead app with a completed result](docs/screenshots/result.png)

## How it works

The workflow takes the first video frame as its reference image. A custom OpenPose effect enlarges the head in the pose guidance, while the video pipeline uses the source motion to animate the result. The final video combines the generated frames with the original source audio.

The app uses workflow **v06**. Head scale is fixed at **1.5** in the custom pose node; there is no size slider. The interface handles uploads, model setup, progress, previews, and downloads locally through ComfyUI.

## Source and reproducibility

- [Editable ComfyUI v06 workflow](workflows/BobHead_Comfyui_v06.json)
- [Compiled API workflow](workflows/BobHead_API.json)
- [Custom pose-effect node](custom_nodes/comfyui-pose-effects)
- [Required node packs and sources](NODE_SETUP.md)
- [Model download locations and licenses](MODELS.md)
- [Developer setup, validation, and packaging](docs/DEVELOPMENT.md)
- [Recorded dependency versions](environment/installed-packages.txt) and [source inventory](environment/source-versions.json)

The app's 16 automated checks pass. The included result was generated with the bundled v06 runtime, and the demo was checked for duration, video decoding, and audible source/result audio. The complete first-time model download has not been rerun from an empty model folder.

## Credits and licensing

BobHead's application code and custom pose effect are provided under the [MIT license](LICENSE). ComfyUI, the third-party custom nodes, Python packages, and model weights retain their own licenses; see [node sources](NODE_SETUP.md) and [model sources](MODELS.md). The bundled runtime preserves third-party license files.

The example footage and demonstration media are separate from the software license; see [media notes](docs/media/README.md). Use footage you have permission to process and share.
