"""UniMate text-to-animation on a run's rig, and putting the finished texture on the clips.

The rig (Mixamo skeleton from Make-It-Animatable) is converted once into a UniMate asset (rig_preprocess, joint labels by rule, no LLM),
motions are sampled from text on the GPU (fast: a 74M-parameter model), and driven onto the character's own mesh, giving one animated
GLB + FBX per clip (in UniMate's canonical frame: facing +Z, normalised size). Everything runs in unimate/.venv (python 3.10, bpy 4.0).
"""
import json, os, re, shutil, subprocess, time
from pathlib import Path
from .. import config as C, gpu

UM = C.ROOT / "unimate"; UM_PY = UM / ".venv" / "bin" / "python"
CKPT = UM / "outputs" / "unimate_uniml3d_f60_v3_preview"


def _dir(R):
    d = R.dir / "09_animate"; os.makedirs(d / "clips", exist_ok=True); return d


def _manifest(R):
    p = _dir(R) / "animations.json"
    try: return json.load(open(p))
    except Exception: return {"status": "idle", "clips": []}


def _save(R, m): json.dump(m, open(_dir(R) / "animations.json", "w"), indent=1)


def _env():
    return dict(os.environ, PATH=f"{UM / 'bin'}:{UM / '.venv' / 'bin'}:{os.environ['PATH']}", VIRTUAL_ENV=str(UM / ".venv"), PYTHONPATH=str(UM), HF_HUB_DISABLE_TELEMETRY="1")


def _run(cmd, log, what, timeout=1800):
    r = subprocess.run(cmd, cwd=UM, env=_env(), capture_output=True, text=True, timeout=timeout)
    if r.returncode: raise RuntimeError(f"{what} failed (exit {r.returncode}): {(r.stderr or r.stdout)[-600:]}")
    return r.stdout


def prompt_text(p):
    """UniMate was trained on captions like 'An object walks forward.': one motion, no character description."""
    p = re.sub(r"\s+", " ", str(p)).strip().rstrip(".")
    if not re.match(r"(?i)^an object\b", p): p = "An object " + (p[0].lower() + p[1:] if p else "moves")
    return p[0].upper() + p[1:] + "."


def _asset(R, log):
    rig = R.A["rig_fbx"]; d = _dir(R) / "asset"; stamp = _dir(R) / "asset.stamp"
    if R.A.get("anim_asset") and (d / "cond.npy").exists() and stamp.exists() and stamp.read_text() == f"{rig}:{os.path.getmtime(rig)}": return str(d)
    shutil.rmtree(d, ignore_errors=True)
    log("[animate] preparing the rig for UniMate")
    _run([str(UM_PY), "-m", "data_process.rig_preprocess", "run", "--input", rig, "--output_dir", str(d), "--no_review", "--annotate", "rule", "--name", "character"], log, "rig preprocessing", 900)
    if not (d / "cond.npy").exists(): raise RuntimeError("rig preprocessing produced no asset")
    stamp.write_text(f"{rig}:{os.path.getmtime(rig)}"); R.A["anim_asset"] = str(d); R.save()
    return str(d)


def hand_layer(glb, prompt, log):
    """Set the finger bones of one clip (GLB + FBX, rewritten in place) from the hand-pose library for this prompt. Returns True when it was applied."""
    if not C.HAND_POSE_LAYER: return False
    from .. import handpose
    spec = {**handpose.poses_for(prompt), "lib": handpose.LIB, "ramp": 6, "fbx": bool(C.KEEP_FBX) and Path(str(glb)[:-4] + ".fbx").exists()}; p = str(glb) + ".handpose.json"; json.dump(spec, open(p, "w"))
    try:
        r = subprocess.run([C.BLENDER, "-b", "--python", str(C.ROOT / "homunculus" / "blender_handpose.py"), "--", str(glb), p], capture_output=True, text=True, timeout=600)
        ok = r.returncode == 0 and "finger bones" in r.stdout
        if ok: log(f"[animate] hands: {spec['left']} / {spec['right']} for '{prompt[:50]}'")
        else: log("[animate] hand poses not applied: " + ((r.stdout + r.stderr).strip().splitlines() or ["?"])[-1][:100])
        return ok
    finally:
        try: os.remove(p)
        except OSError: pass


def relayer(R, log=None):
    """Apply the hand-pose layer to every clip of a run that already exists (and refresh thumbnails and the textured copies). Returns the number of clips changed."""
    log = log or R.log; M = _manifest(R); n = 0
    for c in M.get("clips", []):
        src = R.dir / c["glb"]
        if not src.exists(): continue
        if hand_layer(src, c.get("prompt", ""), log):
            n += 1; thumb = src.with_suffix(".png")
            subprocess.run([C.BLENDER, "-b", "--python", str(C.ROOT / "homunculus" / "blender_clip_thumb.py"), "--", str(src), str(thumb)], capture_output=True, text=True, timeout=300)
    png = (R.A.get("textured_glb") or "")[:-4] + "_basecolor.png"
    if n and R.A.get("textured_glb") and os.path.exists(png): retexture(R, png)
    return n


