"""UltraTex texturing (SIGGRAPH Asia 2026, FLUX.2 Klein base 9B + the UltraTex LoRA, ComfyUI nodes by visualbruno): paint a mesh from one reference picture.

The mesh is unwrapped, six normal views are rendered, FLUX paints the six views from the picture (consistent with each other, back and sides included) and they are baked into a 2K texture.
paint() returns a textured GLB with UltraTex's own UV layout; to_layout() carries that texture onto the UV layout of another mesh (the one a rig was built on) by baking, so it can go on the rig and the clips.
Needs: comfy/ComfyUI/custom_nodes/ComfyUI-UltraTex, the models listed in missing(), a running or startable ComfyUI.
Licence: the FLUX.2 Klein base model is non-commercial (Black Forest Labs); the nodes and UltraTex code are MIT."""
import os, sys, json, time, uuid, shutil, subprocess, requests
from . import config as C, gpu

_CUI = C.COMFY_UI
_MODELS = {"text_encoders/qwen_3_8b_fp8mixed.safetensors": "Comfy-Org/flux2-klein-9B", "vae/flux2-vae.safetensors": "Comfy-Org/flux2-dev", "background_removal/birefnet.safetensors": "Comfy-Org/BiRefNet",
           "loras/ultratex_flux2.safetensors": "ModelScope Yibo-Zhang/UltraTex (flux2/lora/dit_lora.safetensors, renamed)", "ultratex/ultratex_flux2_decoder.pt": "ModelScope Yibo-Zhang/UltraTex (flux2/decoder.pt, renamed)"}


def base_model():
    """The FLUX.2 Klein base 9B file (fp8; gated on Hugging Face: accept the licence of black-forest-labs/FLUX.2-klein-base-9b-fp8 and log in with `hf auth login`), or None."""
    name = "flux-2-klein-base-9b-fp8.safetensors"
    return ("fp8", name) if (_CUI / "models" / "diffusion_models" / name).exists() else None


def missing():
    """What is not installed (empty list: ready)."""
    out = [] if (_CUI / "custom_nodes" / "ComfyUI-UltraTex").exists() else ["custom node ComfyUI-UltraTex (pinned 8137da5)"]
    out += [f"{rel} ({src})" for rel, src in _MODELS.items() if not (_CUI / "models" / rel).exists()]
    if base_model() is None: out.append("models/diffusion_models/flux-2-klein-base-9b-fp8.safetensors (gated, black-forest-labs/FLUX.2-klein-base-9b-fp8)")
    return out


def graph(mesh, ref_name, name, res=1024, steps=25, seed=12345, attention="comfy_default", uv="comfy_gpu", texture=2048, weight_power=4.0, best_view=0.5, feather=6.0):
    kind, bm = base_model()
    unet = {"class_type": "UNETLoader", "inputs": {"unet_name": bm, "weight_dtype": "default"}}
    return {"1": {"class_type": "LoadImage", "inputs": {"image": ref_name}}, "2": {"class_type": "UltraTexLoadMesh", "inputs": {"glb_path": os.path.abspath(mesh), "only_vertices_and_faces": False}},
            "3": {"class_type": "LoadBackgroundRemovalModel", "inputs": {"bg_removal_name": "birefnet.safetensors"}}, "4": {"class_type": "RemoveBackground", "inputs": {"bg_removal_model": ["3", 0], "image": ["1", 0]}},
            "6": unet, "7": {"class_type": "CLIPLoader", "inputs": {"clip_name": "qwen_3_8b_fp8mixed.safetensors", "type": "flux2", "device": "default"}},
            "8": {"class_type": "VAELoader", "inputs": {"vae_name": "flux2-vae.safetensors"}}, "9": {"class_type": "UltraTexForegroundDecoder", "inputs": {"vae": ["8", 0], "decoder_name": "ultratex_flux2_decoder.pt"}},
            "10": {"class_type": "UltraTexLoraLoader", "inputs": {"model": ["6", 0], "lora_name": "ultratex_flux2.safetensors", "strength": 1.0}}, "12": {"class_type": "CLIPTextEncode", "inputs": {"text": "", "clip": ["7", 0]}},
            "14": {"class_type": "UltraTexPrep", "inputs": {"reference_image": ["1", 0], "mesh_path": "", "render_size": 4096, "atlas_size": 4096, "uv_mode": uv, "reference_alignment": "fit_front_silhouette", "mask_meaning": "foreground", "reference_mask": ["4", 0], "trimesh": ["2", 0]}},
            "15": {"class_type": "SaveImage", "inputs": {"images": ["14", 1], "filename_prefix": f"ultratex_{name}/normals"}}, "16": {"class_type": "SaveImage", "inputs": {"images": ["14", 2], "filename_prefix": f"ultratex_{name}/reference"}},
            "18": {"class_type": "UltraTexSampler", "inputs": {"model": ["10", 0], "vae": ["9", 0], "positive": ["12", 0], "prep": ["14", 0], "resolution": res, "steps": steps, "seed": seed, "guidance": 4.0, "drop_background_tokens": True,
                                                              "attention": attention, "sparse_topk": 0.2, "token_chunk": 8192}},
            "19": {"class_type": "SaveImage", "inputs": {"images": ["18", 2], "filename_prefix": f"ultratex_{name}/albedo_atlas"}},
            "23": {"class_type": "UltraTexBake", "inputs": {"prep": ["14", 0], "albedo_views": ["18", 0], "texture_size": texture, "filename_prefix": f"UltraTex/{name}", "view_weight_power": weight_power, "best_view_mix": best_view, "edge_feather_px": feather, "views_2_use": "all"}}}


