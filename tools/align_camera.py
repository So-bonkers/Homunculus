"""Put the real camera into the character's world: a per-frame Blender camera (position, rotation, lens) that frames the retargeted character the way the video framed the dancer.

    python3 -I tools/align_camera.py <incam_joints.npz> <character_joints.npz> <camera_track.npz> <out.npz> [--seconds S] [--fps 30]

incam_joints.npz       tools/incam_joints.py: SMPL-X joints in the camera frame (x right, y down, z forward), GVHMR's own estimate
character_joints.npz   Blender world positions of the retargeted character's bones, every frame (Hips Spine2 Head UpLegs Legs Feet Arms ForeArms Hands; written by tools/blender_bone_dump.py)
camera_track.npz       tools/track_camera.py: rotation R_t and focal f_t of every frame relative to frame 0
The camera turns about its own centre, so a joint seen in camera t is p0 = R_t^T p_t in the camera of frame 0; those points and the character's joints are two copies of the same dance, and
one similarity transform (scale, rotation, translation; Umeyama; the roll is then removed: the video is level, the worst 20% of the residuals dropped twice) maps the first to the second. It gives the position and orientation of frame 0's camera in the
character's world, and R_t / f_t then turn and zoom it. Camera translation in the video is not modelled. Writes: M (N, 4, 4) Blender camera-to-world, lens (N,) mm for a 36 mm sensor, size, resid (m)."""
import sys, numpy as np
a = sys.argv[1:]
def opt(flag, default, cast=str):
    if flag in a: i = a.index(flag); v = a[i + 1]; del a[i:i + 2]; return cast(v)
    return default
secs = opt("--seconds", 60.0, float); fps = opt("--fps", 30.0, float)
inc, chj, trk, dst = a[:4]
I = np.load(inc); C = np.load(chj); T = np.load(trk)
# SMPL-X joint index for each character bone
MAP = {"Hips": 0, "Head": 15, "LeftUpLeg": 1, "RightUpLeg": 2, "LeftLeg": 4, "RightLeg": 5, "LeftFoot": 7, "RightFoot": 8, "LeftArm": 16, "RightArm": 17, "LeftForeArm": 18, "RightForeArm": 19, "LeftHand": 20, "RightHand": 21}
names = list(C["names"]); ci = [names.index(k) for k in MAP]; si = [MAP[k] for k in MAP]
n = min(len(I["J"]), len(C["J"]), len(T["R"])); k = min(n, int(secs * fps))
zoom = np.clip(T["f"][:k] / T["f"][0], 0.6, 1.6)                                                  # GVHMR assumes a constant focal length (tools/compensate_camera.py does the same)
P = np.einsum("tij,tkj->tki", np.transpose(T["R"][:k], (0, 2, 1)), I["J"][:k][:, si] * zoom[:, None, None])           # R_t^T p_t: every frame seen from the camera of frame 0
Q = C["J"][:k][:, ci]                                                                           # the same joints, character world
def umeyama(X, Y, w=None):
    w = np.ones(len(X)) if w is None else w; w = w / w.sum(); mx, my = (w[:, None] * X).sum(0), (w[:, None] * Y).sum(0)
    Xc, Yc = X - mx, Y - my; S = (Yc * w[:, None]).T @ Xc; U, D, Vt = np.linalg.svd(S); d = np.sign(np.linalg.det(U @ Vt)); Dm = np.diag([1, 1, d])
    R = U @ Dm @ Vt; s = (D * np.diag(Dm)).sum() / (w * (Xc ** 2).sum(1)).sum(); return s, R, my - s * R @ mx
X, Y = P.reshape(-1, 3), Q.reshape(-1, 3); keep = np.ones(len(X), bool)
for _ in range(3):
    s, R, t = umeyama(X[keep], Y[keep]); res = np.linalg.norm(Y - (s * (X @ R.T) + t), axis=1); keep = res < np.percentile(res, 80)
