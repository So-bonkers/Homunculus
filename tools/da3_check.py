"""Do the four views of a turnaround sheet agree geometrically? Depth Anything 3 in multi-view mode (Small/Base) estimates, from the four pictures alone, one depth map per view AND the cameras they were
taken from. If the views are views of one object, the clouds from the four depth maps fit together in the shared frame and the cameras sit roughly 90 degrees apart around it; if the generator drew each
view on its own (different arms, scale, hands), they do not.
    .venv/bin/python tools/da3_check.py <out_dir> <front.png> <left.png> <back.png> <right.png> [--model depth_anything_3_base.safetensors] [--res 504]
Needs ComfyUI with the DA3 nodes and the weights in models/geometry_estimation. Writes <out_dir>/report.txt, cloud_top.png, cloud_front.png and the depth maps."""
import json, math, os, shutil, sys, time, uuid
from pathlib import Path
ROOT = Path(__file__).resolve().parent.parent
sys.path[:0] = [str(ROOT), str(ROOT / "comfy")]
import numpy as np
import requests
from PIL import Image
from homunculus import config as C, gpu

PROBE = '''"""Probe for tools/da3_check.py: dumps what Depth Anything 3 estimated (world-frame points per view, camera poses)."""
import json, os, numpy as np, torch
from comfy_extras import nodes_depth_anything_3 as D
import folder_paths

class DA3Probe:
    @classmethod
    def INPUT_TYPES(s): return {"required": {"da3_geometry": ("DA3_GEOMETRY",), "tag": ("STRING", {"default": "da3"})}}
    RETURN_TYPES = (); FUNCTION = "go"; OUTPUT_NODE = True; CATEGORY = "probe"
    def go(self, da3_geometry, tag):
        g = da3_geometry; B = g["depth"].shape[0]; out = {"views": []}; arrs = {}
        img = g["image"].detach().cpu().float()                      # (B, H, W, 3) or (B, 3, H, W)
        if img.shape[1] == 3 and img.shape[-1] != 3: img = img.permute(0, 2, 3, 1)
        for i in range(B):
            depth = g["depth"][i].detach().clone().float(); depth[~torch.isfinite(depth)] = 0; H, W = depth.shape
            K = D._da3_get_K(g, i, H, W); P = D._da3_unproject(depth, K); E = D._da3_get_extrinsic(g, i)
            if E is not None: P = D._da3_apply_extrinsic(P, E)
            mask = D._da3_build_mask(g, i, H, W, 0.1, True) & torch.isfinite(depth) & (depth > 0)
            arrs[f"p{i}"] = P.detach().cpu().numpy().astype(np.float32); arrs[f"m{i}"] = mask.detach().cpu().numpy(); arrs[f"d{i}"] = depth.cpu().numpy().astype(np.float32)
            arrs[f"c{i}"] = torch.nn.functional.interpolate(img[i:i + 1].permute(0, 3, 1, 2), size=(H, W), mode="bilinear").permute(0, 2, 3, 1)[0].numpy().astype(np.float32)
            if "confidence" in g: arrs[f"conf{i}"] = g["confidence"][i].cpu().numpy().astype(np.float32)
            out["views"].append({"extrinsic": (E.detach().cpu().float().tolist() if E is not None else None), "K": K.detach().cpu().float().tolist()})
        p = os.path.join(folder_paths.get_output_directory(), tag + ".npz"); np.savez_compressed(p, **arrs); out["npz"] = p
        return {"ui": {"text": [json.dumps(out)]}}

NODE_CLASS_MAPPINGS = {"DA3Probe": DA3Probe}
'''
NAMES = ("front", "left", "back", "right")


def api(path, **kw): return requests.post(C.COMFY_API + path, **kw)


