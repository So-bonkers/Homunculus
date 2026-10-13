"""Undo GVHMR's static-camera assumption with the camera motion tracked from the video (tools/track_camera.py).

    gvhmr/.venv/bin/python tools/compensate_camera.py <out_dir containing hmr4d_results.pt> <camera_track.npz> <smpl_global_cam.npz> [--seconds S]

GVHMR run with -s treats the camera as fixed, so when the real camera pans, the dancer's global path and heading are off by the pan angle (about 1.3 m for 14 degrees at 5.4 m).
Here the per-frame estimate in the camera's own frame (smpl_params_incam: pelvis position and orientation as seen in frame t) is turned back into the camera of frame 0 with R_t^T, then into GVHMR's
gravity-aligned world with the one rotation that relates the two frames in the first seconds (where the camera has hardly moved: mean of O_global O_incam^T). Only the slow part (1.5 s) of the correction is applied, because the tracker's frame-to-frame noise times 5 m makes the feet skate. Positions are also rescaled by the tracked zoom (GVHMR assumes a constant focal length, so zooming in looks like walking closer). Body pose (local joint rotations) is unchanged.
Writes the same fields as smpl_global.npz (body_pose, betas, global_orient, transl), so tools/smpl_to_bvh.py reads it as before."""
import sys, os, torch, numpy as np, smplx
from scipy.spatial.transform import Rotation as Rot
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
a = sys.argv[1:]; secs = 10.0
if "--seconds" in a: i = a.index("--seconds"); secs = float(a[i + 1]); del a[i:i + 2]
res = torch.load(os.path.join(a[0], "hmr4d_results.pt"), map_location="cpu", weights_only=False); T = np.load(a[1])
G, C = res["smpl_params_global"], res["smpl_params_incam"]; n = min(len(G["transl"]), len(T["R"]))
m = smplx.create(os.path.join(ROOT, "gvhmr/repo/inputs/checkpoints/body_models"), "smplx", gender="neutral", use_pca=False, flat_hand_mean=True, num_betas=10, batch_size=1)
J0 = m(betas=G["betas"][:1], global_orient=torch.zeros(1, 3), body_pose=torch.zeros(1, 63), transl=torch.zeros(1, 3)).joints[0, 0].detach().numpy().astype(float)      # rest pelvis position: transl is relative to it
Og, Oc = Rot.from_rotvec(G["global_orient"].numpy()[:n]), Rot.from_rotvec(C["global_orient"].numpy()[:n]); k = max(3, int(secs * 30))
Rg = (Og[:k] * Oc[:k].inv()).mean()                                                                  # incam frame -> GVHMR world, from the first seconds
pc = C["transl"].numpy()[:n].astype(float) + J0; pg = G["transl"].numpy()[:n].astype(float) + J0       # pelvis positions
Rt = Rot.from_matrix(T["R"][:n]); zoom = np.clip(T["f"][:n] / T["f"][0], 0.6, 1.6)           # GVHMR assumes a constant focal length: a zoom of x2 makes the dancer look half as far away
pc = pc * zoom[:, None]
p_new = Rg.apply(Rt.inv().apply(pc)); p_new += pg[0] - p_new[0]                                        # frame 0 stays where GVHMR put it
O_new = Rg * Rt.inv() * Oc
from scipy.ndimage import gaussian_filter1d                                                            # the tracker's frame-to-frame noise x 5 m of distance makes the feet skate: keep GVHMR's own (foot-consistent) motion and apply only the slow part of the correction
SIG = 45
p_new = pg + gaussian_filter1d(p_new - pg, SIG, axis=0, mode="nearest")
O_new = Rot.from_rotvec(gaussian_filter1d((O_new * Og.inv()).as_rotvec(), SIG, axis=0, mode="nearest")) * Og
mis = np.degrees((Og[:k] * (Rg * Oc[:k]).inv()).magnitude()).mean()
out = {k_: v.numpy() for k_, v in G.items()}; out["transl"] = (p_new - J0).astype(np.float32)[:len(out["transl"])]; out["global_orient"] = O_new.as_rotvec().astype(np.float32)
for k_ in ("body_pose", "betas"): out[k_] = out[k_][:n]
out["global_orient"] = out["global_orient"][:n]; out["transl"] = out["transl"][:n]
np.savez(a[2], **out)
d = np.linalg.norm((p_new - pg)[:, [0, 2]], axis=1)
print(f"[compensate_camera] {n} frames; incam->world rotation fitted on {k} frames (residual {mis:.1f} deg); path moved by up to {d.max():.2f} m (median {np.median(d):.2f} m) against GVHMR's static-camera path -> {a[2]}")