print(f"[align_camera] {k} frames, scale {s:.3f}, residual median {np.median(res):.3f} m, p90 {np.percentile(res, 90):.3f} m; camera of frame 0 at {np.round(t, 2)} (character world)")
d = np.arctan2(-R[2, 0], R[2, 1]); d = d if abs(d) < np.pi / 2 else d - np.sign(d) * np.pi                  # body joints do not pin down roll: the footage is level, so turn the camera of frame 0 about its optical axis until its x axis is horizontal in the (gravity-aligned) character world
Rz = np.array([[np.cos(d), -np.sin(d), 0], [np.sin(d), np.cos(d), 0], [0, 0, 1]]); R = R @ Rz
print(f"[align_camera] levelled the camera: roll {np.degrees(d):.1f} deg removed")
f0 = float(T["f"][0]); W, H = [float(v) for v in T["size"]]; flip = np.diag([1.0, -1.0, -1.0])               # image convention (x right, y down, z forward) -> Blender camera (x right, y up, looking down -Z)
from scipy.ndimage import gaussian_filter1d
from scipy.spatial.transform import Rotation as Rot
cx, cy = W / 2, H / 2; K0 = np.array([[f0, 0, cx], [0, f0, cy], [0, 0, 1.0]])
f_t = np.clip(T["f"][:n], 0.6 * f0, 1.6 * f0); Ri = np.einsum("ij,tkj->tik", R, T["R"][:n])                                     # R @ R_t^T: camera t -> world, image convention (tracked)
# The tracker drifts and the camera also moves in space, which a turning-and-zooming camera cannot follow: so the real dancer is the reference. Where the hips and the head of the real dancer fall in the
# frame (GVHMR's estimate, projected with its own K) is where the character's hips and head must fall, by a small extra turn of the camera and a small extra zoom.
def pix(p, f=f0): return np.stack([f * p[..., 0] / p[..., 2] + cx, f * p[..., 1] / p[..., 2] + cy], -1)
tgt_h, tgt_hd = pix(I["J"][:n, 0]), pix(I["J"][:n, 15])
Wh, Wd = C["J"][:n, names.index("Hips")], C["J"][:n, names.index("Head")]
rs = np.zeros((n, 3))
for i in range(n):
    r = Ri[i].T @ (Wh[i] - t); r /= np.linalg.norm(r); rt = np.array([(tgt_h[i, 0] - cx) / f_t[i], (tgt_h[i, 1] - cy) / f_t[i], 1.0]); rt /= np.linalg.norm(rt)
    ax = np.cross(rt, r); sn = np.linalg.norm(ax); ang = np.arctan2(sn, rt @ r); rs[i] = ax / sn * ang if sn > 1e-9 else 0                  # rotation taking the target direction onto the real one
rs = gaussian_filter1d(rs, 2, axis=0, mode="nearest"); Q = Rot.from_rotvec(rs).as_matrix(); Rn = np.einsum("tij,tjk->tik", Ri, Q)
vh = np.einsum("tji,tj->ti", Rn, Wh - t); vd = np.einsum("tji,tj->ti", Rn, Wd - t)
Lm = np.linalg.norm(pix(vd, f_t) - pix(vh, f_t), axis=1); Lt = np.linalg.norm(tgt_hd - tgt_h, axis=1)
ratio = np.clip(gaussian_filter1d(np.clip(Lt / np.maximum(Lm, 1e-3), 0.3, 3.0), 15, mode="nearest"), 0.5, 2.0); f_fin = f_t * ratio
print(f"[align_camera] dancer-anchored correction: extra turn up to {np.degrees(np.linalg.norm(rs, axis=1)).max():.1f} deg (median {np.median(np.degrees(np.linalg.norm(rs, axis=1))):.1f}), extra zoom x{ratio.min():.2f}..x{ratio.max():.2f}")
M = np.zeros((n, 4, 4)); M[:, 3, 3] = 1
for i in range(n):
    M[i, :3, :3] = Rn[i] @ flip; M[i, :3, 3] = t
lens = f_fin * 36.0 / W
np.savez(dst, M=M, lens=lens, size=np.array([W, H]), resid=np.median(res), scale=s, K0=K0, R_align=R, t_align=t)
