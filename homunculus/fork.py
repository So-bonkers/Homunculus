"""Fork a stopped run: copy what was done before a stage into a new run (or reuse the same run) and restart from that stage,
with your instructions added to the redraw prompt and the judges' context, and optionally different options."""
import json, os, shutil, time
from . import config as C

STAGES = ["ingest", "upscale", "plan", "edit", "pick", "upscale_edit", "mesh", "mesh_check", "color", "rig", "rig_check", "animate", "texture", "report"]
FORKABLE = ["upscale", "plan", "edit", "upscale_edit", "mesh", "color", "rig", "animate", "texture", "report"]
# which stage first writes each run folder; a fork keeps only the folders of the stages before the fork point
DIR_STAGE = {"00_input": "ingest", "01_upscale": "upscale", "02_plan": "plan", "03_edit": "edit", "04_upscale_edit": "upscale_edit",
             "05_mesh": "mesh", "06_mesh_check": "mesh", "07_rig": "rig", "08_rig_check": "rig", "09_animate": "animate"}   # colour and texture write inside 05_mesh
SNAP_STAGE = {"pick": "edit", "mesh_check": "mesh", "rig_check": "rig"}


def prepare(src, dst, stage, notes):
    """Returns the input image path to launch with. src == dst restarts the run in place."""
    if stage not in FORKABLE: raise ValueError(f"can't restart from '{stage}'")
    cut = STAGES.index(stage)
    sdir, ddir = C.RUNS / src, C.RUNS / dst
    S = json.load(open(sdir / "state.json"))
    if src != dst:
        if ddir.exists(): raise ValueError(f"a run called '{dst}' already exists")
        ddir.mkdir(parents=True)
        for d in os.listdir(sdir):
            p = sdir / d
            if d in DIR_STAGE:
                if STAGES.index(DIR_STAGE[d]) < cut: shutil.copytree(p, ddir / d)
            elif d == "progress": shutil.copytree(p, ddir / d)
        txt = json.dumps(S).replace(f"/runs/{src}/", f"/runs/{dst}/")      # artifacts are absolute paths inside the run folder
        S = json.loads(txt); S["name"] = dst
        S["snapshots"] = [x for x in S.get("snapshots", []) if STAGES.index(SNAP_STAGE.get(x.get("stage"), x.get("stage", "ingest"))) < cut]
        with open(ddir / "run.log", "w") as f:
            f.write(time.strftime("%H:%M:%S ") + f"=== forked from {src} at stage '{stage}'" + (f"; instructions: {notes}" if notes else "") + "\n")
    for k in ("t_total", "awaiting_review", "review_open_t", "_judge_best"): S.pop(k, None)
    S["forked_from"] = {"run": src, "stage": stage, "time": time.strftime("%Y-%m-%d %H:%M:%S"), "notes": notes}
    if notes:      # used by the redraw prompt and shown to every judge from here on
        S["human_notes"] = (S.get("human_notes", "") + " " + notes.strip()).strip()[-1500:]
        S.setdefault("human_reviews", []).append({"gate": f"fork@{stage}", "action": "instructions", "choice": -1, "notes": notes, "time": time.strftime("%H:%M:%S")})
    json.dump(S, open(ddir / "state.json", "w"), indent=1)
    img = S.get("input") or str(next(iter(sorted((ddir / "00_input").glob("input.*"))), ""))
    if not img or not os.path.exists(img):
        cand = sorted((ddir / "00_input").glob("input.*"))
        if not cand: raise ValueError("the original input image is missing")
        img = str(cand[0])
    return img
