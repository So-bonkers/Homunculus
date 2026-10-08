"""Trial: does a 4-view turnaround + multiview Pixal3D beat single-image Pixal3D?   Not part of the pipeline.

    .venv/bin/python tools/turnaround_trial.py views  <picture> <out_dir>   # Qwen-Image edit: back / left / right views from the front picture
    .venv/bin/python tools/turnaround_trial.py frame  <picture> <out_dir>   # cut out, one shared scale, black background, 1024 px squares + contact sheet
    .venv/bin/python tools/turnaround_trial.py shape  <out_dir> multi|single [seed]   # Pixal3D shape + texture -> <out_dir>/<mode>.glb (ComfyUI output dir)

Pixal3DMultiViewConditioning: front/left/back/right are 90 degrees apart on an orbit; "left" = the camera sees the character's LEFT side,
so in the left view the character faces the left edge of the image. Every view must be framed at the same scale.
"""
import io, os, sys, threading, time, shutil
from pathlib import Path
ROOT = Path(__file__).resolve().parent.parent
sys.path[:0] = [str(ROOT), str(ROOT / "comfy")]
import numpy as np
import requests
from PIL import Image

SIZE = 1024
KEEP = ("Keep the exact same character: the same helmet, race suit, gloves, shoes, logos, colours, materials and body proportions, "
        "the same arms-out T-pose with open hands, the same scale and the same framing, full body from head to feet, "
        "orthographic camera at the height of the chest, plain light grey background, soft even studio lighting. No new text or objects.")
VIEWS = {
    "back": "Show this same character seen exactly from BEHIND (a 180 degree turnaround of the camera around the character). We see the back of the helmet, the back of the suit and the backs of the hands. ",
    "left": "Show this same character in an exact 90 degree SIDE PROFILE, as the camera moves to the character's LEFT side: the character faces toward the LEFT edge of the image, "
            "we see the character's left side. The arms are stretched out sideways, so from this angle they point straight toward and away from the camera and are foreshortened. ",
    "right": "Show this same character in an exact 90 degree SIDE PROFILE, as the camera moves to the character's RIGHT side: the character faces toward the RIGHT edge of the image, "
             "we see the character's right side. The arms are stretched out sideways, so from this angle they point straight toward and away from the camera and are foreshortened. ",
}


def log(m): print(time.strftime("%H:%M:%S"), m, flush=True)


def views(picture, out, seed=1):
    import qwen_edit as q
    from homunculus import gpu
    os.makedirs(out, exist_ok=True)
    front = Image.open(picture).convert("RGB").resize((SIZE, SIZE), Image.LANCZOS); front.save(f"{out}/front_raw.png")
    b64 = q.to_b64(front)
    gpu.free_all(log, keep="studio"); q.ensure_loaded()
    stop, st = threading.Event(), {"peak": 0.0}
    th = threading.Thread(target=q.watchdog, args=(stop, st), daemon=True); th.start()
    try:
        for name, p in VIEWS.items():
            dst = f"{out}/{name}_raw.png"
            if os.path.exists(dst): continue
            t0 = time.time()
            r = q.post("/api/inference/images/generate", timeout=1800, json={"prompt": p + KEEP, "init_image": b64, "workflow": "edit", "width": SIZE, "height": SIZE,
                       "steps": 30, "seed": seed, "reference_resolution": int(os.environ.get("REFRES", 1024))})
            if r.status_code != 200: log(f"{name}: error {r.status_code} {r.text[:200]}"); continue
            iid = r.json()["images"][0]["id"]
            Image.open(io.BytesIO(requests.get(f"{q.API}/api/inference/images/gallery/{iid}/file", timeout=300).content)).convert("RGB").save(dst)
            log(f"{name}: saved in {time.time() - t0:.0f}s, peak {st['peak']:.1f} GB")
    finally:
        stop.set(); th.join()
        try: q.post("/api/inference/images/unload")
        except Exception: pass


def cutout(im):
    from rembg import remove, new_session
    a = np.asarray(remove(im, session=new_session("u2net")))[..., 3]
    return a > 128