def main():
    a = sys.argv[1:]; model = a[a.index("--model") + 1] if "--model" in a else "depth_anything_3_base.safetensors"; res = int(a[a.index("--res") + 1]) if "--res" in a else 504
    for f in ("--model", "--res"):
        if f in a: i = a.index(f); del a[i:i + 2]
    out, views = Path(a[0]), a[1:5]; out.mkdir(parents=True, exist_ok=True); assert len(views) == 4, "give front, left, back, right"
    cn = C.COMFY_UI / "custom_nodes"; cn.mkdir(exist_ok=True); (cn / "da3_probe.py").write_text(PROBE)
    gpu.free_all(print, keep="comfy"); 
    if gpu.comfy_running(): gpu.comfy_stop(); time.sleep(3)          # the probe node is loaded at start-up
    gpu.comfy_start(print)
    u = uuid.uuid4().hex[:6]; names = []
    for n, p in zip(NAMES, views):
        nm = f"da3check_{u}_{n}.png"; Image.open(p).convert("RGB").save(C.COMFY_UI / "input" / nm); names.append(nm)
    g = {"1": {"class_type": "LoadDA3Model", "inputs": {"model_name": model, "weight_dtype": "fp32"}}}
    for i, nm in enumerate(names): g[str(2 + i)] = {"class_type": "LoadImage", "inputs": {"image": nm}}
    g["6"] = {"class_type": "ImageBatch", "inputs": {"image1": ["2", 0], "image2": ["3", 0]}}; g["7"] = {"class_type": "ImageBatch", "inputs": {"image1": ["6", 0], "image2": ["4", 0]}}
    g["8"] = {"class_type": "ImageBatch", "inputs": {"image1": ["7", 0], "image2": ["5", 0]}}
    g["9"] = {"class_type": "DA3Inference", "inputs": {"da3_model": ["1", 0], "image": ["8", 0], "resolution": res, "resize_method": "upper_bound_resize", "mode": "multiview",
                                                       "mode.ref_view_strategy": "saddle_balanced", "mode.pose_method": "cam_dec"}}
    g["10"] = {"class_type": "DA3Probe", "inputs": {"da3_geometry": ["9", 0], "tag": f"da3check_{u}"}}
    g["11"] = {"class_type": "DA3Render", "inputs": {"da3_geometry": ["9", 0], "output": "depth_colored", "output.normalization": "min_max", "output.apply_sky_clip": False}}
    g["12"] = {"class_type": "SaveImage", "inputs": {"images": ["11", 0], "filename_prefix": f"da3check_{u}_depth"}}
    r = api("/prompt", json={"prompt": g, "client_id": u}); 
    if r.status_code != 200: sys.exit("graph rejected: " + r.text[:1500])
    pid = r.json()["prompt_id"]; t0 = time.time()
    while time.time() - t0 < 900:
        h = requests.get(f"{C.COMFY_API}/history/{pid}").json()
        if pid in h: break
        time.sleep(2)
    res_ = h[pid]
    if res_["status"]["status_str"] != "success": sys.exit("failed: " + json.dumps(res_["status"]["messages"][-3:])[:1500])
    info = json.loads(res_["outputs"]["10"]["text"][0]); print(f"DA3 done in {time.time() - t0:.0f}s")
    for i, im in enumerate(res_["outputs"]["12"]["images"]): shutil.copy(C.COMFY_UI / "output" / im["subfolder"] / im["filename"], out / "depth_colored.png")
    analyse(info, out)


