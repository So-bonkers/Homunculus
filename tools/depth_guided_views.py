"""Experiment: turnaround views generated UNDER A DEPTH MAP of a coarse proxy mesh, so the four views agree about pose, arms and scale by construction (what per-view generation could not do).
    .venv/bin/python tools/depth_guided_views.py <out_dir> <front_tpose.png> <proxy.glb|--make-proxy> [ref ...] [--views back,left,right] [--strength 0.8] [--seed 5]
        [--control depth|normal]  [--back-first PICTURE]  [--turbo 1]  (8-step Turbo: base model + turbo LoRA, Turbo's own sigma schedule)  (the back view takes this picture as its first reference instead of the front T-pose)
The proxy is a rough mesh of the character (the single-image Pixal3D shape of the front T-pose is enough: its back and sides are guessed, but its POSE and PROPORTIONS are one consistent body).
Depth renders (blender_depth_views.py) feed the Qwen-Image 2.1 Fun ControlNet Union; the front T-pose and the other pictures go in as references. Needs ComfyUI with the Qwen-Image 2.1 files (see
the model list in docs/TURNAROUND.md). Runs in ComfyUI, not Unsloth Studio (Studio has no ControlNet)."""
import json, os, shutil, subprocess, sys, time, uuid
from pathlib import Path
ROOT = Path(__file__).resolve().parent.parent
sys.path[:0] = [str(ROOT), str(ROOT / "comfy")]
import requests
from PIL import Image
from homunculus import config as C, gpu

MODEL, TEXT, VAE, PATCH = "qwen_image_2.1_int8_convrot.safetensors", "qwen3vl_8b_int8_convrot.safetensors", "qwen_image_2.1_vae_bf16.safetensors", "qwen_image_2.1_fun_controlnet_union_int8_convrot.safetensors"
KEEP = ("Keep the exact same character and costume as in the first image: the same hood, mask, jacket, suit pattern, shorts, gloves and shoes, the same scale and framing, the whole body from head to feet in view. "
        "Plain light grey background, soft even studio lighting, no motion blur, no scenery, no text. The other pictures show the same character from other angles: use them for the details the first picture cannot show.")
VIEWS = {"back": "The same character seen exactly from BEHIND, the camera 180 degrees around: the back of the hood, jacket and legs; the chest emblem is on the front only and must not appear. ",
         "left": "The same character in a strict 90 degree side profile from the character's LEFT side, facing the left edge of the picture. ",
         "right": "The same character in a strict 90 degree side profile from the character's RIGHT side, facing the right edge of the picture. ",
         "front": "The same character seen exactly from the FRONT. ",
         "top": "The same character seen exactly from DIRECTLY ABOVE, the camera high above looking straight down: the top of the head or helmet, the shoulders and the tops of the arms; the character's front is toward the bottom of the picture. ",
         "bottom": "The same character seen exactly from DIRECTLY BELOW, the camera under the character looking straight up: the soles of the shoes, the underside of the legs, hips and chest; the character's front is toward the top of the picture. "}


LORA = "qwen_image_2.1_turbo_lora_avg_rank_178_bf16.safetensors"
TURBO_SIGMAS = "1.0, 0.978453, 0.95418, 0.926626, 0.89508, 0.845148, 0.704534, 0.414568, 0.0"      # Qwen-Image-2.1-Turbo's shipped 8-step schedule (sample_sigmas in its model_index.json), plus the final 0


