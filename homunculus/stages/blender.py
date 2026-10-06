"""Headless Blender renders: textured mesh views (comfy/render_glb_tex.py) and rig pose test (mia/pose_test.py)."""
import os, subprocess
from .. import config as C

def _bl(script, *args, timeout=900):
    env = dict(os.environ, **({} if C.HAND_VIEWS else {"HOMUNCULUS_NO_HANDS": "1"}))      # hand renders are skipped unless HAND_VIEWS is on
    r = subprocess.run([C.BLENDER, "-b", "--python", str(script), "--", *map(str, args)], capture_output=True, text=True, timeout=timeout, env=env)
    if r.returncode != 0 or "Traceback" in r.stderr + r.stdout:
        raise RuntimeError(f"Blender failed: {(r.stderr + r.stdout)[-800:]}")
    return r.stdout

def mesh_views(glb, out_dir, tag="mesh", grey=False):
    """front/side/face/hands/feet renders; grey=True shades the bare geometry (no texture) for shape checks."""
    os.makedirs(out_dir, exist_ok=True); _bl(C.COMFY / ("render_glb.py" if grey else "render_glb_tex.py"), glb, out_dir, tag)
    v = {k: os.path.join(out_dir, f"{tag}_{k}.png") for k in ("front", "side", "face", "handR", "handL", "feet")}
    for h in ("handR", "handL"):     # four views per hand (back, palm, front, side), see render_glb*.py
        vf = os.path.join(out_dir, f"{tag}_{h}_views.txt")
        for name in (open(vf).read().split(",") if os.path.exists(vf) else []): v[f"{h}_{name}"] = os.path.join(out_dir, f"{tag}_{h}_{name}.png")
    return v

SUITE = os.path.join(os.path.dirname(os.path.dirname(__file__)), "handfix", "pose_suite.py")
def pose_views(fbx, out_dir, tag="rig"):
    """rest / walk / wave / fist renders (fingers curl toward the palm, computed from each hand's own bones)."""
    os.makedirs(out_dir, exist_ok=True); _bl(SUITE, fbx, out_dir)
    v = {k: os.path.join(out_dir, k + ".png") for k in ("rest_front", "rest_34", "walk_front", "walk_34", "walk_side", "wave_front", "wave_hand",
                                                       "fist_Left_a", "fist_Left_b", "fist_Right_a", "fist_Right_b")}
    return {k: p for k, p in v.items() if os.path.exists(p)}
