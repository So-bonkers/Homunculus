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
ap.add_argument("--link-seconds", type=float, default=0.0, help="re-link the fragments of one dancer (the tracker gives a new id when it loses a person): the end of one and the start of another are joined when the gap is at most this long and the boxes are where the dancer could have moved to; the gap is filled by interpolation")
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

def link_fragments(boxes, max_gap_frames):
    """Join fragments (ids) that are plausibly one person.  B starts after A ends, within max_gap_frames; B's first box is within reach of A's last (a dancer drifts at most about half a body height a second, never more than 1.5 body heights), similar size;
    and the match is unambiguous: B is A's nearest candidate and A is B's nearest, and the runner-up on either side is clearly worse.  (Dancers in one costume cross paths: a wrong join is worse than a cut, it makes the clip jump from one person to another.)"""
    if max_gap_frames <= 0: return boxes
    frag = {tid: sorted(fb) for tid, fb in boxes.items()}
    ends = {tid: (fr[-1], np.array(boxes[tid][fr[-1]], float)) for tid, fr in frag.items()}; starts = {tid: (fr[0], np.array(boxes[tid][fr[0]], float)) for tid, fr in frag.items()}
    cost = {}
    for a_, (ea, ba) in ends.items():
        ha = ba[3] - ba[1]; ca = np.array([(ba[0] + ba[2]) / 2, (ba[1] + ba[3]) / 2])
        for b_, (sb, bb) in starts.items():
            g = sb - ea - 1
            if a_ == b_ or g < 0 or g > max_gap_frames: continue
            hb = bb[3] - bb[1]; cb = np.array([(bb[0] + bb[2]) / 2, (bb[1] + bb[3]) / 2])
            if not (0.75 <= hb / max(ha, 1) <= 1.33): continue
            allowed = min(1.5 * max(ha, hb), max(ha, hb) * (0.3 + 0.5 * g / 30.0)); dist = float(np.linalg.norm(ca - cb))
            if dist <= allowed: cost[(a_, b_)] = dist / allowed
    by_a, by_b = {}, {}
    for (a_, b_), c in cost.items(): by_a.setdefault(a_, []).append((c, b_)); by_b.setdefault(b_, []).append((c, a_))
    nxt, prv = {}, {}
    for (a_, b_), c in sorted(cost.items(), key=lambda kv: kv[1]):
        la = sorted(by_a[a_]); lb = sorted(by_b[b_])
        if la[0][1] != b_ or lb[0][1] != a_: continue
        if (len(la) > 1 and la[1][0] < 1.4 * c + 0.05) or (len(lb) > 1 and lb[1][0] < 1.4 * c + 0.05): continue         # the runner-up is too close: ambiguous
        nxt[a_] = b_; prv[b_] = a_
    out = {}; done = set()
    for tid in sorted(boxes):
        if tid in prv or tid in done: continue
        chain = [tid]
        while chain[-1] in nxt: chain.append(nxt[chain[-1]])
        merged = {}
        for c in chain:
            done.add(c)
            for f, b in boxes[c].items(): merged.setdefault(f, b)
        out[tid] = merged
    print(f"re-linked {len(boxes)} fragments into {len(out)} dancers ({len(nxt)} unambiguous joins, gaps up to {max_gap_frames / 30:.1f} s)", flush=True); return out
boxes = link_fragments(boxes, int(a.link_seconds * 30))

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
                 "stretches": [{"from": s, "to": e, "seen": n} for s, e, n in stretches(fr, max(a.max_gap, int(a.link_seconds * 30)))]})
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

# one clip + one box file per STRETCH of every track (with --link-seconds a track has few of them), gaps filled by interpolation
kept = []; clips = []
for r in rows:
    r["kept"] = None; r["clips"] = []
    for k_, st in enumerate(r["stretches"]):
        s, e = st["from"], st["to"]
        if e - s + 1 < a.min_frames: continue
        fb = boxes[r["id"]]; name = f"{r['id']}" if k_ == 0 else f"{r['id']}s{k_}"
        xyxy = np.zeros((e - s + 1, 4), np.float32); have = np.zeros(e - s + 1, bool)
        for f in range(s, e + 1):
            if f in fb: xyxy[f - s] = fb[f]; have[f - s] = True
        idx = np.arange(len(xyxy))
        for k in range(4): xyxy[:, k] = np.interp(idx, idx[have], xyxy[have, k])
        t = torch.from_numpy(xyxy)
        t = moving_average_smooth(moving_average_smooth(t, window_size=5, dim=0), window_size=5, dim=0)
        d = os.path.join(a.out, f"t{name}"); os.makedirs(os.path.join(d, "clip", "preprocess"), exist_ok=True)
        torch.save({"bbx_xyxy": t.float(), "bbx_xys": get_bbx_xys_from_xyxy(t, base_enlarge=1.2).float()}, os.path.join(d, "clip", "preprocess", "bbx.pt"))
        subprocess.run(["ffmpeg", "-v", "error", "-y", "-i", a.video, "-vf", f"select='between(n\\,{s}\\,{e})',setpts=N/30/TB", "-r", "30", "-an", "-c:v", "libx264", "-crf", "14", os.path.join(d, "clip.mp4")])
        c = {"name": name, "from": s, "to": e, "frames": e - s + 1, "interpolated": int((~have).sum()), "height_frac": r["height_frac"]}; r["clips"].append(c); clips.append(c); kept.append(name)
        if r["kept"] is None or c["frames"] > r["kept"]["frames"]: r["kept"] = {k: c[k] for k in ("from", "to", "frames", "interpolated")}

json.dump({"video": a.video, "frames": N, "width": W, "height": H, "people_per_frame": {"min": int(count.min()), "median": float(np.median(count)), "max": int(count.max())}, "tracks": rows}, open(os.path.join(a.out, "tracks.json"), "w"), indent=1)
print(f"{len(rows)} tracks, {len(kept)} kept (>= {a.min_frames} frames): {kept}")
print(f"people per frame: min {count.min()}, median {np.median(count):.0f}, max {count.max()}")
for r in sorted(rows, key=lambda r: -r["frames"]):
    print(f"  #{r['id']:<3} {r['frames']:>4} frames  {r['first']:>4}-{r['last']:<4} height {r['height_frac'] * 100:>3.0f}%  bottom-cut {r['touches_bottom'] * 100:>3.0f}%  side-cut {r['touches_side'] * 100:>3.0f}%  stretches {len(r['stretches'])}  kept {r['kept']['frames'] if r['kept'] else '-'}")
