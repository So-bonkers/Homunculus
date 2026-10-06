"""JSON views of the runs for the web app (homunculus/static/app.html). Read-only; the orchestrator owns state.json."""
import json, os, time
from . import config as C

STAGES = ["ingest", "upscale", "plan", "edit", "pick", "upscale_edit", "mesh", "mesh_check", "color", "rig", "rig_check", "animate", "texture", "report"]
LABEL = {"ingest": "Ingest", "upscale": "Upscale", "plan": "Plan", "edit": "Redraw", "pick": "Pick", "upscale_edit": "Prepare",
         "mesh": "3D shape", "mesh_check": "Shape check", "color": "Colour", "rig": "Auto-rig", "rig_check": "Rig check", "animate": "Animate",
         "texture": "Texture", "report": "Report"}
MODEL = {"upscale": "RealESRGAN · ComfyUI", "plan": "Qwen3.8 27B vision", "edit": "Qwen-Image 2.1 edit", "pick": "3-judge VLM panel",
         "upscale_edit": "RealESRGAN · clean-up", "mesh": "Pixal3D · best of 3", "mesh_check": "judges + digit gate", "color": "quick colours · CPU",
         "rig": "Make-It-Animatable", "rig_check": "pose suite + judges", "animate": "UniMate text-to-motion", "texture": "face fit + extra views · Blender",
         "report": "contact sheet", "ingest": "input"}
# mesh-first runs (an STL/OBJ/... as input): same stages, different work
MESH_LABEL = {"ingest": "Prepare mesh", "upscale": "Upscale", "plan": "Orient + plan", "edit": "Paint", "pick": "Pick painting",
              "upscale_edit": "Prepare", "mesh": "Your mesh", "mesh_check": "Shape check"}
MESH_MODEL = {"ingest": "weld · base · decimate · UVs", "upscale": "not needed (no picture)", "plan": "Qwen3.8: front + colours",
              "edit": "Qwen-Image paints the grey render", "pick": "outline check · you / judges", "upscale_edit": "RealESRGAN · face close-up",
              "mesh": "kept as is (no Pixal3D)", "mesh_check": "not needed (your geometry)", "color": "front painting projected"}
MESH_SKIPPED = {"upscale", "mesh_check"}
GLB_KEYS = [("final_glb", "Final"), ("rig_glb", "Rigged"), ("mesh_glb", "Textured mesh")]
FILE_KEYS = [("final_fbx", "Final rig · FBX"), ("final_glb", "Final rig · GLB"), ("rig_fbx", "Rig · FBX"), ("mesh_glb", "Mesh · GLB"), ("report", "Report")]


def _url(run, p):
    """A path from state.json (absolute, or relative to the run folder) as a URL on this server, or None."""
    if not p or not isinstance(p, str): return None
    ap = p if os.path.isabs(p) else str(C.RUNS / run / p)
    if not os.path.exists(ap): return None
    try: rel = os.path.relpath(ap, C.RUNS)
    except ValueError: return None
    if rel.startswith(".."): return None
    return "/" + rel.replace(os.sep, "/")


def _load(run):
    try: return json.load(open(C.RUNS / run / "state.json"))
    except Exception: return None


def _status(S, live):
    st = [v.get("status") for v in S.get("stages", {}).values()]
    if S.get("t_total"): return "finished"
    if live and S.get("awaiting_review"): return "waiting"
    if live: return "running"
    if "failed" in st: return "failed"
    return "stopped"


def _thumb(run, S):
    A = S.get("artifacts", {})
    for k in ("chosen_edit", "edit_upscaled", "upscaled", "input"):
        u = _url(run, A.get(k))
        if u: return u
    return None


def runs(live):
    out = []
    if not C.RUNS.exists(): return out
    for d in os.listdir(C.RUNS):
        if d.startswith((".", "_")) or not (C.RUNS / d / "state.json").exists(): continue
        S = _load(d)
        if not S: continue
        stages = S.get("stages", {}); done = sum(1 for s in STAGES if stages.get(s, {}).get("status") == "done")
        cur = next((s for s in STAGES if stages.get(s, {}).get("status") == "running"), None)
        snaps = S.get("snapshots") or []
        out.append({"name": d, "status": _status(S, d in live), "live": d in live, "thumb": _thumb(d, S), "input": _url(d, S.get("artifacts", {}).get("input")),
                    "file": os.path.basename(S.get("input", "")), "done": done, "total": len(STAGES), "current": LABEL.get(cur, cur) if cur else None,
                    "last": snaps[-1]["title"] if snaps else "", "t_start": S.get("t_start"), "t_total": S.get("t_total"),
                    "updated": os.path.getmtime(C.RUNS / d / "state.json"), "outfit": S.get("outfit", "keep"),
                    "model": next((_url(d, S.get("artifacts", {}).get(k)) for k, _ in GLB_KEYS if _url(d, S.get("artifacts", {}).get(k))), None)})
    out.sort(key=lambda r: -r["updated"])
    return out


def repairs(name):
    """The repair jobs of a run (newest first): the status files written by <pkg>.repair, with their image paths as URLs."""
    out = []; base = C.RUNS / name / "10_repair"
    if base.is_dir():
        for d in sorted(os.listdir(base), reverse=True):
            try: S = json.load(open(base / d / "status.json"))
            except Exception: continue
            u = lambda rel: _url(name, str(C.RUNS / rel)) if rel else None
            regs = [{**{k: v for k, v in r.items() if k not in ("crop", "candidates", "chosen", "after")}, "crop": u(r.get("crop")), "chosen": u(r.get("chosen")), "after": u(r.get("after")),
                     "candidates": [x for x in (u(c) for c in r.get("candidates", [])) if x]} for r in S.get("regions", [])]
            out.append({"job": d, "status": S.get("status"), "step": S.get("step"), "error": S.get("error"), "log": S.get("log", [])[-8:], "notes": S.get("notes", ""),
                        "seconds": S.get("seconds"), "regions": regs, "result": u(S.get("result"))})
    return out