def paint(mesh, ref, out_dir, log, name="char", res=1024, steps=25, seed=12345, attention="comfy_default", timeout=1800, weight_power=4.0, best_view=0.5, feather=6.0):
    """Texture `mesh` (GLB, any UVs; it is unwrapped again) from the picture `ref`. Returns the path of the textured GLB (UltraTex's UV layout) copied into out_dir. Starts ComfyUI if needed."""
    miss = missing()
    if miss: raise RuntimeError("UltraTex is not installed: " + "; ".join(miss))
    os.makedirs(out_dir, exist_ok=True)
    if not gpu.comfy_running(): gpu.free_all(log, keep="comfy"); gpu.comfy_start(log)
    ref_name = f"ut_{name}_{uuid.uuid4().hex[:6]}{os.path.splitext(ref)[1]}"; shutil.copy(ref, _CUI / "input" / ref_name)
    try:
        r = requests.post(C.COMFY_API + "/prompt", json={"prompt": graph(mesh, ref_name, name, res, steps, seed, attention, weight_power=weight_power, best_view=best_view, feather=feather), "client_id": uuid.uuid4().hex}, timeout=60)
        if r.status_code != 200: raise RuntimeError("ComfyUI rejected the UltraTex graph: " + r.text[:800])
        pid = r.json()["prompt_id"]; t0 = time.time(); bm = base_model(); log(f"[ultratex] painting six views ({bm[0]} base model, {res} px per view, {steps} steps)")
        while time.time() - t0 < timeout:
            h = requests.get(f"{C.COMFY_API}/history/{pid}", timeout=60).json()
            if pid in h:
                res_ = h[pid]
                if res_["status"]["status_str"] != "success": raise RuntimeError("UltraTex failed in ComfyUI: " + json.dumps(res_["status"]["messages"][-3:])[:800])
                break
            time.sleep(3)
        else: raise RuntimeError("UltraTex timed out")
        log(f"[ultratex] painted and baked in {time.time() - t0:.0f} s")
        for o in res_["outputs"].values():
            for it in o.get("3d", []) + o.get("gltf", []) + o.get("files", []):
                if isinstance(it, dict) and str(it.get("filename", "")).endswith(".glb"):
                    src = _CUI / "output" / it.get("subfolder", "") / it["filename"]; dst = os.path.join(out_dir, f"{name}_ultratex.glb"); shutil.copy(src, dst)
                    for o2 in res_["outputs"].values():                      # the painted views too, to look at
                        for im in o2.get("images", []):
                            s2 = _CUI / "output" / im.get("subfolder", "") / im["filename"]
                            if s2.exists(): shutil.copy(s2, os.path.join(out_dir, im["filename"]))
                    return dst
        raise RuntimeError("UltraTex made no GLB")
    finally:
        try: os.remove(_CUI / "input" / ref_name)
        except OSError: pass
        try: gpu.comfy_free()      # release the models from VRAM (the next stage needs the room)
        except Exception: pass


