"""Cut each dancer's timeline into the stretches where the box really is that dancer.  Run with the GVHMR environment, after tools/group_tracks.py:

    gvhmr/.venv/bin/python tools/group_segments.py --dir <group_tracks out dir>

A dancer's boxes can sit on someone else while the dancer is out of the picture or hidden (the tracker keeps a box alive, or a stitched id was wrong). Every 3rd frame the crop under each dancer's box is compared (DINOv2-small embedding
and colour histograms, as in group_tracks.py) with that dancer's own appearance (the mean of the crops that agree most with each other); frames that do not match, or whose box is too small, are dropped; gaps up to --bridge frames
are closed, stretches shorter than --min-seg frames are dropped.  Writes d<k>/s<NN>/clip.mp4 and d<k>/s<NN>/clip/preprocess/bbx.pt for each stretch (what tools/video_to_smpl.py -s reuses: GVHMR then never sees a wrong person),
and segments.json: per dancer the stretches [first frame, end frame), the share of frames covered and how much of each stretch is overlapped by another dancer (the motion is least reliable there)."""
import os, sys, json, argparse, subprocess
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__))); GV = os.path.join(ROOT, "gvhmr")
sys.path[:0] = [os.path.join(GV, "shim"), os.path.join(GV, "repo")]
ap = argparse.ArgumentParser(); ap.add_argument("--dir", required=True); ap.add_argument("--step", type=int, default=3); ap.add_argument("--min-height", type=float, default=0.16)
ap.add_argument("--reuse", action="store_true", help="use the appearance features saved by an earlier run (feats.npz)"); ap.add_argument("--bridge", type=int, default=20); ap.add_argument("--min-seg", type=int, default=45); ap.add_argument("--sigma", type=float, default=3.5, help="a frame is dropped when its similarity is this many MADs under the dancer's median")
a = ap.parse_args(); a.dir = os.path.abspath(a.dir)
import cv2, numpy as np, torch, timm
from hmr4d.utils.geo.hmr_cam import get_bbx_xys_from_xyxy

G = json.load(open(os.path.join(a.dir, "dancers.json"))); N, W, H = G["frames"], G["width"], G["height"]; K = len(G["dancers"])
box = [torch.load(os.path.join(a.dir, f"d{k + 1}", "clip", "preprocess", "bbx.pt"), weights_only=False)["bbx_xyxy"].numpy() for k in range(K)]
m = timm.create_model("vit_small_patch14_dinov2.lvd142m", pretrained=True, num_classes=0, img_size=224).eval().cuda(); mean = torch.tensor([0.485, 0.456, 0.406]).view(1, 3, 1, 1).cuda(); std = torch.tensor([0.229, 0.224, 0.225]).view(1, 3, 1, 1).cuda()
def hist(im, y0, y1):
    h, w = im.shape[:2]; r = im[int(h * y0):int(h * y1), int(w * 0.2):int(w * 0.8)]
    if r.size == 0: return np.zeros(108, np.float32)
    hsv = cv2.cvtColor(r, cv2.COLOR_BGR2HSV); hh = cv2.calcHist([hsv], [0, 1, 2], None, [12, 3, 3], [0, 180, 0, 256, 0, 256]).flatten(); hh /= hh.sum() + 1e-6; return np.sqrt(hh).astype(np.float32)
def iou(p, q):
    x0, y0, x1, y1 = max(p[0], q[0]), max(p[1], q[1]), min(p[2], q[2]), min(p[3], q[3]); i = max(0, x1 - x0) * max(0, y1 - y0)
    return i / ((p[2] - p[0]) * (p[3] - p[1]) + (q[2] - q[0]) * (q[3] - q[1]) - i + 1e-6)

