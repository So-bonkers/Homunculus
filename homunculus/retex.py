"""Targeted re-texturing of a finished run: project a reference image (from any angle) onto a selected part of the model, or have the image model generate that view.
    python -m homunculus.retex <run> --job <id>      job folder runs/<run>/10_retex/<id>/ with request.json:
      {"mode": "project" | "generate" | "apply", "camera": {...}, "strokes": [[x, y, z, r], ...], "notes": "...", "ref": "ref.png", "mask": "mask.png"}
  project  CPU only, about a minute: the reference is projected from the user's camera onto the brushed area (blender_retex.py) and baked into the model's own UV atlas;
           result_basecolor.png + result.glb (preview) + before / after renders from the same camera.
  generate GPU: render the model from the camera, the image model redraws that view as the notes ask; generated.png becomes the reference to project.
  apply    CPU: the job's texture goes onto the rig and every animation clip (the previous final files are kept as *_before_retex).
The model textured by a job becomes the run's textured_glb, so the next retexture starts from it."""
import argparse, fcntl, io, json, math, os, shutil, subprocess, time
from PIL import Image
from . import config as C, gpu, notify
from .orchestrate import Run
from .stages import edit as E

PROMPT = ("This is a render of a textured 3D character model, seen from one viewpoint. Redraw this picture as a finished, clean, correctly textured version of the same view: {notes}"
          "Keep the exact same framing, camera angle, pose, silhouette, size and position of everything and the same plain grey background. Only improve the colours, materials, "
          "patterns and surface detail of the character; do not add, remove or move anything else.")


class Job:
    def __init__(self, R, job):
        self.R = R; self.dir = R.dir / "10_retex" / job; self.dir.mkdir(parents=True, exist_ok=True); self.job = job
        p = self.dir / "status.json"; self.S = json.load(open(p)) if p.exists() else {}
        self.S.setdefault("log", []); self.S.update(job=job, run=R.state["name"])

    def save(self): json.dump(self.S, open(self.dir / "status.json", "w"), indent=1)

    def log(self, msg, **kw):
        self.R.log("[retex] " + msg); self.S["log"] = (self.S["log"] + [msg])[-30:]; self.S.update(kw); self.save()

    def rel(self, p): return os.path.relpath(str(p), C.RUNS)


def base_of(R):
    """The textured model of the run and its base-colour PNG: the final texture, else the quick colours, else the raw mesh."""
    for k in ("textured_glb", "colored_glb", "mesh_glb"):
        g = R.A.get(k)
        if g and os.path.exists(g): return g
    raise RuntimeError("this run has no textured 3D model yet")


def _bl(args, timeout=900):
    r = subprocess.run([C.BLENDER, "-b", "--python", str(C.ROOT / "homunculus" / "blender_retex.py"), "--", *map(str, args)], capture_output=True, text=True, timeout=timeout)
    out = r.stdout + r.stderr; return r.returncode, [l[8:].strip() for l in out.splitlines() if l.startswith("[retex]")], out


def do_project(J, req):
    base = base_of(J.R); d = J.dir; cam = d / "camera.json"; json.dump(req["camera"], open(cam, "w")); json.dump({"strokes": req.get("strokes") or []}, open(d / "strokes.json", "w"))
    ref = d / (req.get("ref") or "ref.png")
    if not ref.exists(): raise RuntimeError("no reference image")
    mask = d / req["mask"] if req.get("mask") and (d / req["mask"]).exists() else None
    J.log("projecting the reference onto the selected area (CPU)")
    rc, lines, out = _bl(["project", base, cam, d / "strokes.json", ref, mask or "-", d / "result_basecolor.png", d / "result.glb"])
    for l in lines: J.log(l)
    if rc == 2: raise RuntimeError("nothing of the selection is visible from this camera: line the model up with the picture, or brush an area that faces the camera")
    if rc != 0 or not (d / "result.glb").exists(): raise RuntimeError("projection failed: " + out[-400:])
    J.log("rendering before and after from the same camera")
    _bl(["render", base, cam, d / "before.png", 768]); _bl(["render", d / "result.glb", cam, d / "after.png", 768])
    J.S.update(status="done", step="done", result=J.rel(d / "result.glb"), before=J.rel(d / "before.png"), after=J.rel(d / "after.png"), ref=J.rel(ref)); J.save()


def _size(aspect, mp=0.62e6):
    h = math.sqrt(mp / aspect); w = h * aspect; r32 = lambda x: max(512, int(round(x / 32)) * 32)
    return r32(w), r32(h)


