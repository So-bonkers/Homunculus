"""charkit core: the per-character state (resumable), the GPU phases (the shared lock runs/.homunculus.lock), the review queue, contact sheets, and the stage runner.

kits/<name>/charkit.json         the state: inputs, the character description, per stage {status, seconds, note, groups...}, every decision, the judge cache
kits/<name>/needs_review.json    what the pipeline could not settle by itself (a list of entries; Claude or the user works through the "open" ones)
kits/<name>/charkit.log          the log
kits/<name>/sheets/*.png         contact sheets (candidates with numbers, judge verdicts and the pick framed in green)
runs/<name>_charkit/             heavy outputs (TRELLIS meshes, placements, the assembled .blend)
(--dry-run: kits/_charkit_test/<name> and runs/_charkit_test/<name>; nothing outside them is written.)"""
import fcntl, json, os, struct, time, traceback
from contextlib import contextmanager
from pathlib import Path
from PIL import Image, ImageDraw
from .. import config as C

KITS = C.ROOT / "kits"

class Kit:
    def __init__(self, picture, name, kit_dir=None, run_dir=None, dry=False):
        self.name, self.dry = name, dry
        self.dir = Path(kit_dir).resolve() if kit_dir else KITS / name              # absolute: units run in other working directories (TRELLIS in ~/trellis2_test)
        self.run = Path(run_dir).resolve() if run_dir else C.RUNS / f"{name}_charkit"
        os.makedirs(self.dir, exist_ok=True); os.makedirs(self.run, exist_ok=True)
        self.sp = self.dir / "charkit.json"; self.rp = self.dir / "needs_review.json"
        self.state = json.load(open(self.sp)) if self.sp.exists() else {"name": name, "input": str(picture), "created": time.strftime("%Y-%m-%d %H:%M:%S"), "stages": {}, "picks": {}, "decisions": [], "vlm": {}}
        self.state["dry_run"] = dry
        self.logf = open(self.dir / "charkit.log", "a"); self.judge = self.jobs = None; self.opts = {}

    def log(self, m):
        line = time.strftime("%H:%M:%S ") + m; print(line, flush=True); self.logf.write(line + "\n"); self.logf.flush()

    def save(self):
        tmp = str(self.sp) + ".tmp"; json.dump(self.state, open(tmp, "w"), indent=1); os.replace(tmp, self.sp)

    def p(self, *a):
        """A path under the kit folder (folders made)."""
        d = self.dir.joinpath(*a[:-1]); os.makedirs(d, exist_ok=True); return str(d / a[-1])

    def r(self, *a):
        """A path under the heavy-output folder (folders made)."""
        d = self.run.joinpath(*a[:-1]); os.makedirs(d, exist_ok=True); return str(d / a[-1])

    @property
    def picks(self): return self.state["picks"]

    def decide(self, stage, item, **kw):
        """Record a decision (every pick, re-roll, fallback and escalation lands here, in order)."""
        d = {"time": time.strftime("%H:%M:%S"), "stage": stage, "item": item, **kw}; self.state["decisions"].append(d); self.save(); return d

    @contextmanager
    def gpu_phase(self, what):
        """Hold the pipeline's GPU lock (the orchestrator, homunculus.kit and tools/redraw_front.py take the same one) for one heavy phase; a dry run never takes it.
        Phases are short and separate (redraws, then judges, then TRELLIS ...) so two jobs never share the 24 GB card and other jobs can slip in between."""
        if self.dry: self.log(f"[dry run] would take the GPU lock for: {what}"); yield; return
        os.makedirs(C.RUNS, exist_ok=True); lf = open(C.RUNS / ".homunculus.lock", "a+")
        try:
            try: fcntl.flock(lf, fcntl.LOCK_EX | fcntl.LOCK_NB)
            except BlockingIOError: self.log(f"waiting for the GPU lock (another job has it) before: {what}"); fcntl.flock(lf, fcntl.LOCK_EX)
            self.log(f"GPU lock taken: {what}"); yield
        finally: lf.close()

    # --- review queue ---------------------------------------------------------------------------------------------------
    def review(self, stage, item, problem, candidates=(), chosen=None, reasons=(), images=()):
        """Append an entry to needs_review.json (an earlier open entry for the same stage and item is replaced: a re-run supersedes it). The run goes on with `chosen`."""
        q = json.load(open(self.rp)) if self.rp.exists() else []
        q = [e for e in q if not (e.get("status") == "open" and e["stage"] == stage and e["item"] == item)]
        e = {"id": f"{stage}:{item}:{int(time.time())}", "time": time.strftime("%Y-%m-%d %H:%M:%S"), "stage": stage, "item": item, "problem": problem, "status": "open",
             "chosen": chosen, "reasons": list(reasons), "candidates": list(candidates), "images": [str(i) for i in images]}
        q.append(e); tmp = str(self.rp) + ".tmp"; json.dump(q, open(tmp, "w"), indent=1); os.replace(tmp, self.rp)
        self.log(f"!! needs review: {stage}/{item}: {problem} (continuing with {os.path.basename(str(chosen)) if chosen else 'nothing'})"); return e

    def supersede(self, stage):
        """A stage that runs again re-decides everything it flagged before: its earlier open entries become 'superseded' (kept for the record)."""
        if not self.rp.exists(): return
        q = json.load(open(self.rp)); n = 0
        for e in q:
            if e.get("status") == "open" and e["stage"] == stage: e["status"] = "superseded"; n += 1
        if n: tmp = str(self.rp) + ".tmp"; json.dump(q, open(tmp, "w"), indent=1); os.replace(tmp, self.rp); self.log(f"{n} earlier review entries of {stage} superseded")

    def open_reviews(self):
        return [e for e in (json.load(open(self.rp)) if self.rp.exists() else []) if e.get("status") == "open"]


