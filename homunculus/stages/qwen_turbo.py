"""Qwen-Image 2.1 Turbo edits in ComfyUI: the int8 base model plus the Comfy-Org turbo LoRA (rank 178), 8 steps on the schedule Turbo ships with, CFG 1.
About 2.6 times faster per picture than the 30-step model (docs/TURNAROUND.md has the comparison). Used by Repair for its redraws (config.REPAIR_TURBO); the picture goes in as the reference to edit.
Needs the Qwen-Image 2.1 files in ComfyUI (see the model list in docs/TURNAROUND.md) and the turbo LoRA in models/loras."""
import json, os, shutil, time, uuid
import requests
from PIL import Image
from .. import config as C, gpu

MODEL, TEXT, VAE = "qwen_image_2.1_int8_convrot.safetensors", "qwen3vl_8b_int8_convrot.safetensors", "qwen_image_2.1_vae_bf16.safetensors"
LORA = "qwen_image_2.1_turbo_lora_avg_rank_178_bf16.safetensors"
TURBO_SIGMAS = "1.0, 0.978453, 0.95418, 0.926626, 0.89508, 0.845148, 0.704534, 0.414568, 0.0"      # Qwen-Image-2.1-Turbo's shipped 8-step schedule (sample_sigmas in its model_index.json), plus the final 0


def graph(ref_names, prompt, seed, size, res=512):
    g = {"1": {"class_type": "UNETLoader", "inputs": {"unet_name": MODEL, "weight_dtype": "default"}},
         "2": {"class_type": "CLIPLoader", "inputs": {"clip_name": TEXT, "type": "qwen_image", "device": "default"}},
         "3": {"class_type": "VAELoader", "inputs": {"vae_name": VAE}},
         "1b": {"class_type": "LoraLoaderModelOnly", "inputs": {"model": ["1", 0], "lora_name": LORA, "strength_model": 1.0}},
         "4": {"class_type": "QwenImage21Cache", "inputs": {"model": ["1b", 0], "device": "auto", "dtype": "default"}},
         "9": {"class_type": "TextEncodeQwenImage21", "inputs": {"clip": ["2", 0], "prompt": prompt, "negative_prompt": "", "resolution": res, "vae": ["3", 0]}},
         "10": {"class_type": "EmptyLatentImage", "inputs": {"width": size, "height": size, "batch_size": 1}},
         "20": {"class_type": "ManualSigmas", "inputs": {"sigmas": TURBO_SIGMAS}}, "21": {"class_type": "KSamplerSelect", "inputs": {"sampler_name": "euler"}},
         "11": {"class_type": "SamplerCustom", "inputs": {"model": ["4", 0], "add_noise": True, "noise_seed": seed, "cfg": 1.0, "positive": ["9", 0], "negative": ["9", 1],
                                                       "sampler": ["21", 0], "sigmas": ["20", 0], "latent_image": ["10", 0]}},
         "12": {"class_type": "VAEDecode", "inputs": {"samples": ["11", 1], "vae": ["3", 0]}},
         "13": {"class_type": "SaveImage", "inputs": {"images": ["12", 0], "filename_prefix": "qwen_turbo/v"}}}
    for i, n in enumerate(ref_names):
        g[f"r{i}"] = {"class_type": "LoadImage", "inputs": {"image": n}}; g["9"]["inputs"][f"images.image_{i + 1}"] = [f"r{i}", 0]
    return g


def _run(g, timeout=900):
    r = requests.post(C.COMFY_API + "/prompt", json={"prompt": g, "client_id": uuid.uuid4().hex}, timeout=60)
    if r.status_code != 200: raise RuntimeError("ComfyUI rejected the Turbo graph: " + r.text[:600])
    pid = r.json()["prompt_id"]; t0 = time.time()
    while time.time() - t0 < timeout:
        h = requests.get(f"{C.COMFY_API}/history/{pid}", timeout=60).json()
        if pid in h:
            res = h[pid]
            if res["status"]["status_str"] != "success": raise RuntimeError("Turbo redraw failed in ComfyUI: " + json.dumps(res["status"]["messages"][-3:])[:600])
            return res
        time.sleep(2)
    raise RuntimeError("Turbo redraw timed out")


def edit_many(image, prompt, seeds, size, out_dir, log, tag="redraw"):
    """Redraw `image` (a PIL picture, used as the reference to edit) once per seed with ComfyUI kept loaded between seeds. Returns {seed: path} of the pictures that came out.
    Raises when ComfyUI cannot be started or the first picture fails (the caller falls back to the 30-step model)."""
    os.makedirs(out_dir, exist_ok=True)
    gpu.free_all(log, keep="comfy"); gpu.comfy_start(log)
    u = uuid.uuid4().hex[:6]; nm = f"qt_{u}.png"; image.convert("RGB").save(C.COMFY_UI / "input" / nm); outs = {}
    try:
        for sd in seeds:
            t0 = time.time()
            try: res = _run(graph([nm], prompt, sd, size), timeout=900)
            except Exception as e:
                if not outs: raise
                log(f"Turbo redraw seed {sd} failed: {str(e)[:120]}"); continue
            im = res["outputs"]["13"]["images"][0]; p = os.path.join(out_dir, f"{tag}_{sd}.png")
            shutil.copy(C.COMFY_UI / "output" / im["subfolder"] / im["filename"], p); outs[sd] = p; log(f"Turbo redraw seed {sd}: {time.time() - t0:.0f}s")
    finally:
        try: os.remove(C.COMFY_UI / "input" / nm)
        except OSError: pass
        gpu.comfy_free()          # drop the models from VRAM (the next step, Pixal3D, needs the room); the server itself stays up
    return outs
