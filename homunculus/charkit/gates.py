"""Numeric gates for charkit: cheap measurements that decide what they can before any judge is asked (CPU only, numpy/scipy/trimesh).
Each gate returns {"ok": bool, "issues": [words from prompts.ISSUES], "score": lower is better, ...measurements}.
    .venv/bin/python -m homunculus.charkit.gates head|body|item|alpha FILE [...] [--kind garment]      prints the measurements (for tuning the thresholds)
    TRELLIS venv python -m homunculus.charkit.gates mesh FILE.glb [--kind garment --region upper --picture ITEM_rgba.png]   (trimesh is only in the TRELLIS venv)
    TRELLIS venv python -m homunculus.charkit.gates batch JOBS.json                                                        (jobs.mesh_gates)"""
import json, sys
import numpy as np
from PIL import Image
from scipy import ndimage as ndi

TILT_MAX = 2.0          # degrees of eye-line tilt a head may have (the eye line of tools/head_tilt.py)
SYM_MAX = 0.095         # mirror-difference of the face band (mean |left - mirrored right| / 255) a head may have; Ren's eight redraws measured 0.076-0.107, the picked 941: 0.085 (docs/CHARKIT.md)
MARGIN = 0.008          # a figure or item must keep this fraction of the picture free on every side (else: cropped)
FIG_MIN_H = 0.55        # a full-body figure fills at least this much of the picture height
LID_MAX, LID_DEPTH = 0.7, 0.08    # garment opening closed by a lid: at least 70 % of the vertical rays through its footprint stop within 8 % of the height
POKE_MAX = 0.005        # assembled kit: at most 0.5 % of the tested body vertices outside the garments
RESIDUAL_MAX = 0.005    # placement: mean trimmed ICP residual at most 0.5 % of the reference height
ITEM_FG = {"base": (0.05, 0.45), "garment": (0.03, 0.45), "shoes": (0.02, 0.45), "hair": (0.01, 0.35), "accessory": (0.005, 0.45)}    # foreground fraction a kit picture may have
ITEM_MAIN = {"base": 0.92, "garment": 0.85, "shoes": 0.80, "hair": 0.80, "accessory": 0.55}      # share of the foreground in the biggest object (shoes: the two biggest; accessories such as glasses come apart in thin pieces)

def _load(path): return np.asarray(Image.open(path).convert("RGB")).astype(float)

def foreground(im, tol=40):
    """Pixels that differ from the plain background (the median colour of the picture's border rows), cleaned of specks."""
    bg = np.median(np.concatenate([im[:6].reshape(-1, 3), im[-6:].reshape(-1, 3), im[:, :6].reshape(-1, 3), im[:, -6:].reshape(-1, 3)]), 0)
    fg = np.abs(im - bg).sum(2) > tol
    return ndi.binary_opening(ndi.binary_fill_holes(ndi.binary_closing(fg, iterations=2)), iterations=2)

def _box(fg):
    ys, xs = np.nonzero(fg)
    return (int(xs.min()), int(ys.min()), int(xs.max()), int(ys.max())) if len(ys) else None

def _margins(fg, box):
    H, W = fg.shape; x0, y0, x1, y1 = box
    return {"top": y0 / H, "bottom": (H - 1 - y1) / H, "left": x0 / W, "right": (W - 1 - x1) / W}

def _skin_blob(im, fg, rows=None):
    sk = fg & (im[..., 0] > im[..., 2] + 25)
    if rows is not None: sk &= np.arange(im.shape[0])[:, None] < rows
    lab, n = ndi.label(ndi.binary_opening(sk, iterations=2))
    if n == 0: return None
    return lab == np.argmax(ndi.sum(sk, lab, range(1, n + 1))) + 1