def contact_sheet(files, labels, out, pick=None, h=300, bad=()):
    """Candidates side by side at height h with a caption under each; the pick framed green, rejected ones red."""
    ims = []
    for f in files:
        try: im = Image.open(f).convert("RGB")
        except Exception: im = Image.new("RGB", (h * 2 // 3, h), (90, 90, 90))
        ims.append(im.resize((max(1, int(im.width * h / im.height)), h)))
    if not ims: return None
    cap = 46; W = sum(i.width for i in ims) + 6 * (len(ims) + 1); s = Image.new("RGB", (W, h + cap + 12), (245, 245, 245)); d = ImageDraw.Draw(s); x = 6
    for f, im, lab in zip(files, ims, labels):
        s.paste(im, (x, 6)); col = (20, 170, 60) if f == pick else (200, 40, 40) if f in bad else None
        if col: d.rectangle([x - 3, 3, x + im.width + 2, h + 8], outline=col, width=5)
        for k, line in enumerate(str(lab).split("\n")[:3]): d.text((x + 2, h + 10 + 12 * k), line[: max(8, im.width // 6)], fill=(0, 0, 0))
        x += im.width + 6
    os.makedirs(os.path.dirname(out), exist_ok=True); s.save(out); return out


def glb_bounds(path):
    """(min xyz, max xyz) of a GLB's POSITION accessors, read from its JSON chunk (no mesh library needed; node transforms are not applied: TRELLIS.2 exports have none)."""
    with open(path, "rb") as f:
        magic, _, _ = struct.unpack("<4sII", f.read(12)); n, typ = struct.unpack("<II", f.read(8))
        if magic != b"glTF" or typ != 0x4E4F534A: raise ValueError(f"{path}: not a GLB")
        g = json.loads(f.read(n))
    lo, hi = [1e9] * 3, [-1e9] * 3
    for m in g.get("meshes", []):
        for p in m.get("primitives", []):
            a = g["accessors"][p["attributes"]["POSITION"]]; lo = [min(x, y) for x, y in zip(lo, a["min"])]; hi = [max(x, y) for x, y in zip(hi, a["max"])]
    return lo, hi


def run(K, stages, todo, force):
    """Run `todo` (stage names, in order). A stage already done is skipped unless it is in `force` (--from / --only re-run it).
    A stage that raises is marked failed and the run stops (fix and resume with --from); a stage's own problems go to the review queue instead and the run continues."""
    for s in todo:
        st = K.state["stages"].get(s, {})
        if st.get("status") == "done" and s not in force: K.log(f"--- {s}: done before, skipped"); continue
        fn = stages[s]; K.log(f"--- stage {s}"); K.supersede(s); t0 = time.time(); K.state["stages"][s] = {**{k: v for k, v in st.items() if k == "groups"}, "status": "running", "started": time.strftime("%H:%M:%S")}; K.save()
        try:
            note = fn(K)
            K.state["stages"][s].update(status="todo" if note == "TODO" else "done", seconds=round(time.time() - t0), note=note); K.save(); K.log(f"--- {s}: {note}")
        except Exception as e:
            K.state["stages"][s].update(status="failed", error=f"{type(e).__name__}: {str(e)[:400]}"); K.save(); K.log(traceback.format_exc()); return False
    return True