cap = cv2.VideoCapture(os.path.join(a.dir, "d1", "clip.mp4")); fr_idx = list(range(0, N, a.step)); feats = [[] for _ in range(K)]; cache = os.path.join(a.dir, "feats.npz")
for f in (range(N) if not (a.reuse and os.path.exists(cache)) else []):
    ok, im = cap.read()
    if not ok: break
    if f % a.step: continue
    crops = []; hs = []
    for k in range(K):
        b = [int(v) for v in box[k][f]]; c = im[max(0, b[1]):min(H, b[3]), max(0, b[0]):min(W, b[2])]
        if c.size == 0: c = np.zeros((16, 16, 3), np.uint8)
        s = max(c.shape[:2]); pad = cv2.copyMakeBorder(c, 0, s - c.shape[0], 0, s - c.shape[1], cv2.BORDER_CONSTANT, value=(0, 0, 0)); crops.append(cv2.resize(pad, (224, 224)))
        hs.append(np.concatenate([hist(c, 0.0, 0.2) * 0.5, hist(c, 0.2, 0.55), hist(c, 0.55, 0.92) * 0.6]))
    x = torch.from_numpy(np.stack(crops)[..., ::-1].copy()).permute(0, 3, 1, 2).float().cuda() / 255
    with torch.no_grad(): e = torch.nn.functional.normalize(m((x - mean) / std), dim=1).cpu().numpy()
    for k in range(K): hv = hs[k]; feats[k].append(np.concatenate([e[k], 1.2 * hv / (np.linalg.norm(hv) + 1e-9)]))
    if (f // a.step) % 200 == 0: print(f"  frame {f}/{N}", flush=True)
if a.reuse and os.path.exists(cache): z = np.load(cache); feats = [z[f"d{k}"] for k in range(K)]
else:
    feats = [np.stack(x) for x in feats]; np.savez(cache, **{f"d{k}": feats[k] for k in range(K)})
M = len(fr_idx)
out = {"frames": N, "fps": 30, "dancers": []}
for k in range(K):
    F = feats[k] / np.linalg.norm(feats[k], axis=1, keepdims=True); hgt = np.array([(box[k][f][3] - box[k][f][1]) / H for f in fr_idx[:len(F)]])
    alone = np.array([all(j == k or iou(box[k][f], box[j][f]) < 0.1 for j in range(K)) for f in fr_idx[:len(F)]]); good = (hgt >= 0.33) & alone
    g = F[good].mean(0) if good.sum() >= 10 else F.mean(0); g /= np.linalg.norm(g)
    for _ in range(3):                                                    # the appearance the dancer's own frames agree on: refit on the most similar 60 %
        sim = F @ g; top = sim >= np.percentile(sim, 40); g = F[top].mean(0); g /= np.linalg.norm(g)
    sim = F @ g; med = np.median(sim[top]); mad = np.median(np.abs(sim[top] - med)) + 1e-6; thr = med - a.sigma * mad
    ok = (sim >= thr) & (hgt >= a.min_height) & (box[k][fr_idx[:len(F)], 0] < W - 8) & (box[k][fr_idx[:len(F)], 2] > 8)
    v = np.zeros(N, bool)
    for i, f in enumerate(fr_idx[:len(F)]): v[f:f + a.step] = ok[i]
    d = np.diff(np.r_[0, v.astype(int), 0]); starts, ends = list(np.where(d == 1)[0]), list(np.where(d == -1)[0])      # close the short gaps, then drop the short stretches
    segs = []
    for s, e in zip(starts, ends):
        if segs and s - segs[-1][1] <= a.bridge: segs[-1][1] = e
        else: segs.append([s, e])
    segs = [s for s in segs if s[1] - s[0] >= a.min_seg]; ent = []
    drop = np.diff(np.r_[0, (~v).astype(int), 0]); dr = [(int(x), int(y)) for x, y in zip(np.where(drop == 1)[0], np.where(drop == -1)[0]) if y - x >= 30]; print(f"  dancer {k + 1}: dropped stretches (>= 1 s): {[(round(x / 30, 1), round(y / 30, 1)) for x, y in dr][:14]}", flush=True)
    for i, (s, e) in enumerate(segs):
        ov = np.mean([any(iou(box[k][f], box[j][f]) > 0.3 for j in range(K) if j != k) for f in range(s, e, 3)])
        sd = os.path.join(a.dir, f"d{k + 1}", f"s{i:02d}"); os.makedirs(os.path.join(sd, "clip", "preprocess"), exist_ok=True)
        t = torch.from_numpy(box[k][s:e]); torch.save({"bbx_xyxy": t.float(), "bbx_xys": get_bbx_xys_from_xyxy(t, base_enlarge=1.2).float()}, os.path.join(sd, "clip", "preprocess", "bbx.pt"))
        subprocess.run(["ffmpeg", "-v", "error", "-y", "-i", os.path.join(a.dir, f"d{k + 1}", "clip.mp4"), "-vf", f"select='between(n\\,{s}\\,{e - 1})',setpts=N/30/TB", "-r", "30", "-an", "-c:v", "libx264", "-crf", "14", os.path.join(sd, "clip.mp4")], check=True)
        ent.append({"i": i, "start": int(s), "end": int(e), "frames": int(e - s), "overlapped": round(float(ov), 2)})
    cov = sum(x["frames"] for x in ent) / N
    out["dancers"].append({"k": k + 1, "similarity_threshold": round(float(thr), 3), "similarity_median": round(float(med), 3), "segments": ent, "coverage": round(cov, 3)})
    print(f"dancer {k + 1}: {len(ent)} stretches covering {100 * cov:.0f} % of the shot (threshold {thr:.3f} under median {med:.3f}); longest {max([x['frames'] for x in ent] + [0]) / 30:.0f} s; overlapped by another dancer in {100 * np.mean([x['overlapped'] for x in ent] + [0]):.0f} % on average", flush=True)
json.dump(out, open(os.path.join(a.dir, "segments.json"), "w"), indent=1); print("segments.json written;", sum(len(d["segments"]) for d in out["dancers"]), "stretches in all")
