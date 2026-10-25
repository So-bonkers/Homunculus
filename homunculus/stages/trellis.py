"""TRELLIS.2 as the 3D shape generator (alternative to Pixal3D in stages/comfy.py, same call shapes): shape() for the shape-only candidates, mesh() for the textured mesh.
TRELLIS.2 runs from its own ROCm venv (see tools/trellis2/README.md; default C.TRELLIS_DIR = ~/trellis2_test) in a memory-capped systemd user unit (it needs ~30 GB of RAM while exporting).
It takes ONE picture: a turnaround sheet's front view is used (it does not take several views). The picture's background is cut out first (rembg birefnet). Output GLBs are in glTF's frame like Pixal3D's."""
import os, json, shutil, subprocess, time
from .. import config as C, gpu

def _rgba(src, out_png):
    from PIL import Image
    from rembg import remove, new_session
    im = Image.open(src)
    if im.mode == "RGBA" and min(im.getchannel("A").getextrema()) < 255: im.save(out_png); return out_png
    remove(im.convert("RGB"), session=new_session("birefnet-general")).save(out_png); return out_png

def _run(img, out_dir, seed, log, texture=True, timeout=3000):
    gpu.free_all(log); gpu.wait_for_headroom("trellis", log)
    img, out_dir = os.path.abspath(img), os.path.abspath(out_dir); td = str(C.TRELLIS_DIR); unit = f"homunculus-trellis-{os.getpid()}-{int(time.time())}"
    cmd = ["systemd-run", "--user", "--quiet", "--wait", "--collect", f"--unit={unit}", "-p", f"MemoryMax={C.TRELLIS_MEM}", f"--working-directory={td}",
           f"{td}/venv/bin/python", "run_trellis.py", img, out_dir, "--seed", str(seed), "--type", C.TRELLIS_TYPE, "--texture", str(C.TRELLIS_TEX)] + ([] if texture else ["--no-glb"])
    t0 = time.time(); r = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout)
    if r.returncode != 0 or not os.path.exists(os.path.join(out_dir, "raw_shape.glb")): raise RuntimeError(f"TRELLIS.2 failed (exit {r.returncode}): {r.stderr[-400:]}")
    log(f"TRELLIS.2 seed {seed} in {time.time() - t0:.0f}s -> {out_dir}"); return out_dir

def _to_gltf(raw, out):
    """raw_shape.glb is in TRELLIS's own frame (z up, faces -y): turn it into glTF's (y up, faces +z). Runs in TRELLIS's venv (the pipeline's has no trimesh)."""
    code = "import sys, trimesh, numpy as np; m = trimesh.load(sys.argv[1], force='mesh', process=False); v = m.vertices.copy(); m.vertices = np.stack([v[:, 0], v[:, 2], -v[:, 1]], 1); m.export(sys.argv[2])"
    subprocess.run([f"{C.TRELLIS_DIR}/venv/bin/python", "-c", code, raw, out], check=True, capture_output=True); return out

def _front(src, views):
    return views[0] if views else src          # a sheet's views: front first

def shape(src, out_dir, tag, seed, log, views=None):
    os.makedirs(out_dir, exist_ok=True); img = _rgba(_front(src, views), os.path.join(out_dir, "input_rgba.png"))
    _run(img, out_dir, seed, log, texture=False); return _to_gltf(os.path.join(out_dir, "raw_shape.glb"), os.path.join(out_dir, "shape.glb"))

def mesh(src, out_dir, tag, seed, log, views=None, **kw):
    os.makedirs(out_dir, exist_ok=True); img = _rgba(_front(src, views), os.path.join(out_dir, "input_rgba.png"))
    _run(img, out_dir, seed, log, texture=True); glb = os.path.join(out_dir, "mesh.glb"); shutil.copy(os.path.join(out_dir, "textured.glb"), glb); return glb
