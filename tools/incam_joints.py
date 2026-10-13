"""GVHMR result -> joint positions in the CAMERA frame (metres, x right, y down, z forward), for tools/align_camera.py.

    gvhmr/.venv/bin/python tools/incam_joints.py <out_dir containing hmr4d_results.pt> <joints.npz>
Runs SMPL-X forward on smpl_params_incam (22 body joints) and keeps the K the model assumed."""
import sys, torch, numpy as np, smplx, os
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
r = torch.load(os.path.join(sys.argv[1], "hmr4d_results.pt"), map_location="cpu", weights_only=False); P = r["smpl_params_incam"]; n = len(P["body_pose"])
m = smplx.create(os.path.join(ROOT, "gvhmr/repo/inputs/checkpoints/body_models"), "smplx", gender="neutral", use_pca=False, flat_hand_mean=True, num_betas=10, batch_size=n)
J = m(betas=P["betas"], global_orient=P["global_orient"], body_pose=P["body_pose"], transl=P["transl"]).joints[:, :22].detach().numpy()
np.savez(sys.argv[2], J=J, K=r["K_fullimg"][0].numpy()); print(f"[incam_joints] {n} frames -> {sys.argv[2]}; pelvis distance from the camera {np.median(J[:, 0, 2]):.1f} m (median)")