def _slug(t): return re.sub(r"[^a-z0-9]+", "_", t.lower()).strip("_")[:36] or "clip"


def generate(R, prompts, reps=2, log=None):
    """Sample + animate. Returns the new clips (dicts also appended to 09_animate/animations.json)."""
    log = log or R.log; reps = max(1, min(6, int(reps)))
    if not R.A.get("rig_fbx") or not os.path.exists(R.A["rig_fbx"]): raise RuntimeError("no rig to animate yet")
    if not (CKPT / "checkpoints" / "checkpoint_step_100000.pt").exists(): raise RuntimeError("UniMate weights are missing (unimate/outputs)")
    M = _manifest(R); M["status"] = "running"; M["error"] = None; _save(R, M)
    try:
        gpu.free_all(log); gpu.wait_for_headroom("unimate", log)
        asset = _asset(R, log)
        ps = [prompt_text(p) for p in prompts]; stamp = time.strftime("%H%M%S"); batch = _dir(R) / f"batch_{stamp}"
        log(f"[animate] sampling {len(ps)} prompt(s) x {reps}: " + " | ".join(ps))
        with gpu.watchdog(log):
            _run([str(UM_PY), "-m", "unimate.inference.sample", "--exp_dir", str(CKPT), "--asset", asset, "--prompt", *ps,
                  "--num_repetitions", str(reps), "--cfg_scale", "3", "--output_dir", str(batch), "--only_save_motion"], log, "UniMate sampling")
        log("[animate] driving the character")
        _run(["bash", "scripts/run_animate_motion.sh", str(batch)], log, "animating the mesh", 1800)
        new = []
        for f in sorted((batch / "animated").glob("*.glb")):
            m = re.match(r"character-(.+)-rep_(\d+)-(\d+)$", f.stem)
            slug, rep, idx = (m.group(1), int(m.group(2)), int(m.group(3))) if m else (f.stem, 0, 0)
            prompt = ps[idx] if idx < len(ps) else slug.replace("_", " ")
            cid = f"{_slug(prompt)}_{stamp}_{rep + 1}"; dst = _dir(R) / "clips" / f"{cid}.glb"
            shutil.move(str(f), dst)
            if f.with_suffix(".fbx").exists():
                if C.KEEP_FBX: shutil.move(str(f.with_suffix(".fbx")), dst.with_suffix(".fbx"))
                else: f.with_suffix(".fbx").unlink()          # GLB only: other formats are made on demand when a run is accepted
            hand_layer(dst, prompt, log)
            thumb = dst.with_suffix(".png")
            subprocess.run([C.BLENDER, "-b", "--python", str(C.ROOT / "homunculus" / "blender_clip_thumb.py"), "--", str(dst), str(thumb)], capture_output=True, text=True, timeout=300)
            rel = lambda p: os.path.relpath(p, R.dir)
            new.append({"id": cid, "prompt": prompt, "rep": rep, "glb": rel(dst), "fbx": rel(dst.with_suffix(".fbx")) if dst.with_suffix(".fbx").exists() else None,
                        "thumb": rel(thumb) if thumb.exists() else None, "time": time.strftime("%H:%M:%S")})
        shutil.rmtree(batch, ignore_errors=True)
        M = _manifest(R); M["clips"] += new; M["status"] = "done"; _save(R, M)
        log(f"[animate] {len(new)} clip(s) ready")
        png = (R.A.get("textured_glb") or "")[:-4] + "_basecolor.png"
        if R.A.get("textured_glb") and os.path.exists(png): retexture(R, png)
        for c in new:      # abs thumb paths for the progress snapshot
            if c.get("thumb"): c["thumb"] = str(R.dir / c["thumb"])
        return new
    except Exception as e:
        M = _manifest(R); M["status"] = "failed"; M["error"] = f"{type(e).__name__}: {str(e)[:300]}"; _save(R, M); raise


def retexture(R, png):
    """Put the finished base-colour texture on every clip (their meshes share the rig's UVs). Returns how many were done."""
    M = _manifest(R); n = 0
    for c in M.get("clips", []):
        src = R.dir / c["glb"]
        if not src.exists(): continue
        out_g = src.with_name(src.stem + "_tex.glb"); out_f = src.with_name(src.stem + "_tex.fbx")
        r = subprocess.run([C.BLENDER, "-b", "--python", str(C.ROOT / "homunculus" / "anim_tex_swap.py"), "--", str(src), png, str(out_g), str(out_f) if C.KEEP_FBX else "-"], capture_output=True, text=True, timeout=600)
        if out_g.exists():
            c["textured"] = os.path.relpath(out_g, R.dir); c["textured_fbx"] = os.path.relpath(out_f, R.dir) if out_f.exists() else None; n += 1
    if n: _save(R, M)
    return n