def eye_tilt(im, full=True):
    """tilt: the eye-line tilt in degrees exactly as tools/head_tilt.py measures it (skin in the top 17 % of the figure, its dark pixels in the middle half of the rows, left half
    against right half: on a head crop this is in practice the eyebrow line; it is the number Ren's heads were judged by).
    sym (head crops, full=False): mirror asymmetry of the face band: the skin blob cut one ear-to-ear width below the hairline (so the neck does not count), rows 25-75 % of it,
    columns within 40 % of its width around its centre; mean |band - mirrored band| / 255."""
    bg = np.median(im[:20].reshape(-1, 3), axis=0); fg = np.abs(im - bg).max(2) > 25
    ys, xs = np.nonzero(fg)
    if not len(ys): return None
    top, bot = ys.min(), ys.max(); H = bot - top
    head = _skin_blob(im, fg, top + 0.17 * H)
    if head is None: return None
    hy, hx = np.nonzero(head); cx = hx.mean()
    dark = ndi.binary_closing(head & (im.max(2) < 85), iterations=1)
    row0 = hy.min() + 0.25 * (hy.max() - hy.min()); row1 = hy.min() + 0.75 * (hy.max() - hy.min()); yy, xx = np.nonzero(dark); sel = (yy > row0) & (yy < row1); yy, xx = yy[sel], xx[sel]
    L = xx < cx; R = ~L
    ang = float(np.degrees(np.arctan2(yy[R].mean() - yy[L].mean(), xx[R].mean() - xx[L].mean()))) if L.any() and R.any() else float("nan")
    out = {"tilt": ang, "sym": float("nan")}
    if full: return out
    face = _skin_blob(im, fg)
    fy, fx = np.nonzero(face); face &= np.arange(im.shape[0])[:, None] < fy.min() + 1.05 * (fx.max() - fx.min()); fy, fx = np.nonzero(face)
    w = fx.max() - fx.min(); half = int(0.4 * w); c = int(round(fx.mean())); r0 = int(fy.min() + 0.25 * (fy.max() - fy.min())); r1 = int(fy.min() + 0.75 * (fy.max() - fy.min()))
    if c - half >= 0 and c + half < im.shape[1]:
        g = im[r0:r1, c - half:c + half].mean(2); out["sym"] = float(np.abs(g - g[:, ::-1]).mean() / 255)
    out["face_box"] = [int(fx.min()), int(fy.min()), int(fx.max()), int(fy.max())]; return out

def head(path):
    """A head redraw: eye line level (|tilt| <= TILT_MAX) and the face band close to its mirror image (sym <= SYM_MAX)."""
    m = eye_tilt(_load(path), full=False)
    if m is None: return {"ok": False, "issues": ["other"], "score": 9.0, "note": "no face found"}
    iss = (["tilted"] if not abs(m["tilt"]) <= TILT_MAX else []) + (["asymmetric"] if not m["sym"] <= SYM_MAX else [])
    score = (abs(m["tilt"]) / TILT_MAX if m["tilt"] == m["tilt"] else 3) + (m["sym"] / SYM_MAX if m["sym"] == m["sym"] else 3)
    return {"ok": not iss, "issues": iss, "score": round(score, 3), "tilt": round(m["tilt"], 2), "sym": round(m["sym"], 4)}

def body(path):
    """A full-body redraw: the figure is whole (a free margin on every side, so head and feet are not cut), tall enough, one figure, and the head level."""
    im = _load(path); fg = foreground(im); box = _box(fg)
    if box is None: return {"ok": False, "issues": ["other"], "score": 9.0, "note": "empty picture"}
    mg = _margins(fg, box); h = (box[3] - box[1]) / fg.shape[0]
    lab, n = ndi.label(fg); sizes = np.sort(ndi.sum(fg, lab, range(1, n + 1)))[::-1] if n else np.array([0]); main = float(sizes[0] / max(1, sizes.sum()))
    t = eye_tilt(im) or {"tilt": float("nan")}
    iss = (["cropped"] if min(mg.values()) < MARGIN else []) + (["cropped"] if h < FIG_MIN_H else []) + (["multiple_objects"] if main < 0.9 else []) + (["tilted"] if not abs(t["tilt"]) <= 2 * TILT_MAX else [])
    iss = sorted(set(iss)); score = (0 if h >= FIG_MIN_H else 1) + (abs(t["tilt"]) / (2 * TILT_MAX) if t["tilt"] == t["tilt"] else 1) + (1 - main) * 5 + (2 if "cropped" in iss else 0)
    return {"ok": not iss, "issues": iss, "score": round(score, 3), "height": round(h, 3), "margins": {k: round(v, 4) for k, v in mg.items()}, "main": round(main, 3), "tilt": round(t["tilt"], 2)}

