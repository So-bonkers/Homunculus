"""Where is a dancer in the picture although the group's verification hid him?   gvhmr/.venv/bin/python tools/group_audit.py --dir <group dir> --tracks tracks_raw.json [--video shot1080.mp4]

Every 3rd frame outside a dancer's verified stretches, every person the detector found (tracks_raw.json: all boxes, not only the ones stitched to the dancers) is compared with the dancer's appearance (the DINOv2 + colour features of
tools/group_segments.py, the mean of his verified frames).  Writes <dir>/audit.json: per dancer a list of [frame, best similarity, box, similarity of the 2nd best, the dancer's threshold] for the hidden frames where the best person
looks like him (similarity above the threshold minus --margin) and is tall enough; the stretches of these are what to look at by eye (tools/group_segments.py --accept)."""
import os, sys, json, argparse
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__))); GV = os.path.join(ROOT, "gvhmr"); sys.path[:0] = [os.path.join(GV, "shim"), os.path.join(GV, "repo")]
ap = argparse.ArgumentParser(); ap.add_argument("--dir", required=True); ap.add_argument("--tracks", required=True); ap.add_argument("--video", default=""); ap.add_argument("--margin", type=float, default=0.06); ap.add_argument("--step", type=int, default=3); ap.add_argument("--min-height", type=float, default=0.12)
a = ap.parse_args(); a.dir = os.path.abspath(a.dir)
import cv2, numpy as np, torch, timm
G = json.load(open(os.path.join(a.dir, "dancers.json"))); N, W, H = G["frames"], G["width"], G["height"]; K = len(G["dancers"]); SEG = json.load(open(os.path.join(a.dir, "segments.json"))); SC = json.load(open(os.path.join(a.dir, "scene", "scene.json")))
raw = json.load(open(a.tracks))["tracks"]; per = [[] for _ in range(N)]
for i, t in raw.items():
    for f, b in t.items():
        if int(f) < N: per[int(f)].append((i, b))
valid = {}
for d in SC["dancers"]:
    v = np.zeros(N, bool)
    for s, e in d["valid_ranges"]: v[s:e] = True
    valid[d["k"]] = v
z = np.load(os.path.join(a.dir, "feats.npz")); gal = {}
for k in range(1, K + 1):
    F = z[f"d{k - 1}"]; F = F / np.linalg.norm(F, axis=1, keepdims=True); idx = [i for i in range(len(F)) if valid[k][min(N - 1, i * 3)]]; g = F[idx].mean(0); g /= np.linalg.norm(g)
    for _ in range(3): sim = F[idx] @ g; g = F[idx][sim >= np.percentile(sim, 40)].mean(0); g /= np.linalg.norm(g)
    gal[k] = g
thr = {d["k"]: d["similarity_threshold"] for d in SEG["dancers"]}
m = timm.create_model("vit_small_patch14_dinov2.lvd142m", pretrained=True, num_classes=0, img_size=224).eval().cuda(); mean = torch.tensor([0.485, 0.456, 0.406]).view(1, 3, 1, 1).cuda(); std = torch.tensor([0.229, 0.224, 0.225]).view(1, 3, 1, 1).cuda()
def hist(im, y0, y1):
    h, w = im.shape[:2]; r = im[int(h * y0):int(h * y1), int(w * 0.2):int(w * 0.8)]
    if r.size == 0: return np.zeros(108, np.float32)
    hsv = cv2.cvtColor(r, cv2.COLOR_BGR2HSV); hh = cv2.calcHist([hsv], [0, 1, 2], None, [12, 3, 3], [0, 180, 0, 256, 0, 256]).flatten(); hh /= hh.sum() + 1e-6; return np.sqrt(hh).astype(np.float32)
need = sorted({f for f in range(0, N, a.step) if any(not valid[k][f] for k in valid)})
cap = cv2.VideoCapture(a.video or os.path.join(a.dir, "d1", "clip.mp4")); out = {str(k): [] for k in range(1, K + 1)}
for f in range(N):
    ok, im = cap.read()
    if not ok: break
    if f % a.step or f not in need: continue
    dets = [(i, b) for i, b in per[f] if (b[3] - b[1]) / H >= a.min_height]
    if not dets: continue
    crops, hs = [], []
    for i, b in dets:
        b = [int(v) for v in b]; c = im[max(0, b[1]):min(H, b[3]), max(0, b[0]):min(W, b[2])]
        if c.size == 0: c = np.zeros((16, 16, 3), np.uint8)
        s = max(c.shape[:2]); pad = cv2.copyMakeBorder(c, 0, s - c.shape[0], 0, s - c.shape[1], cv2.BORDER_CONSTANT, value=(0, 0, 0)); crops.append(cv2.resize(pad, (224, 224))); hs.append(np.concatenate([hist(c, 0.0, 0.2) * 0.5, hist(c, 0.2, 0.55), hist(c, 0.55, 0.92) * 0.6]))
    x = torch.from_numpy(np.stack(crops)[..., ::-1].copy()).permute(0, 3, 1, 2).float().cuda() / 255
    with torch.no_grad(): e = torch.nn.functional.normalize(m((x - mean) / std), dim=1).cpu().numpy()
    Fv = np.stack([np.concatenate([e[j], 1.2 * hs[j] / (np.linalg.norm(hs[j]) + 1e-9)]) for j in range(len(dets))]); Fv /= np.linalg.norm(Fv, axis=1, keepdims=True)
    for k in range(1, K + 1):
        if valid[k][f]: continue
        sim = Fv @ gal[k]; o = np.argsort(-sim); b1 = o[0]; s2 = float(sim[o[1]]) if len(o) > 1 else -1.0
        if sim[b1] >= thr[k] - a.margin: out[str(k)].append([f, round(float(sim[b1]), 3), [round(v) for v in dets[b1][1]], round(s2, 3), round(thr[k], 3), dets[b1][0]])
    if f % 300 == 0: print("  frame", f, flush=True)
json.dump(out, open(os.path.join(a.dir, "audit.json"), "w")); print({k: len(v) for k, v in out.items()}, "candidate frames (every 3rd hidden frame)")
