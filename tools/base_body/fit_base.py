"""Fit our parametric base body to a generated character mesh (the base keeps its clean quads, UVs and Mixamo rig; sliders, pose and placement change).
    gvhmr/.venv/bin/python tools/base_body/fit_base.py MESH.glb OUT_DIR [--age 0.15] [--gender 0.3] [--iters 200] [--save-every 0]
MESH: a GLB in glTF's frame (y up, faces +z), any scale. Writes OUT_DIR/fit.npz (macro, sliders by name, pose, scale, transl, joints), fit.obj (posed body, mesh frame), rest.obj (unposed, shape only).
Stages: 1 placement, macro (gender, age, muscle, weight) and body pose; 2 + detail sliders and finger pose; 3 relaxed priors. Loss: robust chamfer both ways (clothes and hair are far outside the body and count for little)."""
import sys, os, argparse, numpy as np, torch, trimesh
from scipy.spatial import cKDTree
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__))); from model import Base
ap = argparse.ArgumentParser(); ap.add_argument("mesh"); ap.add_argument("out"); ap.add_argument("--age", type=float, default=0.15); ap.add_argument("--gender", type=float, default=0.3); ap.add_argument("--iters", type=int, default=200)
ap.add_argument("--save-every", type=int, default=0); ap.add_argument("--arm-down", type=float, default=0.0); ap.add_argument("--offset-iters", type=int, default=150); ap.add_argument("--offset-cap", type=float, default=0.02, help="cap of the residual offsets, metres of the base (a 1.7 m body)"); ap.add_argument("--flip", default="auto", help="auto | yes | no: the scan faces -z (turn it by 180 degrees about the vertical)"); a = ap.parse_args(); os.makedirs(a.out, exist_ok=True); torch.set_num_threads(8); torch.manual_seed(0)
sc = trimesh.load(a.mesh, force="mesh"); P, _ = trimesh.sample.sample_surface(sc, 100000); S = np.asarray(P, np.float64); H_t = S[:, 1].max() - S[:, 1].min(); S_t = torch.tensor(S, dtype=torch.float32); tree = cKDTree(S)
B = Base(); K = B.J; nb = len(B.bone_names); print(f"scan height {H_t:.3f}; base: {B.n} body vertices, {K} sliders, {nb} bones")
if a.flip != "no":
    c = S.mean(0); S_f = (S - c) * np.array([-1, 1, -1]) + c
    def quick(Sx):            # the base at its default pose, scaled and placed on the scan: nearest-surface error
        with torch.no_grad():
            v, _, _ = B.forward(torch.tensor([a.gender, a.age, 0.5, 0.5]), torch.full((B.J,), 1e-3), torch.zeros(len(B.bone_names), 3)); v = v.numpy(); sc_ = (Sx[:, 1].max() - Sx[:, 1].min()) / (v[:, 1].max() - v[:, 1].min()); v = v * sc_
            v = v - np.array([v[:, 0].mean() - Sx[:, 0].mean(), v[:, 1].min() - Sx[:, 1].min(), v[:, 2].mean() - Sx[:, 2].mean()]); return float(np.mean(cKDTree(Sx).query(v[::7])[0]) + np.mean(cKDTree(v).query(Sx[::40])[0]))
    e0, e1_ = quick(S), quick(S_f); print(f"facing: +z {e0:.4f}, -z {e1_:.4f}")
    if a.flip == "yes" or (a.flip == "auto" and e1_ < e0): S = S_f; S_t = torch.tensor(S, dtype=torch.float32); tree = cKDTree(S); print("scan turned by 180 degrees")
fingers = torch.tensor([any(f in n for f in ("Index", "Middle", "Ring", "Pinky", "Thumb")) for n in B.bone_names]).float()
macro = torch.tensor([a.gender, a.age, 0.5, 0.5], requires_grad=True); sliders = torch.full((K,), 1e-3, requires_grad=True); pose = torch.zeros(nb, 3, requires_grad=True)
with torch.no_grad(): v0, _, _ = B.forward(macro, sliders, pose); H_m = float(v0[:, 1].max() - v0[:, 1].min())
scale = torch.tensor([H_t / H_m], requires_grad=True); transl = torch.tensor([S[:, 0].mean(), S[:, 1].min() - float(v0[:, 1].min()) * H_t / H_m, S[:, 2].mean()], dtype=torch.float32, requires_grad=True)
if a.arm_down:
    with torch.no_grad():
        for n, sgn in (("LeftArm", -1), ("RightArm", 1)): pose[B.bone_names.index("mixamorig:" + n), 2] = sgn * a.arm_down
