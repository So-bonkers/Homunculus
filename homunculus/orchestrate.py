"""homunculus orchestrator: image -> rig-friendly redraw -> textured 3D mesh -> auto-rig, with Qwen3.8-VL as planner/judge.

usage: python -m homunculus.orchestrate <image> --name NAME [--from STAGE] [--only STAGE] [--style photo|anime|3d_render] [--no-open]
State lives in runs/<name>/state.json; completed stages are skipped on re-runs.
Progress: runs/<name>/progress.html (auto-refreshing), runs/<name>/progress/*.png, desktop notifications.
"""
import argparse, json, os, shutil, subprocess, sys, time, traceback
from PIL import Image
from . import config as C, gpu, vlm, prompts, progress, digits, server, notify
from .stages import comfy, edit, blender, rig, report, cleanup, faceproj

STAGES = ["ingest", "upscale", "plan", "edit", "pick", "upscale_edit", "mesh", "mesh_check", "color", "rig", "rig_check", "animate", "texture", "report"]

class Run:
    def __init__(self, image, name, style=None):
        self.dir = C.RUNS / name; os.makedirs(self.dir, exist_ok=True)
        self.state_path = self.dir / "state.json"
        fresh = {"name": name, "input": str(image), "stages": {}, "artifacts": {}, "vlm": {}, "style_override": style}
        if self.state_path.exists():
            self.state = json.load(open(self.state_path))
            if os.path.abspath(self.state.get("input", "")) != os.path.abspath(str(image)):
                # same --name but a different picture: archive the old state and start this run from scratch
                old = self.dir / f"state_{time.strftime('%Y%m%d-%H%M%S')}.json"; shutil.move(self.state_path, old)
                print(f"note: run '{name}' was for {self.state.get('input')}; starting fresh (old state kept as {old.name})")
                self.state = fresh
        else: self.state = fresh
        if style: self.state["style_override"] = style
        self.logf = open(self.dir / "run.log", "a")
    def log(self, m):
        line = time.strftime("%H:%M:%S ") + m; print(line, flush=True); self.logf.write(line + "\n"); self.logf.flush()
    def save(self): json.dump(self.state, open(self.state_path, "w"), indent=1)
    def done(self, s): return self.state["stages"].get(s, {}).get("status") == "done"
    def mark(self, s, status, **kw):
        self.state["stages"].setdefault(s, {}).update(status=status, **kw); self.save(); progress.write_html(self)
    @property
    def A(self): return self.state["artifacts"]
    def p(self, *a):
        d = self.dir.joinpath(*a[:-1]); os.makedirs(d, exist_ok=True); return str(d / a[-1])

def need_gpu(R, job, keep=None):
    """Unload our other models, then wait (with a notification) until other apps leave enough VRAM for `job`."""
    if job == "qwen_image":
        notify.need_studio(R.log, R, what="the redraws")
        if edit.q.is_loaded(): return       # still loaded from the previous one-at-a-time redraw: it is ours, not another app
    gpu.free_all(R.log, keep=keep)
    gpu.wait_for_headroom(job, R.log, notify=lambda m: progress.snap(R, R.state.get("current_stage", job), "waiting for GPU memory", text=m))

def open_review(R, gate, title, images, captions, choose=False):
    """Show the review box right away (buttons usable while the judges are still voting); human_gate() later picks up
    any click made in the meantime."""
    if R.state.get("review_mode", "override") == "off": return
    f = R.dir / "review.json"
    if f.exists(): f.unlink()
    R.state["review_open_t"] = time.time()
    R.state["awaiting_review"] = {"gate": gate, "title": title, "images": [os.path.relpath(i, R.dir) for i in images], "captions": captions,
                                  "verdict": "judges are still voting... (you can already choose)", "manual": True, "grace": 0, "judge_best": 0,
                                  "choose": choose or gate == "pick"}
    R.save(); progress.write_html(R)

MESH_EXT = (".stl", ".obj", ".ply", ".glb", ".gltf", ".fbx")

def mesh_mode(R):
    """Mesh-first run: the input is a 3D model without a picture; the picture is painted onto its grey render."""
    return R.state.get("mode") == "mesh"

def face_on(R):
    """Is there a visible face to work on? --face on|off|auto (auto: the planner says whether a helmet or mask hides it). With no face, the face close-up, face reshape and face fit are all skipped."""
    f = R.state.get("face", "auto")
    if f in ("on", "off"): return f == "on"
    return (R.state.get("vlm", {}).get("plan") or {}).get("face_visible", True) is not False


def face_fit(R, glb_in, src, glb_out, preview_dir, log, **kw):
    """Fit the face texture. With face_source "original" (the default) the face of the user's own picture (upscaled) is first pasted into a copy of the redraw (the two pictures'
    landmarks are matched against each other, which works even when the mesh render has no readable face yet), and that picture is what gets fitted to the model. If either picture
    has no readable face the redraw's own face is used as before."""
    ref = R.A.get("upscaled")
    if R.state.get("face_source", C.FACE_SOURCE) == "original" and ref and os.path.exists(ref) and os.path.abspath(ref) != os.path.abspath(src):
        try:
            hy = os.path.join(os.path.dirname(glb_out), "face_from_original_" + os.path.basename(glb_out)[:-4] + ".png"); faceproj.hybrid_face(src, ref, hy, log); src = hy
        except Exception as e: log(f"[texture] your picture's face could not be used ({type(e).__name__}: {str(e)[:100]}); using the redraw's face")
    return faceproj.run(glb_in, src, glb_out, preview_dir, log, **kw)


def texture_simple(R):
    """Texture from the upscaled picture / chosen redraw alone (the default): no face close-up as the reference, no Qwen-cleaned side and back views, no Qwen face repaint.
    "full" (--texture full) adds those extra generated images, which can make the model look worse than the picture it came from."""
    return R.state.get("texture_mode", C.TEXTURE_MODE) == "simple" or bool(R.state.get("direct"))


def texture_source(R):
    """The picture the colour and texture projections read. A run set to use the picture as is (--direct) textures from that picture, upscaled but not redrawn:
    the face close-up redraw only serves the 3D shape (it is in the Pixal3D input), its pixels are not used for the texture. Otherwise the redraw / mesh source."""
    raw = R.A.get("edit_upscaled_raw")
    if texture_simple(R) and raw and os.path.exists(raw): return raw
    return R.A.get("mesh_source") or R.A["edit_upscaled"]


def face_redraw_on(R):
    """Redraw the face as a full-resolution close-up (before the 3D step, or for the texture)? --face-redraw on|off; default: config FACE_REFINE_EARLY. Never when there is no visible face."""
    v = R.state.get("face_redraw")
    return face_on(R) and (C.FACE_REFINE_EARLY if v is None else bool(v))


def fp(R, prompt):
    return prompt if face_on(R) else prompts.no_face(prompt)


def redraw_prompt(R, plan, notes, hands, look):
    if mesh_mode(R): return prompts.paint_prompt(plan, notes, look=look)
    return prompts.edit_prompt(plan, notes, hands=hands, outfit=R.state.get("outfit", "keep"), look=look)

def outline_iou(a_png, b_png):
    """Silhouette overlap of two images on plain backgrounds (painted candidate vs the grey render it must match)."""
    import numpy as np
    from scipy import ndimage as ndi
    def fg(p, size):
        im = np.asarray(Image.open(p).convert("RGB").resize(size)).astype(np.float32)
        bg = np.median(np.concatenate([im[:8].reshape(-1, 3), im[:, :8].reshape(-1, 3), im[:, -8:].reshape(-1, 3)]), 0)
        return ndi.binary_fill_holes(np.abs(im - bg).sum(2) > 30)
    A = fg(a_png, (512, 512)); B = fg(b_png, (512, 512)); return float((A & B).sum() / max((A | B).sum(), 1))

RIG_CAPS = ["rest", "walk", "walk 3/4", "wave", "open hand", "fist L", "fist R"]

def fing(c):
    """Finger count caption for a shape candidate (only when hand views are on)."""
    return f" · digits R{c['digits']['right']}/L{c['digits']['left']}" if C.HAND_VIEWS else ""

def manual(R):
    """--review manual: you are the judge. One candidate at a time, no VLM judges (they'd only make you wait)."""
    return R.state.get("review_mode", "override") == "manual"

def decided(R):
    """A cancel() for the judges: True once you clicked a real decision on the open review (not 'keep the judges' decision').
    Never in --review off, where the judges are the only deciders."""
    f = R.dir / "review.json"
    def check():
        if R.state.get("review_mode", "override") == "off" or not f.exists() or f.stat().st_mtime < R.state.get("review_open_t", 1e18): return False
        try: return json.load(open(f)).get("action") in ("choose", "accept", "reject", "redo")
        except Exception: return False
    return check

