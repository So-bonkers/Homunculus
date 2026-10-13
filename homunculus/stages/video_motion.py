"""Dance from a video: one person dancing in a video -> motion on a run's rigged character.

GVHMR (video -> SMPL body motion, gvhmr/ environment, docs/VIDEO_MOTION.md) -> the camera's own motion tracked from the background and taken out of the dancer's path (tools/track_camera.py,
tools/compensate_camera.py; skipped when the camera is steady) -> BVH (tools/smpl_to_bvh.py) -> retargeted onto the run's rig (tools/retarget_bvh.py). The result is a clip in 09_animate/animations.json
like the text-to-animation clips, with a preview render and a side-by-side with the video. Body only: no fingers, and the depth of the dancer is a guess from one camera."""
import json, os, re, shutil, subprocess, sys, time
from pathlib import Path
from .. import config as C, gpu
from . import animate

GV = C.ROOT / "gvhmr"; GV_PY = GV / ".venv" / "bin" / "python"; TOOLS = C.ROOT / "tools"
MAX_SECONDS = 180


def available():
    """-> (ok, what is missing)"""
    if not GV_PY.exists(): return False, "the gvhmr/ environment is not set up (docs/VIDEO_MOTION.md)"
    if not (GV / "repo" / "inputs" / "checkpoints" / "gvhmr").exists(): return False, "GVHMR checkpoints are missing (docs/VIDEO_MOTION.md)"
    if not (GV / "repo" / "inputs" / "checkpoints" / "body_models" / "smplx").exists(): return False, "the SMPL-X body model is missing (docs/VIDEO_MOTION.md)"
    return True, ""


def _sh(cmd, what, timeout=3600, cwd=None):
    r = subprocess.run([str(c) for c in cmd], capture_output=True, text=True, timeout=timeout, cwd=cwd)
    if r.returncode: raise RuntimeError(f"{what} failed (exit {r.returncode}): {(r.stderr or r.stdout)[-500:]}")
    return r.stdout


def _steady(track_npz):
    """True when the tracked camera barely moved (then GVHMR's own static-camera path is better than a tracked one) or the tracker found too little background to trust."""
    import numpy as np
    from scipy.spatial.transform import Rotation as Rot
    d = np.load(track_npz); ang = np.degrees(Rot.from_matrix(d["R"]).magnitude()).max(); zoom = d["f"].max() / d["f"].min()
    return bool(ang < 1.5 and zoom < 1.03) or float(np.mean(d["ok"])) < 0.5, float(ang), float(zoom), float(np.mean(d["ok"]))


def _fmt_t(s):
    s = int(round(s)); return f"{s // 60}:{s % 60:02d}"


