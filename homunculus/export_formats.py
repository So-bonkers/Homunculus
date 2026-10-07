"""Accept a run and export the formats the user wants.   python -m homunculus.export_formats <run> --formats fbx,obj [--cleanup]
The pipeline writes GLB only; once the user is satisfied they accept the run and pick the other formats, which are made here from the GLBs (and shared textures are written once).
exports/<run>/<fmt>/...   fbx (character + every clip), usd (same), obj (static textured mesh), stl (static mesh, no colour).
--cleanup also deletes the heavy intermediates nobody needs for the result (ComfyUI's raw shapes, unused candidate meshes in 05_mesh): forking from an early stage or repairing afterwards is then no longer possible."""
import argparse, json, os, re, subprocess, time
from pathlib import Path
from . import config as C, purge

FORMATS = {"fbx": "FBX: rigged character and every animation clip (Blender, Unity, Unreal, Mixamo)", "usd": "USD: rigged character and every clip",
           "obj": "OBJ: static textured mesh before rigging", "stl": "STL: static mesh without colour (3D printing)"}
STATIC = ("obj", "stl")


def _slug(t): return re.sub(r"[^a-z0-9]+", "_", str(t).lower()).strip("_")[:48] or "clip"


def sources(run):
    """What each format is made from: the rigged character GLB, the clips' GLBs, the static textured mesh GLB."""
    rd = C.RUNS / run; S = json.load(open(rd / "state.json")); A = S.get("artifacts") or {}
    char = next((p for p in (A.get("final_glb"), A.get("rig_glb")) if p and os.path.exists(p)), None)
    mesh = next((p for p in (A.get("textured_glb"), A.get("colored_glb"), A.get("mesh_glb")) if p and os.path.exists(p)), None)
    clips = []
    try:
        for c in json.load(open(rd / "09_animate" / "animations.json")).get("clips", []):
            p = rd / (c.get("textured") or c.get("glb") or "")
            if p.exists(): clips.append((f"{_slug(c.get('prompt', ''))}_take{int(c.get('rep', 0)) + 1}", p))
    except Exception: pass
    return char, mesh, clips


def available(run):
    char, mesh, clips = sources(run)
    return {f: bool(mesh if f in STATIC else char) for f in FORMATS}


def cleanup_plan(run):
    """Heavy files that are not part of the result: ComfyUI's raw Pixal3D outputs for the run and the unused big files under 05_mesh."""
    rd = C.RUNS / run; S = json.load(open(rd / "state.json")); A = S.get("artifacts") or {}; keep = set()
    for v in A.values():
        for x in (v if isinstance(v, list) else [v]):
            if isinstance(x, str) and x.startswith(str(rd)): keep.add(os.path.realpath(x)); keep.add(os.path.realpath(x[:-4] + "_basecolor.png"))
    items = []; mine = []
    out = C.COMFY_UI / "output" / "3d"
    P = purge.plan(run)
    for it in P["items"]:
        if it["label"].startswith("Pixal3D files"): items.append({"label": "ComfyUI's raw Pixal3D outputs for this run", "paths": it["paths"], "bytes": it["bytes"]})
    big = []
    for f in (rd / "05_mesh").rglob("*") if (rd / "05_mesh").is_dir() else []:
        if f.is_file() and f.stat().st_size > 20e6 and os.path.realpath(f) not in keep and not f.name.endswith(("_preview.glb",)): big.append(f)
    if big: items.append({"label": f"Unused candidate and intermediate meshes in 05_mesh ({len(big)})", "paths": big, "bytes": sum(f.stat().st_size for f in big)})
    return {"items": [{"label": i["label"], "bytes": i["bytes"]} for i in items], "total": sum(i["bytes"] for i in items), "_paths": items}


def main():
    ap = argparse.ArgumentParser(); ap.add_argument("run"); ap.add_argument("--formats", default=""); ap.add_argument("--cleanup", action="store_true"); a = ap.parse_args()
    rd = C.RUNS / a.run; st = rd / "export"; st.mkdir(exist_ok=True); sp = st / "status.json"; S = {"status": "running", "log": [], "done": []}
    def save(): json.dump(S, open(sp, "w"), indent=1)
    def log(m): print(m, flush=True); S["log"] = (S["log"] + [m])[-20:]; save()
    save()
    try:
        char, mesh, clips = sources(a.run); fmts = [f for f in a.formats.split(",") if f in FORMATS]
        for f in fmts:
            od = C.ROOT / "exports" / a.run / f; jobs = [(f"{a.run}_final" if char else None, mesh if f in STATIC else char)]
            if f not in STATIC: jobs += [(stem, p) for stem, p in clips]
            if f in STATIC: jobs = [(f"{a.run}_mesh", mesh)]
            for stem, p in jobs:
                if not p or not stem: continue
                log(f"{f.upper()}: {stem}")
                r = subprocess.run([C.BLENDER, "-b", "--python", str(C.ROOT / "homunculus" / "blender_export.py"), "--", str(p), str(od), stem, f], capture_output=True, text=True, timeout=900)
                if not (od / f"{stem}.{f}").exists(): raise RuntimeError(f"{f} export of {stem} failed: " + (r.stdout + r.stderr)[-300:])
            S["done"].append(f); save()
        freed = 0
        if a.cleanup:
            log("freeing disk space (raw shapes and unused candidates)")
            for it in cleanup_plan(a.run)["_paths"]:
                for p in it["paths"]:
                    try: sz = Path(p).stat().st_size; Path(p).unlink(); freed += sz
                    except OSError: pass
        s0 = json.load(open(rd / "state.json")); s0["accepted"] = {"time": time.strftime("%Y-%m-%d %H:%M"), "formats": ["glb"] + S["done"], "freed": freed}; json.dump(s0, open(rd / "state.json", "w"), indent=1)
        S.update(status="done", formats=["glb"] + S["done"], freed=freed); log("done" + (f"; freed {freed / 1e9:.1f} GB" if freed else ""))
    except Exception as e:
        S.update(status="failed", error=f"{type(e).__name__}: {str(e)[:300]}"); save(); raise


if __name__ == "__main__":
    main()
