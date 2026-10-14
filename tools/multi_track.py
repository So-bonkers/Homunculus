"""Every person in a clip, one track each: the first step of copying a group's choreography (one GVHMR run per dancer). Run with the GVHMR environment, from anywhere:

    gvhmr/.venv/bin/python tools/multi_track.py --video clip.mp4 --out <dir> [--min-frames 60] [--max-gap 15]

The clip must already be 30 fps and one continuous shot (cut it with ffmpeg first). Writes into <dir>:
  tracks.json    one row per track: frames, first/last frame, size, how often the box touches the frame edge (feet or head cut off), the stretches kept
  overlay.mp4    the clip with every box and its track id, to check the tracks by eye
  t<id>/clip.mp4 and t<id>/clip/preprocess/bbx.pt   for each track that is long enough: the clip cut to the track's longest stretch (gaps up to --max-gap frames are
                 interpolated, longer ones split the stretch) and the box file GVHMR reuses instead of tracking by itself. Then, per dancer:
    gvhmr/.venv/bin/python tools/video_to_smpl.py --video <dir>/t<id>/clip.mp4 --output_root <dir>/t<id> -s
Adapted from GVHMR's own tracker (hmr4d/utils/preproc/tracker.py; ZJU licence: research use)."""
import os, sys, json, subprocess, argparse
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
GV = os.path.join(ROOT, "gvhmr")
sys.path[:0] = [os.path.join(GV, "shim"), os.path.join(GV, "repo")]
ap = argparse.ArgumentParser()
ap.add_argument("--video", required=True); ap.add_argument("--out", required=True)
ap.add_argument("--min-frames", type=int, default=60); ap.add_argument("--max-gap", type=int, default=15)
a = ap.parse_args()
a.video, a.out = os.path.abspath(a.video), os.path.abspath(a.out)
os.chdir(os.path.join(GV, "repo"))
import cv2, numpy as np, torch
from hmr4d.utils.preproc import Tracker
from hmr4d.utils.geo.hmr_cam import get_bbx_xys_from_xyxy
from hmr4d.utils.net_utils import moving_average_smooth

os.makedirs(a.out, exist_ok=True)
cap = cv2.VideoCapture(a.video); W = int(cap.get(3)); H = int(cap.get(4)); N = int(cap.get(7)); cap.release()
hist = Tracker().track(a.video)

boxes = {}                                                   # id -> {frame: xyxy}
for f, dets in enumerate(hist):
    for d in dets: boxes.setdefault(d["id"], {})[f] = d["bbx_xyxy"]

def stretches(frames, max_gap):
    """Runs of frames where consecutive detections are at most max_gap apart."""
    runs, cur = [], [frames[0]]
    for f in frames[1:]:
        if f - cur[-1] - 1 <= max_gap: cur.append(f)
        else: runs.append((cur[0], cur[-1], len(cur))); cur = [f]
    runs.append((cur[0], cur[-1], len(cur))); return runs

rows = []
for tid, fb in sorted(boxes.items()):
    fr = sorted(fb); bb = np.array([fb[f] for f in fr]); wh = bb[:, 2:] - bb[:, :2]
    edge = lambda c: float(np.mean(c))
    rows.append({"id": int(tid), "frames": len(fr), "first": fr[0], "last": fr[-1],
                 "height_px": float(np.median(wh[:, 1])), "height_frac": float(np.median(wh[:, 1]) / H),
                 "touches_bottom": edge(bb[:, 3] >= H - 4), "touches_top": edge(bb[:, 1] <= 4), "touches_side": edge((bb[:, 0] <= 4) | (bb[:, 2] >= W - 4)),
                 "stretches": [{"from": s, "to": e, "seen": n} for s, e, n in stretches(fr, a.max_gap)]})
count = np.zeros(N, int)
for fb in boxes.values():
    for f in fb: count[f] += 1

