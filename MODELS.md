# v06 models — download separately

No model weights are packaged. The app installs these files under its bundled ComfyUI `models/` folder.

| File / destination | Size | Publisher download |
|---|---:|---|
| `vae/LTX23_video_vae_bf16.safetensors` | 1.45 GB | [Download](https://huggingface.co/Kijai/LTX2.3_comfy/resolve/main/vae/LTX23_video_vae_bf16.safetensors) |
| `diffusion_models/ltx-2.3-22b-dev_transformer_only_bf16.safetensors` | 42.02 GB | [Download](https://huggingface.co/Kijai/LTX2.3_comfy/resolve/main/diffusion_models/ltx-2.3-22b-dev_transformer_only_bf16.safetensors) |
| `loras/ltx-2.3-22b-distilled-lora-384.safetensors` | 7.61 GB | [Download](https://huggingface.co/Lightricks/LTX-2.3/resolve/main/ltx-2.3-22b-distilled-lora-384.safetensors) |
| `loras/ltx-2.3-22b-ic-lora-outpaint.safetensors` | 1.31 GB | [Download](https://huggingface.co/oumoumad/LTX-2.3-22b-IC-LoRA-Outpaint/resolve/main/ltx-2.3-22b-ic-lora-outpaint.safetensors) |
| `text_encoders/gemma_3_12B_it_fp4_mixed.safetensors` | 9.45 GB | [Download](https://huggingface.co/Comfy-Org/ltx-2/resolve/main/split_files/text_encoders/gemma_3_12B_it_fp4_mixed.safetensors) |
| `text_encoders/ltx-2.3-22b-dev_embeddings_connectors.safetensors` | 6.34 GB | [Download](https://huggingface.co/unsloth/LTX-2.3-GGUF/resolve/a8c73b7b1fb95cd3218b97d8cbcfcc9239ad3a39/text_encoders/ltx-2.3-22b-dev_embeddings_connectors.safetensors) |
| `diffusion_models/Wan2_2-Animate-14B_fp8_e5m2_scaled_KJ.safetensors` | 18.40 GB | [Download](https://huggingface.co/Kijai/WanVideo_comfy_fp8_scaled/resolve/8bd648df835cff08dd31cbebfb4dd596c1604b88/Wan2_2-Animate-14B_fp8_e5m2_scaled_KJ.safetensors) |
| `loras/WanAnimate_relight_lora_fp16.safetensors` | 1.44 GB | [Download](https://huggingface.co/Kijai/WanVideo_comfy/resolve/main/LoRAs/Wan22_relight/WanAnimate_relight_lora_fp16.safetensors) |
| `loras/lightx2v_I2V_14B_480p_cfg_step_distill_rank64_bf16.safetensors` | 0.74 GB | [Download](https://huggingface.co/Kijai/WanVideo_comfy/resolve/main/Lightx2v/lightx2v_I2V_14B_480p_cfg_step_distill_rank64_bf16.safetensors) |
| `vae/Wan2_1_VAE_bf16.safetensors` | 0.25 GB | [Download](https://huggingface.co/Kijai/WanVideo_comfy/resolve/main/Wan2_1_VAE_bf16.safetensors) |
| `clip_vision/clip_vision_h.safetensors` | 1.26 GB | [Download](https://huggingface.co/calcuis/wan-gguf/resolve/e1b5a63a5c9c8fc999134a19e0732978fc826a52/clip_vision_h.safetensors) |
| `text_encoders/umt5-xxl-enc-bf16.safetensors` | 11.36 GB | [Download](https://huggingface.co/Kijai/WanVideo_comfy/resolve/main/umt5-xxl-enc-bf16.safetensors) |

Exact pinned URLs, byte counts and SHA256 values are in `environment/model-downloads.json`.

The supporting nodes download these additional resources on first generation (Internet required):

- Florence2 caption model: https://huggingface.co/microsoft/Florence-2-base
- SAM2 tiny fp16: https://huggingface.co/1038lab/sam2
- GroundingDINO SwinT config/weights: https://huggingface.co/1038lab/GroundingDINO
- BERT: https://huggingface.co/google-bert/bert-base-uncased
- DWPose yolox_l.onnx and dw-ll_ucoco_384_bs5.torchscript.pt: https://github.com/Fannovel16/comfyui_controlnet_aux

Models retain their publisher licenses. Check the linked repositories before use or redistribution.
The Lightx2v link has been converted from a web page (`blob`) to a direct file (`resolve`) URL.
