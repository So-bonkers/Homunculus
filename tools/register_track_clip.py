"""A tracked dancer's GVHMR motion -> a clip on a rig, registered in a run's Animate tab (what the dance-from-video path does for the one person it follows), for a dancer from tools/multi_track.py.
Run with the GVHMR environment (it needs torch and cv2):

    gvhmr/.venv/bin/python tools/register_track_clip.py --track <dir>/t4 --shot clip.mp4 --start-frame 22 --run kinjaz_center --id video_kinjaz_dancer4 --title "Kinjaz: dancer 4" --rig character.fbx

<track>/clip/ holds GVHMR's smpl_global.npz and preprocess/bbx.pt; --shot is the 30 fps clip the tracks were cut from, --start-frame the frame of it where this track starts (the audio and the crop start there).
The path is the one that worked for a moving camera with a dolly: GVHMR's own path (no camera compensation, which turns a dolly into height changes) with the slow horizontal drift removed (--highpass seconds),
so the dancer dances in place. Writes <id>.glb / .fbx and <id>_ref.mp4 (a 720 px crop of the dancer with the shot's sound) into runs/<run>/09_animate/clips/ and adds the clip to animations.json."""
import argparse, json, os, shutil, subprocess, sys, time
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ap = argparse.ArgumentParser()
ap.add_argument("--track", required=True); ap.add_argument("--shot", required=True); ap.add_argument("--start-frame", type=int, default=0)
ap.add_argument("--run", required=True); ap.add_argument("--id", required=True); ap.add_argument("--title", default=None); ap.add_argument("--rig", required=True)
ap.add_argument("--highpass", type=float, default=1.5, help="seconds: horizontal drift slower than this is removed (0 keeps the path as it is)"); ap.add_argument("--yaw", type=float, default=180.0)
a = ap.parse_args(); a.track, a.shot, a.rig = os.path.abspath(a.track), os.path.abspath(a.shot), os.path.abspath(a.rig)
sys.path.insert(0, ROOT)
import numpy as np, torch, cv2
from scipy.ndimage import gaussian_filter1d
from homunculus import config as C
clipdir = os.path.join(a.track, "clip"); work = os.path.join(a.track, "reg"); os.makedirs(work, exist_ok=True)
runs = C.RUNS / a.run; clips = runs / "09_animate" / "clips"; os.makedirs(clips, exist_ok=True)
# 1. the motion, in place
g = dict(np.load(os.path.join(clipdir, "smpl_global.npz"))); n = len(g["body_pose"])
if a.highpass > 0: t = g["transl"].copy(); t[:, [0, 2]] -= gaussian_filter1d(t[:, [0, 2]], a.highpass * 30, axis=0, mode="nearest"); g["transl"] = t
np.savez(os.path.join(work, "motion.npz"), **g)
# 2. BVH, then onto the rig
py = os.path.join(ROOT, ".venv", "bin", "python")
subprocess.run([py, "-I", os.path.join(ROOT, "tools", "smpl_to_bvh.py"), os.path.join(work, "motion.npz"), os.path.join(work, "motion.bvh"), "--yaw", f"{a.yaw:g}"], check=True, capture_output=True)
r = subprocess.run([C.BLENDER, "-b", "--python", os.path.join(ROOT, "tools", "retarget_bvh.py"), "--", a.rig, os.path.join(work, "motion.bvh"), os.path.join(work, "rt"), a.id, "--map", "smpl", "--fps", "30"], capture_output=True, text=True)
glb, fbx = os.path.join(work, "rt", a.id + ".glb"), os.path.join(work, "rt", a.id + ".fbx")
if not os.path.exists(glb): sys.exit("retargeting failed: " + (r.stdout + r.stderr)[-400:])
shutil.copy(glb, clips / f"{a.id}.glb"); shutil.copy(fbx, clips / f"{a.id}.fbx") if os.path.exists(fbx) else None
# 3. the reference: a crop of the dancer, with the shot's sound
b = torch.load(os.path.join(clipdir, "preprocess", "bbx.pt"), weights_only=False)["bbx_xys"].numpy()
cap = cv2.VideoCapture(a.shot); S = 720; raw = os.path.join(work, "crop_raw.mp4"); vw = cv2.VideoWriter(raw, cv2.VideoWriter_fourcc(*"mp4v"), 30, (S, S)); cap.set(cv2.CAP_PROP_POS_FRAMES, a.start_frame)
for i in range(min(n, len(b))):
    ok, img = cap.read()
    if not ok: break
    cx, cy, s = b[i]; s *= 1.25; pad = int(s) + 2; big = cv2.copyMakeBorder(img, pad, pad, pad, pad, cv2.BORDER_CONSTANT, value=(0, 0, 0))
    c = big[int(cy - s / 2) + pad:int(cy + s / 2) + pad, int(cx - s / 2) + pad:int(cx + s / 2) + pad]; vw.write(cv2.resize(c, (S, S), interpolation=cv2.INTER_AREA))
vw.release(); dur = n / 30
subprocess.run(["ffmpeg", "-v", "error", "-y", "-i", raw, "-ss", f"{a.start_frame / 30:.3f}", "-t", f"{dur:.3f}", "-i", a.shot, "-map", "0:v", "-map", "1:a?", "-c:v", "libx264", "-crf", "23", "-pix_fmt", "yuv420p", "-c:a", "aac",
                "-b:a", "160k", "-movflags", "+faststart", "-shortest", str(clips / f"{a.id}_ref.mp4")], check=True)
# 4. the clip in the run's Animate tab
mp = runs / "09_animate" / "animations.json"
try: M = json.load(open(mp))
except Exception: M = {"status": "done", "error": None, "clips": []}
M["clips"] = [c for c in M["clips"] if c["id"] != a.id] + [{"id": a.id, "prompt": a.title or a.id, "rep": 0, "source": "video", "glb": f"09_animate/clips/{a.id}.glb", "fbx": f"09_animate/clips/{a.id}.fbx" if os.path.exists(clips / f"{a.id}.fbx") else None,
                                                             "thumb": None, "ref": f"09_animate/clips/{a.id}_ref.mp4", "time": time.strftime("%H:%M:%S")}]
M["status"] = "done"; json.dump(M, open(mp, "w"), indent=1); print(f"[register] {a.id}: {n} frames ({dur:.1f} s) in {a.run}")