# overlay: every box with its id
colors = [(255, 80, 80), (80, 255, 80), (80, 160, 255), (255, 220, 60), (255, 80, 255), (60, 255, 255), (255, 150, 60), (160, 100, 255)]
cap = cv2.VideoCapture(a.video); tmp = os.path.join(a.out, "overlay_raw.mp4")
vw = cv2.VideoWriter(tmp, cv2.VideoWriter_fourcc(*"mp4v"), 30, (W, H))
for f in range(N):
    ok, img = cap.read()
    if not ok: break
    for d in hist[f]:
        x0, y0, x1, y1 = [int(v) for v in d["bbx_xyxy"]]; c = colors[d["id"] % len(colors)]
        cv2.rectangle(img, (x0, y0), (x1, y1), c, 3); cv2.putText(img, f"#{d['id']}", (x0 + 6, max(30, y0 + 30)), cv2.FONT_HERSHEY_SIMPLEX, 1.1, c, 3)
    cv2.putText(img, f"{int(count[f])} tracked  f{f}", (20, H - 24), cv2.FONT_HERSHEY_SIMPLEX, 1.0, (255, 255, 255), 2)
    vw.write(img)
vw.release(); cap.release()
subprocess.run(["ffmpeg", "-v", "error", "-y", "-i", tmp, "-c:v", "libx264", "-crf", "23", "-pix_fmt", "yuv420p", os.path.join(a.out, "overlay.mp4")]); os.remove(tmp)

# one clip + one box file per track: its longest stretch, gaps filled by interpolation
kept = []
for r in rows:
    best = max(r["stretches"], key=lambda s: s["to"] - s["from"])
    r["kept"] = None
    if best["to"] - best["from"] + 1 < a.min_frames: continue
    s, e = best["from"], best["to"]; fb = boxes[r["id"]]
    xyxy = np.zeros((e - s + 1, 4), np.float32); have = np.zeros(e - s + 1, bool)
    for f in range(s, e + 1):
        if f in fb: xyxy[f - s] = fb[f]; have[f - s] = True
    idx = np.arange(len(xyxy))
    for k in range(4): xyxy[:, k] = np.interp(idx, idx[have], xyxy[have, k])
    t = torch.from_numpy(xyxy)
    t = moving_average_smooth(moving_average_smooth(t, window_size=5, dim=0), window_size=5, dim=0)
    d = os.path.join(a.out, f"t{r['id']}"); os.makedirs(os.path.join(d, "clip", "preprocess"), exist_ok=True)
    torch.save({"bbx_xyxy": t.float(), "bbx_xys": get_bbx_xys_from_xyxy(t, base_enlarge=1.2).float()}, os.path.join(d, "clip", "preprocess", "bbx.pt"))
    # cut by frame numbers (the clip is 30 fps), re-encoded so the frame count is exact
    subprocess.run(["ffmpeg", "-v", "error", "-y", "-i", a.video, "-vf", f"select='between(n\\,{s}\\,{e})',setpts=N/30/TB", "-r", "30", "-an", "-c:v", "libx264", "-crf", "14", os.path.join(d, "clip.mp4")])
    r["kept"] = {"from": s, "to": e, "frames": e - s + 1, "interpolated": int((~have).sum())}; kept.append(r["id"])

json.dump({"video": a.video, "frames": N, "width": W, "height": H, "people_per_frame": {"min": int(count.min()), "median": float(np.median(count)), "max": int(count.max())}, "tracks": rows}, open(os.path.join(a.out, "tracks.json"), "w"), indent=1)
print(f"{len(rows)} tracks, {len(kept)} kept (>= {a.min_frames} frames): {kept}")
print(f"people per frame: min {count.min()}, median {np.median(count):.0f}, max {count.max()}")
for r in sorted(rows, key=lambda r: -r["frames"]):
    print(f"  #{r['id']:<3} {r['frames']:>4} frames  {r['first']:>4}-{r['last']:<4} height {r['height_frac'] * 100:>3.0f}%  bottom-cut {r['touches_bottom'] * 100:>3.0f}%  side-cut {r['touches_side'] * 100:>3.0f}%  stretches {len(r['stretches'])}  kept {r['kept']['frames'] if r['kept'] else '-'}")