def item(path, kind):
    """A kit picture: a sensible foreground fraction for its kind, one object (two for a pair of shoes), not touching the border."""
    im = _load(path); fg = foreground(im); box = _box(fg)
    if box is None: return {"ok": False, "issues": ["missing_part"], "score": 9.0, "note": "empty picture"}
    frac = float(fg.mean()); mg = _margins(fg, box); lab, n = ndi.label(fg); sizes = np.sort(ndi.sum(fg, lab, range(1, n + 1)))[::-1]
    main = float(sizes[:2 if kind == "shoes" else 1].sum() / sizes.sum()); lo, hi = ITEM_FG[kind]
    iss = (["cropped"] if min(mg.values()) < MARGIN else []) + (["multiple_objects"] if main < ITEM_MAIN[kind] else []) + (["missing_part"] if frac < lo else []) + (["extra_items"] if frac > hi else [])
    score = (1 - main) * 3 + (0 if lo <= frac <= hi else 1) + (2 if "cropped" in iss else 0)
    return {"ok": not iss, "issues": iss, "score": round(score, 3), "fg": round(frac, 4), "main": round(main, 3), "pieces": int(n), "height": round((box[3] - box[1]) / fg.shape[0], 3), "margins": {k: round(v, 4) for k, v in mg.items()}}

def alpha(path, kind="garment"):
    """A background cut (RGBA): the opaque part is one main piece and not empty."""
    a = np.asarray(Image.open(path).convert("RGBA"))[..., 3] > 128; frac = float(a.mean())
    if not a.any(): return {"ok": False, "issues": ["missing_part"], "score": 9.0, "fg": 0.0}
    lab, n = ndi.label(a); sizes = np.sort(ndi.sum(a, lab, range(1, n + 1)))[::-1]; main = float(sizes[:2 if kind == "shoes" else 1].sum() / sizes.sum())
    iss = (["multiple_objects"] if main < ITEM_MAIN.get(kind, 0.85) - 0.05 else []) + (["missing_part"] if frac < 0.004 else [])
    return {"ok": not iss, "issues": iss, "score": round(1 - main, 3), "fg": round(frac, 4), "main": round(main, 3), "pieces": int(n)}

def _first_hits(tri, pts, down=False):
    """Height where a vertical ray (up from below, or down from above) at each (x, z) first meets the triangles; nan where it meets none."""
    lo = tri[:, :, [0, 2]].min(1); hi = tri[:, :, [0, 2]].max(1); a, b, c = tri[:, 0], tri[:, 1], tri[:, 2]; out = []
    for x, z in pts:
        s = (lo[:, 0] <= x) & (hi[:, 0] >= x) & (lo[:, 1] <= z) & (hi[:, 1] >= z); A, B, Cc = a[s], b[s], c[s]
        d = (B[:, 0] - A[:, 0]) * (Cc[:, 2] - A[:, 2]) - (Cc[:, 0] - A[:, 0]) * (B[:, 2] - A[:, 2]); ok = np.abs(d) > 1e-12; dd = np.where(ok, d, 1)
        u = ((x - A[:, 0]) * (Cc[:, 2] - A[:, 2]) - (Cc[:, 0] - A[:, 0]) * (z - A[:, 2])) / dd; w = ((B[:, 0] - A[:, 0]) * (z - A[:, 2]) - (x - A[:, 0]) * (B[:, 2] - A[:, 2])) / dd
        k = ok & (u >= 0) & (w >= 0) & (u + w <= 1); y = A[k, 1] + u[k] * (B[k, 1] - A[k, 1]) + w[k] * (Cc[k, 1] - A[k, 1])
        out.append((y.max() if down else y.min()) if len(y) else np.nan)
    return np.array(out)

def _lid_share(g, where, legs=False):
    v = g.vertices; H = np.ptp(v[:, 1]); y0, y1 = v[:, 1].min(), v[:, 1].max(); tri = v[g.faces]
    band = v[v[:, 1] < y0 + 0.03 * H] if where == "bottom" else v[v[:, 1] > y1 - 0.03 * H]
    parts = [band[band[:, 0] < np.median(band[:, 0])], band[band[:, 0] >= np.median(band[:, 0])]] if legs else [band]
    gx, gz = np.meshgrid(np.linspace(-0.3, 0.3, 7), np.linspace(-0.3, 0.3, 5)); pts = []
    for p in parts:
        cx, cz = np.median(p[:, 0]), np.median(p[:, 2]); ex, ez = np.ptp(p[:, 0]) / 2, np.ptp(p[:, 2]) / 2; pts += list(zip(cx + gx.ravel() * ex, cz + gz.ravel() * ez))
    h = _first_hits(tri, pts, down=where == "top"); depth = (h - y0) / H if where == "bottom" else (y1 - h) / H
    return float(np.mean(depth < LID_DEPTH))