off_s = torch.zeros(B.n, 3, requires_grad=True); use_off = [False]
def offsets(): return torch.tanh(off_s) * a.offset_cap if use_off[0] else None
def body():
    v, J, vr = B.forward(macro, sliders, pose, offsets=offsets()); return v * scale + transl, J * scale + transl
def robust(d, c): return d ** 2 / (d ** 2 + c ** 2)
def loss(w, fing=True):
    v, _ = body(); vn = v.detach().numpy(); d1, i1 = tree.query(vn); l1 = robust((v - S_t[i1]).norm(dim=1), 0.04 * H_t).mean()
    sub = np.random.default_rng(0).choice(len(S), 12000, replace=False); d2, i2 = cKDTree(vn).query(S[sub]); l2 = robust((S_t[sub] - v[torch.tensor(i2)]).norm(dim=1), 0.04 * H_t).mean()
    reg = w["slider"] * (sliders ** 2).sum() + 0.02 * sum((sliders[i] - sliders[j]) ** 2 for i, j in B.lr_pairs) + w["pose"] * (((pose - pose_init) * (1 - fingers[:, None]) * (1 - armb[:, None] * 0.9)) ** 2).sum() * 40 + w["finger"] * ((pose * fingers[:, None]) ** 2).sum() + w["macro"] * ((macro[2:] - 0.5) ** 2).sum()
    return l1 + w["back"] * l2 + reg, float(np.mean(d1)) / H_t * 100, float(np.mean(d2)) / H_t * 100
def stage(name, params, lrs, w, iters, freeze_fingers=True):
    opt = torch.optim.Adam([{"params": [p], "lr": lr} for p, lr in zip(params, lrs)])
    for it in range(iters):
        if a.save_every and it % a.save_every == 0:
            with torch.no_grad(): np.save(os.path.join(a.out, f"ckpt_{name}_{it:03d}.npy"), body()[0].numpy())
        opt.zero_grad(); L, e1, e2 = loss(w); L.backward()
        if freeze_fingers: pose.grad = pose.grad * (1 - fingers[:, None])
        opt.step()
        with torch.no_grad(): macro[:2].clamp_(0, 1); macro[2:].clamp_(0, 1); sliders.copy_(torch.max(torch.min(sliders, B.hi), B.lo))
        if it % 50 == 0 or it == iters - 1: print(f"  {name} {it:4d}: loss {float(L):.4f}  model->scan {e1:.2f} % H  scan->model {e2:.2f} % H", flush=True)
pose_init = torch.zeros(nb, 3); armb = torch.tensor([("Arm" in n and "Fore" not in n) for n in B.bone_names]).float()
print("stage 0: which way do the arms hang? try starting angles, keep the best")
best = None
for ang in (-0.6, -0.3, 0.0, 0.3, 0.6, 0.9, 1.2, 1.5):
    with torch.no_grad():
        for n, sgn in (("LeftArm", 1), ("RightArm", -1)): pose[B.bone_names.index("mixamorig:" + n)] = torch.tensor([0, 0, sgn * ang])
        L0, e1, e2 = loss({"slider": 0, "pose": 0, "finger": 0, "macro": 0, "back": 0.5})
    print(f"  arms {ang:+.1f} rad: model->scan {e1:.2f} % H"); best = (float(L0), ang) if best is None or float(L0) < best[0] else best
with torch.no_grad():
    for n, sgn in (("LeftArm", 1), ("RightArm", -1)): pose[B.bone_names.index("mixamorig:" + n)] = torch.tensor([0, 0, sgn * best[1]])
