"""Pack the free MakeHuman/MPFB 2 data into one library for our parametric base body (run once):
    python3 tools/base_body/build_library.py            -> tools/base_body/library.npz
Contents (units: metres, MakeHuman's frame: y up, faces +z, the character's left is +x):
  verts [19158,3] base vertices (body = first 13380; the rest are helpers: eyes, teeth, joint cubes), faces [13378,4] body quads,
  macro_names / macro_idx / macro_delta: the 24 ethnic gender-age targets and the non-empty universal muscle-weight ones (sparse), stacked,
  slider_names, slider_ptr, slider_idx, slider_delta: every detail target (arms, legs, hands, feet, head, ... not breast/genitals/expression) as a sparse column,
  weights [13380,52] Mixamo skin weights (CC0), bone_names, bone_parent, bone_head_kind/bone_head_idx: how each bone's head is derived from the (morphed) vertices (MEAN of listed vertices, or the centre of a joint cube)."""
import os, sys, json, gzip, numpy as np
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__))); import mh_data as M
D = M.D; V, F, n = M.base(); V = V / 10.0
cubes = {}; grp = None; vi = {}
# vertex indices of every joint cube (helper geometry): from the obj, in face order
verts_of = {}; cur = None
for l in open(os.path.join(D, "3dobjs/base.obj")):
    if l.startswith("g "): cur = l.split()[1]; verts_of.setdefault(cur, set())
    elif l.startswith("f ") and cur and cur.startswith("joint-"): verts_of[cur].update(int(t.split("/")[0]) - 1 for t in l.split()[1:])
def dense_sparse(names):
    idx, dl, ptr = [], [], [0]
    for nm in names:
        i, d = M.target(nm); idx.append(i); dl.append(d / 10.0); ptr.append(ptr[-1] + len(i))
    return np.concatenate(idx), np.concatenate(dl), np.array(ptr)
mdir = os.path.join(D, "targets/macrodetails"); macro = []
for eth in ("caucasian", "african", "asian"):
    for g in ("female", "male"):
        for a in ("baby", "child", "young", "old"): macro.append(f"macrodetails/{eth}-{g}-{a}")
for g in ("female", "male"):
    for a in ("baby", "child", "young", "old"):
        for m in ("minmuscle", "averagemuscle", "maxmuscle"):
            for w in ("minweight", "averageweight", "maxweight"):
                nm = f"macrodetails/universal-{g}-{a}-{m}-{w}"
                if os.path.getsize(os.path.join(D, "targets", nm + ".target.gz")) > 40: macro.append(nm)
mi, md, mp = dense_sparse(macro)
skip = {"macrodetails", "breast", "genitals", "expression", "_images"}; sliders = []
for d in sorted(os.listdir(os.path.join(D, "targets"))):
    p = os.path.join(D, "targets", d)
    if d in skip or not os.path.isdir(p): continue
    for root, _, fs in os.walk(p):
        for f in sorted(fs):
            if f.endswith(".target.gz") and os.path.getsize(os.path.join(root, f)) > 40: sliders.append(os.path.relpath(os.path.join(root, f), os.path.join(D, "targets"))[:-len(".target.gz")])
si, sd, sp = dense_sparse(sliders)
rig = json.load(open(os.path.join(D, "rigs/standard/rig.mixamo.json")))["bones"]; wj = json.load(open(os.path.join(D, "rigs/standard/weights.mixamo.json")))["weights"]
bones = []; seen = set()
def add(b):
    if b in seen: return
    p = rig[b].get("parent")
    if p: add(p)
    seen.add(b); bones.append(b)
for b in sorted(rig): add(b)
W = np.zeros((n, len(bones)), np.float32)
for b, lst in wj.items():
    for i, w in lst:
        if i < n: W[i, bones.index(b)] = w
W /= np.maximum(W.sum(1, keepdims=True), 1e-9)                                  # the file's rows do not always sum to 1
par = np.array([bones.index(rig[b]["parent"]) if rig[b].get("parent") else -1 for b in bones])
kind, hidx, hptr = [], [], [0]
for b in bones:
    h = rig[b]["head"]
    if h["strategy"] == "MEAN": ids = h["vertex_indices"]; kind.append(0)
    elif h["strategy"] == "CUBE": ids = sorted(verts_of[h["cube_name"]]); kind.append(1)
    else: raise SystemExit("unknown strategy " + h["strategy"])
    hidx += list(ids); hptr.append(len(hidx))
np.savez_compressed(os.path.join(os.path.dirname(os.path.abspath(__file__)), "library.npz"), verts=V, faces=F, macro_names=np.array(macro), macro_idx=mi, macro_delta=md, macro_ptr=mp,
                    slider_names=np.array(sliders), slider_idx=si, slider_delta=sd, slider_ptr=sp, weights=W, bone_names=np.array(bones), bone_parent=par, bone_head_kind=np.array(kind), bone_head_idx=np.array(hidx), bone_head_ptr=np.array(hptr))
print(f"verts {len(V)}, macro targets {len(macro)}, sliders {len(sliders)}, bones {len(bones)}, weight rows {len(W)}")
from collections import Counter; print(Counter(s.split('/')[0] for s in sliders))
