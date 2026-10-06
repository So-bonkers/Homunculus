#!/bin/bash
cd "$(dirname "$0")/ComfyUI/models" || exit 1
B=https://huggingface.co/Comfy-Org/Pixal3D/resolve/main
dl(){ [ -f "$2" ] && [ "$(stat -c%s "$2")" -gt 100000 ] && return; curl -L --fail -C - -o "$2" "$1" || echo "FAIL $2"; }
dl $B/clip_vision/dino_v3_L_naf_fp32.safetensors clip_vision/dino_v3_L_naf_fp32.safetensors
dl $B/vae/trellis_2_shape_vae_bf16.safetensors vae/trellis_2_shape_vae_bf16.safetensors
dl $B/vae/trellis_2_texture_vae_bf16.safetensors vae/trellis_2_texture_vae_bf16.safetensors
dl $B/diffusion_models/pixal3d_bf16.safetensors diffusion_models/pixal3d_bf16.safetensors
dl $B/diffusion_models/pixal3d_int8_convrot.safetensors diffusion_models/pixal3d_int8_convrot.safetensors
dl $B/diffusion_models/pixal3d_multiview_int8_convrot.safetensors diffusion_models/pixal3d_multiview_int8_convrot.safetensors
echo DL_DONE
