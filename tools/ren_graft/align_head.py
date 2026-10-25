"""Find where a head-and-shoulders model (bust) sits on a full-body model of the same character: a similarity transform (scale, rotation, translation) by trimmed ICP from several start scales.
    /home/shubhankar/trellis2_test/venv/bin/python tools/ren_graft/align_head.py BODY.glb BUST.glb OUT.json [--head-frac 0.17]
Both GLBs as TRELLIS.2 exports them (glTF, y up). The body's head region is its top `head-frac` of height (crown to below the collar); the bust contributes its upper part (head, neck, headphones).
OUT.json: matrix (4x4, bust glTF coordinates -> body glTF coordinates), scale, mean residual (in body heights), and the heights of the body's crown and chin for the cut."""
import sys, json, argparse, numpy as np, trimesh
from scipy.spatial import cKDTree
ap = argparse.ArgumentParser(); ap.add_argument("body"); ap.add_argument("bust"); ap.add_argument("out"); ap.add_argument("--head-frac", type=float, default=0.17); a = ap.parse_args()
def pts(path, n=60000):
    m = trimesh.load(path, force="mesh"); p, _ = trimesh.sample.sample_surface(m, n); return np.asarray(p)
B = pts(a.body, 150000); H = B[:, 1].max() - B[:, 1].min(); top = B[:, 1].max()
T = B[B[:, 1] > top - a.head_frac * H]                                   # body: head, neck, collar, headphones
S0 = pts(a.bust, 60000); sh = S0[:, 1].max() - S0[:, 1].min(); S = S0[S0[:, 1] > S0[:, 1].max() - 0.62 * sh]     # bust: everything above the upper chest
tree = cKDTree(T)
def umeyama(X, Y):
    mx, my = X.mean(0), Y.mean(0); Xc, Yc = X - mx, Y - my; U, D, Vt = np.linalg.svd(Yc.T @ Xc / len(X)); Sg = np.eye(3)
    if np.linalg.det(U) * np.linalg.det(Vt) < 0: Sg[2, 2] = -1
    R = U @ Sg @ Vt; s = np.trace(np.diag(D) @ Sg) / Xc.var(0).sum(); return s, R, my - s * R @ mx
best = None
for k in (0.18, 0.22, 0.26, 0.30, 0.35):
    s = k * H / sh; R = np.eye(3); t = np.array([T[:, 0].mean(), top, T[:, 2].mean()]) - s * np.array([S[:, 0].mean(), S[:, 1].max(), S[:, 2].mean()])
    for it in range(60):
        Y = (s * S @ R.T) + t; d, i = tree.query(Y); keep = d < np.quantile(d, 0.8)
        s, R, t = umeyama(S[keep], T[i[keep]])
    Y = (s * S @ R.T) + t; d, _ = tree.query(Y); err = float(np.median(d) / H)
    print(f"start scale {k:.2f}: scale {s:.4f}, median residual {err * 100:.3f} % of the body height", flush=True)
    if best is None or err < best[0]: best = (err, s, R, t)
err, s, R, t = best; M = np.eye(4); M[:3, :3] = s * R; M[:3, 3] = t
skin = T[(T[:, 1] < top - 0.04 * H)]
json.dump(dict(matrix=M.tolist(), scale=s, residual=err, body_height=H, body_top=top), open(a.out, "w"), indent=1); print("best residual %.3f %% of the body height; wrote %s" % (err * 100, a.out))
