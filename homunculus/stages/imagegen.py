"""The pipeline's image generation in one place: every redraw (the full-body redraw, the face and hand close-ups, Repair, Retexture, the face repaint) goes through here.
Qwen-Image 2.1 Turbo in ComfyUI by default (config.IMAGE_TURBO: the int8 base + turbo LoRA, 8 steps, about 6 s a picture after the load); if Turbo cannot run, the 30-step model in Unsloth Studio takes over
for the rest of that step (it needs no ComfyUI). Use:  on(log) ... edit(...) ... off()."""
import io, os, subprocess, sys, time
import requests
from PIL import Image
from .. import config as C, gpu
from . import qwen_turbo

sys.path.insert(0, str(C.ROOT))
_mode = {"m": None}            # "turbo" | "studio" | None


def mode(): return _mode["m"]


def _studio_on(log):
    import qwen_edit as q
    gpu.free_all(log, keep="studio"); gpu.wait_for_headroom("qwen_image", log); q.ensure_loaded()


def on(log):
    """Load the image model. Returns 'turbo' or 'studio'."""
    if C.IMAGE_TURBO:
        try: qwen_turbo.up(log); _mode["m"] = "turbo"; return "turbo"
        except Exception as e: log(f"Turbo redraws unavailable ({type(e).__name__}: {str(e)[:140]}); using the 30-step model in Studio")
    _studio_on(log); _mode["m"] = "studio"; return "studio"


def _studio_edit(im, prompt, seed, w, h, ref_res, steps):
    import qwen_edit as q
    for attempt in range(3):          # Studio can still carry a cancel from the previous job: ask again
        r = q.post("/api/inference/images/generate", timeout=900, json={"prompt": prompt, "init_image": q.to_b64(im), "workflow": "edit", "width": w, "height": h,
                   "steps": steps, "seed": seed, "reference_resolution": ref_res})
        if r.status_code == 200 or "cancelled" not in r.text: break
        time.sleep(3); q.ensure_loaded()
    if r.status_code != 200: raise RuntimeError(f"{r.status_code} {r.text[:120]}")
    iid = r.json()["images"][0]["id"]
    return Image.open(io.BytesIO(requests.get(f"{q.API}/api/inference/images/gallery/{iid}/file", timeout=300).content)).convert("RGB")


def edit(im, prompt, seed, size, ref_res=512, log=print, steps=30):
    """One redraw of `im` (PIL, the picture to edit, already at `size`: int or (w, h)). Raises when the model returns nothing."""
    w, h = (size, size) if isinstance(size, int) else size
    if _mode["m"] == "turbo":
        try: return qwen_turbo.edit_image(im, prompt, seed, (w, h), ref_res, log)
        except Exception as e:
            log(f"Turbo redraw failed ({type(e).__name__}: {str(e)[:140]}); switching to the 30-step model in Studio for the rest of this step")
            qwen_turbo.down(); _studio_on(log); _mode["m"] = "studio"
    return _studio_edit(im, prompt, seed, w, h, ref_res, steps)


def off():
    """Drop the image model from VRAM."""
    m, _mode["m"] = _mode["m"], None
    if m == "turbo": qwen_turbo.down()
    elif m == "studio":
        import qwen_edit as q
        try: q.post("/api/inference/images/unload")
        except Exception: pass
