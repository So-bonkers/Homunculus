"""The depth phase before the 3D shape (single-picture runs): the back and the sides of the character, generated under a depth map, so the shape model sees four views that agree.

    1. a quick proxy shape from the front picture (one Pixal3D pass, about 3 minutes): its back and sides are guessed, but its pose and proportions are ONE consistent body;
    2. depth maps of the proxy seen from the back (and, with HOMUNCULUS_DEPTH_VIEWS_SIDES=1, the left and the right) (blender_depth_views.py);
    3. Qwen-Image 2.1 Turbo (ComfyUI, 8 steps) with the Fun ControlNet Union draws each view under its depth map; the back first as an unguided redraw of the front picture (so the front's logos cannot leak onto
       the back), which then is the back view's reference;
    4. a view is kept only if its outline agrees with the proxy's silhouette for that side (IoU >= MIN_IOU, no language model involved): arms that hang down in a side view, a wrong pose, a different scale are dropped;
    5. the kept views and the front are framed at one scale (turnaround.frame) and go to the multiview Pixal3D shape pass, like the four views of a turnaround sheet.
Tried on Miles (views agreed on scale within 1 %) and on the F1 driver (back: logos and lettering on the back, outline IoU 0.88; the sides drew the arms hanging down or forward, IoU 0.78 and 0.91, so they are off by default). Not used for turnaround-sheet runs (the sheet is the views) or mesh input."""
import os, shutil, subprocess, time
import numpy as np
from PIL import Image
from .. import config as C, gpu
from . import comfy, qwen_turbo, turnaround

SIZE = 768
RES = 640               # reference resolution of the text encoder (what the experiments used)
STRENGTH = 0.8          # ControlNet strength
SEED = 5
MIN_IOU = float(os.environ.get("HOMUNCULUS_DEPTH_VIEW_IOU", "0.80"))
KEEP = ("Keep the exact same character and costume as in the first image: the same clothing, colours, materials, logos, accessories and shoes, the same body proportions, scale and framing, the whole body "
        "from head to feet in view. Plain light grey background, soft even studio lighting, no motion blur, no scenery, no new text. The other pictures show the same character from other angles: use them for the "
        "details the first picture cannot show.")
VIEWS = {"back": "The same character seen exactly from BEHIND, the camera 180 degrees around: the back of the head, the back of the clothing and the legs; any emblem or logo on the chest is on the front only and must not appear. ",
         "left": "The same character in a strict 90 degree side profile from the character's LEFT side, facing the left edge of the picture. ",
         "right": "The same character in a strict 90 degree side profile from the character's RIGHT side, facing the right edge of the picture. "}
BACK_FIRST = ("Show this same character seen exactly from BEHIND (a 180 degree turnaround of the camera around the character): we see the back of the head, the back of the clothing and the backs of the hands. "
              "Anything on the chest is on the front only and must not appear. ")
SIDES = os.environ.get("HOMUNCULUS_DEPTH_VIEWS_SIDES", "0") == "1"      # the side views are opt-in: with the T-pose arms pointing at the camera the model draws them hanging down (or forward), which the outline check cannot always catch
ORDER = ("back", "left", "right") if SIDES else ("back",)


def models_ok():
    """The Qwen-Image 2.1 files, the turbo LoRA and the ControlNet are in ComfyUI's model folders."""
    m = C.COMFY_UI / "models"
    need = [m / "diffusion_models" / qwen_turbo.MODEL, m / "text_encoders" / qwen_turbo.TEXT, m / "vae" / qwen_turbo.VAE, m / "loras" / qwen_turbo.LORA, m / "model_patches" / qwen_turbo.PATCH]
    return [p.name for p in need if not p.exists() or p.stat().st_size < 1e6]


