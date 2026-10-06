#!/usr/bin/env bash
# Best-effort installer for the pieces homunculus drives. Run from the repository root:  ./setup.sh [all|app|comfy|mia|unimate|skintokens]
# It was written from the working layout on the author's machine (AMD ROCm); it has NOT been run from a clean machine, so read it and expect to adjust it.
# What it cannot do for you: install Unsloth Studio (serves Qwen-Image + the judge VLMs), Blender, the ROCm/CUDA drivers, and accept gated model licences.
set -e; cd "$(dirname "$0")"; R=$PWD; step() { printf '\n== %s\n' "$*"; }
need_hf() { command -v hf >/dev/null || { echo "install the Hugging Face CLI first:  uv tool install huggingface_hub   (then: hf auth login if a download asks for it)"; exit 1; }; }
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
  [ -f $U/4x-UltraSharp.pth ] || curl -L -o $U/4x-UltraSharp.pth https://huggingface.co/Kim2091/UltraSharp/resolve/main/4x-UltraSharp.pth     # CC BY-NC-SA 4.0
  bash comfy/dl.sh     # Pixal3D (MIT) from Comfy-Org/Pixal3D: bf16 shape model (11 GB, what config.py uses), DINOv3 vision encoder, two VAEs
  echo "ComfyUI is started and stopped by the pipeline as the user unit 'comfy-px' (see homunculus/stages/comfy.py)."
fi

if want $W mia; then step "Make-It-Animatable"
  [ -d mia/repo ] || git clone https://github.com/jasongzy/Make-It-Animatable mia/repo
  cp mia/overlay/run_mia.py mia/repo/run_mia.py          # headless runner + weight sanity pass used by stages/rig.py
  uv venv --python 3.11 mia/.venv && uv pip install --python mia/.venv/bin/python -r mia/repo/requirements.txt
  need_hf; cd mia/repo
  hf download jasongzy/Mixamo --repo-type dataset --include 'bones*.fbx' 'animation/**' --local-dir data/Mixamo     # may need `hf auth login`
  hf download jasongzy/Make-It-Animatable --include 'output/best/new/**' --local-dir .                           # 2.3 GB of pretrained weights
  hf download jasongzy/Make-It-Animatable --include 'data/**' --local-dir .
  wget -q https://github.com/facebookincubator/FBX2glTF/releases/download/v0.9.7/FBX2glTF-linux-x64 -O util/FBX2glTF && chmod +x util/FBX2glTF
  cd ../..; echo "mia/vendor holds small stand-ins for pytorch3d / torch_cluster (put it on PYTHONPATH, stages/rig.py does)."
fi

if want $W unimate; then step "UniMate"
  [ -d unimate/.git ] || { mv unimate/bin /tmp/unimate-bin-$$ ; git clone https://github.com/Friedrich-M/UniMate unimate; mkdir -p unimate/bin; mv /tmp/unimate-bin-$$/* unimate/bin/; }
  uv venv --python 3.10 unimate/.venv
  echo "Install UniMate's requirements into unimate/.venv (see unimate/README.md), plus the bpy wheel: the bin/blender shim runs its scripts with it."
  need_hf; mkdir -p unimate/outputs
  hf download Linzhan/UniMate --include 'unimate_uniml3d_f60_v3/config.json' 'unimate_uniml3d_f60_v3/dataset_stats.npy' 'unimate_uniml3d_f60_v3/checkpoints/checkpoint_step_100000.pt' --local-dir unimate/outputs/_dl   # CC BY-NC 4.0, 1.2 GB
  rm -rf unimate/outputs/unimate_uniml3d_f60_v3_preview; mv unimate/outputs/_dl/unimate_uniml3d_f60_v3 unimate/outputs/unimate_uniml3d_f60_v3_preview; rm -rf unimate/outputs/_dl
  echo "unimate/bin/blender is a shim so UniMate's scripts use the venv's pip bpy instead of the system Blender."
fi

if want $W skintokens; then step "SkinTokens (optional: only for 3D models that are not already in a T-pose)"
  mkdir -p riggers; [ -d riggers/skintokens ] || git clone https://github.com/localai-org/skin-tokens.cpp riggers/skintokens
  need_hf; hf download LocalAI-io/SkinTokens-GGUF --include 'F16/*' --local-dir riggers/skintokens-gguf          # MIT, 1.2 GB
  echo "Build skin-tokens.cpp with CMake (Vulkan) per riggers/skintokens/README.md so that riggers/skintokens/build/bin/skintokens-cli exists (see stages/tpose.py for how it is called)."
fi
echo; echo "The VLM judges and Qwen-Image are not downloaded here: Unsloth Studio fetches them the first time the pipeline loads them (see README, Setup)."
echo "Next: start Unsloth Studio's API on 127.0.0.1:8888, then ./launch.sh (opens http://127.0.0.1:8765)"