def run(name, live):
    S = _load(name)
    if S is None: return None
    A = S.get("artifacts", {}); stages = S.get("stages", {}); is_live = name in live
    st = []; mesh = S.get("mode") == "mesh"
    for s in STAGES:
        x = stages.get(s, {}); status = x.get("status", "pending")
        if status == "running" and not is_live and not S.get("t_total"): status = "stopped"
        if mesh and s in MESH_SKIPPED: status = "skipped"
        st.append({"key": s, "label": (MESH_LABEL if mesh else LABEL).get(s, LABEL[s]), "model": (MESH_MODEL if mesh else MODEL).get(s, MODEL.get(s, "")),
                   "status": status, "seconds": x.get("seconds"),
                   "note": str(x.get("note", "") or "")[:300], "peak_vram": x.get("peak_vram")})
    rv = S.get("awaiting_review") if is_live else None
    review = None
    if rv:
        review = {"gate": rv.get("gate"), "title": rv.get("title"), "verdict": rv.get("verdict", ""), "manual": bool(rv.get("manual")),
                  "grace": rv.get("grace", 0), "opened": rv.get("opened"), "judge_best": int(rv.get("judge_best") or 0),
                  "choose": bool(rv.get("choose", rv.get("gate") == "pick")), "you_judge": S.get("review_mode") == "manual" or rv.get("title") == "choose a look", "kind": "look" if rv.get("title") == "choose a look" else rv.get("gate"),
                  "images": [_url(name, i) for i in rv.get("images", [])], "captions": rv.get("captions", [])}
    snaps = [{"n": x.get("n"), "time": x.get("time"), "stage": x.get("stage"), "label": LABEL.get(x.get("stage"), x.get("stage")),
              "title": x.get("title", ""), "url": _url(name, x.get("file")), "text": x.get("text", ""),
              "images": [{"url": _url(name, i), "caption": (x.get("captions") or [""] * 99)[k] if k < len(x.get("captions") or []) else ""}
                         for k, i in enumerate(x.get("images") or []) if _url(name, i)]} for x in (S.get("snapshots") or [])]
    files = [{"label": lbl, "url": _url(name, A.get(k)), "name": os.path.basename(A.get(k) or "")} for k, lbl in FILE_KEYS if _url(name, A.get(k))]
    models = [{"key": k, "label": lbl, "url": _url(name, A.get(k))} for k, lbl in GLB_KEYS if _url(name, A.get(k))]
    plan = (S.get("vlm") or {}).get("plan") or {}
    anims = None
    try:
        am = json.load(open(C.RUNS / name / "09_animate" / "animations.json"))
        anims = {"status": am.get("status"), "error": am.get("error"), "clips": [
            {"id": c["id"], "prompt": c.get("prompt", ""), "rep": c.get("rep", 0), "url": _url(name, c.get("textured") or c.get("glb")), "fbx": _url(name, c.get("textured_fbx") or c.get("fbx")),
             "thumb": _url(name, c.get("thumb")), "textured": bool(c.get("textured"))} for c in am.get("clips", []) if _url(name, c.get("textured") or c.get("glb"))]}
    except Exception: pass
    looks = None
    try:
        lm = json.load(open(C.RUNS / name / "looks" / "looks.json"))
        looks = {"status": lm.get("status"), "raw": _url(name, A.get("input")), "asis": _url(name, A.get("chosen_edit")),
                 "items": [{"look": k, "label": v.get("label", k), "url": _url(name, v.get("file")), "time": v.get("time")} for k, v in lm.get("looks", {}).items() if _url(name, v.get("file"))]}
    except Exception: pass
    log = []
    try:
        with open(C.RUNS / name / "run.log", "rb") as f:
            f.seek(0, 2); n = f.tell(); f.seek(max(0, n - 24000)); log = f.read().decode(errors="ignore").splitlines()[-160:]
    except Exception: pass
    return {"name": name, "status": _status(S, is_live), "live": is_live, "file": os.path.basename(S.get("input", "")),
            "input": _url(name, A.get("input")), "thumb": _thumb(name, S), "chosen": _url(name, A.get("chosen_edit")),
            "t_start": S.get("t_start"), "t_total": S.get("t_total"), "now": time.time(),
            "looks": looks, "animations": anims, "mode": S.get("mode", "image"), "options": {"face": S.get("face", "auto"), "face_redraw": S.get("face_redraw", True), "rigger": S.get("rigger", "mia"), "anim_prompts": S.get("anim_prompts", []), "anim_reps": S.get("anim_reps", 2), "direct": bool(S.get("direct")), "look": S.get("look", "asis"), "outfit": S.get("outfit", "keep"), "review": S.get("review_mode", "override"), "grace": S.get("review_grace", 60),
                        "style": S.get("style_override") or S.get("style_guess")},
            "stages": st, "review": review, "snapshots": snaps, "files": files, "models": models,
            "zip": f"/api/zip/{name}.zip" if A.get("mesh_glb") else None,
            "plan": {k: plan.get(k) for k in ("style", "subject", "clothing", "remove") if plan.get(k)},
            "human_reviews": S.get("human_reviews", [])[-10:], "log": log, "forked_from": S.get("forked_from"),
            "zip_on": bool(S.get("zip")), "alert": S.get("alert") if (is_live or "failed" in [x.get("status") for x in stages.values()]) else None, "human_notes": S.get("human_notes", "")}
