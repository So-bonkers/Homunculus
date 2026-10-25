"""Fit the SMPL-X template to a generated body mesh: the template keeps its clean topology, skeleton and UVs; only its scale, shape, pose and hands change. (Research use only: SMPL-X's licence.)
    gvhmr/.venv/bin/python tools/template_fit/fit_smplx.py MESH.glb OUT_DIR [--gender male|female|neutral] [--arm-down 0.9]
MESH: a character mesh in the pipeline's frame (z up, the character faces -y, +x is its left), any scale, any triangle soup (a GLB or a PLY). Writes OUT_DIR/fit.obj and fit.glb (the fitted template, in the same frame and scale as MESH),
OUT_DIR/fit.npz (the parameters) and prints how close the fit is, as a percentage of the body height.
Stages: 1 scale/placement/shape/body pose (strong priors), 2 + the hands, 3 relaxed priors. Loss: model -> scan (robust) plus scan -> model (robust, so clothes and hair far outside the template do not drag it).
Runs on the CPU on purpose (the GPU may be busy with the shape model)."""
import sys, os, argparse, numpy as np, torch, trimesh, smplx
from scipy.spatial import cKDTree

ap = argparse.ArgumentParser(); ap.add_argument("mesh"); ap.add_argument("out"); ap.add_argument("--gender", default="neutral"); ap.add_argument("--arm-down", type=float, default=0.9, help="initial angle of the arms below horizontal, radians")
ap.add_argument("--iters", type=int, default=250); ap.add_argument("--betas", type=int, default=40, help="body-shape parameters (the template has up to 300; 10 cannot give a child's big head and short legs)"); ap.add_argument("--no-proportions", action="store_true", help="do not fit the head and leg scales"); ap.add_argument("--save-every", type=int, default=0, help="save a snapshot of the template (OUT_DIR/ckpt_NNN.npy, vertices in the mesh's frame) every N iterations, to watch the fit"); ap.add_argument("--offset-iters", type=int, default=200, help="stage 4: a smooth offset along each vertex normal, capped, to match the scan's shape (0 = skip)"); ap.add_argument("--offset-cap", type=float, default=0.006, help="stage 4: the cap of the offset, in metres of the template"); ap.add_argument("--labels", default=None, help="cloth_labels.npz (tools/template_fit/cloth_labels.py): vertices under clothes are only held INSIDE the scan, with a small inset, and scan points near them are ignored, so the body under baggy clothes follows the visible skin"); ap.add_argument("--cloth-inset", type=float, default=0.012, help="how far inside the scan (cloth surface) the body under the clothes is pulled, as a fraction of the height"); ap.add_argument("--head-frac", type=float, default=None, help="crown-to-chin height of the head as a fraction of the body height, measured on the character's picture (the scan's head is often too big); held with a strong penalty"); ap.add_argument("--models", default=os.path.join(os.path.dirname(os.path.abspath(__file__)), "../../gvhmr/smplsrc/smplx/models_lockedhead")); a = ap.parse_args()
os.makedirs(a.out, exist_ok=True); torch.set_num_threads(8); torch.manual_seed(0)

# the scan, in SMPL's frame (y up, the character faces +z). A GLB is already in that frame (glTF); a PLY/OBJ from Blender (z up, faces -y) is mapped (x, y, z) -> (x, z, -y)
sc = trimesh.load(a.mesh, force="mesh"); P, fidx = trimesh.sample.sample_surface(sc, 120000); P = np.asarray(P, np.float64); SN0 = np.asarray(sc.face_normals)[fidx]
R_in = np.eye(3) if a.mesh.lower().endswith((".glb", ".gltf")) else np.array([[1, 0, 0], [0, 0, 1], [0, -1, 0]], np.float64); S = P @ R_in.T; SN = SN0 @ R_in.T
H_t = S[:, 1].max() - S[:, 1].min(); print(f"scan: {len(sc.vertices)} vertices, height {H_t:.3f}")
S_t = torch.tensor(S, dtype=torch.float32); SN_t = torch.tensor(SN, dtype=torch.float32); tree_scan = cKDTree(S)

