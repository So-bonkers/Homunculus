"""Texture a mesh from one reference picture with UltraTex (see homunculus/ultratex.py):

    .venv/bin/python tools/ultratex_run.py --mesh mesh.glb --ref front.png --name vex [--res 1024] [--steps 25] [--attention comfy_default|ultratex_sparse] [--out dir]

Writes the textured GLB (UltraTex's own UV layout), the albedo atlas and the normal views into runs/_ultratex/<name>."""
import os, sys, argparse
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__))); sys.path.insert(0, ROOT)
from homunculus import ultratex
ap = argparse.ArgumentParser(); ap.add_argument("--mesh", required=True); ap.add_argument("--ref", required=True); ap.add_argument("--name", required=True); ap.add_argument("--out", default=None)
ap.add_argument("--res", type=int, default=1024); ap.add_argument("--steps", type=int, default=25); ap.add_argument("--seed", type=int, default=12345); ap.add_argument("--weight-power", type=float, default=4.0); ap.add_argument("--best-view", type=float, default=0.5); ap.add_argument("--feather", type=float, default=6.0); ap.add_argument("--attention", default="comfy_default", choices=["comfy_default", "ultratex_sparse"]); a = ap.parse_args()
print("->", ultratex.paint(a.mesh, a.ref, a.out or os.path.join(ROOT, "runs", "_ultratex", a.name), print, name=a.name, res=a.res, steps=a.steps, seed=a.seed, attention=a.attention, weight_power=a.weight_power, best_view=a.best_view, feather=a.feather))
