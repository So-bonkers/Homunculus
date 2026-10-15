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
ap = argparse.ArgumentParser(); ap.add_argument("--dir", required=True); ap.add_argument("--out", default="scene"); a = ap.parse_args(); a.dir = os.path.abspath(a.dir); out = os.path.join(a.dir, a.out); os.makedirs(out, exist_ok=True)
G = json.load(open(os.path.join(a.dir, "dancers.json"))); S = json.load(open(os.path.join(a.dir, "segments.json"))); N, W, H = G["frames"], G["width"], G["height"]
F = np.diag([1.0, -1.0, -1.0])
def to_gl(orient, transl):
    R = F @ Rot.from_rotvec(orient).as_matrix(); return Rot.from_matrix(R).as_rotvec(), transl @ F.T                      # R_gl = F R_c, t_gl = F t
D = []
for d in S["dancers"]:
    k = d["k"]; arr = {x: np.zeros((N, n)) for x, n in (("global_orient", 3), ("body_pose", 63), ("betas", 10), ("transl", 3))}; valid = np.zeros(N, bool)
    for s in d["segments"]:
        z = np.load(os.path.join(a.dir, f"d{k}", f"s{s['i']:02d}", "clip", "smpl_incam.npz")); L = min(len(z["transl"]), s["frames"]); go, tr = to_gl(z["global_orient"][:L], z["transl"][:L])
        arr["global_orient"][s["start"]:s["start"] + L] = go; arr["transl"][s["start"]:s["start"] + L] = tr; arr["body_pose"][s["start"]:s["start"] + L] = z["body_pose"][:L]; arr["betas"][s["start"]:s["start"] + L] = z["betas"][:L]; valid[s["start"]:s["start"] + L] = True
    D.append((k, arr, valid)); print(f"dancer {k}: {valid.sum()} verified frames ({100 * valid.mean():.0f} %)")
# the real vertical: feet low on one plane
pts = []; ups = []
for k, arr, valid in D:
    idx = np.where(valid)[0]
    if len(idx) < 30: continue
    rots = [Rot.from_rotvec(np.concatenate([arr["global_orient"][idx][:, None], arr["body_pose"][idx].reshape(-1, 21, 3), np.zeros((len(idx), 2, 3))], 1)[:, j]) for j in range(24)]
    pos = B.fk(rots, arr["transl"][idx]); feet = pos[:, [7, 8, 10, 11]]; head = pos[:, 15]; mid = pos[:, [7, 8]].mean(1); ups.append(head - mid); pts.append((feet, idx))
u = np.concatenate(ups).mean(0); u /= np.linalg.norm(u)                                                              # first guess: the body's up, averaged over everybody (leaning averages out)
for it in range(4):
    low = []
    for feet, idx in pts:
        h = feet @ u; flat = h.reshape(-1); thr = np.percentile(flat, 12); sel = h <= thr; low.append(feet[sel])
    P = np.concatenate(low); c = P.mean(0); U, Sv, Vt = np.linalg.svd(P - c, full_matrices=False); n = Vt[2]; n = n if n @ u > 0 else -n
    spread = np.sqrt(np.mean(((P - c) @ n) ** 2)); u = n / np.linalg.norm(n)
d_floor = float((c @ u))                                                                                            # the floor: u . p = d_floor (negative: it is below the camera)
print(f"up vector in the camera frame (y up, z back): {u.round(3).tolist()}; tilt from the camera's own up {np.degrees(np.arccos(np.clip(u[1], -1, 1))):.1f} deg; the feet's distance from the plane {spread * 100:.1f} cm (rms); camera height {-d_floor:.2f} m")
axis = np.cross(u, [0, 1, 0]); ang = np.arccos(np.clip(u[1], -1, 1)); R_fix = Rot.from_rotvec(axis / (np.linalg.norm(axis) + 1e-12) * ang).as_matrix() if ang > 1e-6 else np.eye(3)       # takes u to +y
cam_R = R_fix                                                                                                       # camera -> gravity frame: a Blender camera looks along its own -z
view = cam_R @ np.array([0, 0, -1.0]); pitch = float(np.degrees(np.arcsin(np.clip(view[1], -1, 1)))); yaw = float(np.degrees(np.arctan2(-view[0], -view[2])))
scene = {"width": W, "height": H, "fps": 30, "frames": N, "fx": float((W ** 2 + H ** 2) ** 0.5), "fy": float((W ** 2 + H ** 2) ** 0.5), "cx": W / 2, "cy": H / 2, "camera_height": -d_floor, "camera_pitch_deg": pitch, "camera_yaw_deg": yaw,
         "up_in_camera_frame": u.tolist(), "floor_rms_cm": float(spread * 100), "dancers": []}
for k, arr, valid in D:
    idx = np.where(valid)[0]
    if len(idx) == 0: continue
    go = Rot.from_matrix(R_fix @ Rot.from_rotvec(arr["global_orient"]).as_matrix()).as_rotvec(); tr = arr["transl"] @ R_fix.T; tr[:, 1] -= d_floor
    for key in ("global_orient", "body_pose", "betas", "transl"):                                                  # outside the verified stretches: the nearest verified frame
        v = go if key == "global_orient" else tr if key == "transl" else arr[key]; near = np.interp(np.arange(N), idx, idx).round().astype(int); v[:] = v[near]
    np.savez(os.path.join(out, f"d{k}_gravity.npz"), body_pose=arr["body_pose"], betas=arr["betas"], global_orient=go, transl=tr)
    ranges = [[int(s), int(e)] for s, e in zip(np.where(np.diff(np.r_[0, valid.astype(int)]) == 1)[0], np.where(np.diff(np.r_[valid.astype(int), 0]) == -1)[0] + 1)]
    scene["dancers"].append({"k": k, "valid_ranges": ranges, "first_valid": int(idx[0]), "start_xz": [float(tr[0, 0]), float(tr[0, 2])], "betas_mean": arr["betas"][idx].mean(0).tolist()})
json.dump(scene, open(os.path.join(out, "scene.json"), "w"), indent=1)
print(f"camera: height {-d_floor:.2f} m, pitched {pitch:.1f} deg, yaw {yaw:.1f} deg; focal {scene['fx']:.0f} px = {scene['fx'] / W * 36:.1f} mm on a 36 mm sensor; written {out}")
