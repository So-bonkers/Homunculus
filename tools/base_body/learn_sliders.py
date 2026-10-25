"""Learn our own sliders from the characters we have: what the stock sliders cannot say is left in each character's residual offset field (fit_base.py stage 4); a PCA per body part over all characters turns it into new sliders.
    gvhmr/.venv/bin/python tools/base_body/learn_sliders.py [--parts head,torso,arms,hands,legs,feet] [--max 4] [--var 0.9]
Reads runs/base_fits/*/fit.npz (offsets [13380,3] in the base's own units), writes tools/base_body/learned.npz: fields [K,13380,3] (a slider at +1 is +1 standard deviation of the characters' scores), names 'learned/<part>-<i>', the variance explained, the characters used.
Offsets include garments (the characters are clothed): the first components of each part may be bulk of clothing rather than body; look at them before keeping them."""
import os, sys, glob, argparse, numpy as np
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__))); from model import Base
ap = argparse.ArgumentParser(); ap.add_argument("--parts", default="head,torso,arms,hands,legs,feet"); ap.add_argument("--max", type=int, default=4); ap.add_argument("--var", type=float, default=0.9); ap.add_argument("--exclude", default="", help="comma list of characters to leave out"); a = ap.parse_args()
B = Base(); names = B.bone_names; W = B.W.numpy(); dom = np.array([names[i] for i in W.argmax(1)])
PART = {"head": ("Head", "Neck"), "torso": ("Hips", "Spine", "Spine1", "Spine2", "LeftShoulder", "RightShoulder"), "arms": ("LeftArm", "RightArm", "LeftForeArm", "RightForeArm"), "legs": ("LeftUpLeg", "RightUpLeg", "LeftLeg", "RightLeg"), "feet": ("LeftFoot", "RightFoot", "LeftToeBase", "RightToeBase")}
def part_mask(p):
    if p == "hands": return np.array(["Hand" in d.replace("mixamorig:", "") and "Fore" not in d for d in dom])
    return np.isin(dom, ["mixamorig:" + b for b in PART[p]])
skip = set(a.exclude.split(",")) - {""}; fits = [(os.path.basename(os.path.dirname(f)), np.load(f)["offsets"]) for f in sorted(glob.glob("runs/base_fits/*/fit.npz"))]; fits = [(n, o) for n, o in fits if n not in skip and np.abs(o).max() > 0]
print(len(fits), "characters:", ", ".join(n for n, _ in fits)); X = np.stack([o for _, o in fits])             # [C, 13380, 3]
fields, fnames, info = [], [], []
for p in a.parts.split(","):
    m = part_mask(p); Y = X[:, m].reshape(len(fits), -1); mu = Y.mean(0); U, s, Vt = np.linalg.svd(Y - mu, full_matrices=False); var = s ** 2 / (s ** 2).sum(); k = int(min(a.max, np.searchsorted(np.cumsum(var), a.var) + 1))
    for i in range(k):
        f = np.zeros((B.n, 3), np.float32); f[m] = (Vt[i] * (s[i] / np.sqrt(max(len(fits) - 1, 1)))).reshape(-1, 3); fields.append(f); fnames.append(f"learned/{p}-{i + 1}"); info.append(float(var[i]))
    print(f"  {p}: {int(m.sum())} vertices, components kept {k}, variance {np.round(var[:k], 2).tolist()}")
np.savez(os.path.join(os.path.dirname(os.path.abspath(__file__)), "learned.npz"), fields=np.stack(fields), names=np.array(fnames), variance=np.array(info), characters=np.array([n for n, _ in fits]))
print(len(fields), "learned sliders ->", "tools/base_body/learned.npz")
