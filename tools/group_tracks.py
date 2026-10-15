"""Follow a fixed number of dancers through one long shot: the tracker's ids change whenever a person is lost and found again, so the ids are stitched back into people by what they wear.  Run with the GVHMR environment:

    gvhmr/.venv/bin/python tools/group_tracks.py --raw tracks_raw.json --video shot.mp4 --out dir --dancers 6

Input: tracks_raw.json from tools/track_raw.py.  Steps: (1) candidate ids = long enough and big enough in the frame (the people standing at the back are small and drop out); (2) each candidate gets an appearance (a DINOv2-small
embedding of the person crop and colour histograms of head, upper and lower body, averaged over frames where the person is alone in the picture); (3) ids that were on screen together can never be the same person; the rest are merged
by average linkage until `--dancers` clusters of long ids are left, and the shorter ids join the nearest cluster they do not clash with; (4) per dancer the boxes of the frames, gaps up to --max-gap frames interpolated.
Writes into dir: dancers.json (per dancer: frames seen, interpolated frames, ids merged), d<k>/clip.mp4 (a link to the shot) and d<k>/clip/preprocess/bbx.pt (what GVHMR reuses instead of tracking), overlay.mp4 (the shot with every dancer
boxed and numbered, 10 fps) and crops.jpg (one crop of each dancer every 10 s, to name them by eye)."""
import os, sys, json, argparse, subprocess
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__))); GV = os.path.join(ROOT, "gvhmr")
sys.path[:0] = [os.path.join(GV, "shim"), os.path.join(GV, "repo")]
ap = argparse.ArgumentParser(); ap.add_argument("--raw", required=True); ap.add_argument("--video", required=True); ap.add_argument("--out", required=True)
ap.add_argument("--dancers", type=int, default=6); ap.add_argument("--min-height", type=float, default=0.30, help="a candidate is at least this tall (fraction of the frame) in most of its frames")
ap.add_argument("--min-frames", type=int, default=20); ap.add_argument("--heavy", type=int, default=120, help="ids with at least this many frames form the clusters; shorter ones join them afterwards")
ap.add_argument("--max-gap", type=int, default=45, help="frames: a gap shorter than this is bridged by interpolation"); ap.add_argument("--join", type=float, default=0.55, help="a short id joins a cluster only if its distance is below this")
a = ap.parse_args(); a.raw, a.video, a.out = os.path.abspath(a.raw), os.path.abspath(a.video), os.path.abspath(a.out); os.makedirs(a.out, exist_ok=True)
import cv2, numpy as np, torch, timm
from hmr4d.utils.geo.hmr_cam import get_bbx_xys_from_xyxy
from hmr4d.utils.net_utils import moving_average_smooth

R = json.load(open(a.raw)); N, W, H = R["frames"], R["width"], R["height"]
T = {int(i): {int(f): b for f, b in fb.items()} for i, fb in R["tracks"].items()}
hgt = lambda b: (b[3] - b[1]) / H
cand = [i for i, fb in T.items() if len(fb) >= a.min_frames and np.mean([hgt(b) >= a.min_height for b in fb.values()]) >= 0.5]
print(f"{len(T)} ids, {len(cand)} candidates (>= {a.min_frames} frames, tall in most of them)")

def iou(p, q):
    x0, y0, x1, y1 = max(p[0], q[0]), max(p[1], q[1]), min(p[2], q[2]), min(p[3], q[3]); i = max(0, x1 - x0) * max(0, y1 - y0)
    return i / ((p[2] - p[0]) * (p[3] - p[1]) + (q[2] - q[0]) * (q[3] - q[1]) - i + 1e-6)
def alone(i, f):
    b = T[i][f]; return all(j == i or f not in T[j] or iou(b, T[j][f]) < 0.1 for j in T if f in T[j] and hgt(T[j][f]) >= 0.2)

# appearance
m = timm.create_model("vit_small_patch14_dinov2.lvd142m", pretrained=True, num_classes=0, img_size=224).eval().cuda(); mean = torch.tensor([0.485, 0.456, 0.406]).view(1, 3, 1, 1).cuda(); std = torch.tensor([0.229, 0.224, 0.225]).view(1, 3, 1, 1).cuda()
cap = cv2.VideoCapture(a.video)
def frame(f):
    cap.set(cv2.CAP_PROP_POS_FRAMES, f); ok, im = cap.read(); return im
