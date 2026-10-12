"""Repair any part of a run's 3D model: the user paints the broken region (cut-off fingers, a crumpled helmet crown, a melted foot, ...) in the web viewer and this regenerates it.
    python -m homunculus.repair <run> --job <id>     (the job folder runs/<run>/10_repair/<id>/ holds request.json: {"strokes": [[x,y,z,r],...], "notes": "...", "label": "...", "view": "auto"})
    python -m homunculus.repair <run> --region hands|head|crown|feet [--auto] [--label "..."] [--view auto|front|back|left|right|top]     (a named region of a T/A-posed figure; the viewer's buttons use the same rules)
The redraw is chosen by YOU on the Repair tab (the job waits for the pick; --auto lets the finger counter / silhouette check and the VLM choose, which the unattended hand repair of a run uses).
Steps (each recorded in status.json for the web app): 1 region from the strokes + a close-up of it, rendered from the side it faces (Blender)  2 the image model redraws the close-up
as a complete, clean version of what the region is (the label), the checks and the VLM choose (hands also get the finger counter)  3 Pixal3D turns the chosen redraw into a small mesh
4 that mesh is mapped back with the same pixel->metre mapping as the close-up, slid over the boundary the region leaves in the surface and joined, the original region deleted
5 before/after close-ups (and a finger count for hands).
Works on the model before rigging (state artifact mesh_glb). Waits for the GPU pipeline lock, so it can be queued while a run is going."""
import argparse, fcntl, io, json, os, re, shutil, subprocess, time
import numpy as np
from PIL import Image
from . import config as C, gpu, notify, vlm, digits
from .orchestrate import Run
from .stages import comfy, edit as E

HANDS = re.compile(r"\b(hand|hands|finger|fingers|glove|gloves|palm|thumb)\b", re.I)

PROMPT = ("This is a grey clay render of part of a 3D character: {what}, where the surface is broken, missing, cut off, fused, dented, crumpled or deformed. "
          "Redraw it as the same grey clay model with a complete, clean, natural version of that part{anatomy}, seen from the same side, with the same size, position and angle, "
          "continuing the surrounding parts in the same way (the same neck, arm, leg or body where it meets them). KEEP WHAT IS ON THE PART: a shoe stays the same shoe, a glove the same glove, a boot, cuff, sleeve, hood or helmet the same garment with the same design; only repair its shape, never replace clothing or equipment by bare skin or a different object. Keep the clay look, the same lighting and the same grey colour: "
          "no skin, no colours, no new details. Plain light grey background, nothing else in the picture.")
_NUM = {"one": 1, "two": 2, "three": 3, "four": 4, "five": 5, "six": 6, "1": 1, "2": 2, "3": 3, "4": 4, "5": 5, "6": 6}


def expected_digits(label):
    """How many digits a hand of this character has: 5 unless the label says otherwise ("three fingers and a thumb" is 4, "four digits" is 4, "four fingers" is 4): a cartoon glove often has fewer."""
    t = (label or "").lower()
    m = re.search(r"\b(one|two|three|four|five|six|[1-6])\s+fingers?\s+and\s+(?:a|one|1)\s+thumb", t)
    if m: return _NUM[m.group(1)] + 1
    m = re.search(r"\b(one|two|three|four|five|six|[1-6])\s+(?:digits?|fingers?)\b", t)
    return _NUM[m.group(1)] if m else 5


def _anatomy(n):
    if n == 5: return ": five clearly separated fingers (thumb, index, middle, ring and little finger), open and relaxed"
    return f": exactly {n} clearly separated digits in all ({n - 1} fingers and a thumb, NOT five), open and relaxed"


def is_hands(label):
    return bool(HANDS.search(label or ""))


def prompt_for(label):
    """The redraw prompt for a region: what it is (the label, or 'the painted part') and, for hands, the anatomy that counts."""
    return PROMPT.format(what=(label.strip().rstrip(".") if label and label.strip() else "the painted part"), anatomy=_anatomy(expected_digits(label)) if is_hands(label) else "")


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


