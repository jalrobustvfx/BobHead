"""Read only Hugging Face metadata; never downloads model weights."""
import asyncio
import json
from pathlib import Path
import re
import aiohttp

ROOT = Path(__file__).resolve().parents[1]
LINKS = [
('vae', 'https://huggingface.co/Kijai/LTX2.3_comfy/resolve/main/vae/LTX23_video_vae_bf16.safetensors'),
('diffusion_models', 'https://huggingface.co/Kijai/LTX2.3_comfy/resolve/main/diffusion_models/ltx-2.3-22b-dev_transformer_only_bf16.safetensors'),
('loras', 'https://huggingface.co/Lightricks/LTX-2.3/resolve/main/ltx-2.3-22b-distilled-lora-384.safetensors'),
('loras', 'https://huggingface.co/oumoumad/LTX-2.3-22b-IC-LoRA-Outpaint/resolve/main/ltx-2.3-22b-ic-lora-outpaint.safetensors'),
('text_encoders', 'https://huggingface.co/Comfy-Org/ltx-2/resolve/main/split_files/text_encoders/gemma_3_12B_it_fp4_mixed.safetensors'),
('text_encoders', 'https://huggingface.co/unsloth/LTX-2.3-GGUF/resolve/a8c73b7b1fb95cd3218b97d8cbcfcc9239ad3a39/text_encoders/ltx-2.3-22b-dev_embeddings_connectors.safetensors'),
('diffusion_models', 'https://huggingface.co/Kijai/WanVideo_comfy_fp8_scaled/resolve/8bd648df835cff08dd31cbebfb4dd596c1604b88/Wan2_2-Animate-14B_fp8_e5m2_scaled_KJ.safetensors'),
('loras', 'https://huggingface.co/Kijai/WanVideo_comfy/resolve/main/LoRAs/Wan22_relight/WanAnimate_relight_lora_fp16.safetensors'),
('loras', 'https://huggingface.co/Kijai/WanVideo_comfy/resolve/main/Lightx2v/lightx2v_I2V_14B_480p_cfg_step_distill_rank64_bf16.safetensors'),
('vae', 'https://huggingface.co/Kijai/WanVideo_comfy/resolve/main/Wan2_1_VAE_bf16.safetensors'),
('clip_vision', 'https://huggingface.co/calcuis/wan-gguf/resolve/e1b5a63a5c9c8fc999134a19e0732978fc826a52/clip_vision_h.safetensors'),
('text_encoders', 'https://huggingface.co/Kijai/WanVideo_comfy/resolve/main/umt5-xxl-enc-bf16.safetensors'),
]

async def main():
    async with aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=60)) as session:
        async def check(folder, url):
            async with session.head(url, allow_redirects=False) as response:
                if response.status not in (200, 302, 307):
                    raise RuntimeError(f'{response.status}: {url}')
                headers = response.headers
                size = int(headers['X-Linked-Size'])
                sha = headers['X-Linked-Etag'].strip('"')
                revision = headers['X-Repo-Commit']
                if not re.fullmatch('[0-9a-f]{64}', sha): raise ValueError('Missing SHA256')
                pinned = url.replace('/resolve/main/', f'/resolve/{revision}/')
                return {'path': folder + '/' + url.rsplit('/', 1)[-1], 'url': pinned,
                        'source_url': url, 'bytes': size, 'sha256': sha}
        rows = await asyncio.gather(*(check(*item) for item in LINKS))
    (ROOT / 'environment/model-downloads.json').write_text(json.dumps(rows, indent=2), encoding='utf-8')
    print(json.dumps({'verified': len(rows), 'GiB': sum(r['bytes'] for r in rows)/1024**3}))

if __name__ == '__main__': asyncio.run(main())