def frame(out):
    """Cut every view out, find one scale for all of them (the widest/tallest extent), centre each on its bounding box, put it on black in a 1024 square at 1/1.1 of the frame."""
    ims, boxes = {}, {}
    for n in ("front", "left", "back", "right"):
        p = f"{out}/{n}_raw.png"
        if not os.path.exists(p): continue
        im = Image.open(p).convert("RGB"); m = cutout(im)
        ys, xs = np.nonzero(m); boxes[n] = (xs.min(), ys.min(), xs.max() + 1, ys.max() + 1); ims[n] = (im, m)
    ext = max(max(b[2] - b[0], b[3] - b[1]) for b in boxes.values()); side = ext * 1.1
    k = SIZE / side
    # vertical centre shared by all views (the front's), so heights line up; horizontal centre per view
    cy = (boxes["front"][1] + boxes["front"][3]) / 2
    sheet = Image.new("RGB", (SIZE * len(ims), SIZE))
    for i, (n, (im, m)) in enumerate(ims.items()):
        b = boxes[n]; cx = (b[0] + b[2]) / 2
        arr = np.asarray(im).copy(); arr[~m] = 0
        canvas = Image.new("RGB", (SIZE, SIZE))
        src = Image.fromarray(arr).resize((round(im.width * k), round(im.height * k)), Image.LANCZOS)
        canvas.paste(src, (round(SIZE / 2 - cx * k), round(SIZE / 2 - cy * k)))
        canvas.save(f"{out}/{n}.png"); sheet.paste(canvas, (i * SIZE, 0))
        log(f"{n}: bbox {b}, framed")
    sheet.resize((sheet.width // 2, sheet.height // 2)).save(f"{out}/sheet_framed.png")


def split(sheet, out):
    """Cut a ready-made sheet (left, front, right, back from left to right, as ChatGPT drew it) into <name>_raw.png, one connected figure each."""
    from scipy import ndimage as ndi
    os.makedirs(out, exist_ok=True)
    im = Image.open(sheet).convert("RGB"); m = cutout(im)
    lab, n = ndi.label(ndi.binary_dilation(m, iterations=3))
    objs = [(ndi.center_of_mass(lab == i)[1], i, int((lab == i).sum())) for i in range(1, n + 1)]
    objs = sorted([o for o in objs if o[2] > 20000])
    log(f"figures found: {[(round(c), a) for c, _, a in objs]}")
    assert len(objs) == 4, "expected four figures"
    for (c, i, a), name in zip(objs, ("left", "front", "right", "back")):
        ys, xs = np.nonzero((lab == i) & m); pad = 20
        im.crop((max(0, xs.min() - pad), max(0, ys.min() - pad), min(im.width, xs.max() + pad), min(im.height, ys.max() + pad))).save(f"{out}/{name}_raw.png")


def shape(out, mode, seed=42):
    import run_px
    from homunculus import gpu, config as C
    inp = C.COMFY_UI / "input"; prefix = f"trial_{Path(out).name}_{mode}"
    if mode == "single":
        shutil.copy(f"{out}/front_raw.png", inp / f"{prefix}_front.png")
        g = run_px.build_tex(f"{prefix}_front.png", prefix, seed)
    else:
        g = run_px.build_tex("x.png", prefix, seed)
        for k in ("122", "193", "192", "248", "303", "312", "55", "56", "242"): g.pop(k, None)
        for i, n in enumerate(("front", "left", "back", "right")):
            if os.path.exists(f"{out}/{n}.png"):
                shutil.copy(f"{out}/{n}.png", inp / f"{prefix}_{n}.png"); g[f"mv{i}"] = {"class_type": "LoadImage", "inputs": {"image": f"{prefix}_{n}.png"}}
        g["298"] = {"class_type": "Pixal3DMultiViewConditioning", "inputs": {"clip_vision_model": ["15", 0], "fov": 20.0,
                    **{n: [f"mv{i}", 0] for i, n in enumerate(("front", "left", "back", "right")) if f"mv{i}" in g}}}
        g["319"]["inputs"]["unet_name"] = "pixal3d_multiview_int8_convrot.safetensors"
    gpu.free_all(log, keep="comfy"); gpu.comfy_start(log)
    res = run_px.run(g, timeout=3600)
    if res: log(f"outputs: {[(k, v) for k, v in res['outputs'].items() if v][:6]}")


if __name__ == "__main__":
    a = sys.argv[1:]
    if a[0] == "views": views(a[1], a[2])
    elif a[0] == "split": split(a[1], a[2])
    elif a[0] == "frame": frame(a[2])
    elif a[0] == "shape": shape(a[1], a[2], int(a[3]) if len(a) > 3 else 42)