def _redraw(J, crop_png, out_dir, seeds, notes, prompt):
    """Qwen-Image redraws the close-up once per seed (the model stays loaded between seeds). Returns the image paths."""
    import requests
    q = E.q; os.makedirs(out_dir, exist_ok=True)
    im = Image.open(crop_png).convert("RGB").resize((SIZE, SIZE), Image.LANCZOS)
    gpu.free_all(J.log, keep="studio"); gpu.wait_for_headroom("qwen_image", J.log); q.ensure_loaded(); outs = []
    try:
        for sd in seeds:
            for attempt in range(3):
                r = q.post("/api/inference/images/generate", timeout=900, json={"prompt": prompt + (" " + notes if notes else ""), "init_image": q.to_b64(im), "workflow": "edit",
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


def _overlap(png, crop_png):
    """Silhouette overlap (IoU) between a redraw and the close-up it replaces. The redraw is asked for the same size, position and angle, so a real repair overlaps most of it; an overlap of
    ~1 means the image model handed the broken part back unchanged."""
    import cv2
    def mask(p):
        g = cv2.cvtColor(cv2.imread(p), cv2.COLOR_BGR2GRAY); g = cv2.resize(g, (256, 256)); bg = np.median(np.concatenate([g[:4].ravel(), g[-4:].ravel(), g[:, :4].ravel(), g[:, -4:].ravel()]))
        return cv2.morphologyEx((np.abs(g.astype(int) - int(bg)) > 14).astype(np.uint8), cv2.MORPH_OPEN, np.ones((3, 3), np.uint8)) > 0
    a, b = mask(png), mask(crop_png); return float((a & b).sum() / max((a | b).sum(), 1))


UNCHANGED = 0.985      # at or above this a redraw is the original handed back; below ~0.5 it is a different object


def _choose(J, k, cands, crop, label=""):
    """Hands: the finger counter filters (five digits). Everything else: the redraw must keep the region's rough shape but really change it (silhouette overlap between 0.5 and 0.985). With several left the VLM picks the most natural;
    with none left the best of the rest wins. Returns (path, counts or overlaps, passed)."""
    hands = is_hands(label)
    if hands:
        want = expected_digits(label); score = {p: _fingers(p) for p in cands}; J.log(f"region {k}: digit counts (want {want}) " + ", ".join(f"{os.path.basename(p)[7:-4]}={n}" for p, n in score.items()))
        ok = [p for p in cands if score[p] == want]; rank = lambda p: abs(score[p] - want)
    else:
        score = {p: _overlap(p, crop) for p in cands}; J.log(f"region {k}: shape overlap with the close-up " + ", ".join(f"{os.path.basename(p)[7:-4]}={v:.2f}" for p, v in score.items()) + f" (a repair overlaps 0.5 to {UNCHANGED}; more is the original handed back)")
        ok = [p for p in cands if 0.5 <= score[p] < UNCHANGED]; rank = lambda p: (score[p] >= UNCHANGED, abs(score[p] - 0.85))
    if len(ok) <= 1: return (ok or sorted(cands, key=rank))[0], score, bool(ok)
    what = (label.strip() if label and label.strip() else "a part of the character")
    try:
        vlm.load(J.log)
        d = vlm.ask_json(f"The first image is a render of {what} of a 3D character where the surface is broken, missing or deformed. The other images are redraws of it. Which redraw is the most natural, "
                         "complete and clean version (correct anatomy and proportions, no melted, fused, extra or missing parts) that still fits the original's size, outline and colours? "
                         'Reply with ONLY this JSON: {"best": <number of the best redraw, counting from 1>, "reason": "short"}', [crop] + ok, required=("best",), log=J.log,
                         labels=["Original:"] + [f"Redraw {i + 1}:" for i in range(len(ok))])
        i = int(d["best"]) - 1; J.log(f"region {k}: VLM prefers redraw {i + 1} ({d.get('reason', '')[:80]})"); return ok[max(0, min(i, len(ok) - 1))], score, True
    except Exception as e: J.log(f"region {k}: VLM choice skipped ({type(e).__name__}); using the first redraw that passed"); return ok[0], score, True
    finally:
        try: vlm.unload(J.log)
        except Exception: pass


def _seed_batch(b, n):
    """Seeds for the b-th batch of n redraws: the fixed list first, then more as you ask for more."""
    pool = SEEDS + [1000 + 37 * i for i in range(200)]
    return pool[b * n:(b + 1) * n]


def _info(cands, crop, label):
    """What the local checks say about each redraw, as plain text for the page: for hands the digit counter, otherwise the silhouette overlap with the close-up. Information only: you decide."""
    out = {}
    for p in cands:
        if is_hands(label): out[p] = f"counter: {_fingers(p)} digits (this character should have {expected_digits(label)})"
        else:
            try: out[p] = f"overlap with the close-up {_overlap(p, crop):.2f} (a repair is about 0.5 to 0.98; 1.0 = the original handed back)"
            except Exception: out[p] = ""
    return out


def _manual_choice(J, reg, gi, k, crop, rd, label, notes, per_round):
    """You are the judge: redraw, show every candidate on the page, wait for your pick (or for more redraws), repeat. No filter, no VLM. The GPU is free while it waits (the image model is unloaded)."""
    cands_all, info, batch = [], {}, 0; f = J.dir / f"choice_{gi}_{k}.json"
    while True:
        reg["status"] = f"redrawing (batch {batch + 1})"; reg["awaiting"] = False; J.save(); J.log(f"region {k}: redrawing the close-up ({per_round} candidates)")
        cands = _redraw(J, crop, str(rd), _seed_batch(batch, per_round), notes, prompt_for(label)); cands_all += cands; info.update(_info(cands, crop, label)); batch += 1
        reg["candidates"] = [J.rel(p) for p in cands_all]; reg["info"] = [info.get(p, "") for p in cands_all]
        if not cands_all: raise RuntimeError(f"region {k}: the image model returned nothing")
        if f.exists(): f.unlink()
        reg["awaiting"] = True; reg["status"] = "waiting for your choice"; J.save(); J.log(f"region {k}: {len(cands_all)} redraws ready: pick one on the page (or ask for more)")
        try: notify.send(f"homunculus · {J.R.state['name']}: pick a redraw", f"Region {k} ({label or 'the painted part'}): {len(cands_all)} redraws are waiting for your choice in the Repair tab.")
        except Exception: pass
        while not f.exists(): time.sleep(0.5)
        try: choice = json.load(open(f))["choice"]
        except Exception: time.sleep(1); choice = json.load(open(f))["choice"]
        f.unlink(); reg["awaiting"] = False
        if choice == "more": J.log(f"region {k}: you asked for more redraws"); continue
        i = int(choice)
        if not 0 <= i < len(cands_all): J.log(f"region {k}: choice {i} is out of range; ignored"); continue
        J.log(f"region {k}: you chose redraw {i + 1}"); return cands_all[i]


def bake_glb(J, merged):
    """One mesh with a fresh UV atlas and the original texture baked onto it (CPU): what the rest of the pipeline can take. Returns the path or None."""
    J.S["step"] = "bake"; J.log("baking one textured mesh (new UV atlas, the original texture carried over)")
    out = str(J.dir / "repaired_textured.glb"); rc, lines, text = _bl(["bake", merged, out, 4096], timeout=1800)
    for l in lines: J.log(l[9:])
    if rc != 0 or not os.path.exists(out): J.log("bake failed: " + text[-300:]); return None
    J.S["result_textured"] = J.rel(out); J.save(); return out


def _rebase(J, base):
    """The job's regions on ANOTHER mesh (e.g. the coloured one: the new part then takes the real colour of what it replaces): the regions are found again from the job's strokes, and each old
    region (which owns a donor) is matched to the new one with the nearest centroid, so a left donor can never land on the right hand. Returns the new merge.json."""
    old = json.load(open(J.dir / "merge.json")); first = json.load(open(old[0]["region"]))
    J.log(f"finding the regions again on {os.path.basename(str(base))}")
    an = J.dir / "an_rebase"; rc, lines, text = _bl(["analyse", base, J.dir / "strokes.json", an, first.get("view", "front")])
    if rc != 0: raise RuntimeError("the regions could not be found on that mesh: " + text[-300:])
    new = [json.load(open(an / f"region{k}.json")) for k in json.load(open(an / "regions_index.json"))["regions"]]
    out = []
    for j in old:
        c = np.array(json.load(open(j["region"]))["centroid"]); i = int(np.argmin([np.linalg.norm(np.array(n["centroid"]) - c) for n in new]))
        if np.linalg.norm(np.array(new[i]["centroid"]) - c) > 0.05: raise RuntimeError("a region has no counterpart on that mesh (more than 5 cm away)")
        out.append({**j, "region": str(an / f"region{new[i]['index']}.json")})
    json.dump(out, open(J.dir / "merge_rebase.json", "w")); return J.dir / "merge_rebase.json"


def remerge(R, job, base=None):
    """Join the donors of an earlier job again (CPU, no GPU lock): after a change to the merge, or onto another base mesh. Keeps the old result as repaired_old.glb."""
    J = Job(R, job); base = base or J.S.get("base") or R.A.get("mesh_glb")
    if len(J.S.get("groups") or []) > 1: raise RuntimeError("that job repaired several parts one after the other: joining them again is not supported (run the repair again)")
    if not os.path.exists(J.dir / "merge.json"): raise RuntimeError("that job has no merge.json (it did not get as far as the merge)")
    out = J.dir / "repaired.glb"
    if out.exists(): shutil.copy(out, J.dir / "repaired_old.glb")
    mj = J.dir / "merge.json"
    J.S.setdefault("orig_base", J.S.get("base"))             # the mesh the job's regions (their vertex numbers) were found on; any other base needs the regions found again
    if os.path.abspath(str(base)) != os.path.abspath(str(J.S["orig_base"] or "")): mj = _rebase(J, base)
    J.log(f"joining the new parts again onto {os.path.basename(str(base))}")
    rc, lines, text = _bl(["merge", base, mj, out, J.dir / "after"])
    for l in lines: J.log(l[9:])
    if rc != 0 or not out.exists(): raise RuntimeError("merge failed: " + text[-400:])
    for reg in J.S.get("regions", []):
        p = str(J.dir / "after" / f"after_region{reg['index']}_crop.png")
        if os.path.exists(p): reg["after"] = J.rel(p); reg["after_fingers"] = _fingers(p)
    J.S["base"] = str(base); J.S["result"] = J.rel(str(out)); bake_glb(J, str(out)); J.save(); return str(out)


def run_job(R, job, groups, notes="", rounds=2, per_round=3, manual=False):
    """groups: [{"strokes": [[x,y,z,r],...], "label": "what it is", "view": "auto|front|..."}, ...]. Each group has its own prompt, view and checks (hands get the finger counter, a foot or a
    helmet top does not); the groups are repaired one after the other on the running result, and the texture is baked once at the end."""
    J = Job(R, job); S = J.S; S.update(status="running", step="regions", notes=notes, groups=[{"label": g.get("label", ""), "view": g.get("view", "auto")} for g in groups],
                                       label=groups[0].get("label", ""), view=groups[0].get("view", "auto"), t0=time.time(), regions=[], result=None); J.save()
    base = R.A.get("mesh_glb")
    if not base or not os.path.exists(base): raise RuntimeError("this run has no 3D model yet (the repair works on the model before rigging)")
    cg = R.A.get("colored_glb")
    if R.state.get("sheet") and cg and os.path.exists(cg): base = cg      # a sheet run's raw mesh has one flat colour: the coloured one carries the real colours, so the new part is made in the colour of what it replaces
    S["base"] = base; cur = base; any_hands = False
    for gi, g in enumerate(groups):
        label, view, strokes = g.get("label", ""), g.get("view") or "auto", g["strokes"]; hands = is_hands(label); any_hands |= hands
        sfx = "" if gi == 0 else f"_g{gi}"; an = J.dir / f"an{sfx}"; tag = f"part {gi + 1} of {len(groups)}" + (f" ({label})" if label else "") if len(groups) > 1 else ""
        json.dump({"strokes": strokes}, open(J.dir / f"strokes{sfx}.json", "w"))
        S["step"] = "regions"; J.log((tag + ": " if tag else "") + "finding the region and rendering its close-up")
        rc, lines, out = _bl(["analyse", cur, J.dir / f"strokes{sfx}.json", an, view])
        for l in lines: J.log(l[9:])
        if rc != 0: raise RuntimeError((tag + ": " if tag else "") + "no usable region in the selection (paint over the broken part, including a bit of the neighbouring part)")
        idx = json.load(open(an / "regions_index.json"))["regions"]
        regs = [{"index": k, "group": gi, "label": label, "crop": J.rel(str(an / f"region{k}_crop.png")), "clay": J.rel(str(an / f"region{k}_clay.png")), "status": "waiting"} for k in idx]
        S["regions"] += regs; J.save(); jobs = []
        for reg in regs:
            k = reg["index"]; crop = str(an / f"region{k}_clay.png"); rd = J.dir / f"region{k}{sfx}"
            best, chosen_ok, cands_all = None, False, []
            if manual:      # you choose: no digit counter or silhouette filter decides, no VLM is loaded
                best = _manual_choice(J, reg, gi, k, crop, rd, label, notes, per_round); chosen_ok = True; cands_all = [str(C.RUNS / c) for c in reg.get("candidates", [])]
            for rnd in range(0 if manual else rounds):
                reg["status"] = f"redrawing (round {rnd + 1})"; J.save(); J.log(f"region {k}{sfx}: redrawing the close-up ({per_round} candidates)")
                cands = _redraw(J, crop, str(rd), SEEDS[rnd * per_round:(rnd + 1) * per_round], notes, prompt_for(label)); cands_all += cands
                reg["candidates"] = [J.rel(p) for p in cands_all]; J.save()
                if not cands: continue
                best, counts, chosen_ok = _choose(J, k, cands, crop, label)
                if chosen_ok: break
                J.log(f"region {k}{sfx}: no redraw passed the check in round {rnd + 1}")
            if not best: raise RuntimeError(f"region {k}{sfx}: the image model returned nothing")
            reg.update(chosen=J.rel(best), checked=chosen_ok, by="you" if manual else "the checks", **({"five_fingers": chosen_ok} if hands else {}), status="building the 3D part"); J.save()
            J.log(f"region {k}{sfx}: Pixal3D on the chosen redraw")
            donor = comfy.mesh(best, str(rd / "donor"), f"repair_{R.state['name']}_{job}_{gi}{k}", seed=7, log=J.log, faces=90000, tex=2048,
                               texture=False, upres=1536 if hands else 1024)      # the donor gets a flat colour anyway: no texture sampling; a part that fills its picture (a helmet top) peaked at 23.3 GB at 1536
            jobs.append({"region": str(an / f"region{k}.json"), "donor": donor, "silhouette": _silhouette(best)})
        try: gpu.comfy_stop()
        except Exception: pass
        json.dump(jobs, open(J.dir / f"merge{sfx}.json", "w"))
        S["step"] = "merge"; J.log((tag + ": " if tag else "") + "mapping the new parts back, sliding them over the boundary and joining")
        out_g = str(J.dir / ("repaired.glb" if len(groups) == 1 else f"repaired_g{gi}.glb"))
        rc, lines, out = _bl(["merge", cur, J.dir / f"merge{sfx}.json", out_g, J.dir / f"after{sfx}"])
        for l in lines: J.log(l[9:])
        if rc != 0 or not os.path.exists(out_g): raise RuntimeError("merge failed: " + out[-400:])
        for reg in regs:
            p = str(J.dir / f"after{sfx}" / f"after_region{reg['index']}_crop.png")
            if os.path.exists(p): reg["after"] = J.rel(p); reg["after_fingers"] = _fingers(p) if hands else None
        cur = out_g; J.save()
    out_glb = str(J.dir / "repaired.glb")
    if cur != out_glb: shutil.copy(cur, out_glb)
    bake_glb(J, out_glb)
    S.update(status="done", step="done", result=J.rel(out_glb), seconds=round(time.time() - S["t0"]))
    J.log(f"done in {S['seconds']} s" + (": " + ", ".join(f"region {r['index']}: {r.get('after_fingers', '?')} fingers" for r in S["regions"] if r.get("after_fingers") is not None) if any_hands else ""))
    return out_glb


def main():
    ap = argparse.ArgumentParser(); ap.add_argument("run"); ap.add_argument("--job", default=None); ap.add_argument("--hands", action="store_true", help="same as --region hands"); ap.add_argument("--region", action="append", choices=["hands", "head", "crown", "feet"], help="a named region of a T/A-posed figure instead of painted strokes; repeat for several (each gets its own label, view and checks)")
    ap.add_argument("--label", default=None, help="what the region is, e.g. \"the top of the helmet\" (default: from --region, or \"the painted part\")"); ap.add_argument("--view", default=None, choices=["auto", "front", "back", "left", "right", "top"], help="the side to redraw it from (default: front for hands, else auto)"); ap.add_argument("--notes", default=""); ap.add_argument("--auto", action="store_true", help="the checks and the VLM choose the redraw (default: you choose it on the Repair tab)")
    ap.add_argument("--remerge", metavar="JOB", help="join the donors of an earlier job again and bake (CPU, no GPU lock); --base PATH names the mesh the job was made on")
    ap.add_argument("--base", default=None)
    ap.add_argument("--bake", metavar="JOB", help="only bake the textured single mesh of an earlier job (CPU, no GPU lock)")
    ap.add_argument("--no-lock", action="store_true", help="do not wait for the GPU lock (only for tests that need no GPU)")
    a = ap.parse_args(); S0 = json.load(open(C.RUNS / a.run / "state.json")); R = Run(S0["input"], a.run)
    if a.remerge: print("remerged:", remerge(R, a.remerge, a.base)); return
    if a.bake:
        J = Job(R, a.bake); out = bake_glb(J, str(J.dir / "repaired.glb")); print("baked:", out); return
    job = a.job or time.strftime("%H%M%S")
    jd = R.dir / "10_repair" / job; jd.mkdir(parents=True, exist_ok=True)
    J = Job(R, job); J.S.update(status="queued"); J.save()
    lockf = open(C.RUNS / ".homunculus.lock", "a+")
    if not a.no_lock:
        try: fcntl.flock(lockf, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError: J.log("waiting for the GPU pipeline to finish its current run"); fcntl.flock(lockf, fcntl.LOCK_EX)
        lockf.seek(0); lockf.truncate(); lockf.write(f"homunculus repair for '{a.run}' (pid {os.getpid()})"); lockf.flush()
    R = Run(S0["input"], a.run)
    try:
        req = json.load(open(jd / "request.json")) if (jd / "request.json").exists() else {}
        regions = a.region or (["hands"] if a.hands else [])
        LABEL = {"hands": "the hands (keep any gloves)", "head": "the head (keep any hood or helmet)", "crown": "the top of the head or helmet", "feet": "the feet (keep the shoes or boots)"}
        if regions:
            if len(regions) > 1 and (a.label or a.view): raise RuntimeError("--label and --view apply to one region: give them only with a single --region")
            groups = []
            for r_ in regions:
                _bl(["preset", R.A["mesh_glb"], jd / f"region_{r_}.json", r_])
                groups.append({"strokes": json.load(open(jd / f"region_{r_}.json"))["strokes"], "label": a.label or LABEL[r_], "view": a.view or ("front" if r_ == "hands" else "auto")})
        elif req.get("groups"): groups = req["groups"]
        else:
            label = a.label if a.label is not None else req.get("label", ""); groups = [{"strokes": req["strokes"], "label": label, "view": a.view or req.get("view") or ("front" if is_hands(label) else "auto")}]
        a.notes = a.notes or req.get("notes", "")
        manual = not a.auto and bool(req.get("manual", True))
        with gpu.watchdog(J.log): out = run_job(R, job, groups, a.notes, manual=manual)
    except Exception as e:
        J = Job(R, job); J.S.update(status="failed", error=f"{type(e).__name__}: {str(e)[:300]}"); J.save(); notify.send(f"homunculus · {a.run}: repair failed", str(e)[:200], critical=True); raise
    notify.send(f"homunculus · {a.run}", "Repair finished. Open the Repair tab to compare before and after.")


if __name__ == "__main__":
    main()
