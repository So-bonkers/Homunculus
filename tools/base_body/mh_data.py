"""The free MakeHuman/MPFB 2 data (CC0 base mesh and skin weights, targets) as plain numpy, for building our own parametric character base.
Data: third_party_dl/mpfb/x (unpacked MPFB 2.0.18 extension, `data/`). Not part of the repo's code; GPL code is not used, only the data files.
    base()            -> (verts [N,3], quads [M,4], body_vertex_count): the body is the first `n` vertices (13380); the rest are helpers (eyes, teeth, joints...)
    target(path)      -> sparse (indices, deltas) of a morph target
    macro(gender, age, muscle=.5, weight=.5) -> vertices of the body with MakeHuman's macro blend (units: 0.1 m, as in MakeHuman; universal targets; gender 0 female 1 male; age 0 baby(1 y) .1875 child(11 y) .5 young(25 y) 1 old(90 y))"""
import os, gzip, numpy as np
D = os.path.join(os.path.dirname(os.path.abspath(__file__)), "../../third_party_dl/mpfb/x/data")
_cache = {}
def base():
    if "base" in _cache: return _cache["base"]
    V = []; F = []; grp = None
    for l in open(os.path.join(D, "3dobjs/base.obj")):
        if l.startswith("v "): V.append([float(x) for x in l.split()[1:4]])
        elif l.startswith("g "): grp = l.split()[1]
        elif l.startswith("f ") and grp == "body": F.append([int(t.split("/")[0]) - 1 for t in l.split()[1:]])
    V = np.array(V); F = np.array(F); n = int(F.max()) + 1; _cache["base"] = (V, F, n); return _cache["base"]
def target(path):
    if path in _cache: return _cache[path]
    p = os.path.join(D, "targets", path + ".target.gz"); idx = []; dl = []
    for l in gzip.open(p, "rt"):
        t = l.split()
        if len(t) == 4 and not l.startswith("#"): idx.append(int(t[0])); dl.append([float(x) for x in t[1:]])
    _cache[path] = (np.array(idx, int), np.array(dl).reshape(-1, 3)); return _cache[path]
def _axis(v, stops):                       # weights for a value on an axis with named stops [(position, name)...]
    out = {}
    for (a, na), (b, nb) in zip(stops[:-1], stops[1:]):
        if a <= v <= b: t = (v - a) / (b - a); out[na] = out.get(na, 0) + 1 - t; out[nb] = out.get(nb, 0) + t; break
    return out
def macro(gender=0.5, age=0.5, muscle=0.5, weight=0.5, ethnic=(1/3, 1/3, 1/3)):
    """MakeHuman's macro blend: the ethnic gender-age targets (caucasian/african/asian, default thirds), plus the universal muscle/weight targets where they are not empty (the universal average-average ones are empty by design)."""
    V, F, n = base(); out = V[:n].copy()
    ga = {"female": 1 - gender, "male": gender}; aa = _axis(age, [(0, "baby"), (0.1875, "child"), (0.5, "young"), (1.0, "old")])
    ma = _axis(muscle, [(0, "minmuscle"), (0.5, "averagemuscle"), (1.0, "maxmuscle")]); wa = _axis(weight, [(0, "minweight"), (0.5, "averageweight"), (1.0, "maxweight")])
    for eth, we in zip(("caucasian", "african", "asian"), ethnic):
        for g, wg in ga.items():
            for a, wa_ in aa.items():
                k = we * wg * wa_
                if k > 1e-6:
                    i, d = target(f"macrodetails/{eth}-{g}-{a}")
                    if len(i): m_ = i < n; out[i[m_]] += k * d[m_]
    for g, wg in ga.items():
        for a, wa_ in aa.items():
            for m, wm in ma.items():
                for w, ww in wa.items():
                    k = wg * wa_ * wm * ww
                    if k > 1e-6:
                        i, d = target(f"macrodetails/universal-{g}-{a}-{m}-{w}")
                        if len(i): m_ = i < n; out[i[m_]] += k * d[m_]
    return out