def mesh(path, kind="garment", region=None, picture=None):
    """A TRELLIS.2 GLB (glTF: y up, faces +z): it loads, has faces, its front outline has about the aspect of the picture's foreground, open-edge count (vertices welded by position:
    the GLB splits them at UV seams), and for garments the 'lid': faces at the bottom (and the top for trousers) that point straight down/up and cover the opening."""
    import trimesh
    try: m = trimesh.load(path, force="mesh")
    except Exception as e: return {"ok": False, "issues": ["missing_part"], "score": 9.0, "note": f"does not load: {type(e).__name__}"}
    if len(m.faces) < 5000: return {"ok": False, "issues": ["missing_part"], "score": 9.0, "faces": int(len(m.faces))}
    ext = np.ptp(m.vertices, 0); out = {"faces": int(len(m.faces)), "extent": [round(float(e), 4) for e in ext]}; iss = []
    g = trimesh.Trimesh(m.vertices, m.faces, process=False); g.merge_vertices(merge_tex=True, merge_norm=True)
    e = np.sort(g.edges, 1); _, cnt = np.unique(e, axis=0, return_counts=True); out["open_edges"] = int((cnt == 1).sum()); out["nonmanifold_edges"] = int((cnt > 2).sum())
    if picture:
        a = np.asarray(Image.open(picture).convert("RGBA"))[..., 3] > 128; ys, xs = np.nonzero(a)
        if len(ys):
            pic = (np.ptp(xs) + 1) / (np.ptp(ys) + 1); mod = ext[0] / max(ext[1], 1e-6); out["aspect_pic"], out["aspect_mesh"] = round(float(pic), 3), round(float(mod), 3)
            if kind != "shoes" and not (0.6 < mod / pic < 1.65): iss.append("wrong_shape")      # shoes are drawn three-quarter from above: no aspect check
    if kind == "garment":       # lid: vertical rays through the opening's footprint (one grid per leg at trouser cuffs); TRELLIS's lid sits a few % of the height inside the hem,
        lid = {}                # an open hem lets the rays travel up to the shoulders / hood. lid = the share of rays that hit within LID_DEPTH of the opening (Ren: hoodie s7 0.94, s42 0.37)
        for where in (("bottom", "top") if region == "lower" else ("bottom",)): lid[where] = round(_lid_share(g, where, legs=(region == "lower" and where == "bottom")), 3)
        out["lid"] = lid
        if max(lid.values()) >= LID_MAX: iss.append("lid")          # informational for the judges: assemble_kit.py removes such lids; not a reason to reject on its own
    hard = [i for i in iss if i != "lid"]
    return {"ok": not hard, "issues": iss, "score": round(len(hard) + 0.5 * ("lid" in iss) + min(out["open_edges"], 20000) / 20000, 3), **out}      # a lid ranks a seed lower

if __name__ == "__main__" and len(sys.argv) > 2 and sys.argv[1] == "batch":        # jobs.mesh_gates: [{"glb", "kind", "region", "picture"}] -> one JSON line {glb: result}
    res = {}
    for j in json.load(open(sys.argv[2])):
        try: res[j["glb"]] = mesh(j["glb"], j.get("kind", "garment"), j.get("region"), j.get("picture"))
        except Exception as e: res[j["glb"]] = {"ok": False, "issues": ["other"], "score": 9.0, "note": f"{type(e).__name__}: {str(e)[:120]}"}
        print("gated", j["glb"], file=sys.stderr, flush=True)
    print(json.dumps(res))
elif __name__ == "__main__":
    import argparse
    ap = argparse.ArgumentParser(); ap.add_argument("what", choices=["head", "body", "item", "alpha", "mesh"]); ap.add_argument("files", nargs="+"); ap.add_argument("--kind", default="garment"); ap.add_argument("--region"); ap.add_argument("--picture"); a = ap.parse_args()
    for f in a.files:
        r = {"head": lambda: head(f), "body": lambda: body(f), "item": lambda: item(f, a.kind), "alpha": lambda: alpha(f, a.kind), "mesh": lambda: mesh(f, a.kind, a.region, a.picture)}[a.what]()
        print(f, json.dumps(r))
