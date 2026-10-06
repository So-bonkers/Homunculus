"""Repair part of a run's 3D model: the user paints the broken region (fingers cut off, fused hands) in the web viewer and this regenerates it.
    python -m homunculus.repair <run> --job <id>     (the job folder runs/<run>/10_repair/<id>/ holds request.json: {"strokes": [[x,y,z,r],...], "notes": "..."})
    python -m homunculus.repair <run> --hands        (both hands of a T/A-posed figure; the same rule as the viewer's 'Select hands')
Steps (each recorded in status.json for the web app): 1 region from the strokes + a front close-up of it (Blender)  2 the image model redraws the close-up with a
complete anatomy, the finger counter and the VLM choose  3 Pixal3D turns the chosen redraw into a small mesh  4 that mesh is mapped back with the same pixel->metre
mapping as the close-up, snapped to the wrist ring and joined, the original region deleted  5 before/after close-ups and a finger count.
Works on the model before rigging (state artifact mesh_glb). Waits for the GPU pipeline lock, so it can be queued while a run is going."""
import argparse, fcntl, io, json, os, shutil, subprocess, time
import numpy as np
from PIL import Image
from . import config as C, gpu, notify, vlm, digits
from .orchestrate import Run
from .stages import comfy, edit as E

PROMPT = ("This is a grey clay render of part of a 3D character: a hand and wrist where some fingers are missing, cut off, fused or deformed. "
          "Redraw it as the same grey clay model with a complete, natural hand: five clearly separated fingers (thumb, index, middle, ring and little finger), open and relaxed, "
          "seen from the same side, with the same size, position and angle of the hand, the same wrist and forearm. Keep the clay look, the same lighting and the same grey colour: "
          "no skin, no colours, no new details. Plain light grey background, nothing else in the picture.")


SEEDS = [11, 23, 37, 41, 59, 73]
SIZE = 768      # redraw size; 1024 with a 1024 reference peaked at 23.2 GB (over the 22.5 GB limit). Studio only accepts reference_resolution 512, 1024 or 2048: 512 keeps the peak down


class Job:
    def __init__(self, R, job):
        self.R = R; self.dir = R.dir / "10_repair" / job; self.dir.mkdir(parents=True, exist_ok=True); self.job = job
        p = self.dir / "status.json"; self.S = json.load(open(p)) if p.exists() else {}
        self.S.setdefault("log", []); self.S.update(job=job, run=R.state["name"])

    def save(self): json.dump(self.S, open(self.dir / "status.json", "w"), indent=1)

    def log(self, msg, **kw):
        self.R.log("[repair] " + msg); self.S["log"] = (self.S["log"] + [msg])[-40:]; self.S.update(kw); self.save()

    def rel(self, p): return os.path.relpath(p, C.RUNS)


def _bl(args, timeout=900):
    r = subprocess.run([C.BLENDER, "-b", "--python", str(C.ROOT / "homunculus" / "blender_repair.py"), "--", *map(str, args)], capture_output=True, text=True, timeout=timeout)
    out = r.stdout + r.stderr
    return r.returncode, [l for l in out.splitlines() if l.startswith("[repair]")], out


def _redraw(J, crop_png, out_dir, seeds, notes):
    """Qwen-Image redraws the close-up once per seed (the model stays loaded between seeds). Returns the image paths."""
    import requests
    q = E.q; os.makedirs(out_dir, exist_ok=True)
    im = Image.open(crop_png).convert("RGB").resize((SIZE, SIZE), Image.LANCZOS)
    gpu.free_all(J.log, keep="studio"); gpu.wait_for_headroom("qwen_image", J.log); q.ensure_loaded(); outs = []
    try:
        for sd in seeds:
            for attempt in range(3):
                r = q.post("/api/inference/images/generate", timeout=900, json={"prompt": PROMPT + (" " + notes if notes else ""), "init_image": q.to_b64(im), "workflow": "edit",
                           "width": SIZE, "height": SIZE, "steps": 30, "seed": sd, "reference_resolution": 512})
                if r.status_code == 200 or "cancelled" not in r.text: break
                time.sleep(3); q.ensure_loaded()
            if r.status_code != 200: J.log(f"redraw seed {sd} failed: {r.status_code} {r.text[:100]}"); continue
            iid = r.json()["images"][0]["id"]
            img = Image.open(io.BytesIO(requests.get(f"{q.API}/api/inference/images/gallery/{iid}/file", timeout=300).content)).convert("RGB")
            p = os.path.join(out_dir, f"redraw_{sd}.png"); img.save(p); outs.append(p)
    finally:
        try: q.post("/api/inference/images/unload")
        except Exception: pass
    return outs