model = smplx.create(a.models, model_type="smplx", gender=a.gender, use_pca=False, flat_hand_mean=True, num_betas=a.betas, batch_size=1)
v0 = model.v_template.detach().numpy(); H_m = v0[:, 1].max() - v0[:, 1].min(); faces = model.faces
scale = torch.tensor([H_t / H_m], requires_grad=True)
transl = torch.tensor([[S[:, 0].mean(), S[:, 1].min() - v0[:, 1].min() * H_t / H_m, S[:, 2].mean()]], dtype=torch.float32, requires_grad=True)
betas = torch.zeros(1, a.betas, requires_grad=True); glob = torch.zeros(1, 3, requires_grad=True)
body = torch.zeros(1, 63, requires_grad=True); lh = torch.zeros(1, 45, requires_grad=True); rh = torch.zeros(1, 45, requires_grad=True)


base_vt = model.v_template.detach().clone(); off_s = torch.zeros(base_vt.shape[0], requires_grad=True); use_off = [False]
# proportions: the head and the legs are scaled on the template's own vertices (through the skinning weights, so the joints derived from them move too: the skeleton follows)
LW = model.lbs_weights.detach(); w_head = LW[:, [15, 22, 23, 24]].sum(1); w_leg = LW[:, [1, 2, 4, 5, 7, 8, 10, 11]].sum(1)
J0 = (model.J_regressor.detach() @ base_vt); c_neck = J0[12].clone(); pelvis_y = float(J0[0, 1])
log_head = torch.zeros(1, requires_grad=True); log_leg = torch.zeros(1, requires_grad=True)


def proportioned():
    if a.no_proportions: return base_vt
    sh, sl = torch.exp(log_head), torch.exp(log_leg); vt = base_vt + w_head[:, None] * (sh - 1) * (base_vt - c_neck)
    return torch.stack([vt[:, 0], vt[:, 1] + w_leg * (sl - 1) * (vt[:, 1] - pelvis_y), vt[:, 2]], dim=1)
_n = trimesh.Trimesh(vertices=base_vt.numpy(), faces=model.faces, process=False).vertex_normals; base_n = torch.tensor(np.asarray(_n), dtype=torch.float32)       # unit normals of the template, fixed


def forward():
    model.v_template = proportioned() + (torch.tanh(off_s)[:, None] * a.offset_cap * base_n if use_off[0] else 0.0)                                  # SMPL+D: the offsets are in the template's space, so the skinning carries them
    o = model(betas=betas, global_orient=glob, body_pose=body, left_hand_pose=lh, right_hand_pose=rh, transl=torch.zeros(1, 3), return_verts=True)
    return o.vertices[0] * scale + transl[0], o.joints[0] * scale + transl[0]


def arms(angle):
    b = torch.zeros(1, 63); b[0, 3 * 15 + 2] = -angle; b[0, 3 * 16 + 2] = angle                   # joints 16 and 17 (left, right shoulder) are entries 15 and 16 of the body pose; z-rotation lowers the arm
    return b


CL = torch.tensor(np.load(a.labels)["labels"] > 0) if a.labels else None; CLn = CL.numpy() if CL is not None else None
def scan_term(v, nn_idx):
    """model -> scan, robust; for the vertices under clothes only the part outside the scan counts, plus a gentle pull to `cloth-inset` inside it"""
    nn = S_t[nn_idx]; d = (v - nn).norm(dim=1); r = robust(d, 0.04 * H_t)
    if CL is None: return r.mean()
    sd = ((v - nn) * SN_t[nn_idx]).sum(1)                                                                                  # signed: > 0 outside the scan
    rc = robust(torch.relu(sd), 0.04 * H_t) + 0.3 * robust(sd + a.cloth_inset * H_t, 0.04 * H_t)
    return torch.where(CL, rc, r).mean()


