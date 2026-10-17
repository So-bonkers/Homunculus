"""Put the dancers of one fixed-camera shot into ONE scene:   python3 tools/group_scene.py --dir <group_tracks dir> [--out scene]

Input: the stretches of tools/group_segments.py after tools/gvhmr_segments.py (each has clip/smpl_incam.npz: the body in the camera's own frame, x right, y down, z forward, metres, with the intrinsics GVHMR assumes:
focal = the image diagonal, principal point in the middle).  Steps: (1) the camera frame is turned into a y-up frame by flipping y and z (the camera then looks along -z, the way a Blender camera does); (2) the real vertical is found:
the feet of all dancers, when they are low, lie on one floor plane, fitted by least squares (a camera that looks down makes people lean in its frame, so its own y is not up); the frame is rotated so that the floor's normal is +y and the
floor lies at y = 0 (the camera is then at height h above it, pitched down); (3) per dancer a full-length (all frames) SMPL-parameter file in that gravity frame, with the frames outside the verified stretches filled from the nearest verified one.
Writes <dir>/<out>/d<k>_gravity.npz (body_pose, betas, global_orient, transl: what tools/smpl_to_bvh.py reads) and <dir>/<out>/scene.json: intrinsics, the camera's position and orientation, the floor, per dancer the verified
frame ranges and the first absolute position (smpl_to_bvh keeps only the root's travel relative to the first frame, so the scene puts each character at that position)."""
import os, sys, json, argparse
import numpy as np
from scipy.spatial.transform import Rotation as Rot
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__))); sys.path.insert(0, os.path.join(ROOT, "tools"))
import smpl_to_bvh as B
ap = argparse.ArgumentParser(); ap.add_argument("--dir", required=True); ap.add_argument("--out", default="scene"); ap.add_argument("--cuts", default="", help="comma-separated frames where the video cuts to another camera: each shot gets its own floor plane and camera (the render's camera is then set per shot)"); a = ap.parse_args(); a.dir = os.path.abspath(a.dir); out = os.path.join(a.dir, a.out); os.makedirs(out, exist_ok=True)
G = json.load(open(os.path.join(a.dir, "dancers.json"))); S = json.load(open(os.path.join(a.dir, "segments.json"))); N, W, H = G["frames"], G["width"], G["height"]
F = np.diag([1.0, -1.0, -1.0])
PELVIS = np.array([0.0, 0.39, 0.0])       # GVHMR's `transl` is the SMPL-X model's origin, not its pelvis: the pelvis is 0.39 m above it in the body's own frame (fitted to ViTPose keypoints over 2855 frames of six dancers: the reprojection error fell from 0.243 m to 0.043 m; before this the dancers stood 0.39 m too low)
def to_gl(orient, transl):
    R = F @ Rot.from_rotvec(orient).as_matrix(); return Rot.from_matrix(R).as_rotvec(), transl @ F.T                      # R_gl = F R_c, t_gl = F t
def fill_gaps(idx, N, go, bp, betas, tr):
    """Frames outside the verified ones (idx) get a pose: before the first and after the last the nearest verified one; across a gap a blend (rotations by slerp, the root position linearly) of the pose before and the one after.
    (An earlier version took the rounded interpolated index, which maps a gap frame to itself and left it as the zero pose, a T-pose.)"""
    go, bp, betas, tr = go.copy(), bp.copy(), betas.copy(), tr.copy(); ok = np.zeros(N, bool); ok[idx] = True
    for f in range(0, idx[0]): go[f], bp[f], betas[f], tr[f] = go[idx[0]], bp[idx[0]], betas[idx[0]], tr[idx[0]]
    for f in range(idx[-1] + 1, N): go[f], bp[f], betas[f], tr[f] = go[idx[-1]], bp[idx[-1]], betas[idx[-1]], tr[idx[-1]]
    for a, b in zip(idx[:-1], idx[1:]):
        if b - a <= 1: continue
        t = (np.arange(a + 1, b) - a) / (b - a)
        def sl(r0, r1): return Rot.concatenate([Rot.from_rotvec(r0), Rot.from_rotvec(r1)])
        from scipy.spatial.transform import Slerp
        g = Slerp([0, 1], sl(go[a], go[b]))(t).as_rotvec(); go[a + 1:b] = g
        P = bp[a].reshape(21, 3), bp[b].reshape(21, 3); out = np.zeros((b - a - 1, 21, 3))
        for j in range(21): out[:, j] = Slerp([0, 1], sl(P[0][j], P[1][j]))(t).as_rotvec()
        bp[a + 1:b] = out.reshape(-1, 63); tr[a + 1:b] = tr[a] + (tr[b] - tr[a]) * t[:, None]; betas[a + 1:b] = betas[a]
    return go, bp, betas, tr
