# BobHead v08

[Editable workflow](BobHead_Comfyui_v08.json) · [Raw API export](BobHead_Comfyui_v08_API_source.json) · [Active app API graph](BobHead_API.json)

The editable JSON is copied unchanged from the supplied v08 workflow. The app compiles the active graph and preserves the authored optimization settings: 480×813 pre-resize, pose detection at 512, both VRAM cleanup/model-unload nodes, block swap of 25 blocks, and the updated seeds. The existing slider controls head scale from 1.2× to 2.0×; duration and output filenames are set per job, and the final video retains source audio. Debug previews are excluded from the app graph.

The workflow uses the same 15 main model files as v07. No additional model downloads are required. `VRAM_Debug` comes from the existing KJNodes pack; [node setup](../NODE_SETUP.md).

## Update an installed app

- **Installed using the GitHub starter:** download the latest Start-BobHead.cmd into the parent folder containing BobHead-Standalone-v07, then run it. It reuses the completed runtime and applies the small v08 update.
- **Installed using the Drive ZIP/manual extraction:** download BobHead-App-v08.zip from the v0.8.0 release and extract its contents inside the existing app folder, replacing application files. Launch BobHead.cmd then opens v08. The ZIP contains no runtime, models or user data.

The existing runtime folder keeps its name to preserve model locations. The new launcher uses app port 8800 and engine port 8200 to avoid accidentally using an older version's engine. Models continue to download separately on new installations.

The source app was validated with 33 automated checks and a real one-second sample. The final sample is 25 frames at 30 fps (0.83 seconds), 448×800, with source/result audio correlation of about 0.986. See environment/v08-validation.json. This is a functional validation, not a performance benchmark.
