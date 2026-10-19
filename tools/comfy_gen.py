"""Make character pictures from text with the project's Qwen-Image 2.1 Turbo graph (8 steps, a few seconds each after a one-time load):

    .venv/bin/python tools/comfy_gen.py --out ~/Downloads/character_refs --prompts prompts.txt [--seeds 2] [--size 768x1152]

prompts.txt: one line per picture, "name | prompt".  Writes <out>/<name>_s<seed>.png and a prompts.csv next to them.  ComfyUI is started if it is not running (everything else is unloaded from the GPU first) and its models are released at the end.
This is the same graph the app's Redraw stage uses; run `python -m homunculus.orchestrate` or the web app for a full picture-to-character run.  The text-only form (no reference picture) is what is used here."""
import os, sys, csv, argparse, json, shutil
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__))); sys.path.insert(0, ROOT)
from homunculus import config as C, gpu
from homunculus.stages import qwen_turbo as Q
ap = argparse.ArgumentParser(); ap.add_argument("--out", required=True); ap.add_argument("--prompts", required=True); ap.add_argument("--seeds", type=int, default=2); ap.add_argument("--size", default="768x1152"); a = ap.parse_args()
W, H = (int(x) for x in a.size.split("x")); out = os.path.expanduser(a.out); os.makedirs(out, exist_ok=True); rows = []
items = [l.split("|", 1) for l in open(a.prompts) if "|" in l and not l.startswith("#")]
log = lambda m: print(m, flush=True)
Q.up(log)
try:
    for name, prompt in items:
        name, prompt = name.strip(), prompt.strip()
        for s in range(a.seeds):
            seed = 1000 + s; res = Q._run(Q.graph([], prompt, seed, (W, H)), timeout=900); im = res["outputs"]["13"]["images"][0]
            dst = os.path.join(out, f"{name}_s{seed}.png"); shutil.copy(C.COMFY_UI / "output" / im["subfolder"] / im["filename"], dst); rows.append((os.path.basename(dst), prompt)); log(f"  {os.path.basename(dst)}")
finally:
    Q.down()
with open(os.path.join(out, "prompts.csv"), "w", newline="") as f: csv.writer(f).writerows([("file", "prompt")] + rows)
print(f"{len(rows)} pictures -> {out}")
