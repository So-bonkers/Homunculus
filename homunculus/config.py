"""Paths, endpoints and limits shared by every stage."""
import os, shutil
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent      # the repository folder; every tool is expected below it (see setup.sh)
RUNS = ROOT / "runs"
COMFY = ROOT / "comfy"
COMFY_UI = COMFY / "ComfyUI"
COMFY_PY = COMFY / ".venv/bin/python"
MIA = ROOT / "mia"
MIA_REPO = MIA / "repo"
MIA_PY = MIA / ".venv/bin/python"
BLENDER = os.environ.get("BLENDER") or shutil.which("blender") or "/snap/bin/blender"

STUDIO = "http://127.0.0.1:8888"          # Unsloth Studio (Qwen-Image + Qwen3.8)
COMFY_API = "http://127.0.0.1:8188"       # ComfyUI (upscaler + Pixal3D)
COMFY_UNIT = "comfy-px"

VLM_MODEL = "unsloth/Qwen3.8-27B-GGUF"      # planner (writes the redraw prompt)
VLM_VARIANT = "UD-Q4_K_M"
VLM_CTX = 12288
# judge panel: every gate asks all three in turn (one on the GPU at a time) and takes the majority
JUDGES = [("unsloth/Qwen3.8-27B-GGUF", "UD-Q4_K_M"),
          ("unsloth/gemma-4-26B-A4B-it-qat-GGUF", "UD-Q4_K_XL"),
          ("unsloth/Qwen3.6-35B-A3B-MTP-GGUF", "UD-IQ4_NL")]

def _card():
    """The GPU whose VRAM and usage we watch: HOMUNCULUS_CARD=/sys/class/drm/cardN/device, else the card with the most VRAM."""
    if os.environ.get("HOMUNCULUS_CARD"): return Path(os.environ["HOMUNCULUS_CARD"])
    best, size = Path("/sys/class/drm/card0/device"), -1
    for d in sorted(Path("/sys/class/drm").glob("card[0-9]*/device")):
        try: n = int((d / "mem_info_vram_total").read_text())
        except Exception: continue
        if n > size: best, size = d, n
    return best


CARD = _card()
SOFT_LIMIT_GB = 22.5      # cancel the running GPU job
HARD_LIMIT_GB = 22.5      # stop/unload the model (protects the desktop)
IDLE_GB = 3.0             # "GPU is free" threshold

UPSCALERS = {"photo": "RealESRGAN_x4plus.pth", "3d_render": "4x-UltraSharp.pth", "anime": "RealESRGAN_x4plus_anime_6B.pth"}

EDIT_W, EDIT_H = 576, 1024    # Qwen-Image output (multiples of 32, portrait 9:16) for A-poses
EDIT_SIZE = {"tpose": (960, 960), "spread": (576, 1024), "relaxed": (576, 1024)}   # T-pose is as wide as it is tall
DEFAULT_POSE = "tpose"
FACE_SIZE = 1024              # face close-up redraw (square)
EDIT_SEEDS = 4
EDIT_ROUNDS = 3               # first round + up to 2 VLM-guided retries
MESH_ATTEMPTS = 2             # rounds of shape candidates per chosen redraw
SHAPE_SEEDS = 3               # shape candidates generated per round (best of N)
MESH_FACES, MESH_TEX = 250000, 4096

FACE_FIT = "auto"          # face texture fit: auto (landmark warp if both faces are readable, else repaint) | landmarks | repaint
FACE_REFINE_EARLY = True   # redraw the face close-up before the 3D step (better face geometry), not only for the texture
FACE_RESHAPE = True        # move the mesh's face features to where the reference has them (before rigging)
FACE_SOURCE = "original"      # the face texture is fitted from: original = your own picture, upscaled (the face as it really is; falls back to the redraw when its landmarks are not readable) | redraw
HAND_POSE_LAYER = True       # set the fingers of every animation clip from a hand-pose library chosen from the prompt (fist, open, grip, point, thumbs up): the motion models do not drive fingers
TEXTURE_MODE = "simple"      # simple: texture from the upscaled picture / chosen redraw only (front projection + landmark face fit, no extra generated images); full: also the face close-up redraw as a reference and Qwen-cleaned side/back views
TEXTURE_VIEWS = True       # texture: project the redraw onto the body front, then clean the head sides, body sides and back from extra views
HAND_REFINE_EARLY = False  # (off) redraw each hand as a close-up before the 3D step
SILHOUETTE_CARVE = True    # delete Pixal3D geometry outside the picture's front outline (fins/plates at the hands)

# auto-riggers you can pick (state "rigger"): key -> (label, ladder variant, extra args). Other riggers need their own skeleton handling.
RIGGERS = {"mia": ("Make-It-Animatable", "default", []),
           "mia_normal": ("Make-It-Animatable, normal-aware weights", "normal_weights", ["--normal"])}
DEFAULT_RIGGER = "mia"
HAND_VIEWS = False         # (off) hand renders, finger counting and hand/fist close-ups in the shape check and the rig check
TPOSE_POSED = True           # mesh-first runs: a mesh that is not in a T/A-pose is rigged with SkinTokens and baked into a T-pose first
TPOSE_DEVICE = "vulkan"        # SkinTokens device (falls back to cpu)