def _square(path, size):
    """The picture on its own background colour in a square (what the references and the unguided back are made from)."""
    im = Image.open(path).convert("RGB"); w, h = im.size; s = max(w, h)
    a = np.asarray(im); bg = tuple(int(x) for x in np.median(np.concatenate([a[:6].reshape(-1, 3), a[-6:].reshape(-1, 3), a[:, :6].reshape(-1, 3), a[:, -6:].reshape(-1, 3)]), axis=0))
    c = Image.new("RGB", (s, s), bg); c.paste(im, ((s - w) // 2, (s - h) // 2)); return c.resize((size, size), Image.LANCZOS)


def _iou(a, b):
    u = (a | b).sum(); return float((a & b).sum()) / u if u else 0.0


def make(front_png, out_dir, tag, log):
    """Returns {"views": {name: framed picture} (front plus the generated views that agreed), "raw": {name: picture}, "iou": {name: IoU}, "dropped": [names]} or None when no generated view agreed."""
    os.makedirs(out_dir, exist_ok=True); t0 = time.time()
    proxy = comfy.shape(front_png, os.path.join(out_dir, "proxy"), f"dv_{tag}", 42, log)                  # 1. the proxy shape (single picture)
    ddir = os.path.join(out_dir, "depth")                                                                  # 2. depth maps of the proxy
    r = subprocess.run([C.BLENDER, "-b", "--python", str(C.ROOT / "homunculus" / "blender_depth_views.py"), "--", proxy, ddir, str(SIZE), ",".join(ORDER)], capture_output=True, text=True, timeout=900)
    if not all(os.path.exists(os.path.join(ddir, f"{v}_depth.png")) for v in ORDER): raise RuntimeError("depth maps of the proxy shape failed: " + (r.stdout + r.stderr)[-300:])
    front = _square(front_png, SIZE); front.save(os.path.join(out_dir, "front_ref.png"))
    qwen_turbo.up(log); gen = {}
    try:
        t1 = time.time()
        back_first = qwen_turbo.edit_image(front, BACK_FIRST + KEEP, SEED, SIZE, RES, log); back_first.save(os.path.join(out_dir, "back_unguided.png"))      # 3. the back without a depth map first
        for v in ORDER:
            depth = Image.open(os.path.join(ddir, f"{v}_depth.png")).convert("RGB")
            first, refs = (back_first, ()) if v == "back" else (front, ())
            im = qwen_turbo.edit_image(first, VIEWS[v] + KEEP, SEED, SIZE, RES, log, control=depth, strength=STRENGTH, refs=refs)
            p = os.path.join(out_dir, f"{v}_gen.png"); im.save(p); gen[v] = p
        log(f"[views] {len(gen)} views drawn in {time.time() - t1:.0f}s (Turbo + depth ControlNet)")
    finally:
        qwen_turbo.down()
    iou, keep, dropped = {}, {}, []                                                                         # 4. does each view agree with the proxy's outline?
    for v, p in gen.items():
        want = np.asarray(Image.open(os.path.join(ddir, f"{v}_mask.png")).convert("L")) > 128
        got = turnaround._cutout(Image.open(p).convert("RGB").resize(want.shape[::-1], Image.LANCZOS))
        iou[v] = _iou(want, got)
        if iou[v] >= MIN_IOU: keep[v] = p
        else: dropped.append(v)
    log("[views] outline agreement with the proxy (IoU, need " + f"{MIN_IOU:.2f}): " + ", ".join(f"{v} {iou[v]:.2f}" + ("" if v in keep else " DROPPED") for v in ORDER if v in iou))
    if not keep: return None
    raw = {"front": os.path.join(out_dir, "front_ref.png"), **keep}                                         # 5. one scale for all, black background, 1024 px squares
    os.makedirs(os.path.join(out_dir, "framed"), exist_ok=True)
    views = turnaround.frame(raw, os.path.join(out_dir, "framed"), log, equal_height=True)
    log(f"[views] done in {time.time() - t0:.0f}s: front + {', '.join(keep)}")
    return {"views": views, "raw": raw, "iou": iou, "dropped": dropped, "proxy": proxy, "unguided_back": os.path.join(out_dir, "back_unguided.png"), "depth_dir": ddir}