def hist(im, y0, y1):
    h, w = im.shape[:2]; r = im[int(h * y0):int(h * y1), int(w * 0.2):int(w * 0.8)]
    if r.size == 0: return np.zeros(108, np.float32)
    hsv = cv2.cvtColor(r, cv2.COLOR_BGR2HSV); hh = cv2.calcHist([hsv], [0, 1, 2], None, [12, 3, 3], [0, 180, 0, 256, 0, 256]).flatten(); hh /= hh.sum() + 1e-6; return np.sqrt(hh).astype(np.float32)
feat = {}
for n, i in enumerate(cand):
    fs = sorted(f for f in T[i] if hgt(T[i][f]) >= a.min_height * 0.8); al = [f for f in fs if alone(i, f)] or fs
    pick = [al[int(k)] for k in np.linspace(0, len(al) - 1, min(10, len(al)))]; crops, hs = [], []
    for f in pick:
        im = frame(f); b = [int(v) for v in T[i][f]]; c = im[max(0, b[1]):min(H, b[3]), max(0, b[0]):min(W, b[2])]
        if c.size == 0: continue
        s = max(c.shape[:2]); pad = cv2.copyMakeBorder(c, 0, s - c.shape[0], 0, s - c.shape[1], cv2.BORDER_CONSTANT, value=(0, 0, 0)); crops.append(cv2.resize(pad, (224, 224)))
        hs.append(np.concatenate([hist(c, 0.0, 0.2) * 0.5, hist(c, 0.2, 0.55) * 1.0, hist(c, 0.55, 0.92) * 0.6]))
    x = torch.from_numpy(np.stack(crops)[..., ::-1].copy()).permute(0, 3, 1, 2).float().cuda() / 255
    with torch.no_grad(): e = torch.nn.functional.normalize(m((x - mean) / std), dim=1).mean(0).cpu().numpy()
    hv = np.mean(hs, 0); feat[i] = np.concatenate([e / (np.linalg.norm(e) + 1e-9), 1.2 * hv / (np.linalg.norm(hv) + 1e-9)])
    if n % 20 == 0: print(f"  appearance {n}/{len(cand)}", flush=True)
ids = list(feat); F = np.stack([feat[i] / np.linalg.norm(feat[i]) for i in ids]); D = 1 - F @ F.T
frames_of = {i: set(T[i]) for i in ids}
clash = lambda p, q: len(frames_of[p] & frames_of[q]) > 6
heavy = [i for i in ids if len(T[i]) >= a.heavy]; light = [i for i in ids if i not in heavy]; ix = {i: k for k, i in enumerate(ids)}
clusters = [[i] for i in heavy]
def dist(c1, c2):
    if any(clash(p, q) for p in c1 for q in c2): return 9.0
    return float(np.mean([D[ix[p], ix[q]] for p in c1 for q in c2]))
while len(clusters) > a.dancers:
    best = min(((dist(clusters[p], clusters[q]), p, q) for p in range(len(clusters)) for q in range(p + 1, len(clusters))), key=lambda t: t[0])
    if best[0] >= 9.0: print("cannot merge further without a clash; stopping at", len(clusters), "clusters"); break
    _, p, q = best; clusters[p] += clusters[q]; del clusters[q]
for i in sorted(light, key=lambda i: -len(T[i])):
    d = [(dist(c, [i]), k) for k, c in enumerate(clusters)]; dm, k = min(d)
    if dm < a.join: clusters[k].append(i)
clusters.sort(key=lambda c: -sum(len(T[i]) for i in c))
print("clusters:", [(len(c), sum(len(T[i]) for i in c)) for c in clusters])

