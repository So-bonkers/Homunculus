#!/usr/bin/env bash
# Best-effort installer for the pieces homunculus drives. Run from the repository root:  ./setup.sh [all|app|comfy|mia|unimate|skintokens]
# It was written from the working layout on the author's machine (AMD ROCm); it has NOT been run from a clean machine, so read it and expect to adjust it.
# What it cannot do for you: install Unsloth Studio (serves Qwen-Image + the judge VLMs), Blender, the ROCm/CUDA drivers, and accept gated model licences.
set -e; cd "$(dirname "$0")"; R=$PWD; step() { printf '\n== %s\n' "$*"; }
want() { [ "${1:-all}" = all ] || [ "$1" = "$2" ]; }
W=${1:-all}

if want $W app; then step "web app + orchestrator (python venv)"
  command -v uv >/dev/null || { echo "install uv first: https://docs.astral.sh/uv/"; exit 1; }
  uv venv --python 3.12 .venv; uv pip install --python .venv/bin/python -r requirements.txt
  mkdir -p runs uploads
  mkdir -p ~/.config/systemd/user && sed "s#%h/figure-pipeline#$R#g" systemd/homunculus-web.service > ~/.config/systemd/user/homunculus-web.service && systemctl --user daemon-reload
fi

if want $W comfy; then step "ComfyUI + upscalers + Pixal3D weights (ROCm torch shown; use the CUDA wheel on NVIDIA)"
  [ -d comfy/ComfyUI ] || git clone https://github.com/comfyanonymous/ComfyUI comfy/ComfyUI
  uv venv --python 3.12 comfy/.venv
  uv pip install --python comfy/.venv/bin/python torch torchvision --index-url https://download.pytorch.org/whl/rocm7.2
  uv pip install --python comfy/.venv/bin/python -r comfy/ComfyUI/requirements.txt requests
  U=comfy/ComfyUI/models/upscale_models; mkdir -p $U
  [ -f $U/RealESRGAN_x4plus.pth ] || curl -L -o $U/RealESRGAN_x4plus.pth https://github.com/xinntao/Real-ESRGAN/releases/download/v0.1.0/RealESRGAN_x4plus.pth
  [ -f $U/RealESRGAN_x4plus_anime_6B.pth ] || curl -L -o $U/RealESRGAN_x4plus_anime_6B.pth https://github.com/xinntao/Real-ESRGAN/releases/download/v0.2.2.4/RealESRGAN_x4plus_anime_6B.pth
  echo "4x-UltraSharp.pth (3D-render upscaler): download it from https://huggingface.co/Kim2091/UltraSharp and put it in $U"
  bash comfy/dl.sh     # Pixal3D shape/texture weights from Comfy-Org/Pixal3D. config.py uses pixal3d_bf16.safetensors (full precision); put it in comfy/ComfyUI/models/diffusion_models/
  echo "ComfyUI is started and stopped by the pipeline as the user unit 'comfy-px' (see homunculus/stages/comfy.py)."
fi

if want $W mia; then step "Make-It-Animatable"
  [ -d mia/repo ] || git clone https://github.com/jasongzy/Make-It-Animatable mia/repo
  cp mia/overlay/run_mia.py mia/repo/run_mia.py          # headless runner + weight sanity pass used by stages/rig.py
  uv venv --python 3.11 mia/.venv && uv pip install --python mia/.venv/bin/python -r mia/repo/requirements.txt
  echo "Follow mia/repo/README.md for its checkpoints and (gated) template asset; mia/vendor holds small stand-ins for pytorch3d / torch_cluster."
fi

if want $W unimate; then step "UniMate"
  [ -d unimate/.git ] || { mv unimate/bin /tmp/unimate-bin-$$ ; git clone https://github.com/Friedrich-M/UniMate unimate; mkdir -p unimate/bin; mv /tmp/unimate-bin-$$/* unimate/bin/; }
  uv venv --python 3.10 unimate/.venv
  echo "Install UniMate's requirements into unimate/.venv and download its preview checkpoint to"
  echo "  unimate/outputs/unimate_uniml3d_f60_v3_preview   (see unimate/README.md; weights are CC BY-NC 4.0)"
  echo "unimate/bin/blender is a shim so UniMate's scripts use the venv's pip bpy instead of the system Blender."
fi

if want $W skintokens; then step "SkinTokens (optional: only for 3D models that are not already in a T-pose)"
  mkdir -p riggers; [ -d riggers/skintokens ] || git clone https://github.com/localai-org/skin-tokens.cpp riggers/skintokens
  echo "Build it with CMake (Vulkan) per its README and put the F16 GGUF in riggers/skintokens-gguf/F16 (see stages/tpose.py for the exact command)."
fi
echo; echo "Next: start Unsloth Studio's API on 127.0.0.1:8888, then ./launch.sh (opens http://127.0.0.1:8765)"
