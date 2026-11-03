# BobHead v07 workflow

Download [BobHead_Comfyui_v07.json](BobHead_Comfyui_v07.json) and drag it into ComfyUI to open the editable workflow.

This version adds a Qwen Image 2.1 image-edit stage to create a doll-style reference from the first processed video frame and the enlarged OpenPose guide. The custom pose-effects node controls head scale. The original workflow is included unchanged, with its authored 1.7 scale.

## Setup

1. Install the custom nodes listed in [NODE_SETUP.md](../NODE_SETUP.md), including the bundled [pose-effects node](../custom_nodes/comfyui-pose-effects).
2. Use a ComfyUI version that includes `TextEncodeQwenImage21` and `QwenImage21Cache`. The validated local environment uses ComfyUI 0.43.0.
3. Keep the existing workflow models described in [MODELS.md](../MODELS.md), and add these three files under your ComfyUI `models` directory:

| Destination | Download |
| --- | --- |
| `diffusion_models/qwen_image_2.1_int8_convrot.safetensors` | [Qwen image model](https://huggingface.co/Comfy-Org/Qwen-Image-2.1/resolve/main/diffusion_models/qwen_image_2.1_int8_convrot.safetensors) |
| `text_encoders/qwen3vl_8b_int8_convrot.safetensors` | [Qwen text encoder](https://huggingface.co/Comfy-Org/Qwen-Image-2.1/resolve/main/text_encoders/qwen3vl_8b_int8_convrot.safetensors) |
| `vae/qwen_image_2.1_vae_bf16.safetensors` | [Qwen VAE](https://huggingface.co/Comfy-Org/Qwen-Image-2.1/resolve/main/vae/qwen_image_2.1_vae_bf16.safetensors) |

These additional models require about 17.3 GB. Model weights are not included in this repository.

4. Restart ComfyUI, open the workflow, and select your own video in the video loader. Replace any saved input selection from the author's computer.
5. Start with a short clip and run the workflow. The prompt-enhancer branch is disabled; an additional enhancer model is not needed for the active workflow.

## API export

[BobHead_Comfyui_v07_API_source.json](BobHead_Comfyui_v07_API_source.json) is the flattened API graph for integration, with the disabled prompt-enhancer branch pruned. It is not the editable canvas file. API users must supply their own uploaded input filename and output prefix.

The source app now uses v07 by default, with a redesigned interface and a head-size slider from 1.2× to 2.0×. See the [source setup guide](../docs/DEVELOPMENT.md). The downloadable v0.6.0 Windows release and older walkthrough still describe v06.
