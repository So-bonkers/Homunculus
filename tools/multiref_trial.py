"""Trial: does a T-pose redraw get better when the other pictures of the character are passed as references?
    .venv/bin/python tools/multiref_trial.py <out_dir> <main_picture> [reference ...]            (no references = the pipeline's single-picture redraw)
Qwen-Image 2.1 edit takes the first picture as the one to redraw and up to 9 more as references (reference_images); not part of the pipeline."""
import io, os, sys, threading, time
from pathlib import Path
ROOT = Path(__file__).resolve().parent.parent
sys.path[:0] = [str(ROOT)]
import requests
from PIL import Image
import qwen_edit as q
from homunculus import gpu

PROMPT = ("Redraw the character of the first image as a clean full-body character-sheet pose: standing straight, facing the camera, in a T-pose with both arms stretched out straight to the sides, "
          "open hands with five separated fingers, legs straight and slightly apart, the whole body from head to feet in view. Keep the exact same character and costume, including every detail of the "
          "mask, hood, jacket, suit pattern, emblem, shorts and shoes{refs}. Plain light grey background, soft even studio lighting, no text, no motion blur, no scenery.")
REFS_TXT = " as they appear in the other pictures (they show the same character from other angles: use them to get the details that the first picture hides)"
W, H, SEED = 576, 1024, 11


def fit(path, long_side=1024):
    im = Image.open(path).convert("RGB"); k = long_side / max(im.size); return im.resize((max(32, round(im.width * k / 32) * 32), max(32, round(im.height * k / 32) * 32)), Image.LANCZOS)


def main():
    out, main_p, refs = sys.argv[1], sys.argv[2], sys.argv[3:]
    os.makedirs(out, exist_ok=True); log = print
    gpu.free_all(log, keep="studio"); q.ensure_loaded()
    stop, st = threading.Event(), {"peak": 0.0}; th = threading.Thread(target=q.watchdog, args=(stop, st), daemon=True); th.start()
    try:
        t0 = time.time()
        body = {"prompt": PROMPT.format(refs=REFS_TXT if refs else ""), "init_image": q.to_b64(fit(main_p)), "workflow": "edit", "width": W, "height": H, "steps": 30, "seed": SEED, "reference_resolution": 512}
        if refs: body["reference_images"] = [q.to_b64(fit(p, 768)) for p in refs]
        r = q.post("/api/inference/images/generate", timeout=1800, json=body)
        if r.status_code != 200: sys.exit(f"error {r.status_code}: {r.text[:300]}")
        iid = r.json()["images"][0]["id"]
        Image.open(io.BytesIO(requests.get(f"{q.API}/api/inference/images/gallery/{iid}/file", timeout=300).content)).convert("RGB").save(f"{out}/redraw.png")
        log(f"done in {time.time() - t0:.0f}s with {len(refs)} reference picture(s), peak VRAM {st['peak']:.1f} GB")
    finally:
        stop.set(); th.join()
        try: q.post("/api/inference/images/unload")
        except Exception: pass


if __name__ == "__main__":
    main()