D = []
for d in S["dancers"]:
    k = d["k"]; arr = {x: np.zeros((N, n)) for x, n in (("global_orient", 3), ("body_pose", 63), ("betas", 10), ("transl", 3))}; valid = np.zeros(N, bool)
    for s in d["segments"]:
        z = np.load(os.path.join(a.dir, f"d{k}", f"s{s['i']:02d}", "clip", "smpl_incam.npz")); L = min(len(z["transl"]), s["frames"]); go, tr = to_gl(z["global_orient"][:L], z["transl"][:L]); tr = tr + Rot.from_rotvec(go).apply(PELVIS)
        arr["global_orient"][s["start"]:s["start"] + L] = go; arr["transl"][s["start"]:s["start"] + L] = tr; arr["body_pose"][s["start"]:s["start"] + L] = z["body_pose"][:L]; arr["betas"][s["start"]:s["start"] + L] = z["betas"][:L]; valid[s["start"]:s["start"] + L] = True
    D.append((k, arr, valid)); print(f"dancer {k}: {valid.sum()} verified frames ({100 * valid.mean():.0f} %)")
# the real vertical: feet low on one plane (per shot when the video has cuts)
pts = []; ups = []
for k, arr, valid in D:
    idx = np.where(valid)[0]
    if len(idx) < 30: continue
    rots = [Rot.from_rotvec(np.concatenate([arr["global_orient"][idx][:, None], arr["body_pose"][idx].reshape(-1, 21, 3), np.zeros((len(idx), 2, 3))], 1)[:, j]) for j in range(24)]
    pos = B.fk(rots, arr["transl"][idx]); feet = pos[:, [7, 8, 10, 11]]; head = pos[:, 15]; mid = pos[:, [7, 8]].mean(1); pts.append((feet, idx, head - mid))
def fit_floor(sel_lo, sel_hi, label):
    ps = []; us = []
    for feet, idx, up_ in pts:
        m_ = (idx >= sel_lo) & (idx < sel_hi)
        if m_.any(): ps.append((feet[m_], idx[m_])); us.append(up_[m_])
    if not ps or sum(len(i) for _, i in ps) < 60: return None
    u = np.concatenate(us).mean(0); u /= np.linalg.norm(u)                                                          # first guess: the body's up, averaged over everybody (leaning averages out)
    for it in range(4):
        low = []
        for feet, idx in ps:
            h = feet @ u; flat = h.reshape(-1); thr = np.percentile(flat, 12); sel = h <= thr; low.append(feet[sel])
        P = np.concatenate(low); c = P.mean(0); U, Sv, Vt = np.linalg.svd(P - c, full_matrices=False); n = Vt[2]; n = n if n @ u > 0 else -n
        spread = np.sqrt(np.mean(((P - c) @ n) ** 2)); u = n / np.linalg.norm(n)
    d_floor = float((c @ u))                                                                                        # the floor: u . p = d_floor (negative: it is below the camera)
    axis = np.cross(u, [0, 1, 0]); ang = np.arccos(np.clip(u[1], -1, 1)); R_fix = Rot.from_rotvec(axis / (np.linalg.norm(axis) + 1e-12) * ang).as_matrix() if ang > 1e-6 else np.eye(3)       # takes u to +y
    view = R_fix @ np.array([0, 0, -1.0]); pitch = float(np.degrees(np.arcsin(np.clip(view[1], -1, 1))))
    print(f"{label}: up vector {u.round(3).tolist()}, tilt {np.degrees(np.arccos(np.clip(u[1], -1, 1))):.1f} deg; feet {spread * 100:.1f} cm (rms) from the plane; camera height {-d_floor:.2f} m; pitch {pitch:.1f} deg")
    return {"u": u, "d_floor": d_floor, "R_fix": R_fix, "spread": float(spread), "pitch": pitch}