def do_generate(J, req):
    import requests
    base = base_of(J.R); d = J.dir; cam = d / "camera.json"; json.dump(req["camera"], open(cam, "w"))
    J.log("rendering the current view"); _bl(["render", base, cam, d / "view.png", 1024])
    if not (d / "view.png").exists(): raise RuntimeError("could not render the view")
    view = Image.open(d / "view.png").convert("RGB"); W, H = _size(req["camera"]["aspect"]); notes = (req.get("notes") or "").strip()
    prompt = PROMPT.format(notes=(notes + ". ") if notes else "")
    q = E.q; gpu.free_all(J.log, keep="studio"); gpu.wait_for_headroom("qwen_image", J.log); q.ensure_loaded(); outs = []
    try:
        for sd in (7, 19):
            for attempt in range(3):
                r = q.post("/api/inference/images/generate", timeout=900, json={"prompt": prompt, "init_image": q.to_b64(view.resize((W, H), Image.LANCZOS)), "workflow": "edit",
                           "width": W, "height": H, "steps": 30, "seed": sd, "reference_resolution": 512})
                if r.status_code == 200 or "cancelled" not in r.text: break
                time.sleep(3); q.ensure_loaded()
            if r.status_code != 200: J.log(f"seed {sd} failed: {r.status_code} {r.text[:100]}"); continue
            iid = r.json()["images"][0]["id"]
            img = Image.open(io.BytesIO(requests.get(f"{q.API}/api/inference/images/gallery/{iid}/file", timeout=300).content)).convert("RGB").resize(view.size, Image.LANCZOS)
            p = d / f"generated_{sd}.png"; img.save(p); outs.append(J.rel(p)); J.log(f"generated a view (seed {sd})", generated=outs)
    finally:
        try: q.post("/api/inference/images/unload")
        except Exception: pass
    if not outs: raise RuntimeError("the image model returned nothing")
    shutil.copy(C.RUNS / outs[0], d / "generated.png")
    J.S.update(status="done", step="done", view=J.rel(d / "view.png"), generated=outs, ref=outs[0]); J.save()


def do_apply(J, req):
    R = J.R; src = C.RUNS / req["from_job"] if False else R.dir / "10_retex" / req["from_job"]
    res, png = src / "result.glb", src / "result_basecolor.png"
    if not res.exists() or not png.exists(): raise RuntimeError("that job has no result yet")
    A = R.A; A.setdefault("textured_glb_before_retex", A.get("textured_glb") or A.get("colored_glb") or A.get("mesh_glb"))
    if A.get("rig_fbx") and os.path.exists(A["rig_fbx"]):
        final = os.path.join(str(R.dir / "07_rig"), f"{R.state['name']}_final.fbx"); old = {}
        for ext in (".fbx", ".glb"):
            f = final[:-4] + ext
            if os.path.exists(f) and not os.path.exists(final[:-4] + "_before_retex" + ext): shutil.copy(f, final[:-4] + "_before_retex" + ext)
        J.log("putting the texture on the rig")
        r = subprocess.run([C.BLENDER, "-b", "--python", str(C.ROOT / "homunculus" / "tex_swap.py"), "--", A["rig_fbx"], str(png), final], capture_output=True, text=True)
        if not os.path.exists(final): raise RuntimeError("texture swap failed: " + (r.stdout + r.stderr)[-500:])
        A["final_fbx"] = final; A["final_glb"] = final[:-4] + ".glb"
    A["textured_glb"] = str(res); R.save()
    try:
        from .stages import animate
        n = animate.retexture(R, str(png)); J.log(f"texture put on {n} animation clip(s)")
    except Exception as e: J.log(f"clips not re-textured ({type(e).__name__}: {str(e)[:100]})")
    J.S.update(status="done", step="applied", applied_from=req["from_job"]); J.save()


def main():
    ap = argparse.ArgumentParser(); ap.add_argument("run"); ap.add_argument("--job", required=True); a = ap.parse_args()
    S0 = json.load(open(C.RUNS / a.run / "state.json")); R = Run(S0["input"], a.run); jd = R.dir / "10_retex" / a.job; req = json.load(open(jd / "request.json")); mode = req["mode"]
    J = Job(R, a.job); J.S.update(status="queued", mode=mode, notes=req.get("notes", "")); J.save()
    lockf = open(C.RUNS / ".homunculus.lock", "a+")
    if mode == "generate":      # the only mode that needs the GPU
        try: fcntl.flock(lockf, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError: J.log("waiting for the GPU pipeline to finish its current run"); fcntl.flock(lockf, fcntl.LOCK_EX)
        lockf.seek(0); lockf.truncate(); lockf.write(f"homunculus retexture for '{a.run}' (pid {os.getpid()})"); lockf.flush()
    R = Run(S0["input"], a.run); J = Job(R, a.job); J.S.update(status="running", step=mode); J.save()
    try:
        with gpu.watchdog(J.log) as wd: {"project": do_project, "generate": do_generate, "apply": do_apply}[mode](J, req)
    except Exception as e:
        J.S.update(status="failed", error=f"{type(e).__name__}: {str(e)[:300]}"); J.save(); notify.send(f"homunculus · {a.run}: retexture failed", str(e)[:200], critical=True); raise
    if mode == "generate": notify.send(f"homunculus · {a.run}", "The generated view is ready in the Retexture tab.")


if __name__ == "__main__":
    main()
