"""One high-resolution crop video per dancer, cut from the ORIGINAL (4K) video at its own frame rate:   python tools/group_crops.py --video original.mp4 --start 13 --seconds 110 --dir <group_tracks dir> [--size 960]
(any Python with numpy; it starts ffmpeg).  The dancer's box comes from d<k>/clip/preprocess/bbx.pt of tools/group_tracks.py (taken on a 1080p, 30 fps cut of the same stretch, so its frame f is the original's frame
f * fps / 30; the box is scaled to the original's size).  Each crop is a square around the dancer (the box's own square, a little wider), black where it leaves the picture, scaled to --size.
Writes <dir>/crops/d<k>.mp4 (H.264, no sound) and <dir>/crops/crops.json (frame rate, frame count, size). One decode of the 4K video serves all dancers."""
import os, sys, json, argparse, subprocess
import numpy as np
ap = argparse.ArgumentParser(); ap.add_argument("--video", required=True); ap.add_argument("--start", type=float, required=True); ap.add_argument("--seconds", type=float, required=True); ap.add_argument("--dir", required=True)
ap.add_argument("--size", type=int, default=960); ap.add_argument("--widen", type=float, default=1.15); a = ap.parse_args(); a.dir = os.path.abspath(a.dir); os.makedirs(os.path.join(a.dir, "crops"), exist_ok=True)
import torch, cv2
meta = json.loads(subprocess.run(["ffprobe", "-v", "error", "-select_streams", "v:0", "-show_entries", "stream=width,height,avg_frame_rate", "-of", "json", a.video], capture_output=True, text=True).stdout)["streams"][0]
W, H = int(meta["width"]), int(meta["height"]); n_, d_ = meta["avg_frame_rate"].split("/"); FPS = float(n_) / float(d_); NF = int(round(a.seconds * FPS))
G = json.load(open(os.path.join(a.dir, "dancers.json"))); K = len(G["dancers"]); S30 = G["width"]; scale = W / G["width"]
xys = [torch.load(os.path.join(a.dir, f"d{k + 1}", "clip", "preprocess", "bbx.pt"), weights_only=False)["bbx_xys"].numpy() for k in range(K)]
dec = subprocess.Popen(["ffmpeg", "-v", "error", "-ss", str(a.start), "-t", str(a.seconds), "-i", a.video, "-f", "rawvideo", "-pix_fmt", "bgr24", "-"], stdout=subprocess.PIPE, bufsize=W * H * 3 * 4)
enc = [subprocess.Popen(["ffmpeg", "-v", "error", "-y", "-f", "rawvideo", "-pix_fmt", "bgr24", "-s", f"{a.size}x{a.size}", "-r", f"{FPS:.5f}", "-i", "-", "-c:v", "libx264", "-crf", "16", "-preset", "veryfast", "-pix_fmt", "yuv420p",
                       os.path.join(a.dir, "crops", f"d{k + 1}.mp4")], stdin=subprocess.PIPE) for k in range(K)]
n = 0
while n < NF + 2:
    buf = dec.stdout.read(W * H * 3)
    if len(buf) < W * H * 3: break
    im = np.frombuffer(buf, np.uint8).reshape(H, W, 3); f30 = min(len(xys[0]) - 1, int(round(n * 30 / FPS)))
    for k in range(K):
        cx, cy, s = xys[k][f30] * np.array([scale, scale, scale]); s = int(max(64, s * a.widen)); x0, y0 = int(round(cx - s / 2)), int(round(cy - s / 2))
        sx0, sy0, sx1, sy1 = max(0, x0), max(0, y0), min(W, x0 + s), min(H, y0 + s); out = np.zeros((s, s, 3), np.uint8)
        if sx1 > sx0 and sy1 > sy0: out[sy0 - y0:sy1 - y0, sx0 - x0:sx1 - x0] = im[sy0:sy1, sx0:sx1]
        enc[k].stdin.write(cv2.resize(out, (a.size, a.size), interpolation=cv2.INTER_AREA).tobytes())
    n += 1
    if n % 300 == 0: print(f"  {n}/{NF} frames", flush=True)
for e in enc: e.stdin.close(); e.wait()
dec.stdout.close(); dec.wait()
json.dump({"fps": FPS, "frames": n, "size": a.size, "start": a.start, "seconds": a.seconds, "source": [W, H]}, open(os.path.join(a.dir, "crops", "crops.json"), "w")); print(f"{n} frames at {FPS:.3f} fps for {K} dancers -> {a.dir}/crops")
