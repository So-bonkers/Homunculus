"""Posed meshes (STL etc. not in a T-pose): rig them with SkinTokens (any pose in, Mixamo-52 skeleton out), rotate the skeleton into a T-pose
from its own bone positions and bake that pose into the mesh (blender_tpose.py). The rest of the pipeline then sees a T-posed model."""
import os, subprocess, time
from .. import config as C, gpu

SK = C.ROOT / "riggers" / "skintokens"; CLI = SK / "build" / "bin" / "skintokens-cli"; MODEL = C.ROOT / "riggers" / "skintokens-gguf" / "F16"


def available():
    return CLI.exists() and (MODEL / "tokenrig.gguf").exists()


def normalize(glb_in, out_dir, log):
    """Returns the path of the T-posed static GLB, or None when it could not be done (the caller keeps the original mesh)."""
    if not available(): log("[tpose] SkinTokens is not installed (riggers/); the mesh is used in its own pose"); return None
    os.makedirs(out_dir, exist_ok=True); rigged = os.path.join(out_dir, "rigged_in_given_pose.glb"); out = os.path.join(out_dir, "model_tpose.glb")
    gpu.free_all(log); gpu.wait_for_headroom("skintokens", log)
    for dev in ([C.TPOSE_DEVICE] + (["cpu"] if C.TPOSE_DEVICE != "cpu" else [])):
        t0 = time.time(); log(f"[tpose] rigging the posed mesh with SkinTokens ({dev})")
        try:
            r = subprocess.run([str(CLI), "rig", str(MODEL), glb_in, rigged, "--device", dev], capture_output=True, text=True, timeout=3600, cwd=str(SK))
        except subprocess.TimeoutExpired: log(f"[tpose] SkinTokens timed out on {dev}"); continue
        if os.path.exists(rigged) and os.path.getmtime(rigged) >= t0: log(f"[tpose] rigged in {time.time() - t0:.0f}s"); break
        log(f"[tpose] SkinTokens failed on {dev}: {(r.stderr or r.stdout)[-300:]}")
    else: return None
    r = subprocess.run([C.BLENDER, "-b", "--python", str(C.ROOT / "homunculus" / "blender_tpose.py"), "--", rigged, out], capture_output=True, text=True, timeout=900)
    log(next((l for l in r.stdout.splitlines() if l.startswith("[tpose]")), "[tpose] done") if os.path.exists(out) else "[tpose] could not pose the skeleton: " + (r.stdout + r.stderr)[-300:])
    return out if os.path.exists(out) else None