# crown and chin vertices (found on the rest template): the 20 highest vertices of the head, the 20 lowest vertices that the jaw joint owns
_dom = LW.argmax(1).numpy(); _hd = np.nonzero(np.isin(_dom, [15, 22]))[0]; _y0 = base_vt[:, 1].numpy()
crown_idx = torch.tensor(_hd[np.argsort(-_y0[_hd])[:20]]); _jw = np.nonzero(_dom == 22)[0]; chin_idx = torch.tensor(_jw[np.argsort(_y0[_jw])[:20]])
def head_term(v):
    if a.head_frac is None: return 0.0
    hh = (v[crown_idx, 1].mean() - v[chin_idx, 1].mean()) / H_t; return 400.0 * (hh - a.head_frac) ** 2


def robust(d, c):                                                                                 # Geman-McClure: far points (clothes, hair) count for little
    return (d ** 2) / (d ** 2 + c ** 2)


def loss(w):
    v, _ = forward(); vn = v.detach().numpy()
    d1, i1 = tree_scan.query(vn); nn = S_t[i1]; l1 = scan_term(v, torch.tensor(i1))                    # model -> scan
    sub = np.random.default_rng(0).choice(len(S), 12000, replace=False); d2, i2 = cKDTree(vn).query(S[sub])
    if CLn is not None: keep = ~CLn[i2]; sub, i2, d2 = sub[keep], i2[keep], d2[keep]                                  # scan points whose nearest template vertex is under clothes say nothing about the body
    l2 = robust((S_t[sub] - v[torch.tensor(i2)]).norm(dim=1), 0.04 * H_t).mean()   # scan -> model
    reg = w["beta"] * (betas ** 2).sum() + w["pose"] * (body ** 2).sum() + w["hand"] * ((lh ** 2).sum() + (rh ** 2).sum())
    return l1 + w["back"] * l2 + reg + head_term(v), float(np.mean(d1)) / H_t * 100, float(np.mean(d2)) / H_t * 100


_ck = [0]
def snapshot(tag):
    if not a.save_every: return
    with torch.no_grad(): v, _ = forward()
    np.save(os.path.join(a.out, f"ckpt_{_ck[0]:03d}_{tag}.npy"), (v.numpy().astype(np.float64) @ R_in).astype(np.float32)); _ck[0] += 1                  # back to the mesh's frame (R_in is orthogonal: x @ R_in = R_in^T x)


def stage(name, params, lrs, w, iters):
    opt = torch.optim.Adam([{"params": [p], "lr": lr} for p, lr in zip(params, lrs)])
    for it in range(iters):
        if a.save_every and it % a.save_every == 0: snapshot(f"s{name}")
        opt.zero_grad(); L, e1, e2 = loss(w); L.backward(); opt.step()
        with torch.no_grad(): log_head.clamp_(np.log(0.8), np.log(1.9)); log_leg.clamp_(np.log(0.55), np.log(1.1))      # a head up to 1.9x, legs 0.55-1.1x
        if it % 50 == 0 or it == iters - 1: print(f"  {name} {it:4d}: loss {float(L):.4f}  model->scan {e1:.2f} % H  scan->model {e2:.2f} % H", flush=True)


# stage 0: which way do the arms hang? try the initial angle and half of it, keep the better start
best = None
for ang in (a.arm_down, a.arm_down * 0.6):
    with torch.no_grad(): body.copy_(arms(ang)); L, e1, e2 = loss({"beta": 0, "pose": 0, "hand": 0, "back": 1.0})
    print(f"init arms {ang:.2f} rad: model->scan {e1:.2f} % H"); best = (float(L), ang) if best is None or float(L) < best[0] else best
with torch.no_grad(): body.copy_(arms(best[1]))
snapshot("init")
print("stage 1: scale, placement, shape, body pose, head and leg scales")
stage("1", [scale, transl, glob, betas, body, log_head, log_leg], [0.01, 0.01, 0.02, 0.05, 0.03, 0.02, 0.02], {"beta": 0.002, "pose": 0.002, "hand": 0.0, "back": 0.5}, a.iters)
print("stage 2: + hands")
stage("2", [scale, transl, glob, betas, body, lh, rh, log_head, log_leg], [0.005, 0.005, 0.01, 0.03, 0.02, 0.03, 0.03, 0.01, 0.01], {"beta": 0.002, "pose": 0.001, "hand": 0.0005, "back": 1.0}, a.iters)
print("stage 3: relaxed priors")
stage("3", [scale, transl, glob, betas, body, lh, rh, log_head, log_leg], [0.002, 0.002, 0.005, 0.02, 0.01, 0.02, 0.02, 0.005, 0.005], {"beta": 0.0005, "pose": 0.0003, "hand": 0.0002, "back": 1.0}, a.iters)

