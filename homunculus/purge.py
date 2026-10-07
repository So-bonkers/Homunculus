"""Delete a run and every file that belongs to it: the run folder, the uploaded input, the Mixamo export and the Pixal3D outputs ComfyUI kept for it.
Refuses while anything of the run is running. Files are matched by exact names (never by a bare prefix), and a file another run also claims is left alone."""
import json, os, re, shutil, subprocess
from pathlib import Path
from . import config as C

PKG = __package__.split(".")[0]                       # ComfyUI output files carry the package name: <pkg>_<run>_<try>...
UNITS = ("run", "repair", "retex", "anim", "looks")


def _size(p):
    p = Path(p)
    if p.is_symlink() or not p.exists(): return 0
    if p.is_file(): return p.stat().st_size
    return sum(f.stat().st_size for f in p.rglob("*") if f.is_file() and not f.is_symlink())


def busy(name):
    """What is still running for this run (empty list = safe to delete)."""
    out = []
    for u in UNITS:
        if subprocess.run(["systemctl", "--user", "is-active", "--quiet", f"{PKG}-{u}-{name}.service"]).returncode == 0: out.append(u)
    try:
        for pid in os.listdir("/proc"):
            if not pid.isdigit(): continue
            try: cmd = open(f"/proc/{pid}/cmdline", "rb").read().decode(errors="ignore").split("\0")
            except Exception: continue
            if any(c.endswith(f"{PKG}.orchestrate") for c in cmd) and "--name" in cmd and cmd[cmd.index("--name") + 1] == name and "run" not in out: out.append("run")
    except Exception: pass
    return out


def _comfy_re(name):
    n = re.escape(name)
    return re.compile(rf"^{PKG}_(?:{n}_\d+(?:_shape|_hi)?|repair_{n}_[A-Za-z0-9]+_\d+(?:_hi)?)_\d+_\.(?:glb|png)$")


def plan(name):
    if not re.fullmatch(r"[A-Za-z0-9_-]{1,40}", name or ""): raise ValueError("bad run name")
    rd = C.RUNS / name
    if not (rd / "state.json").exists() or rd.is_symlink(): raise ValueError("no such run")
    S = json.load(open(rd / "state.json")); items = [{"label": "Run folder (every stage, snapshots, clips, repairs, log)", "paths": [rd]}]
    others = [d for d in os.listdir(C.RUNS) if d != name and (C.RUNS / d / "state.json").exists() and not d.startswith((".", "_"))]
    inp = S.get("input")
    if inp and os.path.exists(inp) and Path(inp).resolve().parent == (C.ROOT / "uploads").resolve():
        shared = False
        for o in others:
            try:
                if json.load(open(C.RUNS / o / "state.json")).get("input") == inp: shared = True; break
            except Exception: pass
        if not shared: items.append({"label": "Uploaded input", "paths": [Path(inp)]})
    ex = [p for p in (C.ROOT / "exports" / f"mixamo_{name}", C.ROOT / "exports" / f"mixamo_{name}.zip") if p.exists()]
    if ex: items.append({"label": "Mixamo export", "paths": ex})
    out = C.COMFY_UI / "output" / "3d"
    if out.is_dir():
        mine = _comfy_re(name); rivals = [_comfy_re(o) for o in others]
        fs = [out / f for f in os.listdir(out) if mine.match(f) and not any(r.match(f) for r in rivals)]
        if fs: items.append({"label": f"Pixal3D files kept by ComfyUI ({len(fs)})", "paths": fs})
    for it in items: it["bytes"] = sum(_size(p) for p in it["paths"])
    return {"run": name, "items": items, "total": sum(i["bytes"] for i in items), "busy": busy(name)}


def delete(name):
    P = plan(name)
    if P["busy"]: raise RuntimeError("still running: " + ", ".join(P["busy"]) + ". Stop it first.")
    root = C.RUNS.resolve()
    for it in P["items"]:
        for p in it["paths"]:
            if p.is_symlink(): p.unlink(); continue
            if p == C.RUNS / name:
                if p.resolve().parent != root: raise RuntimeError("refusing to delete outside the runs folder")
                shutil.rmtree(p)
            elif p.is_dir(): shutil.rmtree(p)
            elif p.exists(): p.unlink()
    for u in UNITS: subprocess.run(["systemctl", "--user", "reset-failed", f"{PKG}-{u}-{name}.service"], capture_output=True)
    return P["total"]
