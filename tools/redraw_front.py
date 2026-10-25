"""Redraw a character's front picture with a changed instruction (Qwen-Image edit, Turbo, in ComfyUI), several seeds, e.g. to level a tilted head or to fix the proportions.
    .venv/bin/python tools/redraw_front.py --front front.png --out DIR --prompt "..." [--seeds 6] [--first-seed 910] [--ref approved_face.png ...]
Writes DIR/front_s<seed>.png and DIR/contact.png (all candidates side by side). Waits for the GPU lock the pipeline uses."""
import os, sys, argparse, fcntl
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__))); sys.path.insert(0, ROOT)
from PIL import Image
from homunculus import config as C
from homunculus.stages import qwen_turbo as Q
ap = argparse.ArgumentParser(); ap.add_argument("--front", required=True); ap.add_argument("--out", required=True); ap.add_argument("--prompt", required=True); ap.add_argument("--seeds", type=int, default=6); ap.add_argument("--first-seed", type=int, default=910); ap.add_argument("--ref", action="append", default=[], help="extra reference picture(s) the edit may draw on (e.g. an approved face)"); a = ap.parse_args()
os.makedirs(a.out, exist_ok=True); im = Image.open(a.front).convert("RGB"); W, H = im.size
lf = open(C.RUNS / ".homunculus.lock", "a+"); print("waiting for the GPU lock ...", flush=True); fcntl.flock(lf, fcntl.LOCK_EX); log = lambda m: print(m, flush=True)
Q.up(log); outs = []
try:
    for s in range(a.seeds):
        seed = a.first_seed + s; f = os.path.join(a.out, f"front_s{seed}.png"); Q.edit_image(im, a.prompt, seed, (W, H), 1024, log, refs=[Image.open(r).convert("RGB") for r in a.ref]).save(f); outs.append(f); log("wrote " + f)
finally:
    Q.down(); lf.close()
ims = [Image.open(f).crop((int(W * .15), int(H * .30), int(W * .85), H)) for f in outs]; cw, ch = ims[0].size; sheet = Image.new("RGB", (cw * len(ims), ch))
for i, c in enumerate(ims): sheet.paste(c, (i * cw, 0))
sheet.save(os.path.join(a.out, "contact.png")); print("contact sheet:", os.path.join(a.out, "contact.png"))