snapshot("s3end")
if a.offset_iters:
    print("stage 4: smooth offsets along the normals (capped), template shape")
    use_off[0] = True; ed = np.concatenate([model.faces[:, [0, 1]], model.faces[:, [1, 2]], model.faces[:, [2, 0]]]); ed = np.unique(np.sort(ed, axis=1), axis=0); ei = torch.tensor(ed, dtype=torch.long)
    deg = torch.zeros(base_vt.shape[0]).index_add_(0, ei[:, 0], torch.ones(len(ei))).index_add_(0, ei[:, 1], torch.ones(len(ei))).clamp(min=1)
    def lap(x): acc = torch.zeros_like(x).index_add_(0, ei[:, 0], x[ei[:, 1]]).index_add_(0, ei[:, 1], x[ei[:, 0]]); return acc / deg - x
    def loss4(w):
        v, _ = forward(); vn = v.detach().numpy(); d1, i1 = tree_scan.query(vn); l1 = scan_term(v, torch.tensor(i1))
        sm = torch.tanh(off_s); return l1 + head_term(v) + w["lap"] * (lap(sm) ** 2).mean() + w["mag"] * (sm ** 2).mean(), float(np.mean(d1)) / H_t * 100
    opt = torch.optim.Adam([off_s], lr=0.05)
    for it in range(a.offset_iters):
        if a.save_every and it % a.save_every == 0: snapshot("s4")
        opt.zero_grad(); L, e1 = loss4({"lap": 8.0, "mag": 0.002}); L.backward(); opt.step()
        if it % 50 == 0 or it == a.offset_iters - 1: print(f"  4 {it:4d}: loss {float(L):.4f}  model->scan {e1:.2f} % H", flush=True)
    snapshot("s4end")
with torch.no_grad(): v, j = forward()
vn = v.numpy().astype(np.float64); R_out = R_in.T                                               # back to the pipeline's frame
out_v = vn @ R_out.T
tm = trimesh.Trimesh(vertices=out_v, faces=faces, process=False); tm.export(os.path.join(a.out, "fit.obj")); tm.export(os.path.join(a.out, "fit.glb"))
np.savez(os.path.join(a.out, "fit.npz"), head_scale=float(torch.exp(log_head)), leg_scale=float(torch.exp(log_leg)), offsets=(torch.tanh(off_s) * a.offset_cap).detach().numpy() if a.offset_iters else np.zeros(1), betas=betas.detach().numpy(), glob=glob.detach().numpy(), body=body.detach().numpy(), lh=lh.detach().numpy(), rh=rh.detach().numpy(), scale=scale.detach().numpy(), transl=transl.detach().numpy(),
         joints=(j.numpy() @ R_out.T), gender=a.gender)
_, e1, e2 = loss({"beta": 0, "pose": 0, "hand": 0, "back": 1.0})
d_hi, _ = tree_scan.query(vn); _v, _ = forward(); print(f"head height {float((_v[crown_idx, 1].mean() - _v[chin_idx, 1].mean()) / H_t) * 100:.1f} % of the body height")
print(f"proportions: head x{float(torch.exp(log_head)):.2f}, legs x{float(torch.exp(log_leg)):.2f}; betas used {int((betas.abs() > 0.05).sum())} of {a.betas} (|beta| > 0.05)")
print(f"FIT: model->scan mean {e1:.2f} % of the height, scan->model mean {e2:.2f} %; template vertices within 1 % of H of the scan: {100 * float((d_hi < 0.01 * H_t).mean()):.0f} %")