def _fingers(png):
    try: return int(digits.hand_digits(png)[0])
    except Exception: return 0


def _silhouette(png):
    import cv2
    g = cv2.cvtColor(cv2.imread(png), cv2.COLOR_BGR2GRAY); h, w = g.shape
    bg = np.median(np.concatenate([g[:6].ravel(), g[-6:].ravel(), g[:, :6].ravel(), g[:, -6:].ravel()]))
    m = (np.abs(g.astype(int) - int(bg)) > 14).astype(np.uint8); m = cv2.morphologyEx(m, cv2.MORPH_OPEN, np.ones((5, 5), np.uint8))
    ys, xs = np.nonzero(m)
    if len(xs) < 100: raise RuntimeError("the redraw has no visible subject")
    return [int(xs.min()), int(ys.min()), int(xs.max()), int(ys.max()), w, h]


def _choose(J, k, cands, crop):
    """The finger counter filters (five digits); with several left, the VLM picks the most natural; with none left the closest count wins."""
    counts = {p: _fingers(p) for p in cands}; J.log(f"region {k}: finger counts " + ", ".join(f"{os.path.basename(p)[7:-4]}={n}" for p, n in counts.items()))
    ok = [p for p in cands if counts[p] == 5]
    if len(ok) <= 1: return (ok or sorted(cands, key=lambda p: abs(counts[p] - 5)))[0], counts, bool(ok)
    try:
        vlm.load(J.log)
        d = vlm.ask_json("The first image is a render of a character's hand with broken or missing fingers. The other images are redraws of it. Which redraw is the most natural, "
                         "complete human hand (five separated fingers, correct anatomy, no extra or fused fingers, no melted shapes) that still fits the original's glove, cuff and colours? "
                         'Reply with ONLY this JSON: {"best": <number of the best redraw, counting from 1>, "reason": "short"}', [crop] + ok, required=("best",), log=J.log,
                         labels=["Original:"] + [f"Redraw {i + 1}:" for i in range(len(ok))])
        i = int(d["best"]) - 1; J.log(f"region {k}: VLM prefers redraw {i + 1} ({d.get('reason', '')[:80]})"); return ok[max(0, min(i, len(ok) - 1))], counts, True
    except Exception as e: J.log(f"region {k}: VLM choice skipped ({type(e).__name__}); using the first redraw with five fingers"); return ok[0], counts, True
    finally:
        try: vlm.unload(J.log)
        except Exception: pass