pose_init = pose.detach().clone()
print("stage 1: placement, macro, body pose")
stage("1", [scale, transl, macro, pose], [0.01, 0.01, 0.01, 0.02], {"slider": 0, "pose": 0.0005, "finger": 1, "macro": 0.02, "back": 0.5}, a.iters)
print("stage 2: + detail sliders, fingers")
stage("2", [scale, transl, macro, pose, sliders], [0.005, 0.005, 0.005, 0.02, 0.02], {"slider": 0.01, "pose": 0.0005, "finger": 0.001, "macro": 0.02, "back": 1.0}, a.iters, freeze_fingers=False)
print("stage 3: relaxed")
stage("3", [scale, transl, macro, pose, sliders], [0.002, 0.002, 0.002, 0.01, 0.01], {"slider": 0.001, "pose": 0.0005, "finger": 0.0005, "macro": 0.01, "back": 1.0}, a.iters, freeze_fingers=False)
if a.offset_iters:
    print("stage 4: free per-vertex residual (smooth, capped): what the sliders cannot say")
    use_off[0] = True; q = torch.tensor(B.faces, dtype=torch.long); ed = torch.cat([q[:, [0, 1]], q[:, [1, 2]], q[:, [2, 3]], q[:, [3, 0]]]); ed = torch.cat([ed, ed.flip(1)])
    deg = torch.zeros(B.n).index_add_(0, ed[:, 0], torch.ones(len(ed))).clamp(min=1)
    def lap(x): return torch.zeros_like(x).index_add_(0, ed[:, 0], x[ed[:, 1]]) / deg[:, None] - x
    opt = torch.optim.Adam([off_s], lr=0.05)
    for it in range(a.offset_iters):
        opt.zero_grad(); L, e1, e2 = loss({"slider": 0, "pose": 0, "finger": 0, "macro": 0, "back": 1.0}); sm = torch.tanh(off_s); L = L + 3.0 * (lap(sm) ** 2).mean() + 0.002 * (sm ** 2).mean(); L.backward(); opt.step()
        if it % 50 == 0 or it == a.offset_iters - 1: print(f"  4 {it:4d}: model->scan {e1:.2f} % H  scan->model {e2:.2f} % H", flush=True)
with torch.no_grad():
    v, J = body(); vr = B.forward(macro, sliders, torch.zeros(nb, 3), offsets=offsets())[0] * scale + transl                  # the rest A-pose of this character (shape only)
    trimesh.Trimesh(vertices=v.numpy(), faces=np.concatenate([B.faces[:, [0, 1, 2]], B.faces[:, [0, 2, 3]]]), process=False).export(os.path.join(a.out, "fit.obj"))
    trimesh.Trimesh(vertices=vr.numpy(), faces=np.concatenate([B.faces[:, [0, 1, 2]], B.faces[:, [0, 2, 3]]]), process=False).export(os.path.join(a.out, "rest.obj"))
    _, e1, e2 = loss({"slider": 0, "pose": 0, "finger": 0, "macro": 0, "back": 1.0}); d, _ = tree.query(v.numpy())
    np.savez(os.path.join(a.out, "fit.npz"), macro=macro.numpy(), sliders=sliders.detach().numpy(), slider_names=np.array(B.slider_names), offsets=(offsets().detach().numpy() if a.offset_iters else np.zeros((B.n, 3))), pose=pose.detach().numpy(), scale=scale.numpy(), transl=transl.detach().numpy(), joints=J.numpy(), bone_names=np.array(B.bone_names))
top = np.abs(sliders.detach().numpy()).argsort()[::-1][:12]; print("macro (gender, age, muscle, weight):", [round(float(x), 2) for x in macro]); print("strongest sliders:", [(B.slider_names[i], round(float(sliders[i]), 2)) for i in top])
print(f"FIT: model->scan mean {e1:.2f} % of the height, scan->model {e2:.2f} %; vertices within 1 % of H: {100 * float((d < 0.01 * H_t).mean()):.0f} %")

# QA picture: scan points (grey) and the fitted body (red), front (x, y) and side (z, y)
from PIL import Image, ImageDraw
H_px = 700; sc_ = H_px / H_t; im = Image.new("RGB", (1000, H_px + 40), (255, 255, 255)); dr = ImageDraw.Draw(im); y0 = S[:, 1].min(); xs = S[:, 0].mean(); zs = S[:, 2].mean(); vv = v.numpy()
for pts, col in ((S[::20], (170, 170, 170)), (vv[::2], (220, 30, 30))):
    for q in pts:
        dr.point((250 + (q[0] - xs) * sc_, H_px + 20 - (q[1] - y0) * sc_), fill=col); dr.point((750 + (q[2] - zs) * sc_, H_px + 20 - (q[1] - y0) * sc_), fill=col)
im.save(os.path.join(a.out, "overlay.png"))
