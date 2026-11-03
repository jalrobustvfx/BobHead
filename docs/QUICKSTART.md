# Download and install BobHead v0.8.0

**[Watch the 1:56 narrated walkthrough](media/download-launch-use.mp4)** — the new interface, one-file installation, model setup and first video.

## Alternative: download the complete ZIP

If **Start-BobHead.cmd** cannot download the runtime, **[download the v07 ZIP from Google Drive](https://drive.google.com/file/d/1AybkXAA47niFAuONsnjIE33zdB76Z3DU/view?usp=sharing)** (about **3.41 GB**). Choose **Extract All**, open `BobHead-Standalone-v07`, and apply the small v08 update described below. Then double-click **Launch BobHead.cmd**. Then continue with **3. Download models once** below. Model weights are not included in the ZIP.

## Updating an existing installation to v08

The models are unchanged from v07. If the original starter completed the installation, save the new **Start-BobHead.cmd** beside `BobHead-Standalone-v07` and run it. It reuses the installed runtime and applies the small v08 app update. The runtime folder keeps its name so model paths stay valid.

For a Google Drive/manual installation, download [BobHead-App-v08.zip](https://github.com/jalrobustvfx/BobHead/releases/download/v0.8.0/BobHead-App-v08.zip). Extract its contents inside the existing `BobHead-Standalone-v07` folder, replacing application files. Then run **Launch BobHead.cmd**. Runtime files, models and user data are not in the update ZIP.

v08 opens on **http://127.0.0.1:8800** with its engine on **8200**. This separates it from older apps/engines on 8790/8190.

## 1. Get the starter

Open the [latest Windows release](https://github.com/jalrobustvfx/BobHead/releases/latest). Under **Assets**, download **Start-BobHead.cmd** into a new, empty folder on the drive where you want to install BobHead. The starter downloads the large `.part` files automatically; you only download the starter yourself.

Windows 10/11 and an NVIDIA CUDA GPU with a compatible driver are required. Allow room for the runtime, about **118.9 GB of main models**, supporting downloads and output files. The validated GPU has 96 GiB VRAM; the minimum has not been established.

## 2. Launch

Double-click **Start-BobHead.cmd**. Its live progress bar shows the overall percentage, downloaded MiB and speed. If data stops arriving, it shows a waiting message, then reconnects automatically (up to five attempts), preserving the partial download. Keep its window open while it downloads, verifies and extracts the shared runtime into `BobHead-Standalone-v07`, then applies the v08 app update. The app opens in your browser automatically. Python, ComfyUI and the required custom nodes are included; no separate installation or folder picker is needed.

If you previously installed v06, use a new folder for the current starter. To upgrade v07, follow the in-place update instructions above. Older starters stay pinned to their original version. For a fresh launch later, reuse the new starter or open **Launch BobHead.cmd** inside the v07 folder.

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
- **A runtime download stops:** run the same starter again; verified complete parts are reused and partial runtime files resume where they stopped.
- **The engine does not start:** check the startup logs under the app's `.data/logs` folder and confirm your NVIDIA driver is compatible.

### “An older BobHead (v06) is running on this port”

An older BobHead app is still running in the background on the port needed by v07. Closing the browser tab does not stop that background process.

**Simplest option:** save your work, restart the computer, then launch only **BobHead v08**.

To stop just the old app without restarting:

1. Open **PowerShell** and find the process listening on the bundled app's default port, **8800** (use 8790 when checking an older v06/v07 installation):

   ```powershell
   Get-NetTCPConnection -LocalPort 8800 -State Listen |
     Select-Object LocalPort, OwningProcess
   ```

2. Replace `12345` below with the number shown under **OwningProcess**. Inspect its launch command to confirm that it belongs to the older BobHead installation:

   ```powershell
   Get-CimInstance Win32_Process -Filter "ProcessId = 12345" |
     Select-Object ProcessId, Name, CommandLine
   ```

3. If it is the old BobHead Python server, stop that specific process:

   ```powershell
   Stop-Process -Id 12345
   ```

4. Run **Launch BobHead.cmd** from the updated app folder again.

If access is denied, open PowerShell as administrator and repeat the steps. Stop only the confirmed old BobHead process; do not stop every Python process. If the port query returns no listener, try the v07 launcher again. This error concerns the app port; you do not need to stop ComfyUI just to free the app port.

The exact starter passed a clean-folder installation test on this computer, including checksum verification, extraction and startup of the freshly extracted app and engine. A separate-machine installation and the complete fresh model download have not been rerun.

## Source code

**Code → Download ZIP** contains source only. To use your own ComfyUI, follow the [developer guide](DEVELOPMENT.md). For the self-contained Windows app, use **Start-BobHead.cmd** above.