def run_job(R, job, strokes, notes="", rounds=2, per_round=3):
    J = Job(R, job); S = J.S; S.update(status="running", step="regions", notes=notes, t0=time.time(), regions=[], result=None); J.save()
    base = R.A.get("mesh_glb")
    if not base or not os.path.exists(base): raise RuntimeError("this run has no 3D model yet (the repair works on the model before rigging)")
    json.dump({"strokes": strokes}, open(J.dir / "strokes.json", "w"))
    J.log("finding the region and rendering its close-up")
    rc, lines, out = _bl(["analyse", base, J.dir / "strokes.json", J.dir / "an"])
    for l in lines: J.log(l[9:])
    if rc != 0: raise RuntimeError("no usable region in the selection (paint over the broken part, including a bit of the arm)")
    idx = json.load(open(J.dir / "an" / "regions_index.json"))["regions"]
    S["regions"] = [{"index": k, "crop": J.rel(str(J.dir / "an" / f"region{k}_crop.png")), "clay": J.rel(str(J.dir / "an" / f"region{k}_clay.png")), "status": "waiting"} for k in idx]; J.save()
    jobs = []
    for reg in S["regions"]:
        k = reg["index"]; crop = str(J.dir / "an" / f"region{k}_clay.png"); rd = J.dir / f"region{k}"
        best, chosen_ok, cands_all = None, False, []
        for rnd in range(rounds):
            reg["status"] = f"redrawing (round {rnd + 1})"; J.save(); J.log(f"region {k}: redrawing the close-up ({per_round} candidates)")
            cands = _redraw(J, crop, str(rd), SEEDS[rnd * per_round:(rnd + 1) * per_round], notes); cands_all += cands
            reg["candidates"] = [J.rel(p) for p in cands_all]; J.save()
            if not cands: continue
            best, counts, chosen_ok = _choose(J, k, cands, crop)
            if chosen_ok: break
            J.log(f"region {k}: no redraw with five fingers in round {rnd + 1}")
        if not best: raise RuntimeError(f"region {k}: the image model returned nothing")
        reg.update(chosen=J.rel(best), five_fingers=chosen_ok, status="building the 3D hand"); J.save()
        J.log(f"region {k}: Pixal3D on the chosen redraw")
        donor = comfy.mesh(best, str(rd / "donor"), f"repair_{R.state['name']}_{job}_{k}", seed=7, log=J.log, faces=90000, tex=2048)
        jobs.append({"region": str(J.dir / "an" / f"region{k}.json"), "donor": donor, "silhouette": _silhouette(best)})
    try: gpu.comfy_stop()
    except Exception: pass
    json.dump(jobs, open(J.dir / "merge.json", "w"))
    S["step"] = "merge"; J.log("mapping the new hands back, snapping to the wrist and joining")
    out_glb = str(J.dir / "repaired.glb"); rc, lines, out = _bl(["merge", base, J.dir / "merge.json", out_glb, J.dir / "after"])
    for l in lines: J.log(l[9:])
    if rc != 0 or not os.path.exists(out_glb): raise RuntimeError("merge failed: " + out[-400:])
    after = {}
    for reg in S["regions"]:
        p = str(J.dir / "after" / f"after_region{reg['index']}_crop.png")
        if os.path.exists(p): reg["after"] = J.rel(p); reg["after_fingers"] = _fingers(p)
    S.update(status="done", step="done", result=J.rel(out_glb), seconds=round(time.time() - S["t0"])); J.log(f"done in {S['seconds']} s: " + ", ".join(f"region {r['index']}: {r.get('after_fingers', '?')} fingers" for r in S["regions"]))
    return out_glb


def main():
    ap = argparse.ArgumentParser(); ap.add_argument("run"); ap.add_argument("--job", default=None); ap.add_argument("--hands", action="store_true"); ap.add_argument("--notes", default="")
    ap.add_argument("--no-lock", action="store_true", help="do not wait for the GPU lock (only for tests that need no GPU)")
    a = ap.parse_args(); S0 = json.load(open(C.RUNS / a.run / "state.json")); R = Run(S0["input"], a.run); job = a.job or time.strftime("%H%M%S")
    jd = R.dir / "10_repair" / job; jd.mkdir(parents=True, exist_ok=True)
    J = Job(R, job); J.S.update(status="queued"); J.save()
    lockf = open(C.RUNS / ".homunculus.lock", "a+")
    if not a.no_lock:
        try: fcntl.flock(lockf, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError: J.log("waiting for the GPU pipeline to finish its current run"); fcntl.flock(lockf, fcntl.LOCK_EX)
        lockf.seek(0); lockf.truncate(); lockf.write(f"homunculus repair for '{a.run}' (pid {os.getpid()})"); lockf.flush()
    R = Run(S0["input"], a.run)
    try:
        if a.hands:
            rc, lines, out = _bl(["hands", R.A["mesh_glb"], jd / "hands.json"]); strokes = json.load(open(jd / "hands.json"))["strokes"]
        else: strokes = json.load(open(jd / "request.json"))["strokes"]; a.notes = a.notes or json.load(open(jd / "request.json")).get("notes", "")
        with gpu.watchdog(J.log): out = run_job(R, job, strokes, a.notes)
    except Exception as e:
        J = Job(R, job); J.S.update(status="failed", error=f"{type(e).__name__}: {str(e)[:300]}"); J.save(); notify.send(f"homunculus · {a.run}: repair failed", str(e)[:200], critical=True); raise
    notify.send(f"homunculus · {a.run}", "Repair finished. Open the Repair tab to compare before and after.")


if __name__ == "__main__":
    main()