cut_frames = [int(x) for x in a.cuts.split(",") if x]; bounds = [0] + cut_frames + [N]
fit_all = fit_floor(0, N, "all frames")
fits = []
for i, (lo, hi) in enumerate(zip(bounds[:-1], bounds[1:])):
    f_ = fit_floor(lo, hi, f"shot {i} ({lo}-{hi})") if len(bounds) > 2 else fit_all
    fits.append(f_ if f_ is not None else fit_all)
shot_of = np.zeros(N, int)
for i, (lo, hi) in enumerate(zip(bounds[:-1], bounds[1:])): shot_of[lo:hi] = i
u, d_floor, R_fix, spread, pitch = fit_all["u"], fit_all["d_floor"], fit_all["R_fix"], fit_all["spread"], fit_all["pitch"]; yaw = 0.0
scene = {"width": W, "height": H, "fps": 30, "frames": N, "fx": float((W ** 2 + H ** 2) ** 0.5), "fy": float((W ** 2 + H ** 2) ** 0.5), "cx": W / 2, "cy": H / 2, "camera_height": -d_floor, "camera_pitch_deg": pitch, "camera_yaw_deg": yaw,
         "up_in_camera_frame": u.tolist(), "floor_rms_cm": float(spread * 100), "dancers": [],
         "shots": [{"start": int(lo), "end": int(hi), "camera_height": -f_["d_floor"], "up_in_camera_frame": f_["u"].tolist(), "pitch_deg": f_["pitch"]} for f_, (lo, hi) in zip(fits, zip(bounds[:-1], bounds[1:]))]}
for k, arr, valid in D:
    idx = np.where(valid)[0]
    if len(idx) == 0: continue
    go = np.zeros((N, 3)); tr = np.zeros((N, 3))
    for i, (lo, hi) in enumerate(zip(bounds[:-1], bounds[1:])):                                                       # every shot in its own gravity frame (camera at the origin, floor below it)
        Rf, df = fits[i]["R_fix"], fits[i]["d_floor"]
        go[lo:hi] = Rot.from_matrix(Rf @ Rot.from_rotvec(arr["global_orient"][lo:hi]).as_matrix()).as_rotvec(); tr[lo:hi] = arr["transl"][lo:hi] @ Rf.T; tr[lo:hi, 1] -= df
    bp, bt = arr["body_pose"].copy(), arr["betas"].copy()
    for lo, hi in zip(bounds[:-1], bounds[1:]):                                                                       # outside the verified stretches: held at the ends, blended across the gaps (inside one shot: a cut is not blended across)
        ids = idx[(idx >= lo) & (idx < hi)]
        if len(ids) == 0: continue
        g_, p_, b_, t_ = fill_gaps(ids - lo, hi - lo, go[lo:hi], bp[lo:hi], bt[lo:hi], tr[lo:hi]); go[lo:hi], bp[lo:hi], bt[lo:hi], tr[lo:hi] = g_, p_, b_, t_
    for lo, hi in zip(bounds[:-1], bounds[1:]):                                                                       # a shot where this dancer was never verified: the nearest verified frame of another shot
        if not ((idx >= lo) & (idx < hi)).any():
            near = idx[np.argmin(np.abs(idx - (lo + hi) // 2))]; go[lo:hi], bp[lo:hi], bt[lo:hi], tr[lo:hi] = go[near], bp[near], bt[near], tr[near]
    arr["body_pose"], arr["betas"] = bp, bt
    np.savez(os.path.join(out, f"d{k}_gravity.npz"), body_pose=arr["body_pose"], betas=arr["betas"], global_orient=go, transl=tr)
    ranges = [[int(s), int(e)] for s, e in zip(np.where(np.diff(np.r_[0, valid.astype(int)]) == 1)[0], np.where(np.diff(np.r_[valid.astype(int), 0]) == -1)[0] + 1)]
    scene["dancers"].append({"k": k, "valid_ranges": ranges, "first_valid": int(idx[0]), "start_xz": [float(tr[0, 0]), float(tr[0, 2])], "betas_mean": arr["betas"][idx].mean(0).tolist()})
json.dump(scene, open(os.path.join(out, "scene.json"), "w"), indent=1)
print(f"camera: height {-d_floor:.2f} m, pitched {pitch:.1f} deg, yaw {yaw:.1f} deg; focal {scene['fx']:.0f} px = {scene['fx'] / W * 36:.1f} mm on a 36 mm sensor; written {out}")