def graph(depth_name, ref_names, prompt, seed, strength, size=768, res=640, steps=25, turbo=False):
    g = {"1": {"class_type": "UNETLoader", "inputs": {"unet_name": MODEL, "weight_dtype": "default"}},
         "2": {"class_type": "CLIPLoader", "inputs": {"clip_name": TEXT, "type": "qwen_image", "device": "default"}},
         "3": {"class_type": "VAELoader", "inputs": {"vae_name": VAE}},
         "4": {"class_type": "QwenImage21Cache", "inputs": {"model": ["1", 0], "device": "auto", "dtype": "default"}},
         "5": {"class_type": "ModelPatchLoader", "inputs": {"name": PATCH}},
         "6": {"class_type": "LoadImage", "inputs": {"image": depth_name}},
         "7": {"class_type": "QwenImageDiffsynthControlnet", "inputs": {"model": ["4", 0], "model_patch": ["5", 0], "vae": ["3", 0], "image": ["6", 0], "strength": strength}},
         "9": {"class_type": "TextEncodeQwenImage21", "inputs": {"clip": ["2", 0], "prompt": prompt, "negative_prompt": "", "resolution": res, "vae": ["3", 0]}},
         "10": {"class_type": "EmptyLatentImage", "inputs": {"width": size, "height": size, "batch_size": 1}},
         "11": {"class_type": "KSampler", "inputs": {"model": ["7", 0], "seed": seed, "steps": steps, "cfg": 1.0, "sampler_name": "euler", "scheduler": "simple", "positive": ["9", 0], "negative": ["9", 1], "latent_image": ["10", 0], "denoise": 1.0}},
         "12": {"class_type": "VAEDecode", "inputs": {"samples": ["11", 0], "vae": ["3", 0]}},
         "13": {"class_type": "SaveImage", "inputs": {"images": ["12", 0], "filename_prefix": "depthviews/v"}}}
    if turbo:      # the 8-step distilled model = the base int8 model + the Comfy-Org turbo LoRA (rank 178), sampled on the schedule Turbo ships with, CFG 1
        g["1b"] = {"class_type": "LoraLoaderModelOnly", "inputs": {"model": ["1", 0], "lora_name": LORA, "strength_model": 1.0}}; g["4"]["inputs"]["model"] = ["1b", 0]
        g["20"] = {"class_type": "ManualSigmas", "inputs": {"sigmas": TURBO_SIGMAS}}; g["21"] = {"class_type": "KSamplerSelect", "inputs": {"sampler_name": "euler"}}
        g["11"] = {"class_type": "SamplerCustom", "inputs": {"model": ["7", 0], "add_noise": True, "noise_seed": seed, "cfg": 1.0, "positive": ["9", 0], "negative": ["9", 1], "sampler": ["21", 0], "sigmas": ["20", 0], "latent_image": ["10", 0]}}
        g["12"]["inputs"]["samples"] = ["11", 1]
    for i, n in enumerate(ref_names):
        g[f"r{i}"] = {"class_type": "LoadImage", "inputs": {"image": n}}; g["9"]["inputs"][f"images.image_{i + 1}"] = [f"r{i}", 0]
    return g


def run(g, timeout=1800):
    r = requests.post(C.COMFY_API + "/prompt", json={"prompt": g, "client_id": uuid.uuid4().hex})
    if r.status_code != 200: sys.exit("graph rejected: " + r.text[:2500])
    pid = r.json()["prompt_id"]; t0 = time.time()
    while time.time() - t0 < timeout:
        h = requests.get(f"{C.COMFY_API}/history/{pid}").json()
        if pid in h:
            res = h[pid]
            if res["status"]["status_str"] != "success": sys.exit("failed: " + json.dumps(res["status"]["messages"][-3:])[:2000])
            return res
        time.sleep(3)
    sys.exit("timeout")


def main():
    a = sys.argv[1:]
    def opt(f, d):
        if f in a: i = a.index(f); v = a[i + 1]; del a[i:i + 2]; return v
        return d
    views = opt("--views", "back,left,right").split(","); strength = float(opt("--strength", 0.8)); seed = int(opt("--seed", 5)); control = opt("--control", "depth"); back_first = opt("--back-first", None); turbo = opt("--turbo", "0") == "1"
    out, front, proxy, refs = Path(a[0]), a[1], a[2], a[3:]; out.mkdir(parents=True, exist_ok=True); log = print
    if proxy == "--make-proxy":
        from homunculus.stages import comfy
        proxy = comfy.shape(front, str(out / "proxy"), "proxy", 42, log)                       # the single-image shape pass of the front T-pose (about 2 minutes)
    if not (out / "depth" / f"{views[0]}_{control}.png").exists() or True: subprocess.run([C.BLENDER, "-b", "--python", str(ROOT / "homunculus" / "blender_depth_views.py"), "--", proxy, str(out / "depth"), "768", ",".join(views)], capture_output=True, text=True, check=True)
    gpu.free_all(log, keep="comfy"); gpu.comfy_start(log); u = uuid.uuid4().hex[:6]
    def to_input(p, tag): nm = f"dg_{u}_{tag}.png"; Image.open(p).convert("RGB").save(C.COMFY_UI / "input" / nm); return nm
    names = [to_input(front, "front")] + [to_input(p, f"ref{i}") for i, p in enumerate(refs)]
    for v in views:
        nm = [to_input(back_first, "backfirst")] + names[1:] if (v == "back" and back_first) else names      # the back view's first reference: not the front picture, so its emblem cannot leak in
        t0 = time.time(); res = run(graph(to_input(out / "depth" / f"{v}_{control}.png", f"c_{v}"), nm, VIEWS[v] + KEEP, seed, strength, turbo=turbo))
        im = res["outputs"]["13"]["images"][0]; shutil.copy(C.COMFY_UI / "output" / im["subfolder"] / im["filename"], out / f"{v}.png"); log(f"{v}: done in {time.time() - t0:.0f}s")
    shutil.copy(front, out / "front.png"); gpu.comfy_stop()


if __name__ == "__main__":
    main()
