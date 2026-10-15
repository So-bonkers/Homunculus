"""GVHMR on every stretch of every dancer cut by tools/group_segments.py, one after the other:  python tools/gvhmr_segments.py --dir <dir>  (any Python; it starts the GVHMR environment's tools/video_to_smpl.py for each stretch, static camera).
Skips a stretch that already has smpl_global.npz, so it can be stopped and started again. Progress is appended to <dir>/gvhmr_progress.txt."""
import os, sys, json, time, subprocess, argparse
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__))); PY = os.path.join(ROOT, "gvhmr", ".venv", "bin", "python")
ap = argparse.ArgumentParser(); ap.add_argument("--dir", required=True); a = ap.parse_args(); a.dir = os.path.abspath(a.dir); S = json.load(open(os.path.join(a.dir, "segments.json"))); log = open(os.path.join(a.dir, "gvhmr_progress.txt"), "a")
todo = [(d["k"], s) for d in S["dancers"] for s in d["segments"]]; t0 = time.time(); n = 0
for k, s in todo:
    sd = os.path.join(a.dir, f"d{k}", f"s{s['i']:02d}")
    if os.path.exists(os.path.join(sd, "clip", "smpl_incam.npz")): n += 1; continue
    t1 = time.time(); r = subprocess.run([PY, os.path.join(ROOT, "tools", "video_to_smpl.py"), "--video", os.path.join(sd, "clip.mp4"), "--output_root", sd, "-s"], capture_output=True, text=True)
    ok = os.path.exists(os.path.join(sd, "clip", "smpl_incam.npz")); n += ok
    log.write(f"{time.strftime('%H:%M:%S')} d{k} s{s['i']:02d} {s['frames']} frames: {'ok' if ok else 'FAILED ' + (r.stdout + r.stderr)[-300:]} ({time.time() - t1:.0f} s) [{n}/{len(todo)}]\n"); log.flush()
log.write(f"{time.strftime('%H:%M:%S')} ALL DONE {n}/{len(todo)} in {(time.time() - t0) / 60:.0f} min\n"); log.flush()