# per dancer: boxes per frame, gaps bridged
out = {"video": a.video, "frames": N, "width": W, "height": H, "dancers": []}; boxes = []
for k, c in enumerate(clusters[:a.dancers]):
    per = {}
    for i in c:
        for f, b in T[i].items():
            if f not in per or (b[2] - b[0]) * (b[3] - b[1]) > (per[f][2] - per[f][0]) * (per[f][3] - per[f][1]): per[f] = b
    seen = sorted(per); arr = np.full((N, 4), np.nan, np.float32); kind = np.zeros(N, np.int8)         # 2 seen, 1 interpolated, 0 outside
    for f in seen: arr[f] = per[f]; kind[f] = 2
    for f0, f1 in zip(seen, seen[1:]):
        if 1 < f1 - f0 <= a.max_gap:
            for f in range(f0 + 1, f1): arr[f] = arr[f0] + (arr[f1] - arr[f0]) * (f - f0) / (f1 - f0); kind[f] = 1
    first, last = seen[0], seen[-1]; idx = np.arange(N); ok = ~np.isnan(arr[:, 0])
    for q in range(4): arr[:, q] = np.interp(idx, idx[ok], arr[ok, q])                                  # the long gaps and the ends: held / interpolated so that GVHMR has a box (those frames are marked unreliable)
    boxes.append(arr); out["dancers"].append({"k": k + 1, "ids": sorted(c), "frames_seen": int((kind == 2).sum()), "frames_interpolated": int((kind == 1).sum()), "frames_unreliable": int((kind == 0).sum()), "first": first, "last": last,
        "unreliable_ranges": [[int(s), int(e)] for s, e in zip(np.where(np.diff(np.r_[0, (kind == 0).astype(int)]) == 1)[0], np.where(np.diff(np.r_[(kind == 0).astype(int), 0]) == -1)[0])]})
    d = os.path.join(a.out, f"d{k + 1}"); os.makedirs(os.path.join(d, "clip", "preprocess"), exist_ok=True)
    t = torch.from_numpy(arr); t = moving_average_smooth(moving_average_smooth(t, window_size=5, dim=0), window_size=5, dim=0)
    torch.save({"bbx_xyxy": t.float(), "bbx_xys": get_bbx_xys_from_xyxy(t, base_enlarge=1.2).float()}, os.path.join(d, "clip", "preprocess", "bbx.pt"))
    link = os.path.join(d, "clip.mp4")
    if not os.path.exists(link): os.link(a.video, link)
    e = out["dancers"][-1]; print(f"  dancer {k + 1}: seen {e['frames_seen']} ({100 * e['frames_seen'] / N:.0f} %), interpolated {e['frames_interpolated']}, unreliable {e['frames_unreliable']}, ids {len(c)}")
json.dump(out, open(os.path.join(a.out, "dancers.json"), "w"), indent=1)
# overlay and one crop of each dancer every 10 s
COL = [(80, 80, 255), (80, 255, 80), (255, 160, 60), (60, 230, 255), (255, 80, 255), (255, 255, 80)]
vw = cv2.VideoWriter(os.path.join(a.out, "overlay_raw.mp4"), cv2.VideoWriter_fourcc(*"mp4v"), 10, (W // 2, H // 2)); sheet = []
for f in range(0, N, 3):
    im = frame(f)
    for k, arr in enumerate(boxes):
        b = [int(v) for v in arr[f]]; c = COL[k % 6]; cv2.rectangle(im, (b[0], b[1]), (b[2], b[3]), c, 4 if out["dancers"][k]["frames_unreliable"] == 0 or True else 2); cv2.putText(im, f"D{k + 1}", (b[0] + 6, b[1] + 44), 0, 1.6, c, 4)
    vw.write(cv2.resize(im, (W // 2, H // 2)))
vw.release(); subprocess.run(["ffmpeg", "-v", "error", "-y", "-i", os.path.join(a.out, "overlay_raw.mp4"), "-c:v", "libx264", "-crf", "24", "-pix_fmt", "yuv420p", os.path.join(a.out, "overlay.mp4")]); os.remove(os.path.join(a.out, "overlay_raw.mp4"))
rows = []
for k, arr in enumerate(boxes):
    tiles = []
    for f in range(150, N, 300):
        im = frame(f); b = [int(v) for v in arr[f]]; c = im[max(0, b[1]):min(H, b[3]), max(0, b[0]):min(W, b[2])]
        s = max(c.shape[:2]) if c.size else 1; pad = cv2.copyMergeBorder if False else None
        c = cv2.resize(c, (int(c.shape[1] * 220 / max(c.shape[0], 1)), 220)) if c.size else np.zeros((220, 100, 3), np.uint8); t = np.zeros((220, 120, 3), np.uint8); t[:, :min(120, c.shape[1])] = c[:, :120]; tiles.append(t)
    rows.append(np.hstack(tiles))
cv2.imwrite(os.path.join(a.out, "crops.jpg"), np.vstack(rows)); print("done:", a.out)
