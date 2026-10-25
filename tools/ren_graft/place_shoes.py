"""Place a left and a right shoe on a body's feet deterministically (glTF frame, y up, the character faces +z): the shoe keeps its up axis, its long axis (PCA of the footprint)
is turned onto the foot's, the toe end (the end whose top is lower: the heel has the collar) points like the foot's toes (+z side of the foot), its length is FIT x the foot's,
its sole sits on the foot's lowest point. -> OUT_DIR/place_shoe_{left,right}.json (matrix shoe glTF -> body glTF), same format as align_item.py.
    trellis venv python tools/ren_graft/place_shoes.py BODY.glb SHOE_LEFT.glb SHOE_RIGHT.glb OUT_DIR [--fit 1.12] [--foot-top -0.43]"""
import sys, json, argparse, numpy as np, trimesh
ap = argparse.ArgumentParser(); ap.add_argument("body"); ap.add_argument("left"); ap.add_argument("right"); ap.add_argument("out"); ap.add_argument("--fit", type=float, default=1.12); ap.add_argument("--foot-top", type=float, default=-0.43); a = ap.parse_args()
def pts(p, n): m = trimesh.load(p, force="mesh"); q, _ = trimesh.sample.sample_surface(m, n); return np.asarray(q)
B = pts(a.body, 400000); feet = B[B[:, 1] < a.foot_top]
def frame(P):                                      # footprint PCA in the ground plane: centre, long axis, length
    xz = P[:, [0, 2]]; c = xz.mean(0); U, S, Vt = np.linalg.svd(xz - c, full_matrices=False); ax = Vt[0]; t = (xz - c) @ ax; return c, ax, np.ptp(t), t
for side, sel in (("left", feet[:, 0] > 0), ("right", feet[:, 0] < 0)):
    F = feet[sel]; fc, fax, flen, ft = frame(F)
    if fax[1] < 0: fax = -fax                      # the foot's long axis points to its toes (+z)
    S = pts(getattr(a, side), 120000); sc, sax, slen, st = frame(S)
    top_hi = S[st > np.quantile(st, 0.8), 1].max(); top_lo = S[st < np.quantile(st, 0.2), 1].max()
    if top_hi > top_lo: sax = -sax                 # make sax point to the shoe's toe (the lower end)
    ang = np.arctan2(fax[0], fax[1]) - np.arctan2(sax[0], sax[1]); c, s_ = np.cos(ang), np.sin(ang)
    R = np.array([[c, 0, s_], [0, 1, 0], [-s_, 0, c]]); k = a.fit * flen / slen
    X = (S - [sc[0], 0, sc[1]]) @ R.T * k; t = np.array([fc[0], F[:, 1].min() - X[:, 1].min(), fc[1]])
    M = np.eye(4); M[:3, :3] = k * R; M[:3, 3] = t - k * R @ np.array([sc[0], 0, sc[1]])
    json.dump(dict(matrix=M.tolist(), scale=float(k), foot_length=float(flen)), open(f"{a.out}/place_shoe_{side}.json", "w"), indent=1)
    print(f"{side}: foot length {flen:.4f}, shoe scale {k:.4f}, turned {np.degrees(ang):.1f} deg")
