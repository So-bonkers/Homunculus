"""ComfyUI jobs: ESRGAN-family upscaling and Pixal3D shape+texture (graph builder reused from comfy/run_px.py)."""
import glob, os, shutil, sys, time, uuid
from PIL import Image
from .. import config as C, gpu
sys.path.insert(0, str(C.COMFY))
import run_px   # build_tex(), run()  (has its own VRAM watchdog: stops ComfyUI above 22.5 GB)

def _to_input(src, tag):
    name = f"homunculus_{tag}_{uuid.uuid4().hex[:6]}.png"
    Image.open(src).convert("RGB").save(C.COMFY_UI / "input" / name); return name

def upscale(src, dst, model, log, long_side=2048):
    gpu.free_all(log, keep="comfy"); gpu.wait_for_headroom("upscale", log); gpu.comfy_start(log)
    W, H = Image.open(src).size
    k = min(4.0, long_side / max(W, H)); w, h = int(round(W * k)), int(round(H * k))
    name = _to_input(src, "up"); prefix = f"homunculus/up_{uuid.uuid4().hex[:6]}"
    g = {"1": {"class_type": "LoadImage", "inputs": {"image": name}},
         "2": {"class_type": "UpscaleModelLoader", "inputs": {"model_name": model}},
         "3": {"class_type": "ImageUpscaleWithModel", "inputs": {"upscale_model": ["2", 0], "image": ["1", 0]}},
         "4": {"class_type": "ImageScale", "inputs": {"image": ["3", 0], "upscale_method": "lanczos", "width": w, "height": h, "crop": "disabled"}},
         "5": {"class_type": "SaveImage", "inputs": {"images": ["4", 0], "filename_prefix": prefix}}}
    res = run_px.run(g, timeout=900)
    if not res or res["status"]["status_str"] != "success": raise RuntimeError("upscale failed (see comfy/server.log)")
    im = res["outputs"]["5"]["images"][0]
    shutil.copy(C.COMFY_UI / "output" / im["subfolder"] / im["filename"], dst)
    log(f"upscaled {W}x{H} -> {w}x{h} with {model}")
    return dst

def mesh(src, out_dir, tag, seed, log, faces=None, tex=None):
    gpu.free_all(log, keep="comfy"); gpu.wait_for_headroom("pixal3d", log); gpu.comfy_start(log)
    name = _to_input(src, "mesh"); prefix = f"3d/homunculus_{tag}"
    t0 = time.time()
    res = run_px.run(run_px.build_tex(name, prefix, seed, faces=faces or C.MESH_FACES, tex=tex or C.MESH_TEX), timeout=3300)
    if not res or res["status"]["status_str"] != "success": raise RuntimeError("Pixal3D failed (see comfy/server.log)")
    def newest(pat):
        fs = sorted(glob.glob(str(C.COMFY_UI / "output" / pat)), key=os.path.getmtime); return fs[-1] if fs else None
    lo = newest(f"3d/homunculus_{tag}_0*.glb"); hi = newest(f"3d/homunculus_{tag}_hi_*.glb")
    os.makedirs(out_dir, exist_ok=True)
    glb = os.path.join(out_dir, "mesh.glb"); shutil.copy(lo, glb)
    if hi: shutil.copy(hi, os.path.join(out_dir, "mesh_hi.glb"))
    log(f"Pixal3D done in {time.time()-t0:.0f}s -> {glb}")
    return glb


def shape(src, out_dir, tag, seed, log):
    """Fast shape-only Pixal3D pass (no remesh, no texture) used to judge the geometry before paying for the texture."""
    gpu.free_all(log, keep="comfy"); gpu.wait_for_headroom("pixal3d", log); gpu.comfy_start(log)
    name = _to_input(src, "shape"); prefix = f"3d/homunculus_{tag}_shape"
    t0 = time.time(); res = run_px.run(run_px.build_single(name, prefix, seed), timeout=1800)
    if not res or res["status"]["status_str"] != "success": raise RuntimeError("Pixal3D shape pass failed (see comfy/server.log)")
    fs = sorted(glob.glob(str(C.COMFY_UI / "output" / f"3d/homunculus_{tag}_shape_*.glb")), key=os.path.getmtime)
    os.makedirs(out_dir, exist_ok=True); glb = os.path.join(out_dir, "shape.glb"); shutil.copy(fs[-1], glb)
    log(f"Pixal3D shape pass in {time.time()-t0:.0f}s -> {glb}"); return glb
