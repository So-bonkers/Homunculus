"""Train the palm-direction prior (homunculus/hand_prior.py) on FineDance and write homunculus/data/hand_prior.npz. Run with the GVHMR environment (torch):

    gvhmr/.venv/bin/python tools/train_hand_prior.py [--finedance mocap_test/finedance/fd/finedance/motion]

FineDance: 315 numbers a frame = 3 translation + 52 joints x 6D rotation; the 22 body joints give the arms, the 30 finger joints give the finger closure (a second head, not used by the palm).
Files that cannot be read (a damaged archive) are skipped; 31 files are held out and the accuracy on them is printed."""
import argparse, glob, os, sys, numpy as np, torch
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__))); sys.path.insert(0, ROOT)
from scipy.spatial.transform import Rotation as Rot
from homunculus import hand_prior as hp
ap = argparse.ArgumentParser(); ap.add_argument("--finedance", default=os.path.join(ROOT, "mocap_test/finedance/fd/finedance/motion")); ap.add_argument("--epochs", type=int, default=12); a = ap.parse_args()
fs = []
for f in sorted(glob.glob(os.path.join(a.finedance, "*.npy"))):
    try: np.load(f, mmap_mode="r"); fs.append(f)
    except Exception: pass
print(len(fs), "readable files")
X, Y, FID = [], [], []
for k, f in enumerate(fs):
    d = np.load(f, allow_pickle=False).astype(np.float64); n = len(d); d6 = d[:, 3:].reshape(n, -1, 6); G, P = hp.fk(hp.rot6d_to_mat(d6[:, :22])); fin = Rot.from_matrix(hp.rot6d_to_mat(d6[:, 22:52]).reshape(-1, 3, 3)).as_rotvec().reshape(n, 2, 15, 3)
    for h, side in enumerate(("left", "right")):
        H = hp.hand_frames(G, P, side); Fw = hp.window(hp.features(H))
        # targets: the palm direction in the torso frame, from the wrist's own rotation (known in FineDance; it is not an input)
        s = 0 if side == "left" else 1; wr = 20 + s; fw = G[:, 9] @ np.array([0, 0, 1.0]); fw[:, 1] = 0; fw /= np.linalg.norm(fw, axis=1, keepdims=True) + 1e-9; lf = np.cross([0, 1.0, 0], fw)
        nrm = G[:, wr] @ np.array([0, -1.0, 0]); nt = np.stack([(nrm * lf).sum(1), nrm[:, 1], (nrm * fw).sum(1)], 1) * (np.array([1, 1, 1.0]) if s == 0 else np.array([-1, 1, 1.0]))
        palm = np.stack([-nt[:, 1], nt[:, 1], nt[:, 2], -nt[:, 2], -nt[:, 0], nt[:, 0]], 1).argmax(1)
        c = np.degrees(fin[:, h, :12, 2]) * (-1 if h == 0 else 1); cb = np.digitize(c.mean(1), [12, 28, 45])
        X.append(Fw[::3].astype(np.float32)); Y.append(np.stack([palm, cb], 1)[::3]); FID.append(np.full(len(Fw[::3]), k))
X = np.concatenate(X); Y = np.concatenate(Y); FID = np.concatenate(FID); rng = np.random.default_rng(0); order = rng.permutation(len(fs)); test = np.isin(FID, order[:31]); tr = ~test
mu, sd = X[tr].mean(0), X[tr].std(0) + 1e-6; dev = "cuda" if torch.cuda.is_available() else "cpu"; torch.manual_seed(0)
net = torch.nn.Sequential(torch.nn.Linear(X.shape[1], 384), torch.nn.GELU(), torch.nn.Dropout(0.2), torch.nn.Linear(384, 384), torch.nn.GELU(), torch.nn.Dropout(0.2), torch.nn.Linear(384, 6 + 4)).to(dev)
opt = torch.optim.AdamW(net.parameters(), lr=2e-3, weight_decay=1e-3); Xt = torch.tensor((X[tr] - mu) / sd).to(dev); yp = torch.tensor(Y[tr, 0].astype(np.int64)).to(dev); yc = torch.tensor(Y[tr, 1].astype(np.int64)).to(dev)
for ep in range(a.epochs):
    perm = torch.randperm(len(Xt), device=dev); net.train()
    for i in range(0, len(Xt), 1024):
        b = perm[i:i + 1024]; o = net(Xt[b]); loss = torch.nn.functional.cross_entropy(o[:, :6], yp[b]) + torch.nn.functional.cross_entropy(o[:, 6:], yc[b]); opt.zero_grad(); loss.backward(); opt.step()
net.eval()
with torch.no_grad(): o = net(torch.tensor((X[test] - mu) / sd).to(dev))[:, :6].argmax(1).cpu().numpy()
print(f"held-out FineDance files: palm direction {np.mean(o == Y[test, 0]) * 100:.0f} % (guessing the commonest class: {np.mean(Y[test, 0] == np.bincount(Y[tr, 0]).argmax()) * 100:.0f} %)")
L = [m for m in net if isinstance(m, torch.nn.Linear)]; w = {f"W{i + 1}": l.weight.detach().cpu().numpy().T for i, l in enumerate(L)}; w.update({f"b{i + 1}": l.bias.detach().cpu().numpy() for i, l in enumerate(L)}); w["mu"] = mu; w["sd"] = sd
os.makedirs(os.path.join(ROOT, "homunculus", "data"), exist_ok=True); np.savez(os.path.join(ROOT, "homunculus", "data", "hand_prior.npz"), **w); print("wrote homunculus/data/hand_prior.npz")
