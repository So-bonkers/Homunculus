"""Render an animated rigged character (FBX) to an MP4 with a moving camera: Blender processes in parallel (tools/render_dance.py), then ffmpeg (H.264).
    .venv/bin/python tools/make_mp4.py <character.fbx> <out.mp4> [--workers 4] [--fps 30] [--size 1280x720] [--seed 7] [--cuts f1,f2] [--samples 12] [--keep-frames]
No sound. Frames go to a temporary folder next to the output and are deleted when the video is made."""
import argparse, os, shutil, subprocess, sys, threading, time
from pathlib import Path
ROOT = Path(__file__).resolve().parent.parent
ap = argparse.ArgumentParser(); ap.add_argument("fbx"); ap.add_argument("out"); ap.add_argument("--workers", type=int, default=4); ap.add_argument("--fps", type=int, default=30); ap.add_argument("--size", default="1280x720")
ap.add_argument("--seed", type=int, default=7); ap.add_argument("--cuts", default=""); ap.add_argument("--samples", type=int, default=12); ap.add_argument("--keep-frames", action="store_true"); ap.add_argument("--fixed", action="store_true")
a = ap.parse_args(); out = Path(a.out).resolve(); fr = out.parent / f"_frames_{out.stem}"; shutil.rmtree(fr, ignore_errors=True); fr.mkdir(parents=True)
BL = shutil.which("blender") or "/snap/bin/blender"
def blender(args, **kw): return subprocess.Popen([BL, "-b", "--python", str(ROOT / "tools" / "render_dance.py"), "--", a.fbx, str(fr), "--fps", str(a.fps), "--size", a.size, "--seed", str(a.seed), "--samples", str(a.samples), *( ["--fixed"] if a.fixed else []), *( ["--cuts", a.cuts] if a.cuts else []), *args], **kw)
probe = subprocess.run([BL, "-b", "--python", str(ROOT / "tools" / "render_dance.py"), "--", a.fbx, str(fr), "--fps", str(a.fps), "--probe", "--range", "0", "1", "--size", "320x180", "--seed", str(a.seed)], capture_output=True, text=True)
line = next(l for l in probe.stdout.splitlines() if "frames at" in l); N = int(line.split("->")[1].split("frames")[0]); print(f"{out.name}: {N} frames at {a.fps} fps ({N / a.fps:.1f} s), {a.workers} workers", flush=True)
for f in fr.glob("probe_*.png"): f.unlink()
# (the snap build of Blender does nothing when its stdout is redirected to a FILE; pipes work, so each worker's output is drained by a thread that writes the log)
def drain(p, path):
    with open(path, "w") as f:
        for line in p.stdout: f.write(line); f.flush()
t0 = time.time(); per = -(-N // a.workers); procs = []; threads = []
for w in range(a.workers):
    lo, hi = w * per, min(N, (w + 1) * per)
    if lo < hi:
        p = blender(["--range", str(lo), str(hi)], stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True); procs.append(p)
        th = threading.Thread(target=drain, args=(p, fr / f"worker{w}.log"), daemon=True); th.start(); threads.append(th)
for p in procs: p.wait()
for th in threads: th.join()
done = len(list(fr.glob("f*.png"))); print(f"rendered {done}/{N} frames in {time.time() - t0:.0f} s", flush=True)
if done != N: sys.exit(f"missing frames ({N - done}); see {fr}/worker*.log")
r = subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-framerate", str(a.fps), "-i", str(fr / "f%05d.png"), "-c:v", "libx264", "-preset", "medium", "-crf", "18", "-pix_fmt", "yuv420p", "-movflags", "+faststart", str(out)], capture_output=True, text=True)
if r.returncode: sys.exit("ffmpeg failed: " + r.stderr[-400:])
if not a.keep_frames: shutil.rmtree(fr, ignore_errors=True)
info = subprocess.run(["ffprobe", "-v", "error", "-select_streams", "v:0", "-show_entries", "stream=width,height,r_frame_rate,nb_frames,duration", "-of", "default=nw=1", str(out)], capture_output=True, text=True).stdout.split()
print(f"wrote {out} ({out.stat().st_size / 1048576:.1f} MB): " + ", ".join(info), flush=True)
