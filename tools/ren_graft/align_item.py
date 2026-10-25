"""Place a separately generated kit item (TRELLIS.2 GLB) on the matching region of a reference model of the dressed character: a similarity transform (scale, rotation, translation)
found by trying 24 axis-aligned orientations x yaw steps x start scales, then trimmed ICP. -> OUT.json (matrix: item glTF -> reference glTF, residual in reference heights).
    trellis venv python tools/ren_graft/align_item.py ITEM.glb REFERENCE.glb OUT.json --box xmin xmax ymin ymax zmin zmax [--yaw-steps 12] [--frac 0.7]
--box: the region of the reference (glTF frame: y up, the character faces +z) the item should cover; the item's own points all count (trimmed to the best `frac`)."""
import sys, json, argparse, itertools, numpy as np, trimesh
from scipy.spatial import cKDTree
from scipy.spatial.transform import Rotation as Rot
ap = argparse.ArgumentParser(); ap.add_argument("item"); ap.add_argument("ref"); ap.add_argument("out"); ap.add_argument("--box", type=float, nargs=6, required=True); ap.add_argument("--yaw-steps", type=int, default=12)
ap.add_argument("--frac", type=float, default=0.7); ap.add_argument("--axes", default="all", help="all | upright (keep the item's up axis: for garments drawn as worn)"); a = ap.parse_args()
def pts(path, n):
    m = trimesh.load(path, force="mesh"); p, _ = trimesh.sample.sample_surface(m, n); return np.asarray(p)
R0 = pts(a.ref, 300000); b = a.box; T = R0[(R0[:, 0] > b[0]) & (R0[:, 0] < b[1]) & (R0[:, 1] > b[2]) & (R0[:, 1] < b[3]) & (R0[:, 2] > b[4]) & (R0[:, 2] < b[5])]
S = pts(a.item, 40000); tree = cKDTree(T); print("reference points in the box:", len(T), flush=True)
def umeyama(X, Y):
    mx, my = X.mean(0), Y.mean(0); Xc, Yc = X - mx, Y - my; U, D, Vt = np.linalg.svd(Yc.T @ Xc / len(X)); Sg = np.eye(3)
    if np.linalg.det(U) * np.linalg.det(Vt) < 0: Sg[2, 2] = -1
    R = U @ Sg @ Vt; return np.trace(np.diag(D) @ Sg) / Xc.var(0).sum(), R, my - (np.trace(np.diag(D) @ Sg) / Xc.var(0).sum()) * R @ mx
base = [np.eye(3)] if a.axes == "upright" else [r.as_matrix() for r in Rot.create_group("O")]
yaws = [Rot.from_euler("y", 360 * k / a.yaw_steps, degrees=True).as_matrix() for k in range(a.yaw_steps)]
ext_t = np.ptp(T, 0).max(); ext_s = np.ptp(S, 0).max(); cands = []
for B, Y in itertools.product(base, yaws):
    R = Y @ B; s = ext_t / ext_s; t = T.mean(0) - s * (S @ R.T).mean(0); X = s * S[::8] @ R.T + t; d, _ = tree.query(X); cands.append((np.mean(np.sort(d)[: int(len(d) * a.frac)]), R))
cands.sort(key=lambda c: c[0]); best = None
for _, R in cands[:6]:
    for k in (0.85, 1.0, 1.15):
        s = k * ext_t / ext_s; t = T.mean(0) - s * (S @ R.T).mean(0)
        for it in range(50):
            X = s * S @ R.T + t; d, i = tree.query(X); keep = d <= np.quantile(d, a.frac); s, R, t = umeyama(S[keep], T[i[keep]])
        X = s * S @ R.T + t; d, _ = tree.query(X); err = float(np.mean(np.sort(d)[: int(len(d) * a.frac)]))
        if best is None or err < best[0]: best = (err, s, R, t)
err, s, R, t = best; H = R0[:, 1].max() - R0[:, 1].min(); M = np.eye(4); M[:3, :3] = s * R; M[:3, 3] = t
json.dump(dict(matrix=M.tolist(), scale=float(s), residual=err / H), open(a.out, "w"), indent=1); print(f"placed: scale {s:.4f}, residual {err / H * 100:.3f} % of the reference height -> {a.out}")
