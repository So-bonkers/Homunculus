"""Zip a run's textured mesh for Mixamo (OBJ + MTL + texture).   python -m homunculus.export_zip <run-name>   or   --zip on the orchestrator."""
import os, sys, shutil, subprocess, zipfile
from . import config as C

def make(run_dir, name, mesh_glb, log=print):
    exp = C.ROOT / "exports"; work = exp / f"mixamo_{name}"; zpath = exp / f"mixamo_{name}.zip"
    shutil.rmtree(work, ignore_errors=True)
    glb = next((g for g in (mesh_glb.replace(".glb", "_final_tex.glb"), mesh_glb.replace(".glb", "_textured.glb"), mesh_glb.replace(".glb", "_faceproj.glb"))
                if os.path.exists(g)), mesh_glb)
    r = subprocess.run([C.BLENDER, "-b", "--python", str(C.ROOT / "homunculus" / "blender_obj_export.py"), "--", glb, str(work)], capture_output=True, text=True)
    if not (work / "character.obj").exists(): raise RuntimeError("OBJ export failed: " + (r.stdout + r.stderr)[-500:])
    with zipfile.ZipFile(zpath, "w", zipfile.ZIP_DEFLATED) as z:
        for f in ("character.obj", "character.mtl", "Image_0.png"): z.write(work / f, f)
    log(f"Mixamo zip: {zpath} ({zpath.stat().st_size/1e6:.0f} MB, from {os.path.basename(glb)}) - upload it at mixamo.com")
    return str(zpath)

if __name__ == "__main__":
    import json
    run = sys.argv[1]; S = json.load(open(C.RUNS / run / "state.json"))
    print(make(C.RUNS / run, run, S["artifacts"]["mesh_glb"]))