def human_gate(R, gate, title, images, captions, verdict_text, wait=False):
    """Optional human review after a judge decision. Returns {"action": accept|reject|choose|redo|none, "choice": k, "notes": str}.
    --review off: skipped; override (default): continues after REVIEW_GRACE s; manual: waits for the user. wait=True: always waits."""
    mode = R.state.get("review_mode", "override"); grace = int(R.state.get("review_grace", 60))
    if not wait and (mode == "off" or (mode == "override" and grace <= 0)): return {"action": "none", "choice": -1, "notes": ""}
    manual = mode == "manual" or wait; f = R.dir / "review.json"
    early = f.exists() and f.stat().st_mtime >= R.state.get("review_open_t", 1e18)    # clicked while the judges were voting
    if f.exists() and not early: f.unlink()
    R.state["awaiting_review"] = {"gate": gate, "title": title, "images": [os.path.relpath(i, R.dir) for i in images], "captions": captions,
                                  "verdict": verdict_text, "manual": manual, "grace": grace,
                                  "judge_best": R.state.get("_judge_best", 0), "choose": gate in ("pick", "mesh_check", "orient"), "opened": time.time()}
    R.save(); progress.write_html(R)
    msg = "waiting for you" if manual else f"{grace}s to override"
    subprocess.run(["notify-send", "-a", "homunculus", f"homunculus · {R.state['name']}: review {gate}", f"{title} - {msg}\n{server.url(R.state['name'])}"], capture_output=True)
    R.log(f"[review] {gate}: {msg} on {server.url(R.state['name'])}")
    t0 = time.time(); rec = {"action": "none", "choice": -1, "notes": ""}
    if early: grace = 0; manual = False; rec = json.load(open(f))
    while (manual or time.time() - t0 < grace) and not early:
        if f.exists():
            try: rec = json.load(open(f)); break
            except Exception: pass
        time.sleep(2)
    R.state.pop("awaiting_review", None); R.state.pop("review_open_t", None)
    if rec["action"] != "none" or rec.get("notes"):
        R.state.setdefault("human_reviews", []).append({"gate": gate, "title": title, **rec, "time": time.strftime("%H:%M:%S")})
        R.log(f"[review] {gate}: user {rec['action']}" + (f" #{rec['choice']}" if rec["action"] == "choose" else "") + (f" - notes: {rec['notes']}" if rec.get("notes") else ""))
    if rec.get("notes"):     # human observations steer the next redraw and the judges
        if rec["notes"].strip() not in R.state.get("human_notes", ""):      # don't repeat the same note
            R.state["human_notes"] = (R.state.get("human_notes", "") + " " + rec["notes"].strip()).strip()[-1500:]
    R.save(); progress.write_html(R)
    return rec

def combine_pick(votes, n, log):
    """Merge the judges' candidate scores; the winner is the candidate most judges picked (ties: best total score).
    If most judges found nothing usable, return best=0 so the caller can retry/fall back."""
    ok = [v for _, v in votes if v]
    merged = []
    for i in range(1, n + 1):
        cs = [next((c for c in v.get("candidates", []) if c.get("id") == i), None) for v in ok]; cs = [c for c in cs if c]
        if not cs: merged.append({"id": i, "identity": 0, "outfit": 0, "problems": []}); continue
        m = {"id": i, "identity": round(sum(c.get("identity", 0) for c in cs) / len(cs), 1), "outfit": round(sum(c.get("outfit", 0) for c in cs) / len(cs), 1)}
        for k in ("pose_ok", "hands_ok", "full_body", "clean"): m[k] = sum(bool(c.get(k)) for c in cs) * 2 > len(cs)
        m["problems"] = sorted({p for c in cs for p in c.get("problems", [])})[:6]; merged.append(m)
    picks = [int(v.get("best") or 0) for v in ok]
    none_votes = sum(p == 0 for p in picks)
    total = lambda c: c["identity"] + c["outfit"] + 3 * sum(c.get(k, False) for k in ("pose_ok", "hands_ok", "full_body", "clean"))
    if not ok or none_votes * 2 > len(ok): best = 0
    else:
        tally = {i: picks.count(i) for i in set(picks) if i}
        top = max(tally.values()); tied = [i for i, c in tally.items() if c == top]
        best = max(tied, key=lambda i: total(merged[i - 1]))
    fixes = " ".join(v.get("fix_notes", "") for v in ok if not v.get("best")).strip()
    log(f"panel pick: votes {picks} -> {best}")
    return {"candidates": merged, "best": best, "fix_notes": fixes[:400], "votes": {nm: v for nm, v in votes}}

# ---------------------------------------------------------------- stages
def st_ingest_mesh(R):
    """Mesh-first: weld, drop debris and a separate display base, decimate, scale to 1.8 m, UVs + blank texture, four grey views."""
    src = R.state["input"]; ext = os.path.splitext(src)[1].lower(); dst = R.p("00_input", "source" + ext); shutil.copy(src, dst); R.A["source_mesh"] = dst
    out = R.p("00_input", "prepped.glb"); vd = R.p("00_input", "views"); info = R.p("00_input", "prep.json")
    r_ = subprocess.run([C.BLENDER, "-b", "--python", str(C.ROOT / "homunculus" / "blender_mesh_prep.py"), "--", "prep", dst, out, vd, info], capture_output=True, text=True)
    if not os.path.exists(out): raise RuntimeError("mesh preparation failed: " + (r_.stdout + r_.stderr)[-800:])
    I = json.load(open(info)); R.A["prepped_glb"] = out; R.state["mesh_info"] = I
    views = [os.path.join(vd, f"view{i}.png") for i in range(1, 5)]; R.A["mesh_views4"] = views; R.A["input"] = views[0]; R.A["upscaled"] = views[0]
    note = (f"{I['faces_in']:,} faces in, {I['faces_out']:,} out, {I['parts']} part(s)" + (", display base removed" if I.get("base_removed") else "")
            + (f", {I['debris_removed_verts']} debris vertices dropped" if I.get("debris_removed_verts") else ""))
    progress.snap(R, "ingest", "3D model prepared: " + note, views, ["view 1", "view 2", "view 3", "view 4"])
    return note

def st_ingest(R):
    if mesh_mode(R): return st_ingest_mesh(R)
    src = R.state["input"]; dst = R.p("00_input", "input" + os.path.splitext(src)[1].lower())
    shutil.copy(src, dst); im = Image.open(dst); R.A["input"] = dst
    progress.snap(R, "ingest", f"input {im.size[0]}x{im.size[1]}", [dst])
    return f"{im.size[0]}x{im.size[1]} {im.mode}"

def guess_style(path):
    import numpy as np
    a = np.asarray(Image.open(path).convert("RGB").resize((256, 256))).astype(float)
    flat = (np.abs(np.diff(a, axis=0)).sum(2) < 6).mean()          # share of flat-colour pixels: high for anime/cel art
    return "anime" if flat > 0.62 else "photo"

def st_upscale(R):
    if mesh_mode(R): return "mesh input: nothing to upscale"
    style = R.state.get("style_override") or guess_style(R.A["input"]); R.state["style_guess"] = style
    R.A["upscaled"] = comfy.upscale(R.A["input"], R.p("01_upscale", "upscaled.png"), C.UPSCALERS[style], R.log)
    w, h = Image.open(R.A["upscaled"]).size
    progress.snap(R, "upscale", f"upscaled to {w}x{h} ({C.UPSCALERS[style]})", [R.A["input"], R.A["upscaled"]], ["original", "upscaled"])
    return f"style guess {style}"

def humanoid_ok(o): return bool(o.get("humanoid", True))

