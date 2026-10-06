#!/usr/bin/env python
"""Reusable, VRAM-safe Qwen-Image-2.1 edit via Unsloth Studio's API.

Edit the CONFIG block below, then run:  .venv/bin/python qwen_edit.py
Safety: loads in low_vram mode, uses a small output size, logs VRAM every 0.5 s,
cancels (then unloads) if VRAM crosses the limits, and unloads the model afterwards.
"""
import base64
import io
import os
import sys
import threading
import time
from pathlib import Path

import requests
from PIL import Image

# ----------------------------- CONFIG -----------------------------
INPUT_IMAGE = "views/front_apose.png"
PROMPT = (
    "Edit this image: remove all clothing and accessories (bikini, wristbands, "
    "armbands, heels, necklace, forehead gem, earrings) and show the same adult "
    "character as a neutral, nude 3D-base-mesh-style figure. Keep the exact same "
    "face, hair with both twin tails, body proportions, muscle tone, skin tone, art "
    "style, A-pose (arms about 35 degrees from the body, open relaxed hands) and "
    "plain grey background. Barefoot, feet flat. Smooth, non-explicit anatomy like "
    "an anatomical mannequin. Full body, no text, no watermark."
)
OUTPUT_IMAGE = "views/front_base.png"
SEED = 1
REFERENCE_RESOLUTION = 512   # px (by area) each condition image is encoded at; 1024 default uses much more VRAM
REFERENCE_IMAGES = []   # extra reference images (Qwen-Image-2.1 allows up to 10 in total)

API = "http://127.0.0.1:8888"
MODEL_REPO = "unsloth/Qwen-Image-2.1-GGUF"
MODEL_FILE = "qwen-image-2.1-F16.gguf"   # swap for a smaller quant (e.g. Q8_0) if desired
MEMORY_MODE = "low_vram"                 # auto | fast | balanced | low_vram

import os
MAX_SIDE = int(os.environ.get("QWEN_MAX_SIDE", 896))   # longest output side in px (snapped to multiples of 32)
STEPS = 30
UNLOAD_AFTER = True   # free VRAM when done

MIN_FREE_GB = 12.0    # refuse to start if less VRAM than this is free
SOFT_LIMIT_GB = 20.5  # cancel the generation above this
HARD_LIMIT_GB = 22.0  # unload the model above this (protects the desktop)
VRAM_LOG = os.path.join(os.path.dirname(os.path.abspath(__file__)), "vram.log")
CARD = "/sys/class/drm/card1/device"
# ------------------------------------------------------------------

GB = 1024 ** 3


def vram_used_gb():
    return int(Path(f"{CARD}/mem_info_vram_used").read_text()) / GB


def vram_total_gb():
    return int(Path(f"{CARD}/mem_info_vram_total").read_text()) / GB


def post(path, **kw):
    return requests.post(f"{API}{path}", timeout=kw.pop("timeout", 60), **kw)


def is_loaded():
    return requests.get(f"{API}/api/inference/images/status", timeout=10).json().get("loaded", False)


def ensure_loaded():
    if is_loaded():
        return
    print(f"Loading {MODEL_FILE} ({MEMORY_MODE})...")
    post("/api/inference/images/load", json={
        "model_path": MODEL_REPO, "gguf_filename": MODEL_FILE, "memory_mode": MEMORY_MODE})
    while True:
        p = requests.get(f"{API}/api/inference/images/load-progress", timeout=10).json()
        if p.get("error"):
            sys.exit(f"Load failed: {p['error']}")
        if p["phase"] == "ready":
            return
        time.sleep(3)


def watchdog(stop, state):
    with open(VRAM_LOG, "a") as log:
        log.write(f"# run {time.strftime('%F %T')} total={vram_total_gb():.1f}GB\n")
        while not stop.is_set():
            used = vram_used_gb()
            state["peak"] = max(state["peak"], used)
            log.write(f"{time.time():.1f} {used:.2f}\n")
            log.flush()
            if used > HARD_LIMIT_GB and not state.get("unloaded"):
                state["unloaded"] = True
                print(f"!! VRAM {used:.1f} GB > hard limit; unloading model")
                post("/api/inference/images/generate/cancel")
                post("/api/inference/images/unload")
            elif used > SOFT_LIMIT_GB and not state.get("cancelled"):
                state["cancelled"] = True
                print(f"!! VRAM {used:.1f} GB > soft limit; cancelling")
                post("/api/inference/images/generate/cancel")
            stop.wait(0.5)


def to_b64(im):
    buf = io.BytesIO()
    im.save(buf, "PNG")
    return "data:image/png;base64," + base64.b64encode(buf.getvalue()).decode()


def main():
    global INPUT_IMAGE, OUTPUT_IMAGE, PROMPT, SEED, REFERENCE_IMAGES
    # optional overrides: qwen_edit.py [input] [output] [prompt] [seed] [ref1,ref2,...]
    args = sys.argv[1:]
    if len(args) > 0:
        INPUT_IMAGE = args[0]
    if len(args) > 1:
        OUTPUT_IMAGE = args[1]
    if len(args) > 2:
        PROMPT = args[2]
    if len(args) > 3:
        SEED = int(args[3])
    if len(args) > 4:
        REFERENCE_IMAGES = [x for x in args[4].split(",") if x]
    free =vram_total_gb() - vram_used_gb()
    if free < MIN_FREE_GB:
        sys.exit(f"Only {free:.1f} GB VRAM free (need {MIN_FREE_GB}). Close GPU apps first.")

    img = Image.open(INPUT_IMAGE).convert("RGB")
    scale = MAX_SIDE / max(img.size)
    w = max(32, round(img.width * scale / 32) * 32)
    h = max(32, round(img.height * scale / 32) * 32)
    img = img.resize((w, h), Image.LANCZOS)
    b64 = to_b64(img)
    refs = [to_b64(Image.open(p).convert("RGB")) for p in REFERENCE_IMAGES]

    ensure_loaded()
    stop, state = threading.Event(), {"peak": 0.0}
    t = threading.Thread(target=watchdog, args=(stop, state), daemon=True)
    t.start()
    try:
        print(f"Generating {w}x{h}, {STEPS} steps...")
        r = post("/api/inference/images/generate", timeout=3600, json={
            "prompt": PROMPT, "init_image": b64, "workflow": "edit",
            "reference_images": refs or None,
            "reference_resolution": REFERENCE_RESOLUTION,
            "width": w, "height": h, "steps": STEPS, "seed": SEED})
        r.raise_for_status()
        image_id = r.json()["images"][0]["id"]
        out = requests.get(f"{API}/api/inference/images/gallery/{image_id}/file", timeout=60)
        out.raise_for_status()
        Path(OUTPUT_IMAGE).write_bytes(out.content)
        print(f"Saved {OUTPUT_IMAGE}")
    finally:
        stop.set()
        t.join()
        print(f"Peak VRAM: {state['peak']:.1f} GB (log: {VRAM_LOG})")
        if UNLOAD_AFTER:
            try:
                post("/api/inference/images/unload")
            except requests.RequestException:
                pass


if __name__ == "__main__":
    main()
