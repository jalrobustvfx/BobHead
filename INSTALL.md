# Download and install BobHead

You can install BobHead by downloading and running one starter file. Python, ComfyUI, and the required custom nodes are included; you do not need to install them separately.

## Before you start

- Use Windows 10 or 11 with an NVIDIA CUDA GPU and a compatible driver.
- Choose a drive with plenty of free space. The model downloads alone total about **102 GB**, with additional space needed for the app, supporting models, and generated videos.
- Keep Internet access available during setup and the first generation.

The demonstrated setup uses an RTX PRO 6000 Blackwell with 96 GiB VRAM. Minimum VRAM has not been established, and installation on a separate computer has not yet been validated.

## 1. Download the starter from GitHub

1. Open the **[BobHead Releases page](https://github.com/jalrobustvfx/BobHead/releases/latest)**.
2. Scroll down to **Assets**. If the file list is collapsed, click **Assets** to expand it.
3. Click **Start-BobHead.cmd** to download it.
4. Create an empty folder on the drive where you want BobHead installed, then move the downloaded starter into that folder.

You only need to download **Start-BobHead.cmd** yourself. It automatically downloads the two large runtime parts, joins them, checks their integrity, and extracts the app. Leave the `.part` files and checksum files on the release page for the starter to handle.

## 2. Install and launch

Double-click **Start-BobHead.cmd** in your chosen folder. Keep its window open while it downloads and extracts the app. BobHead opens in your browser when ready.

The starter uses the bundled ComfyUI installation automatically. You do not need to select a ComfyUI folder.

## 3. Download the models

On the first launch, click **Download required models** in the app. The 12 main model files total approximately **101.6 GB**. Model weights are downloaded separately from their publishers to keep the app download smaller.

![Model download screen](docs/screenshots/model-downloads.png)

Wait until all 12 models show **Installed**. You can pause and resume the model downloads. Supporting caption, segmentation, and pose models may download during the first generation, so keep Internet access available until it finishes.

## 4. Make your first video

1. **[Download the example source video with dialogue (MP4, 5.3 MB)](https://raw.githubusercontent.com/jalrobustvfx/BobHead/main/docs/media/before.mp4)**. If it opens in your browser, use the video's download menu or right-click and choose **Save video as**. This is `Tonigh_v003.mp4`, stored in the repository as `before.mp4`.
2. Upload the saved video in BobHead.
3. Choose **5 seconds** for the example clip.
4. Click **Make me a bobhead** and wait for generation to finish.
5. Preview the result with sound, then click **Download MP4**. You can compare it with the [included example result](docs/media/after.mp4).

Head size is fixed by the workflow, and the original dialogue is carried into the output.

## Launch again later

Keep the installation folder together. Run the same **Start-BobHead.cmd** again, or open **Launch BobHead.cmd** inside the extracted `BobHead-Standalone-v06` folder. Completed setup is reused.

If a runtime download is interrupted, run the starter again. Verified completed parts are reused; an incomplete runtime part downloads again.

## Downloading just the source code

For the project source, open the **[repository](https://github.com/jalrobustvfx/BobHead)** and choose **Code → Download ZIP**. Developers can also clone it with Git:

```sh
git clone https://github.com/jalrobustvfx/BobHead.git
```

The source download includes the app code, workflow, custom pose node, documentation, and examples. It does not include the bundled Python/ComfyUI runtime or model weights. To run the complete Windows app, use the release starter above. For source setup, see the **[developer guide](docs/DEVELOPMENT.md)**.

**[Illustrated quick start and troubleshooting](docs/QUICKSTART.md)** · **[1:54 walkthrough](docs/media/how-to-use.mp4)** · **[Model links and folders](MODELS.md)**