def st_plan_mesh(R):
    """Mesh-first: the VLM finds up and front on four grey views (you can override the front), the model is turned, an exact grey front render
    is made (the picture to paint), and the VLM invents colours and materials for it."""
    glb = R.A["prepped_glb"]; views = R.A["mesh_views4"]; turned = 0
    vlm.load(R.log)
    try:
        for attempt in range(2):
            o = vlm.ask_json(prompts.ORIENT, views, required=("upright", "front_view"), labels=[f"VIEW {i}" for i in range(1, 5)], log=R.log)
            R.state["vlm"][f"orient_{attempt}"] = o
            rx = 180 if o.get("upside_down") else 90 if (o.get("lying_down") or not o.get("upright", True)) else 0
            if rx and attempt == 0:
                R.log(f"model is not upright ({o.get('notes', '')}); turning it {rx} degrees")
                out = R.p("00_input", f"oriented{attempt}.glb"); vd = R.p("00_input", f"views_o{attempt}")
                subprocess.run([C.BLENDER, "-b", "--python", str(C.ROOT / "homunculus" / "blender_mesh_prep.py"), "--", "orient", glb, out, str(rx), "0", vd], capture_output=True)
                if os.path.exists(out): glb = out; views = [os.path.join(vd, f"view{i}.png") for i in range(1, 5)]
                continue
            break
    finally: vlm.unload(R.log)
    front = int(o.get("front_view") or 1) if 1 <= int(o.get("front_view") or 1) <= 4 else 1
    R.state["_judge_best"] = front
    if R.state.get("review_mode", "override") != "off":
        rec = human_gate(R, "orient", "which view is the FRONT of the model?", views, [f"view {i}" + (" (planner's choice)" if i == front else "") for i in range(1, 5)],
                         f"planner: view {front} is the front; {o.get('pose', '?')} pose; {o.get('notes', '')}")
        if rec["action"] == "choose" and 1 <= rec["choice"] <= 4: front = rec["choice"]
    R.state["mesh_pose"] = o.get("pose"); R.state["mesh_humanoid"] = o.get("humanoid", True)
    if o.get("pose") == "posed" and not (C.TPOSE_POSED and humanoid_ok(o)): R.log("!! the model is in an action pose: the auto-rigger expects a T/A-pose, so expect a weaker rig")
    if o.get("base"): R.log("!! the planner sees a display base attached to the feet; it could not be separated automatically")
    rz = [0, -90, 180, 90][front - 1]          # bring that side to face the front camera
    out = R.p("00_input", "model.glb"); vd = R.p("00_input", "views_final")
    subprocess.run([C.BLENDER, "-b", "--python", str(C.ROOT / "homunculus" / "blender_mesh_prep.py"), "--", "orient", glb, out, "0", str(rz), vd], capture_output=True)
    if not os.path.exists(out): raise RuntimeError("could not turn the model to the front")
    # not in a T/A-pose (an action pose, arms in front...): put it into a T-pose first, so the painting, the rig and the animation all work
    if o.get("humanoid", True) and o.get("pose") in ("posed", "other") and C.TPOSE_POSED:
        try:
            from .stages import tpose
            before = R.p("00_input", "tpose", "front_before.png")
            subprocess.run([C.BLENDER, "-b", "--python", str(C.ROOT / "homunculus" / "blender_mesh_prep.py"), "--", "front", out, before, R.p("00_input", "tpose", "frame_before.json"), "1024"], capture_output=True, text=True)
            tp = tpose.normalize(out, str(R.dir / "00_input" / "tpose"), R.log)
            if tp:
                out = tp; R.state["tposed"] = True
                after = R.p("00_input", "tpose", "front_after.png")
                subprocess.run([C.BLENDER, "-b", "--python", str(C.ROOT / "homunculus" / "blender_mesh_prep.py"), "--", "front", out, after, R.p("00_input", "tpose", "frame_after.json"), "1024"], capture_output=True, text=True)
                progress.snap(R, "plan", "the model was not in a T-pose: rigged with SkinTokens and baked into a T-pose", [p for p in (before, after) if os.path.exists(p)], ["as given", "T-posed"])
            else: R.log("!! the model could not be put into a T-pose; it is used as given (expect a weaker rig)")
        except Exception as e: R.log(f"!! T-pose step skipped ({type(e).__name__}: {str(e)[:120]})")
    R.A["model_glb"] = out
    fpng, fjson = R.p("01_upscale", "grey_front.png"), R.p("01_upscale", "frame.json")
    r_ = subprocess.run([C.BLENDER, "-b", "--python", str(C.ROOT / "homunculus" / "blender_mesh_prep.py"), "--", "front", out, fpng, fjson, "2048"], capture_output=True, text=True)
    if not os.path.exists(fpng): raise RuntimeError("front render failed: " + (r_.stdout + r_.stderr)[-500:])
    R.A["upscaled"] = fpng; R.A["input"] = fpng; R.A["frame_json"] = fjson
    # close-ups of the head and both hands: small modelled details (gloves, wrist straps) vanish in the full view
    im = Image.open(fpng).convert("RGB"); fr = json.load(open(fjson)); s_ = fr["s"]; top = fr["top"]; cx = fr["canvas"] / 2
    crops = []
    try:
        import numpy as np
        from scipy import ndimage as ndi
        a = np.asarray(im).astype(np.float32); bg = np.median(a[:8].reshape(-1, 3), 0); fg = ndi.binary_fill_holes(np.abs(a - bg).sum(2) > 30)
        ys, xs = np.nonzero(fg); x0, x1 = xs.min(), xs.max(); hb = int(0.16 * (ys.max() - ys.min()))
        for nm, box in (("head", (int(cx - hb), int(top), int(cx + hb), int(top + 2 * hb))),
                        ("right-side hand", (x0 - 10, int(np.median(ys[xs < x0 + hb // 3]) - hb // 3), x0 + int(hb * 0.66), int(np.median(ys[xs < x0 + hb // 3]) + hb // 3))),
                        ("left-side hand", (x1 - int(hb * 0.66), int(np.median(ys[xs > x1 - hb // 3]) - hb // 3), x1 + 10, int(np.median(ys[xs > x1 - hb // 3]) + hb // 3)))):
            p_ = R.p("02_plan", f"closeup_{nm.split()[0].replace('-', '_')}.png"); im.crop(box).resize((512, 512)).save(p_); crops.append((nm, p_))
    except Exception as e: R.log(f"close-ups skipped ({e})")
    vlm.load(R.log)
    try: plan = vlm.ask_json(prompts.PLAN_MESH, [fpng] + [c[1] for c in crops], required=("style", "subject", "clothing"), log=R.log,
                             labels=["FULL FRONT VIEW"] + [f"CLOSE-UP: {c[0]}" for c in crops])
    finally: vlm.unload(R.log)
    plan.setdefault("remove", []); plan.setdefault("cropped", []); plan.setdefault("loose_parts", [])
    R.state["vlm"]["plan"] = plan; R.state["edit_prompt"] = prompts.paint_prompt(plan); open(R.p("02_plan", "edit_prompt.txt"), "w").write(R.state["edit_prompt"])
    progress.snap(R, "plan", f"model turned to the front (view {front}); the planner chose its colours", [fpng],
                  text=f"pose: {o.get('pose')} · {o.get('notes', '')}\nsubject: {plan.get('subject')}\nclothing: {plan.get('clothing')}\nhair: {plan.get('hair')}")
    return f"front = view {front}, {o.get('pose')}; {str(plan.get('subject', ''))[:80]}"

def st_plan(R):
    if mesh_mode(R): return st_plan_mesh(R)
    vlm.load(R.log)
    try:
        plan = vlm.ask_json(prompts.PLAN, [R.A["upscaled"]], required=("style", "subject", "clothing", "remove"), log=R.log)
    finally: vlm.unload(R.log)
    if R.state.get("style_override"): plan["style"] = R.state["style_override"]
    R.state["vlm"]["plan"] = plan; R.state["edit_prompt"] = prompts.edit_prompt(plan, hands=R.state.get("hands", C.DEFAULT_POSE), outfit=R.state.get("outfit", "keep"))
    open(R.p("02_plan", "edit_prompt.txt"), "w").write(R.state["edit_prompt"])
    txt = (f"VLM plan · style: {plan.get('style')}\nsubject: {plan.get('subject')}\nclothing: {plan.get('clothing')}\n"
           f"remove: {', '.join(plan.get('remove') or [])}\ncropped: {', '.join(plan.get('cropped') or []) or '-'}")
    progress.snap(R, "plan", "VLM described the character", [R.A["upscaled"]], text=txt)
    return plan.get("subject", "")[:100]

def choose_look(R, hands):
    """--look choose (the default): the first redraw is one image per look (As is + every style); you pick the look and that image.
    Returns True when a look and its redraw were chosen (the pick is then done), False to fall back to the normal redraw rounds."""
    if R.state.get("look") != "choose": return False
    if R.state.get("review_mode", "override") == "off":
        R.state["look"] = "asis"; R.log("look: review is off, so nobody can choose; using As is"); return False
    looks = ["asis", *prompts.LOOK]; plan = R.state["vlm"]["plan"]; rnd = 0
    while True:
        rnd += 1; gen = R.state.get("edit_gen", 0); outs = []; t0 = time.time()
        need_gpu(R, "qwen_image", keep="studio")
        for i, look in enumerate(looks):
            prompt = redraw_prompt(R, plan, R.state.get("human_notes", ""), hands, look)
            res, peak = edit.run(R.A["upscaled"], str(R.dir / "03_edit"), prompt, f"{gen}{rnd}L{look}", R.log, n=1, size=C.EDIT_SIZE[hands], keep_loaded=True)
            outs += res
            if res: progress.snap(R, "edit", f"looks round {rnd}: {prompts.LOOK_LABEL[look]} ({len(outs)}/{len(looks)})", res, [prompts.LOOK_LABEL[look]])
        if not outs: raise RuntimeError("the look redraws produced no images")
        R.A.setdefault("edit_candidates", []).extend(outs)
        R.mark("edit", "running", seconds=round(time.time() - t0), note=f"looks round {rnd}: {len(outs)} looks, waiting for your pick")
        caps = [prompts.LOOK_LABEL[l] for l in looks][:len(outs)]
        if mesh_mode(R):      # the painting is projected back onto the model: it must keep the grey render's outline
            caps = [f"{c} · outline {outline_iou(o_, R.A['upscaled']):.2f}" + ("" if outline_iou(o_, R.A["upscaled"]) >= 0.88 else " (shape changed!)") for c, o_ in zip(caps, outs)]
        R.state["_judge_best"] = 0
        rec = human_gate(R, "pick", "choose a look", outs, caps, "one redraw per look: pick the one you want to build", wait=True)
        if rec["action"] == "choose" and 1 <= rec["choice"] <= len(outs):
            k = rec["choice"]; look = looks[k - 1]; R.state["look"] = look
            R.A["chosen_edit"] = outs[k - 1]; R.state["ranked_edits"] = [outs[k - 1]] + [o for o in outs if o != outs[k - 1]]
            progress.snap(R, "pick", f"you picked the look: {prompts.LOOK_LABEL[look]}", [outs[k - 1]], [prompts.LOOK_LABEL[look]]); R.save()
            R.log(f"look chosen: {look}"); return f"look {prompts.LOOK_LABEL[look]} (redraw {os.path.basename(outs[k - 1])})"
        R.log("new look redraws requested" + (f" with notes: {rec.get('notes')}" if rec.get("notes") else ""))

def st_edit_and_pick(R):
    """edit -> pick loop with VLM fix notes (both stages marked together)."""
    if R.state.get("direct"):      # --direct: the picture is already a clean reference; use it as the chosen redraw
        R.A["chosen_edit"] = R.A["input"]; R.state["ranked_edits"] = [R.A["input"]]
        progress.snap(R, "pick", "your picture is used as is (no redraw)", [R.A["input"]], ["input"])
        return "direct: your picture is used as the redraw"
    note = choose_look(R, R.state.get("hands", C.DEFAULT_POSE))
    if note: return note
    fix = R.state.get("fix_notes", ""); rnd = R.state.get("edit_round", 0); hands = R.state.get("hands", C.DEFAULT_POSE)
    rounds = R.state.get("edit_round_limit", C.EDIT_ROUNDS) if not manual(R) else 99
    n = 1 if manual(R) else C.EDIT_SEEDS
    while rnd < rounds:
        rnd += 1; R.state["edit_round"] = rnd
        prompt = redraw_prompt(R, R.state["vlm"]["plan"], (fix + " " + R.state.get("human_notes", "")).strip(), hands, R.state.get("look", "asis"))
        t0 = time.time()
        def live(done, rnd=rnd):
            if len(done) in (1, n) and not (manual(R) and rnd > 1):
                progress.snap(R, "edit", f"round {rnd}: {len(done)}/{n} redraws ({hands})", done, [os.path.basename(x) for x in done])
        need_gpu(R, "qwen_image", keep="studio")
        gen = R.state.get("edit_gen", 0)       # bumped whenever the redraw step is redone, so old candidate files are never reused
        outs, peak = edit.run(R.A["upscaled"], str(R.dir / "03_edit"), prompt, f"{gen}{rnd}{hands[0]}", R.log, n=n, on_saved=live, size=C.EDIT_SIZE[hands],
                              keep_loaded=manual(R))
        if not outs:
            R.log("this round produced no images; retrying"); continue
        R.A.setdefault("edit_candidates", []).extend(outs); R.mark("edit", "running", seconds=round(time.time() - t0), peak_vram=round(peak, 1), note=f"round {rnd}: redraws done, picking")
        open_review(R, "pick", f"redraw candidates, round {rnd}", outs, [f"candidate #{i+1}" for i in range(len(outs))])
        labels = ["Image 1 = ORIGINAL"] + [f"Image {i+2} = CANDIDATE {i+1}" for i in range(len(outs))]
        if mesh_mode(R):
            ious = [outline_iou(o_, R.A["upscaled"]) for o_ in outs]; R.log("outline overlap with the grey model: " + ", ".join(f"#{i+1} {v:.2f}" for i, v in enumerate(ious)))
        votes = [] if manual(R) else vlm.panel(prompts.pick_prompt(len(outs), R.state.get("outfit", "keep"), hands, R.state.get("look", "asis"), mesh=mesh_mode(R)), [R.A["upscaled"]] + outs, required=("candidates", "best"), labels=labels, log=R.log, cancel=decided(R), human_notes=R.state.get("human_notes", ""))
        verdict = combine_pick(votes, len(outs), R.log) if not manual(R) else {"candidates": [{"id": 1, "identity": 0, "outfit": 0, "problems": []}], "best": 0, "fix_notes": "", "votes": {}}
        R.state["vlm"][f"pick_round{rnd}_{hands}"] = verdict
        for c in verdict["candidates"]:
            if 1 <= c.get("id", 0) <= len(outs): R.state.setdefault("edit_problems", {})[outs[c["id"] - 1]] = c.get("problems", [])
        ranked = sorted(verdict["candidates"], key=lambda c: -(c.get("identity", 0) + c.get("outfit", 0) + 3 * sum(bool(c.get(k)) for k in ("pose_ok", "hands_ok", "full_body", "clean"))))
        R.state["ranked_edits"] = [outs[c["id"] - 1] for c in ranked if 1 <= c.get("id", 0) <= len(outs)]
        best = int(verdict.get("best") or 0)
        if mesh_mode(R) and best and ious[best - 1] < 0.88:      # a painting that moved the outline would land beside the mesh
            ok_ = [c["id"] for c in ranked if 1 <= c.get("id", 0) <= len(outs) and ious[c["id"] - 1] >= 0.88]
            R.log(f"#{best} changed the model's outline ({ious[best - 1]:.2f}); " + (f"using #{ok_[0]} instead" if ok_ else "no candidate kept the outline"))
            best = ok_[0] if ok_ else 0
        if not (1 <= best <= len(outs)) and not manual(R):
            # safety net: accept the best-ranked candidate whose only issues are cosmetic (background / residue)
            ok = [c for c in ranked if c.get("pose_ok") and c.get("hands_ok") and c.get("full_body") and c.get("identity", 0) >= 6
                  and c.get("outfit", 0) >= 6 and 1 <= c.get("id", 0) <= len(outs)]      # outfit must match (e.g. shirtless really shirtless)
            if ok: best = ok[0]["id"]; R.log(f"VLM said none usable, but #{best} only has cosmetic issues; accepting it")
        R.state["_judge_best"] = best
        hc = [f"identity {c.get('identity','?')} outfit {c.get('outfit','?')} {'; '.join(c.get('problems', []))[:80]}"
              for c in sorted(verdict["candidates"], key=lambda c: c.get("id", 0))][:len(outs)]
        if manual(R): hc = [f"redraw {rnd}"]
        rec = human_gate(R, "pick", f"redraw {rnd}" if manual(R) else f"redraw candidates, round {rnd}", outs, hc,
                         "manual mode: you are the judge" if manual(R) else f"picked #{best}" if best else "none usable")
        if rec["action"] == "choose" and 1 <= rec["choice"] <= len(outs): best = rec["choice"]
        elif rec["action"] == "redo": best = 0; verdict["fix_notes"] = (verdict.get("fix_notes", "") + " " + rec.get("notes", "")).strip()
        caps, borders = [], []
        for i, o in enumerate(outs):
            c = next((x for x in verdict["candidates"] if x.get("id") == i + 1), {})
            caps.append(f"#{i+1} identity {c.get('identity','?')} outfit {c.get('outfit','?')} · {'; '.join(c.get('problems', []))[:70]}")
            borders.append((40, 170, 60) if i + 1 == best else (200, 50, 50))
        you = manual(R) or rec["action"] in ("choose", "redo")
        if manual(R): caps = [f"redraw {rnd}"]
        progress.snap(R, "pick", f"round {rnd}: " + (f"{'you' if you else 'judges'} picked #{best}" if best
                      else "you asked for another one" if you else f"none usable - retrying: {verdict.get('fix_notes','')[:60]}"), outs, caps, borders)
        R.save()
        if 1 <= best <= len(outs):
            R.A["chosen_edit"] = outs[best - 1]; R.state["ranked_edits"].remove(outs[best - 1]); R.state["ranked_edits"].insert(0, outs[best - 1])
            return f"round {rnd} ({hands} hands): picked candidate {best}"
        fix = verdict.get("fix_notes", ""); R.state["fix_notes"] = fix; R.log(f"no usable candidate; fix notes: {fix}")
    if not R.state.get("ranked_edits"): raise RuntimeError("the redraw step produced no usable images")
    R.A["chosen_edit"] = R.state["ranked_edits"][0]; return "no candidate passed; using best-ranked (flagged)"

def st_upscale_edit(R):
    style = prompts.LOOK_UPSCALE.get(R.state.get("look", "asis")) or R.state["vlm"]["plan"].get("style", "photo")
    src = cleanup.clean_residue(R.A["chosen_edit"], R.p("04_upscale_edit", "edit_cleaned.png"), R.state.get("edit_problems", {}).get(R.A["chosen_edit"]), R.log)
    R.A["edit_cleaned"] = src
    R.A["edit_upscaled"] = comfy.upscale(src, R.p("04_upscale_edit", "edit_upscaled.png"), C.UPSCALERS.get(style, C.UPSCALERS["photo"]), R.log)
    progress.snap(R, "upscale_edit", "chosen redraw, cleaned and upscaled for Pixal3D", [R.A["chosen_edit"], src, R.A["edit_upscaled"]],
                  ["chosen", "residue clean-up" if src != R.A["chosen_edit"] else "(no clean-up needed)", "upscaled"])
    R.state["face_refined_early"] = False
    if not face_on(R): R.log("no visible face (helmet/mask): the face close-up and face fit are skipped")
    if face_redraw_on(R):      # a sharp face in Pixal3D's input gives the mesh real eye sockets, nose and lips
        try:
            ref, (fb, fa) = edit.refine_face(R.A["edit_upscaled"], R.p("04_upscale_edit", "edit_face_refined.png"),
                                             prompts.FACE_REFINE.format(style=prompts.style_text(R.state["vlm"]["plan"], R.state.get("look", "asis"))), R.log)
            R.A["edit_upscaled_raw"] = R.A["edit_upscaled"]; R.A["edit_upscaled"] = ref; R.state["face_refined_early"] = True
            progress.snap(R, "upscale_edit", "face redrawn at full resolution before the 3D step", [fb, fa], ["face in the redraw", "close-up redraw"])
        except Exception as e:
            R.log(f"face close-up failed ({type(e).__name__}: {str(e)[:100]}); the 3D step uses the redraw as is")
    if C.HAND_REFINE_EARLY and not mesh_mode(R):      # tiny or fused fingers in the picture become paddle hands in the 3D model
        try:
            ref, pairs = edit.refine_hands(R.A["edit_upscaled"], R.p("04_upscale_edit", "edit_hands_refined.png"),
                                           prompts.HAND_REFINE.format(style=prompts.style_text(R.state["vlm"]["plan"], R.state.get("look", "asis"))), R.log)
            if pairs:
                R.A["edit_upscaled"] = ref
                progress.snap(R, "upscale_edit", "hands redrawn at full resolution before the 3D step", [x for p_ in pairs for x in p_],
                              [c for _ in pairs for c in ("hand in the redraw", "close-up redraw")])
        except Exception as e:
            R.log(f"hand close-ups failed ({type(e).__name__}: {str(e)[:100]}); the 3D step uses the redraw as is")
    return style

def _shape_sheet(sviews, out):
    """one image per shape candidate: front, face and every hand view, for the review box"""
    from PIL import ImageDraw
    keys = ["front", "face"] + ([k for k in sviews if k.startswith(("handR_", "handL_"))] if C.HAND_VIEWS else [])
    cell = 220; cols = 5; rows = (len(keys) + cols - 1) // cols
    sh = Image.new("RGB", (cell * cols, (cell + 18) * rows), (245, 245, 245)); d = ImageDraw.Draw(sh)
    for i, k in enumerate(keys):
        if not os.path.exists(sviews[k]): continue
        im = Image.open(sviews[k]).convert("RGB"); im.thumbnail((cell, cell)); x, y = (i % cols) * cell, (i // cols) * (cell + 18)
        sh.paste(im, (x + (cell - im.width) // 2, y + 18)); d.text((x + 4, y + 2), k.replace("handR_", "R hand ").replace("handL_", "L hand "), fill=(0, 0, 0))
    sh.save(out); return out

def st_mesh_from_input(R):
    """Mesh-first: the 3D model is the input (no Pixal3D, no face reshape: your geometry is kept as it is)."""
    R.A["mesh_glb"] = R.A["model_glb"]; R.A["mesh_source"] = R.A["edit_upscaled"]; R.A.pop("textured_glb", None)
    views = blender.mesh_views(R.A["mesh_glb"], str(R.dir / "06_mesh_check" / "input"), grey=True); R.A["mesh_views"] = views
    progress.snap(R, "mesh", "your 3D model (kept as it is)", [views["front"], views["side"], views["face"]], ["front", "side", "face"])
    return "mesh input used as is"

def st_mesh_and_check(R):
    if mesh_mode(R): return st_mesh_from_input(R)
    """Best-of-N: each round makes SHAPE_SEEDS shape-only candidates in one ComfyUI session, drops any with extra fingers
    (digit gate), asks every judge about all survivors in ONE model load each, then you can pick on the page."""
    tries = R.state.setdefault("mesh_tries", 0)
    cands_img = [R.A["chosen_edit"]] + [e for e in R.state.get("ranked_edits", [])[1:2]]
    last = None
    for ci, cand in enumerate(cands_img):
        if ci > 0:
            R.log(f"falling back to next-best redraw {os.path.basename(cand)}"); R.A["chosen_edit"] = cand; st_upscale_edit(R)
        for rnd in range(C.MESH_ATTEMPTS if not manual(R) else 12):
            t0 = time.time(); shapes = []
            with gpu.watchdog(R.log) as wd:
                for k in range(C.SHAPE_SEEDS if not manual(R) else 1):
                    tries += 1; R.state["mesh_tries"] = tries; tag = f"{R.state['name']}_{tries}"; seed = 42 + 11 * tries
                    tdir = str(R.dir / "05_mesh" / f"try{tries}"); sh = comfy.shape(R.A["edit_upscaled"], tdir, tag, seed, R.log)
                    sh = carve(R, sh)
                    shapes.append({"try": tries, "tdir": tdir, "tag": tag, "seed": seed, "glb": sh}); last = (tdir, tag, seed)
            gpu.free_all(R.log)
            for c in shapes:
                vd = str(R.dir / "06_mesh_check" / f"try{c['try']}"); c["views"] = blender.mesh_views(c["glb"], vd, grey=True)
                c["digits"] = digits.count(vd, "mesh") if C.HAND_VIEWS else {"right": 5, "left": 5}; c["sheet"] = _shape_sheet(c["views"], os.path.join(vd, "sheet.png"))
                if C.HAND_VIEWS: R.log(f"try {c['try']}: digit count R{c['digits']['right']} / L{c['digits']['left']}")
            ok = [c for c in shapes if c["digits"]["right"] <= 5 and c["digits"]["left"] <= 5]
            for c in shapes:
                if c not in ok: c["verdict"] = {"pass": False, "score": 0, "tally": "digit gate", "problems": [f"extra finger (R{c['digits']['right']}/L{c['digits']['left']})"]}
            R.A["shape_candidates"] = [{"label": f"Shape #{i + 1} (try {c['try']}, grey)", "glb": c["glb"]} for i, c in enumerate(shapes)]; R.save()      # viewable in 3D while you judge them
            open_review(R, "mesh_check", f"3D shape candidates, round {rnd + 1}", [c["sheet"] for c in shapes],
                        [f"#{i+1} (try {c['try']}){fing(c)}" for i, c in enumerate(shapes)], choose=True)
            if manual(R):        # you are the judge; the finger count is still shown on each candidate
                for c in ok: c["verdict"] = {"pass": True, "score": 0, "tally": "your call", "problems": []}
            elif ok:
                queries = []
                for c in ok:
                    keys = ["front", "side", "face"] + ([k for k in c["views"] if k.startswith(("handR_", "handL_"))] if C.HAND_VIEWS else [])
                    labels = ["Image 1 = REFERENCE image"] + [f"Image {i+2} = {k.replace('handR_', 'RIGHT HAND, view: ').replace('handL_', 'LEFT HAND, view: ').upper()}" for i, k in enumerate(keys)]
                    queries.append((fp(R, prompts.MESH_CHECK if C.HAND_VIEWS else prompts.MESH_CHECK_NOHANDS), [R.A["edit_upscaled"]] + [c["views"][k] for k in keys], labels))
                for c, votes in zip(ok, vlm.panel_multi(queries, required=("pass",), log=R.log, cancel=decided(R), human_notes=R.state.get("human_notes", ""))):
                    c["verdict"] = vlm.majority_pass(votes, R.log)
            for c in shapes: R.state["vlm"][f"mesh_check_try{c['try']}"] = c["verdict"]
            R.save()
            rank = sorted(range(len(shapes)), key=lambda i: (-int(bool(shapes[i]["verdict"].get("pass"))), -float(shapes[i]["verdict"].get("score", 0))))
            best = rank[0] + 1 if shapes[rank[0]]["verdict"].get("pass") else 0
            caps = [f"#{i+1}: {'PASS' if c['verdict'].get('pass') else 'FAIL'} {c['verdict'].get('score')}/10 ({c['verdict'].get('tally')}){fing(c)}" for i, c in enumerate(shapes)]
            progress.snap(R, "mesh_check", f"3D shape {rnd + 1}: your call" if manual(R)
                          else f"3D shape candidates round {rnd + 1}: judges' best " + (f"#{best}" if best else "none"), [c["sheet"] for c in shapes], caps, cell=420,
                          text=" | ".join(f"#{i+1}: " + "; ".join(c["verdict"].get("problems") or [])[:220] for i, c in enumerate(shapes)))
            R.state["_judge_best"] = 0 if manual(R) else best
            rec = human_gate(R, "mesh_check", f"3D shape candidates, round {rnd + 1}", [c["sheet"] for c in shapes], caps,
                             f"best #{best}" if best else "no candidate passed")
            if rec["action"] == "choose" and 1 <= rec["choice"] <= len(shapes): best = rec["choice"]
            elif rec["action"] in ("redo", "reject"): best = 0
            elif rec["action"] == "accept" and not best: best = rank[0] + 1
            if best:
                c = shapes[best - 1]
                return _full_mesh(R, c["tdir"], c["tag"], c["seed"], t0) + f" (candidate #{best} of round {rnd + 1}, {c['verdict'].get('tally')})"
            R.log(f"no shape candidate accepted in round {rnd + 1}")
    R.log("no shape passed; texturing the last attempt anyway (flagged)")
    tdir, tag, seed = last
    return _full_mesh(R, tdir, tag, seed, time.time()) + " - no shape passed the judges (flagged)"

def carve(R, glb):
    """Delete geometry outside the character's front outline (Pixal3D fins and plates around the hands, floaters)."""
    if not C.SILHOUETTE_CARVE: return glb
    try:
        import numpy as np
        mp = R.p("04_upscale_edit", "outline_mask.npy")
        if not os.path.exists(mp) or os.path.getmtime(mp) < os.path.getmtime(R.A["edit_upscaled"]):
            np.save(mp, faceproj._fgmask(R.A["edit_upscaled"]))
        out = glb.replace(".glb", "_carved.glb")
        r_ = subprocess.run([C.BLENDER, "-b", "--python", str(C.ROOT / "homunculus" / "blender_carve.py"), "--", glb, mp, out], capture_output=True, text=True)
        if os.path.exists(out):
            R.log(next((l for l in r_.stdout.splitlines() if l.startswith("[carve]")), "[carve] done")); return out
    except Exception as e: R.log(f"[carve] skipped ({type(e).__name__}: {str(e)[:100]})")
    return glb

def _full_mesh(R, tdir, tag, seed, t0):
    with gpu.watchdog(R.log) as wd:
        glb = comfy.mesh(R.A["edit_upscaled"], tdir, tag, seed, R.log)
    R.A["mesh_glb"] = glb; R.save()          # the textured mesh is viewable as soon as Pixal3D has made it; the steps below refine it
    glb = carve(R, glb)
    R.A["mesh_glb"] = glb; R.save()
    clean = glb.replace(".glb", "_clean.glb")
    r_ = subprocess.run([C.BLENDER, "-b", "--python", str(C.ROOT / "homunculus" / "clean_mesh.py"), "--", glb, clean], capture_output=True, text=True)
    if os.path.exists(clean): R.log(next((l for l in r_.stdout.splitlines() if l.startswith("[clean]")), "[clean] done")); glb = clean; R.A["mesh_glb"] = glb; R.save()
    if C.FACE_RESHAPE and face_on(R):      # move the mesh's eyes/nose/mouth to where the reference has them, before rigging
        try:
            fit = faceproj.reshape(glb, R.A["edit_upscaled"], glb.replace(".glb", "_facefit.glb"), os.path.join(os.path.dirname(glb), "facefit"), R.log,
                                   style=prompts.style_text(R.state["vlm"]["plan"], R.state.get("look", "asis")), face_desc=str(R.state["vlm"]["plan"].get("face", "")))
            if fit: glb = fit
        except Exception as e: R.log(f"[facefit] skipped ({type(e).__name__}: {str(e)[:120]})")
    R.A["mesh_glb"] = glb; hi = os.path.join(os.path.dirname(glb), "mesh_hi.glb"); R.A["mesh_hi_glb"] = hi if os.path.exists(hi) else None
    src_copy = os.path.join(os.path.dirname(glb), "source.png"); shutil.copy(R.A["edit_upscaled"], src_copy); R.A["mesh_source"] = src_copy
    R.mark("mesh", "running", seconds=round(time.time() - t0), peak_vram=round(wd["peak"], 1), note=f"{os.path.basename(tdir)} textured")
    return f"{os.path.basename(tdir)} textured mesh built" + hand_gate(R)

def st_color(R):
    """A quick base colour before rigging (CPU only, ~20 s): the redraw's front is projected onto the mesh, so the rig is built and
    checked on a coloured model. The full texture (face fit, extra views) comes last, after animating, and is swapped onto the rig."""
    faceproj.FRAME = R.A.get("frame_json") if mesh_mode(R) else None
    raw = R.A["mesh_glb"]; d = os.path.dirname(raw); src = texture_source(R)
    out, note = raw, "kept the mesh's own colours"
    try:
        out = faceproj.project_body(raw, src, raw.replace(".glb", "_colored.glb"), os.path.join(d, "color"), R.log, agree_check=not mesh_mode(R)); note = "front colours projected onto the mesh"
    except Exception as e: R.log(f"[color] skipped ({type(e).__name__}: {str(e)[:120]}); the rig uses the mesh as it is")
    R.A["colored_glb"] = out
    try:
        views = blender.mesh_views(out, os.path.join(d, "color_views"), tag="color")
        progress.snap(R, "color", "quick colours before rigging: " + note, [views["front"], views["side"], views["face"]], ["front", "side", "face"])
    except Exception as e: R.log(f"[color] preview skipped ({type(e).__name__}: {str(e)[:100]})")
    return note

def st_texture(R):
    """Last step: sharpen the face by projecting the redraw onto the (raw, textured) mesh, then put that texture on the rig."""
    faceproj.FRAME = R.A.get("frame_json") if mesh_mode(R) else None
    raw = R.A["mesh_glb"]; d = os.path.dirname(raw); src = texture_source(R)
    plan = R.state["vlm"]["plan"]; sty = prompts.style_text(plan, R.state.get("look", "asis"))
    # video tip: redraw a close-up of the face at full resolution and use it as the texture reference for the head
    # (already done before the 3D step in new runs: mesh_source is that sharpened image)
    if not R.state.get("face_refined_early") and face_redraw_on(R) and not texture_simple(R):      # as-is runs keep the picture's own face pixels
      try:
        style = R.state["vlm"]["plan"].get("style", "photo")
        src, (fb, fa) = edit.refine_face(src, os.path.join(d, "source_face_refined.png"), prompts.FACE_REFINE.format(style=prompts.style_text(R.state["vlm"]["plan"], R.state.get("look", "asis"))), R.log)
        progress.snap(R, "texture", "face close-up redrawn at full resolution (texture reference)", [fb, fa], ["face in the full-body redraw", "close-up redraw"])
      except Exception as e:
        R.log(f"face close-up failed ({type(e).__name__}: {str(e)[:100]}); projecting the full-body redraw instead")
    base = raw
    if C.TEXTURE_VIEWS:      # clothes and body: the redraw's front, projected (pixel-aligned with the mesh)
        try: base = faceproj.project_body(raw, src, raw.replace(".glb", "_body.glb"), os.path.join(d, "texviews"), R.log, agree_check=not mesh_mode(R))
        except Exception as e: R.log(f"[texture] body projection skipped ({type(e).__name__}: {str(e)[:120]})")
    out = raw.replace(".glb", "_faceproj.glb")
    before = after = None
    if face_on(R):
        glb, before, after = face_fit(R, base, src, out, os.path.join(d, "faceproj"), R.log, style=prompts.style_text(R.state["vlm"]["plan"], R.state.get("look", "asis")),
                                          method="landmarks" if texture_simple(R) else C.FACE_FIT, face_desc=str(R.state["vlm"]["plan"].get("face", "")))
    else:      # a helmet or mask: no face to fit, the body projection covers the head too
        R.log("[texture] no visible face: face fit skipped")
        shutil.copy(base, out); bp = base[:-4] + "_basecolor.png"
        if os.path.exists(bp): shutil.copy(bp, out[:-4] + "_basecolor.png")
    if C.TEXTURE_VIEWS and not texture_simple(R):      # turn the model; the image model cleans each view; project back where that view sees best
        try:
            desc = "; ".join(str(plan.get(k)) for k in ("hair", "clothing", "footwear", "accessories") if plan.get(k) and plan.get(k) != "none")[:500]
            mv = faceproj.multiview(out, src, raw.replace(".glb", "_textured.glb"), os.path.join(d, "texviews"), R.log, style=sty, desc=desc, paint_grey=mesh_mode(R))
            if mv:
                # the extra views may have repainted the edges of the fitted face: fit the face once more so it has the final say
                try:
                    if not face_on(R): raise RuntimeError("no visible face")
                    out2, before, after = face_fit(R, mv, src, raw.replace(".glb", "_final_tex.glb"), os.path.join(d, "faceproj2"), R.log, style=sty,
                                                       method=C.FACE_FIT, face_desc=str(plan.get("face", "")))
                    mv = out2
                except Exception as e: R.log(f"[texture] final face pass skipped ({type(e).__name__}: {str(e)[:100]})")
                out = mv; vd = os.path.join(d, "texviews")
                shots = [os.path.join(vd, f) for f in sorted(os.listdir(vd)) if f.endswith("_fixed.png")]
                if shots: progress.snap(R, "texture", "texture cleaned from more angles (head sides, body sides, back)", shots, [os.path.basename(x)[:-10] for x in shots])
        except Exception as e: R.log(f"[texture] extra views skipped ({type(e).__name__}: {str(e)[:120]})")
    # last step: the finished texture goes onto the rig and onto every animation clip (same UVs: the rig was built from this mesh)
    R.A["textured_glb"] = out; png = out[:-4] + "_basecolor.png"
    if R.A.get("rig_fbx") and os.path.exists(R.A["rig_fbx"]):
        final = os.path.join(str(R.dir / "07_rig"), f"{R.state['name']}_final.fbx")
        r_ = subprocess.run([C.BLENDER, "-b", "--python", str(C.ROOT / "homunculus" / "tex_swap.py"), "--", R.A["rig_fbx"], png, final], capture_output=True, text=True)
        if not os.path.exists(final): raise RuntimeError("texture swap failed: " + (r_.stdout + r_.stderr)[-600:])
        R.A["final_fbx"] = final; R.A["final_glb"] = final[:-4] + ".glb"
    try:
        from .stages import animate
        n = animate.retexture(R, png)
        if n: R.log(f"[texture] final texture put on {n} animation clip(s)")
    except Exception as e: R.log(f"[texture] clips not re-textured ({type(e).__name__}: {str(e)[:120]})")
    os.makedirs(os.path.join(d, "faceproj"), exist_ok=True)      # absent when there is no visible face (the face fit never ran)
    ref = os.path.join(d, "faceproj", "reference_face.png"); im = Image.open(src).convert("RGB"); W, H = im.size
    im.crop((W // 2 - H // 12, int(H * 0.06), W // 2 + H // 12, int(H * 0.06) + H // 6)).save(ref)
    views = blender.mesh_views(out, os.path.join(d, "final_views"), tag="final"); R.A["final_views"] = views
    progress.snap(R, "texture", "final texture: body front from the redraw, fitted face, cleaned side and back views" if (C.TEXTURE_VIEWS and not texture_simple(R)) else "final texture: the picture projected, face fitted (no extra generated images)", ([before, after] if before else []) + [ref, views["front"], views["side"]],
                  (["Pixal3D face", "after projection"] if before else []) + ["redraw", "final front", "final side"])
    return os.path.basename(out)

def st_animate(R):
    """Text-to-animation (UniMate) on the rigged model: the prompts typed on the website (one clip per prompt and repetition)."""
    ps = [p for p in (R.state.get("anim_prompts") or []) if str(p).strip()]
    if not ps: return "no animation prompts (add some on the run page: Animate tab)"
    from .stages import animate
    clips = animate.generate(R, ps, reps=int(R.state.get("anim_reps", 2)))
    thumbs = [c["thumb"] for c in clips if c.get("thumb")][:8]
    progress.snap(R, "animate", f"{len(clips)} animation clip(s) generated", thumbs, [c["prompt"][:40] for c in clips if c.get("thumb")][:8])
    return f"{len(clips)} clip(s) for {len(ps)} prompt(s)"

def hand_gate(R):
    """After the 3D mesh is final: do the hands look broken? Cut-off or torn fingers leave open edges (blender_handcheck.py, CPU). --auto-repair alert (default): warn and point to the
    Repair tab; auto: run the repair here, before rigging, with the GPU the run already holds, and continue with the repaired mesh; off: skip. Returns a note for the stage."""
    mode = R.state.get("auto_repair", C.AUTO_REPAIR)
    if mode == "off" or mesh_mode(R) or not R.A.get("mesh_glb"): return ""
    try:
        out = R.p("05_mesh", "hand_check.json")
        subprocess.run([C.BLENDER, "-b", "--python", str(C.ROOT / "homunculus" / "blender_handcheck.py"), "--", R.A["mesh_glb"], out], capture_output=True, text=True, timeout=300)
        res = json.load(open(out)); R.state["hand_check"] = res; R.save()
    except Exception as e:
        R.log(f"[hands] check skipped ({type(e).__name__}: {str(e)[:80]})"); return ""
    bad = [s for s in ("left", "right") if (res.get(s) or {}).get("broken")]
    if not bad: R.log("[hands] the hands look intact"); return ""
    why = " and ".join(f"{s} ({res[s]['open_per_1000']} open edges per 1000 vertices)" for s in bad)
    if mode != "auto":
        msg = f"the {why} hand look broken (torn or cut-off fingers): repair them in the Repair tab before or after rigging"
        R.log("[hands] " + msg); R.state["alert"] = {"msg": msg, "time": time.strftime("%H:%M:%S")}; R.save(); notify.send(f"homunculus · {R.state['name']}: hands look broken", msg)
        return " - the hands look broken (see the Repair tab)"
    R.log(f"[hands] the {why} hand look broken: repairing them now")
    try:
        from . import repair
        job = "auto_" + time.strftime("%H%M%S"); jd = R.dir / "10_repair" / job; jd.mkdir(parents=True, exist_ok=True)
        rc, lines, _ = repair._bl(["hands", R.A["mesh_glb"], jd / "hands.json"]); strokes = json.load(open(jd / "hands.json"))["strokes"]
        xs = [s_[0] for s_ in strokes]; mid = (min(xs) + max(xs)) / 2
        strokes = [s_ for s_ in strokes if ("left" in bad and s_[0] > mid) or ("right" in bad and s_[0] < mid)]      # only the broken side(s); the character's left is +X
        old = R.A["mesh_glb"]; repair.run_job(R, job, strokes, "")
        tex = jd / "repaired_textured.glb"
        if not tex.exists(): raise RuntimeError("the repair produced no textured mesh")
        new = os.path.join(os.path.dirname(old), "mesh_repaired.glb"); shutil.copy(tex, new)
        R.A["mesh_before_repair"] = R.A.get("mesh_before_repair") or old; R.A["mesh_glb"] = new; R.A["mesh_hi_glb"] = new; R.save()
        R.log("[hands] repaired: the run continues with the repaired mesh"); return " - broken hands repaired automatically"
    except Exception as e:
        msg = f"automatic hand repair failed ({type(e).__name__}: {str(e)[:100]}); continuing with the original mesh: repair it in the Repair tab"
        R.log("[hands] " + msg); R.state["alert"] = {"msg": msg, "time": time.strftime("%H:%M:%S")}; R.save(); return " - hand repair failed"


def wrist_check(R, fbx):
    """Bend each wrist of the rigged model and measure whether the hand stays attached to the forearm (blender_wristcheck.py, CPU). Returns [(side, result)] for the hands that are NOT ok."""
    try:
        out = R.p("08_rig_check", "wrist.json")
        subprocess.run([C.BLENDER, "-b", "--python", str(C.ROOT / "homunculus" / "blender_wristcheck.py"), "--", fbx, out], capture_output=True, text=True, timeout=300)
        res = json.load(open(out)); R.state["wrist_check"] = res; R.save()
        bad = [(side, r) for side, r in res.items() if isinstance(r, dict) and not r.get("ok", True)]
        for side, r in res.items():
            if isinstance(r, dict): R.log(f"[wrist] {side} hand: " + ("one mesh with the forearm" if not r.get("separate") else f"separate piece, gap {r['gap_rest_cm']} cm at rest / {r['gap_bent_cm']} cm bent") + (" - DETACHED" if not r.get("ok", True) else " - ok"))
        return bad
    except Exception as e:
        R.log(f"[wrist] check skipped ({type(e).__name__}: {str(e)[:80]})"); return []


def rig_once(R, variant, extra):
    t0 = time.time()
    with gpu.watchdog(R.log) as wd:
        fbx = rig.run(R.A.get("colored_glb") or R.A["mesh_glb"], str(R.dir / "07_rig"), R.state["name"], R.log, extra)
    R.A["rig_fbx"] = fbx; g = fbx.replace(".fbx", ".glb"); R.A["rig_glb"] = g if os.path.exists(g) else None
    R.A["final_fbx"] = fbx; R.A["final_glb"] = R.A["rig_glb"]      # coloured rig for now; the texture stage replaces these with the finished texture
    R.A.pop("anim_asset", None)                                  # a new rig needs a new animation asset
    R.log(f"rig ({variant}) built in {time.time()-t0:.0f}s, peak {wd['peak']:.1f} GB")
    views = blender.pose_views(fbx, str(R.dir / "08_rig_check" / variant)); R.A["pose_views"] = views
    keys = ("rest_front", "walk_front", "walk_34", "wave_front") + (("wave_hand", "fist_Left_a", "fist_Right_a") if C.HAND_VIEWS else ())
    open_review(R, "rig_check", f"rig ({variant}) test poses", [views[k] for k in keys], RIG_CAPS[:len(keys)])
    v = {"pass": True, "score": 0, "tally": "your call", "problems": [], "votes": {}} if manual(R) else vlm.majority_pass(vlm.panel(fp(R, prompts.RIG_CHECK if C.HAND_VIEWS else prompts.RIG_CHECK_NOHANDS), [views[k] for k in keys], required=("pass",), log=R.log, cancel=decided(R), human_notes=R.state.get("human_notes", "")), R.log)
    R.state["vlm"][f"rig_check_{variant}"] = v; R.save()
    for side, r_ in wrist_check(R, fbx): v.setdefault("problems", []).append(f"the {side} hand is detached from the forearm (gap {r_['gap_bent_cm']} cm when the wrist bends): repair it in the Repair tab")
    R.state["needs_repair"] = [side for side in ("left", "right") if side in (R.state.get("wrist_check") or {}) and not R.state["wrist_check"][side].get("ok", True)]; R.save()
    progress.snap(R, "rig_check", f"rig ({variant}) test poses: your call" if manual(R) else
                  f"rig ({variant}): judges {v['tally']} -> {'PASS' if v.get('pass') else 'FAIL'} (mean {v.get('score')}/10) - test poses, not the final pose",
                  [views[k] for k in keys], RIG_CAPS[:len(keys)],
                  text="; ".join(v.get("problems") or []) or "no problems reported")
    rec = human_gate(R, "rig_check", f"rig ({variant}) test poses", [views[k] for k in keys], RIG_CAPS[:len(keys)],
                     f"{'PASS' if v.get('pass') else 'FAIL'} ({v['tally']}, mean {v.get('score')}/10). " + "; ".join(v.get("problems") or [])[:400])
    if rec["action"] == "accept": v["pass"] = True; v["human"] = "accepted"
    elif rec["action"] == "reject": v["pass"] = False; v["human"] = "rejected"
    R.state["vlm"][f"rig_check_{variant}"] = v; R.save()
    return bool(v.get("pass")), v

def st_rig_ladder(R):
    """1) MIA default  2) MIA with its normal-aware weight model  3) redraw with relaxed hands (closer to the rigger's
    training data) -> mesh -> rig  4) next-best redraw -> mesh -> rig.  Stops at the first rig the VLM passes."""
    tried = R.state.setdefault("rig_tried", [])
    def attempt(variant, extra):
        tried.append(variant); R.save(); return rig_once(R, variant, extra)
    first = C.RIGGERS.get(R.state.get("rigger", C.DEFAULT_RIGGER), C.RIGGERS[C.DEFAULT_RIGGER])[1]
    order = sorted((("default", []), ("normal_weights", ["--normal"])), key=lambda x: x[0] != first)       # the rigger you picked goes first
    for variant, extra in order:
        if variant in tried: continue
        ok, v = attempt(variant, extra)
        if ok: return f"{variant}: pass ({v.get('score')}/10)"
    if mesh_mode(R): return "no rig passed the check (your own model: no redraw fallback; flagged for review)"
    if "relaxed_hands" not in tried:
        R.log("rig failed twice; redrawing with relaxed hands")
        R.state.update(hands="relaxed", edit_round=0, fix_notes="", edit_round_limit=2, edit_gen=R.state.get("edit_gen", 0) + 1); R.save()
        R.A.pop("colored_glb", None); st_edit_and_pick(R); st_upscale_edit(R); st_mesh_and_check(R); st_color(R)
        for variant, extra in (("relaxed_hands", []), ("relaxed_hands_normal", ["--normal"])):
            ok, v = attempt(variant, extra)
            if ok: return f"{variant}: pass ({v.get('score')}/10)"
    nxt = (R.state.get("ranked_edits") or [None, None])[1:2]
    if nxt and nxt[0] and "next_best" not in tried:
        R.log("trying the next-best redraw"); R.A["chosen_edit"] = nxt[0]; R.A.pop("colored_glb", None); st_upscale_edit(R); st_mesh_and_check(R); st_color(R)
        ok, v = attempt("next_best", [])
        if ok: return f"next-best redraw: pass ({v.get('score')}/10)"
    return "no rig passed the VLM check (flagged for review)"

def st_report(R):
    p = report.write(str(R.dir), R.state); R.A["report"] = p
    progress.snap(R, "report", "finished - contact sheet", [str(R.dir / "contact_sheet.png")], cell=900)
    return p

RUNNERS = {"ingest": st_ingest, "upscale": st_upscale, "plan": st_plan, "edit": st_edit_and_pick, "pick": None, "upscale_edit": st_upscale_edit,
           "mesh": st_mesh_and_check, "mesh_check": None, "color": st_color, "rig": st_rig_ladder, "rig_check": None, "animate": st_animate,
           "texture": st_texture, "report": st_report}

def main():
    ap = argparse.ArgumentParser(); ap.add_argument("image"); ap.add_argument("--name", required=True)
    ap.add_argument("--from", dest="frm", choices=STAGES); ap.add_argument("--only", choices=STAGES); ap.add_argument("--style", choices=list(C.UPSCALERS))
    ap.add_argument("--no-open", action="store_true", help="don't open the live progress page in the browser")
    ap.add_argument("--review", choices=["off", "override", "manual"], default=None,
                    help="human review after every judge decision (pick, 3D shape, rig): override = judges decide, you can override on the page "
                         "within --review-grace s (default); manual = the run waits for you; off = fully automatic")
    ap.add_argument("--look", choices=["choose", "asis", *prompts.LOOK], help="choose (default for new runs): one redraw per look and you pick; asis: keep the input's style; or one of " + ", ".join(prompts.LOOK))
    ap.add_argument("--direct", action="store_true", help="skip the redraw: the picture is already a clean full-body reference (T/A-pose, plain background)")
    ap.add_argument("--rigger", choices=list(C.RIGGERS), help="auto-rigger: " + ", ".join(f"{k} ({v[0]})" for k, v in C.RIGGERS.items()) + f" (default {C.DEFAULT_RIGGER})")
    ap.add_argument("--anim", action="append", metavar="PROMPT", help="animation prompt for the Animate stage (repeat for several), e.g. --anim 'walks forward'")
    ap.add_argument("--anim-reps", type=int, default=None, help="clips per prompt (default 2)")
    ap.add_argument("--zip", action="store_true", help="also write exports/mixamo_<name>.zip (OBJ+MTL+texture) for uploading to Mixamo")
    ap.add_argument("--review-grace", type=int, default=None, help="seconds to respond in override mode (default 60)")
    ap.add_argument("--texture", choices=["simple", "full"], help="simple (default): texture from the upscaled picture / chosen redraw only; full: also the face close-up redraw and Qwen-cleaned side/back views")
    ap.add_argument("--face-source", dest="face_source", choices=["original", "redraw"], help="original (default): fit the face texture from your own picture, upscaled (falls back to the redraw if its landmarks cannot be matched); redraw: from the redrawn picture")
    ap.add_argument("--auto-repair", dest="auto_repair", choices=["alert", "auto", "off"], help="broken hands (torn or cut-off fingers) in the finished 3D model: alert (default) warns and points to the Repair tab; auto repairs them before rigging; off")
    ap.add_argument("--face", choices=["auto", "on", "off"], help="auto (default): the planner decides whether a full-face helmet or mask hides the face; off: no face work at all (no face close-up, reshape or fit); on: always work on the face")
    ap.add_argument("--face-redraw", dest="face_redraw", choices=["on", "off"], help="on (default): redraw the face as a full-resolution close-up before the 3D step (a sharper face in the mesh and texture); off: use the full-body redraw as it is")
    ap.add_argument("--outfit", choices=["keep", "shirtless", "nude"], help="keep: outfit from the image (default); shirtless: bare torso and arms (avoids sleeve/cuff layers at the wrists); nude: unclothed, anatomy preserved")
    a = ap.parse_args()
    # one run at a time: runs share the GPU, ComfyUI and Studio, and each frees the GPU between stages
    import fcntl
    os.makedirs(C.RUNS, exist_ok=True); lockf = open(C.RUNS / ".homunculus.lock", "a+")
    try: fcntl.flock(lockf, fcntl.LOCK_EX | fcntl.LOCK_NB)
    except BlockingIOError:
        lockf.seek(0); holder = lockf.read().strip() or "another run"
        print(f"waiting: {holder} is using the GPU pipeline; this run starts automatically when it finishes (Ctrl+C to cancel)", flush=True)
        fcntl.flock(lockf, fcntl.LOCK_EX)
    lockf.seek(0); lockf.truncate(); lockf.write(f"homunculus run '{a.name}' (pid {os.getpid()})"); lockf.flush()
    R = Run(os.path.abspath(a.image), a.name, a.style)
    if a.outfit: R.state["outfit"] = a.outfit; R.save()
    if a.face: R.state["face"] = a.face; R.save()
    if a.auto_repair: R.state["auto_repair"] = a.auto_repair; R.save()
    if a.face_source: R.state["face_source"] = a.face_source; R.save()
    if a.texture: R.state["texture_mode"] = a.texture; R.save()
    if a.face_redraw: R.state["face_redraw"] = a.face_redraw == "on"; R.save()
    if a.review: R.state["review_mode"] = a.review
    if a.review_grace is not None: R.state["review_grace"] = a.review_grace
    R.state["zip"] = bool(a.zip)
    if a.rigger: R.state["rigger"] = a.rigger
    if a.anim is not None: R.state["anim_prompts"] = [p.strip() for p in a.anim if p.strip()]
    if a.anim_reps: R.state["anim_reps"] = a.anim_reps
    if a.direct: R.state["direct"] = True; R.state["look"] = "asis"
    if os.path.splitext(a.image)[1].lower() in MESH_EXT: R.state["mode"] = "mesh"; R.state["outfit"] = "keep"
    if a.look: R.state["look"] = a.look
    elif "look" not in R.state and not R.done("edit"): R.state["look"] = "choose"
    R.save(); server.ensure_service()
    todo = [a.only] if a.only else STAGES[STAGES.index(a.frm):] if a.frm else STAGES
    if a.frm or a.only:
        for s in todo: R.state["stages"].pop(s, None)
        if any(s in todo for s in ("edit", "pick")):
            R.state.update(edit_round=0, fix_notes="", hands=C.DEFAULT_POSE, edit_gen=R.state.get("edit_gen", 0) + 1); R.state.pop("edit_round_limit", None); R.A["edit_candidates"] = []
        if any(s in todo for s in ("mesh", "mesh_check")): R.state["mesh_tries"] = 0
        if any(s in todo for s in ("rig", "rig_check")): R.state["rig_tried"] = []; R.A.pop("anim_asset", None)
        if any(s in todo for s in ("mesh", "color")): R.A.pop("colored_glb", None)
        if any(s in todo for s in ("mesh", "texture")): R.A.pop("textured_glb", None)
    progress.write_html(R)
    if not a.no_open and (os.environ.get("DISPLAY") or os.environ.get("WAYLAND_DISPLAY")):
        subprocess.Popen(["xdg-open", server.url(a.name)], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    R.state["t_start"] = time.time(); R.state.pop("t_total", None); R.state.pop("alert", None); R.save(); notify.CURRENT["R"] = R
    R.log(f"=== homunculus {a.name}: stages {todo}  (live progress: {server.url(a.name)})")
    t_all = time.time()
    for s in todo:
        fn = RUNNERS[s]
        if fn is None or R.done(s): continue
        R.log(f"--- stage {s}"); R.mark(s, "running")
        t0 = time.time()
        try:
            note = fn(R)
        except Exception as e:
            R.mark(s, "failed", note=f"{type(e).__name__}: {e}"); R.log(traceback.format_exc()); notify.stopped(R, s, e)
            progress.snap(R, s, "FAILED", text=traceback.format_exc()[-1500:]); gpu.free_all(R.log); sys.exit(1)
        R.mark(s, "done", seconds=round(time.time() - t0), note=note)
        for twin, src in (("pick", "edit"), ("mesh_check", "mesh"), ("rig_check", "rig")):
            if s == src: R.mark(twin, "done", note=note)
        R.log(f"--- {s} done in {time.time()-t0:.0f}s: {note}")
    gpu.free_all(R.log)
    R.state["t_total"] = time.time() - R.state.get("t_start", time.time()); R.save()
    if a.zip:
        from . import export_zip
        try: R.A["mixamo_zip"] = export_zip.make(R.dir, R.state["name"], R.A["mesh_glb"], R.log); R.save()
        except Exception as e: R.log(f"zip export failed: {e}")
    progress.write_html(R, final=True)
    R.log(f"=== finished in {time.time()-t_all:.0f}s; report: {R.A.get('report')}")
    notify.send(f"homunculus · {R.state['name']} finished", f"Done in {time.time()-t_all:.0f}s. Open {server.url(R.state['name'])}")

if __name__ == "__main__":
    main()
