"""ComfyUI jobs: ESRGAN-family upscaling and Pixal3D shape+texture (graph builder reused from comfy/run_px.py)."""
import glob, os, shutil, subprocess, sys, time, uuid
from PIL import Image
from .. import config as C, gpu
sys.path.insert(0, str(C.COMFY))
import run_px   # build_tex(), run()  (has its own VRAM watchdog: stops ComfyUI above 22.5 GB)

def _to_input(src, tag):
    name = f"homunculus_{tag}_{uuid.uuid4().hex[:6]}.png"
    Image.open(src).convert("RGB").save(C.COMFY_UI / "input" / name); return name

def _views_to_input(views, tag):
    """The four framed turnaround views into ComfyUI's input folder: {name: file name}."""
    u = uuid.uuid4().hex[:6]; out = {}
    for n, p in views.items():
        out[n] = f"homunculus_{tag}_{n}_{u}.png"; shutil.copy(p, C.COMFY_UI / "input" / out[n])
    return out

def mv_model():
    """bf16 multiview checkpoint when it is installed, else the int8 one (about 2x slower per step on ROCm, but 5 GB instead of 11)."""
    d = C.COMFY_UI / "models" / "diffusion_models"
    return run_px.PIXAL_MV_MODEL if (d / run_px.PIXAL_MV_MODEL).exists() and (d / run_px.PIXAL_MV_MODEL).stat().st_size > 9e9 else "pixal3d_multiview_int8_convrot.safetensors"

def turn_around(glb, log, deg=180.0):
    """The multiview model builds the character facing the other way from the single-image one: turn the GLB so the front is the front again (in place)."""
    tmp = glb + ".turn.glb"
    r = subprocess.run([C.BLENDER, "-b", "--python", str(C.ROOT / "homunculus" / "blender_rotz.py"), "--", glb, tmp, str(deg)], capture_output=True, text=True)
    if not os.path.exists(tmp): raise RuntimeError("turning the multiview mesh failed: " + (r.stdout + r.stderr)[-400:])
    os.replace(tmp, glb); log(f"multiview mesh turned {deg:.0f} degrees: {os.path.basename(glb)}")

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

def mesh(src, out_dir, tag, seed, log, faces=None, tex=None, views=None, texture=True, base_color=0x808080, upres=None):
    gpu.free_all(log, keep="comfy"); gpu.wait_for_headroom("pixal3d", log); gpu.comfy_start(log)
    prefix = f"3d/homunculus_{tag}"
    t0 = time.time()
    if views: g = run_px.build_tex_mv(_views_to_input(views, "mesh"), prefix, seed, model=mv_model(), faces=faces or C.MESH_FACES, tex=tex or C.MESH_TEX, texture=texture, base_color=base_color, upres=upres)
    else: g = run_px.build_tex(_to_input(src, "mesh"), prefix, seed, faces=faces or C.MESH_FACES, tex=tex or C.MESH_TEX, texture=texture, base_color=base_color, upres=upres)
    res = run_px.run(g, timeout=3300)
    if not res or res["status"]["status_str"] != "success": raise RuntimeError("Pixal3D failed (see comfy/server.log)")
    def newest(pat):
        fs = sorted(glob.glob(str(C.COMFY_UI / "output" / pat)), key=os.path.getmtime); return fs[-1] if fs else None
    lo = newest(f"3d/homunculus_{tag}_0*.glb"); hi = newest(f"3d/homunculus_{tag}_hi_*.glb")
    os.makedirs(out_dir, exist_ok=True)
    glb = os.path.join(out_dir, "mesh.glb"); shutil.copy(lo, glb)
    if hi: shutil.copy(hi, os.path.join(out_dir, "mesh_hi.glb"))
    if views:
        turn_around(glb, log)
        if hi: turn_around(os.path.join(out_dir, "mesh_hi.glb"), log)
    log(f"Pixal3D done in {time.time()-t0:.0f}s -> {glb}")
    return glb


def shape(src, out_dir, tag, seed, log, views=None):
    """Fast shape-only Pixal3D pass (no remesh, no texture) used to judge the geometry before paying for the texture."""
    gpu.free_all(log, keep="comfy"); gpu.wait_for_headroom("pixal3d", log); gpu.comfy_start(log)
    prefix = f"3d/homunculus_{tag}_shape"
    g = run_px.build_single_mv(_views_to_input(views, "shape"), prefix, seed, model=mv_model()) if views else run_px.build_single(_to_input(src, "shape"), prefix, seed)
    t0 = time.time(); res = run_px.run(g, timeout=1800)
    if not res or res["status"]["status_str"] != "success": raise RuntimeError("Pixal3D shape pass failed (see comfy/server.log)")
    fs = sorted(glob.glob(str(C.COMFY_UI / "output" / f"3d/homunculus_{tag}_shape_*.glb")), key=os.path.getmtime)
    os.makedirs(out_dir, exist_ok=True); glb = os.path.join(out_dir, "shape.glb"); shutil.copy(fs[-1], glb)
    if views: turn_around(glb, log)
    log(f"Pixal3D shape pass in {time.time()-t0:.0f}s -> {glb}"); return glb