def to_layout(textured_glb, target_glb, out_png, log, size=4096, ray=0.05):
    """Carry the base-colour texture of `textured_glb` onto the UV layout of `target_glb` (the same surface; e.g. the mesh the rig was built from) by baking; writes out_png. Cycles on the CPU, about 15 s."""
    r = subprocess.run([C.BLENDER, "-b", "--python", os.path.join(os.path.dirname(__file__), "blender_bake_transfer.py"), "--", textured_glb, target_glb, out_png, str(size), "--ray", str(ray)], capture_output=True, text=True, timeout=1800)
    if not os.path.exists(out_png): raise RuntimeError("the texture transfer failed: " + (r.stdout + r.stderr)[-600:])
    log("[ultratex] " + next((l for l in r.stdout.splitlines() if "[bake] wrote" in l), "texture transferred"))
    return out_png


def set_texture(mesh_glb, png, out_glb):
    r = subprocess.run([C.BLENDER, "-b", "--python", os.path.join(os.path.dirname(__file__), "blender_set_texture.py"), "--", mesh_glb, png, out_glb], capture_output=True, text=True, timeout=900)
    if not os.path.exists(out_glb): raise RuntimeError("could not put the texture on the mesh: " + (r.stdout + r.stderr)[-500:])
    return out_glb


def coverage(mesh_glb, work, log, size=1024):
    """(size, size) floats in 0..1: how well the six views UltraTex paints see each texel of mesh_glb's UV layout (homunculus/blender_coverage.py). Surfaces no view sees (under an arm, the inside of a coat, a layer below the outer
    surface) get no real colour from the bake."""
    import numpy as np
    from .stages import texfill
    os.makedirs(work, exist_ok=True); pre = os.path.join(work, "cov")
    out = texfill._bl("prep", mesh_glb, pre, size)
    if "[texfill] baked" not in out: raise RuntimeError("could not bake texel positions: " + out[-300:])
    r = subprocess.run([C.BLENDER, "-b", "--python", os.path.join(os.path.dirname(__file__), "blender_coverage.py"), "--", mesh_glb, pre + "_pos.npy", pre + "_cov.npy"], capture_output=True, text=True, timeout=1800)
    if not os.path.exists(pre + "_cov.npy"): raise RuntimeError("coverage failed: " + (r.stdout + r.stderr)[-500:])
    log("[ultratex] " + next((l for l in r.stdout.splitlines() if "[coverage]" in l and "texels" in l), "coverage computed"))
    return np.load(pre + "_cov.npy"), np.load(pre + "_mask.npy")


def composite(baked_png, fallback_png, cov, out_png, log):
    """UltraTex's texture where its six views saw the surface, the fallback texture (the classic projection of the picture, same UV layout) elsewhere, blended softly at the border of the seen area:
    a surface the views do not see is not coloured by UltraTex, and in a posed or moved model (the rig is in a T-pose, the arms are away from the body) it shows."""
    import numpy as np
    from PIL import Image
    from scipy import ndimage as ndi
    U = Image.open(baked_png).convert("RGB"); W, H = U.size; F = Image.open(fallback_png).convert("RGB").resize((W, H), Image.BILINEAR)
    c = ndi.gaussian_filter(np.clip(cov, 0, 1).astype(np.float32), 2.0)                       # a soft border at the working resolution
    a = np.asarray(Image.fromarray(c).resize((W, H), Image.BILINEAR), np.float32)[..., None]
    out = np.asarray(U, np.float32) * a + np.asarray(F, np.float32) * (1 - a)
    Image.fromarray(np.clip(out + 0.5, 0, 255).astype(np.uint8)).save(out_png)
    log(f"[ultratex] texture: UltraTex where seen ({float((cov >= 0.5).mean()) * 100:.0f} % of the layout), the classic projection elsewhere")
    return out_png


def rest_mesh(rigged_glb, out_glb):
    """The mesh of a rigged GLB in the rig's rest pose, alone (what UltraTex should paint: see blender_rest_mesh.py)."""
    r = subprocess.run([C.BLENDER, "-b", "--python", os.path.join(os.path.dirname(__file__), "blender_rest_mesh.py"), "--", rigged_glb, out_glb], capture_output=True, text=True, timeout=900)
    if not os.path.exists(out_glb): raise RuntimeError("could not extract the rest-pose mesh: " + (r.stdout + r.stderr)[-500:])
    return out_glb