def analyse(info, out):
    import matplotlib; matplotlib.use("Agg"); import matplotlib.pyplot as plt
    z = np.load(info["npz"]); lines = []; clouds = []; cams = []
    for i, n in enumerate(NAMES):
        P, M, Cc = z[f"p{i}"], z[f"m{i}"], z[f"c{i}"]; fg = M & (Cc.sum(-1) > 0.06)                    # not the black background
        clouds.append(P[fg]); v = info["views"][i]
        if v["extrinsic"] is not None:
            E = np.array(v["extrinsic"]); E = E if E.shape == (4, 4) else np.vstack([E, [0, 0, 0, 1]]); R, t = E[:3, :3], E[:3, 3]; cams.append(-R.T @ t)
    allp = np.concatenate(clouds); ctr = np.median(allp, axis=0); cams = np.array(cams) if len(cams) == 4 else None
    # the vertical axis: the one the four cameras barely move along (they circle the subject in a horizontal plane)
    vert = int(np.argmin(np.var(cams, axis=0))) if cams is not None else int(np.argmax(np.percentile(allp, 99, axis=0) - np.percentile(allp, 1, axis=0)))
    hz = [i for i in range(3) if i != vert]; ax_n = "xyz"
    lines.append(f"Depth Anything 3 (multi-view) on the four views of the sheet; vertical axis = {ax_n[vert]}, horizontal plane = {ax_n[hz[0]]}{ax_n[hz[1]]}")
    lo = np.percentile(allp[:, vert], 1); H = np.percentile(allp[:, vert], 99) - lo; lines.append(f"Cameras (relative to the cloud's centre) and the spacing between them:")
    if cams is not None:
        rel = cams - ctr; ang = np.degrees(np.arctan2(rel[:, hz[1]], rel[:, hz[0]]))
        for n, c in zip(NAMES, rel): lines.append(f"  {n:5s}: ({c[0]:+.2f}, {c[1]:+.2f}, {c[2]:+.2f}) distance {np.linalg.norm(c):.2f}")
        d = [abs((ang[(i + 1) % 4] - ang[i] + 540) % 360 - 180) for i in range(4)]
        lines.append("  spacing front->left->back->right->front (a turntable of four views is 90 each): " + ", ".join(f"{x:.0f}" for x in d) + " degrees")
    hts = [np.percentile(c[:, vert], 99) - np.percentile(c[:, vert], 1) for c in clouds]
    lines.append("Figure height in each view's cloud (equal if the views agree): " + ", ".join(f"{n} {h:.2f}" for n, h in zip(NAMES, hts)) + f"   spread {100 * (max(hts) - min(hts)) / np.mean(hts):.1f} %")
    # registration: the torso (hips to chest) is in all four views; if the clouds belong to one body, its horizontal centre is the same in all of them
    ycut = lambda p, f0, f1: p[(p[:, vert] > lo + f0 * H) & (p[:, vert] < lo + f1 * H)]
    cen = []
    for n, c in zip(NAMES, clouds):
        t = ycut(c, 0.45, 0.62); cen.append(np.median(t[:, hz], axis=0)); 
    cen = np.array(cen); off = max(np.linalg.norm(cen[i] - cen[j]) for i in range(4) for j in range(i + 1, 4))
    lines.append("Torso centre in the horizontal plane, per view: " + "; ".join(f"{n} ({c[0]:+.2f}, {c[1]:+.2f})" for n, c in zip(NAMES, cen)) + f"   largest offset between two views {100 * off / H:.0f} % of the height")
    # body depth: from the side views (their horizontal extent) against the front and back surfaces together
    a0 = hz[0]
    def ext(c, ax): t = ycut(c, 0.45, 0.62); return np.percentile(t[:, ax], 99) - np.percentile(t[:, ax], 1)
    lines.append(f"Body depth (torso) along {ax_n[a0]}: the left view's width {ext(clouds[1], a0):.3f}, the right view's {ext(clouds[3], a0):.3f}; the front view's surface thickness {ext(clouds[0], a0):.3f} + the back's {ext(clouds[2], a0):.3f} = {ext(clouds[0], a0) + ext(clouds[2], a0):.3f}")
    (out / "report.txt").write_text("\n".join(lines)); print("\n".join(lines))
    col = ["tab:red", "tab:green", "tab:blue", "tab:orange"]
    for name, ax_ in (("top", (hz[0], hz[1])), ("front", (hz[1], vert)), ("side", (hz[0], vert))):
        fig, axx = plt.subplots(figsize=(7, 7))
        for i, n in enumerate(NAMES):
            p = clouds[i][::5]; axx.scatter(p[:, ax_[0]], p[:, ax_[1]], s=0.6, c=col[i], label=n, alpha=0.6)
        if cams is not None and name == "top": axx.scatter(cams[:, ax_[0]], cams[:, ax_[1]], marker="^", s=120, c=col, edgecolors="k")
        axx.set_aspect("equal"); axx.legend(markerscale=12); axx.set_title(f"fused clouds, {name} projection ({ax_n[ax_[0]]} by {ax_n[ax_[1]]})"); fig.savefig(out / f"cloud_{name}.png", dpi=110); plt.close(fig)


if __name__ == "__main__":
    main()
