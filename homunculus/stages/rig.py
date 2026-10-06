"""Make-It-Animatable auto-rig (52-bone Mixamo skeleton with fingers), run in its own venv."""
import os, shutil, subprocess
from .. import config as C, gpu

def run(glb, out_dir, name, log, extra=()):
    gpu.free_all(log); gpu.wait_for_headroom("mia", log)
    import time; start = time.time()
    env = dict(os.environ, PYTHONPATH=str(C.MIA / "vendor"))
    r = subprocess.run([str(C.MIA_PY), "run_mia.py", str(glb), name, *extra], cwd=C.MIA_REPO, env=env, capture_output=True, text=True, timeout=1800)
    produced = name + ("_n" if "--normal" in extra else "")
    src = C.MIA / "work" / produced
    # MIA can exit non-zero while tearing down bpy even after a good export: trust the output file, not the exit code
    if not (src / f"{produced}.fbx").exists() or (src / f"{produced}.fbx").stat().st_mtime < start:
        raise RuntimeError(f"MIA failed (exit {r.returncode}): {(r.stderr or r.stdout)[-800:]}")
    os.makedirs(out_dir, exist_ok=True)
    fbx = os.path.join(out_dir, f"{name}_rigged.fbx"); shutil.copy(src / f"{produced}.fbx", fbx)
    if (src / f"{produced}.glb").exists(): shutil.copy(src / f"{produced}.glb", os.path.join(out_dir, f"{name}_rigged.glb"))
    log("MIA rig done"); return fbx
