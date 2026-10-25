"""Place an approved head bust on a bald base body by matching the FACE only (the bust's hood, headphones and hair would drag a whole-bust fit up and small):
source = the bust's skin points above its chin (face, ears, forehead), target = the body's points above its narrowest neck; trimmed similarity ICP from the bust's known placement on the dressed
model (PRIOR.json, bust glTF -> that model's glTF frame) rescaled by head height. -> OUT.json (bust glTF -> body glTF).
    trellis venv python tools/ren_graft/align_face.py BODY.glb BUST.glb PRIOR.json OUT.json --chin-prior 0.345 --neck 0.36 [--frac 0.55]"""
import sys, json, argparse, numpy as np, trimesh
from scipy.spatial import cKDTree
ap = argparse.ArgumentParser(); ap.add_argument("body"); ap.add_argument("bust"); ap.add_argument("prior"); ap.add_argument("out"); ap.add_argument("--chin-prior", type=float, default=0.345); ap.add_argument("--neck", type=float, default=0.36); ap.add_argument("--frac", type=float, default=0.55); a = ap.parse_args()
def sample(path, n):
    m = trimesh.load(path, force="mesh", process=False); p, fi = trimesh.sample.sample_surface(m, n); tex = np.asarray(m.visual.material.baseColorTexture.convert("RGB")).astype(float) / 255
    uv = np.asarray(m.visual.uv)[m.faces[fi]].mean(1); H, W = tex.shape[:2]; c = tex[np.clip(((1 - uv[:, 1]) * H).astype(int), 0, H - 1), np.clip((uv[:, 0] * W).astype(int), 0, W - 1)]; return np.asarray(p), c
B, _ = sample(a.body, 300000); T = B[B[:, 1] > a.neck + 0.01]
S0, C = sample(a.bust, 200000); r, g, b = C[:, 0], C[:, 1], C[:, 2]; skin = (r > 0.15) & (g < 0.75 * r) & (b < 0.6 * r) & (r - b > 0.12)
P = np.array(json.load(open(a.prior))["matrix"]); Sp = S0 @ P[:3, :3].T + P[:3, 3]; S = S0[skin & (Sp[:, 1] > a.chin_prior + 0.005)]
Spf = Sp[skin & (Sp[:, 1] > a.chin_prior + 0.005)]; k0 = np.ptp(T[:, 1]) / max(np.ptp(Spf[:, 1]), 1e-6) * 0.85      # the face is ~85 % of the bald head's height
R = P[:3, :3] / np.cbrt(np.linalg.det(P[:3, :3])); s = np.cbrt(np.linalg.det(P[:3, :3])) * k0
t = np.array([T[:, 0].mean(), T[:, 1].min(), T[:, 2].max()]) - s * np.array([(S @ R.T)[:, 0].mean(), (S @ R.T)[:, 1].min(), (S @ R.T)[:, 2].max()])      # chin on the neck, face to the front (+z)
tree = cKDTree(T)
for it in range(80):
    X = s * S @ R.T + t; d, i = tree.query(X); keep = d <= np.quantile(d, a.frac); A, Bp = S[keep], T[i[keep]]; ma, mb = A.mean(0), Bp.mean(0); Ac, Bc = A - ma, Bp - mb
    U, D, Vt = np.linalg.svd(Bc.T @ Ac / len(A)); Sg = np.eye(3); Sg[2, 2] = -1 if np.linalg.det(U) * np.linalg.det(Vt) < 0 else 1; R = U @ Sg @ Vt; s = np.trace(np.diag(D) @ Sg) / Ac.var(0).sum(); t = mb - s * R @ ma
d, _ = tree.query(s * S @ R.T + t); M = np.eye(4); M[:3, :3] = s * R; M[:3, 3] = t
json.dump(dict(matrix=M.tolist(), scale=float(s), residual=float(np.median(d))), open(a.out, "w"), indent=1)
print(f"face fit: scale {s:.4f}, median {np.median(d):.4f}, face points {len(S)}, head points {len(T)}")