def generate(R, video, start, end, label=None, title=None, yaw=180.0, log=None):
    """Make one clip from video[start:end] (seconds). Returns the clip dict (also appended to 09_animate/animations.json)."""
    log = log or R.log; start, end = float(start), float(end); dur = end - start
    ok, why = available()
    if not ok: raise RuntimeError("Dance from video is not available: " + why)
    if not (0 <= start < end) or dur > MAX_SECONDS: raise RuntimeError(f"Choose a range of 1 to {MAX_SECONDS} seconds (got {start:g} to {end:g}).")
    rig = R.A.get("rig_fbx")
    if not rig or not os.path.exists(rig): raise RuntimeError("no rig to animate yet")
    M = animate._manifest(R); M["status"] = "running"; M["error"] = None; animate._save(R, M)
    title = (title or Path(video).stem).strip(); stem = re.sub(r"[^A-Za-z0-9]+", "_", title).strip("_")[:24] or "video"
    cid = f"video_{stem}_{time.strftime('%H%M%S')}"; work = animate._dir(R) / "video" / cid; shutil.rmtree(work, ignore_errors=True); os.makedirs(work)
    name = label or f"From video: {title[:40]} ({_fmt_t(start)}-{_fmt_t(end)})"
    try:
        log(f"[video] {name}")
        clip = work / "clip.mp4"
        _sh(["ffmpeg", "-v", "error", "-y", "-ss", f"{start:.3f}", "-t", f"{dur:.3f}", "-i", video, "-vf", "fps=30", "-an", "-c:v", "libx264", "-crf", "14", clip], "cutting the video", 900)
        log("[video] estimating the body motion (GVHMR)")
        gpu.free_all(log); gpu.wait_for_headroom("gvhmr", log)
        with gpu.watchdog(log):
            _sh([GV_PY, TOOLS / "video_to_smpl.py", "--video", clip, "--output_root", work / "out", "-s"], "GVHMR", 3600)
        out = work / "out" / "clip"; npz = out / "smpl_global.npz"
        if not npz.exists(): raise RuntimeError("GVHMR produced no motion (is a person visible in the video?)")
        log("[video] following the camera")
        track = work / "cam.npz"; use = npz
        try:
            _sh([GV_PY, "-I", TOOLS / "track_camera.py", clip, track, "--bbx", out / "preprocess" / "bbx.pt"], "camera tracking", 1800)
            steady, ang, zoom, found = _steady(track)
            if steady: log(f"[video] steady camera (moved {ang:.1f} deg, zoom x{zoom:.2f}, background found {found * 100:.0f}%): GVHMR's own path is used")
            else:
                _sh([GV_PY, "-I", TOOLS / "compensate_camera.py", out, track, work / "smpl_global_cam.npz"], "camera compensation", 900); use = work / "smpl_global_cam.npz"
                log(f"[video] moving camera (up to {ang:.0f} deg, zoom x{zoom:.2f}): the dancer's path is corrected for it")
        except Exception as e: log(f"[video] camera tracking skipped ({str(e)[:120]})")
        log("[video] building the animation")
        bvh = work / "clip.bvh"
        _sh([sys.executable, "-I", TOOLS / "smpl_to_bvh.py", use, bvh, "--yaw", f"{yaw:g}"], "converting to BVH", 600)
        rt = work / "rt"
        _sh([C.BLENDER, "-b", "--python", TOOLS / "retarget_bvh.py", "--", rig, bvh, rt, cid, "--map", "smpl", "--fps", "30"], "retargeting onto the rig", 1800)
        g, f = rt / f"{cid}.glb", rt / f"{cid}.fbx"
        if not g.exists(): raise RuntimeError("retargeting produced no clip")
        dst = animate._dir(R) / "clips" / f"{cid}.glb"; shutil.move(str(g), dst)
        if C.KEEP_FBX and f.exists(): shutil.copy(f, dst.with_suffix(".fbx"))
        thumb = dst.with_suffix(".png")
        subprocess.run([C.BLENDER, "-b", "--python", str(C.ROOT / "homunculus" / "blender_clip_thumb.py"), "--", str(dst), str(thumb)], capture_output=True, text=True, timeout=300)
        rel = lambda p: os.path.relpath(p, R.dir)
        entry = {"id": cid, "prompt": name, "rep": 0, "source": "video", "range": [start, end], "glb": rel(dst), "fbx": rel(dst.with_suffix(".fbx")) if dst.with_suffix(".fbx").exists() else None,
                 "thumb": rel(thumb) if thumb.exists() else None, "time": time.strftime("%H:%M:%S")}
        M = animate._manifest(R); M["clips"] += [entry]; M["status"] = "done"; animate._save(R, M)
        log("[video] clip ready; rendering the preview")
        png = (R.A.get("textured_glb") or "")[:-4] + "_basecolor.png"
        if R.A.get("textured_glb") and os.path.exists(png): animate.retexture(R, png)
        py_ = C.ROOT / ".venv" / "bin" / "python"; py_ = py_ if py_.exists() else sys.executable
        try:        # a preview with the video's own sound, and the video next to it
            pv = animate._dir(R) / "clips" / f"{cid}_preview.mp4"; cmp_ = animate._dir(R) / "clips" / f"{cid}_compare.mp4"; tmp = work / "render.mp4"
            _sh([py_, TOOLS / "make_mp4.py", f, tmp, "--fixed", "--samples", "12"], "rendering the preview", 7200)
            _sh(["ffmpeg", "-v", "error", "-y", "-i", tmp, "-ss", f"{start:.3f}", "-t", f"{dur:.3f}", "-i", video, "-map", "0:v", "-map", "1:a?", "-c:v", "libx264", "-crf", "20", "-pix_fmt", "yuv420p", "-c:a", "aac", "-b:a", "160k", "-shortest", pv], "adding the sound", 900)
            _sh(["ffmpeg", "-v", "error", "-y", "-i", clip, "-i", tmp, "-ss", f"{start:.3f}", "-t", f"{dur:.3f}", "-i", video, "-filter_complex", "[0:v]scale=-2:720,setsar=1[a];[1:v]scale=-2:720,setsar=1[b];[a][b]hstack=2[v]",
                 "-map", "[v]", "-map", "2:a?", "-c:v", "libx264", "-crf", "22", "-pix_fmt", "yuv420p", "-c:a", "aac", "-b:a", "160k", "-shortest", cmp_], "side by side", 1800)
            M = animate._manifest(R)
            for c in M["clips"]:
                if c["id"] == cid: c["video"] = rel(pv); c["compare"] = rel(cmp_)
            animate._save(R, M)
        except Exception as e: log(f"[video] preview render failed ({str(e)[:160]}); the clip itself is fine")
        for p in ("out", "clip.mp4", "render.mp4", "rt"): shutil.rmtree(work / p, ignore_errors=True) if (work / p).is_dir() else (work / p).unlink(missing_ok=True)     # keeps cam.npz, the BVH and the SMPL motion (small) for later
        log("[video] done"); return entry
    except Exception as e:
        M = animate._manifest(R); M["status"] = "failed"; M["error"] = f"{type(e).__name__}: {str(e)[:300]}"; animate._save(R, M); raise
