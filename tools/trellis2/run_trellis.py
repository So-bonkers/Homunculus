"""TRELLIS.2 on an AMD RX 7900 XTX (ROCm): image -> textured 3D mesh (GLB with a PBR texture).
    venv/bin/python run_trellis.py IMAGE_RGBA.png OUT_DIR [--seed 42] [--type 1024_cascade|1536_cascade|1024|512] [--texture 4096] [--faces 1000000]
ROCm stand-ins (see README_ROCM.md): attention through torch SDPA (dense: ATTN_BACKEND=sdpa; sparse: a flash_attn shim in the venv), nvdiffrast through a torch UV rasteriser (only the texture bake uses it),
DINOv3 from timm's ungated copy of the same weights (the facebook repo is gated), no RMBG-2.0 (gated; give a picture whose background is already transparent)."""
import os, sys, time, argparse, json
os.environ.setdefault("ATTN_BACKEND", "sdpa"); os.environ.setdefault("SPARSE_ATTN_BACKEND", "flash_attn"); os.environ["OPENCV_IO_ENABLE_OPENEXR"] = "1"
# expandable_segments is NOT set: on ROCm 7.2 it produced illegal memory accesses (the run died in plain torch ops)
HERE = os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0, os.path.join(HERE, "TRELLIS.2"))
ap = argparse.ArgumentParser(); ap.add_argument("image"); ap.add_argument("out"); ap.add_argument("--seed", type=int, default=42); ap.add_argument("--seeds", default=None, help="comma list: several seeds in one run (models loaded once), each into OUT/s<seed>"); ap.add_argument("--type", default="1024_cascade"); ap.add_argument("--texture", type=int, default=4096); ap.add_argument("--faces", type=int, default=1000000); ap.add_argument("--no-glb", action="store_true"); ap.add_argument("--batch", default=None, help="file with lines IMAGE OUT_DIR: several pictures in one run (models loaded once); IMAGE/OUT positional args are then ignored"); a = ap.parse_args()
os.makedirs(a.out, exist_ok=True)
import torch, timm, numpy as np, torch.nn.functional as F
from torchvision import transforms
from PIL import Image
from trellis2.modules import image_feature_extractor as ife
from trellis2.pipelines import rembg as RB
class TimmDinoV3(ife.DinoV3FeatureExtractor):
    """The same DINOv3 ViT-L/16 (LVD-1689M) weights through timm; returns [cls, 4 registers, patches] before the final norm, then a plain layer norm, as the transformers version does."""
    def __init__(self, model_name, image_size=512):
        self.model_name = model_name; self.image_size = image_size
        self.model = timm.create_model("vit_large_patch16_dinov3.lvd1689m", pretrained=True, img_size=image_size, dynamic_img_size=True).eval()          # the pipeline asks for 512 and 1024 pixel features: the rotary position table must follow the input size
        self.transform = transforms.Compose([transforms.Normalize(mean=[0.485, 0.456, 0.406], std=[0.229, 0.224, 0.225])])
    def extract_features(self, image):
        image = image.to(next(self.model.parameters()).dtype)
        patches, prefix = self.model.forward_intermediates(image, indices=1, norm=False, output_fmt="NLC", return_prefix_tokens=True, intermediates_only=True)[0]
        h = torch.cat([prefix, patches], 1); return F.layer_norm(h, h.shape[-1:])
class NoRembg:
    def __init__(self, **k): pass
    def to(self, *a, **k): return self
    def cpu(self): return self
    def cuda(self): return self
    def __call__(self, im): raise RuntimeError("give a picture with a transparent background (RMBG-2.0 is gated)")
ife.DinoV3FeatureExtractor = TimmDinoV3; RB.BiRefNet = NoRembg
from trellis2.pipelines import Trellis2ImageTo3DPipeline
from trellis2.representations.mesh import base as MB
_holes = os.environ.get("TRELLIS_FILL_HOLES", "0") == "1"
_orig_fill = MB.Mesh.fill_holes
def _fill_holes(self, *k, **kw):
    """CuMesh's hole filling faulted on gfx1100 on a real decoded mesh (not on synthetic ones): the mesh is saved for an offline repro and the step is skipped (the GLB export remeshes, which closes small holes)."""
    np.savez(os.path.join(a.out, "before_fill_holes.npz"), v=self.vertices.cpu().numpy(), f=self.faces.cpu().numpy())
    if _holes: return _orig_fill(self, *k, **kw)
MB.Mesh.fill_holes = _fill_holes
import cumesh as _cm
if not _holes: _cm.CuMesh.fill_holes = lambda self, *k, **kw: None      # also skipped inside the GLB export (CuMesh's boundary-loop tracing gives out-of-range edge ids on gfx1100; remeshing closes small holes)
import o_voxel
log = {}; t0 = time.time()
pipe = Trellis2ImageTo3DPipeline.from_pretrained("microsoft/TRELLIS.2-4B")
for m in pipe.models.values(): m.requires_grad_(False)          # inference only: FlexGEMM's training-path kernel (neighbor map with backward prep) faults on gfx1100
pipe.image_cond_model.model.requires_grad_(False); pipe.cuda(); torch.set_grad_enabled(False); log["load_s"] = round(time.time() - t0, 1); print("loaded", log["load_s"], "s", flush=True)
seeds = [int(x) for x in a.seeds.split(",")] if a.seeds else [a.seed]
jobs = [l.split() for l in open(a.batch) if l.strip()] if a.batch else [(a.image, a.out)]
for (IMG, OUT), seed in [(j, sd) for j in jobs for sd in seeds]:
    img = Image.open(IMG)
    a.out = os.path.join(OUT, f"s{seed}") if a.seeds else OUT; print('job', IMG, '->', a.out, flush=True); os.makedirs(a.out, exist_ok=True); a.seed = seed; t0s = time.time()
    torch.cuda.reset_peak_memory_stats(); t1 = time.time()
    mesh = pipe.run(img, seed=a.seed, pipeline_type=a.type)[0]; torch.cuda.synchronize(); log["generate_s"] = round(time.time() - t1, 1); log["peak_vram_gb"] = round(torch.cuda.max_memory_allocated() / 1e9, 1)
    print("generated", log, flush=True)
    torch.save(dict(vertices=mesh.vertices.cpu(), faces=mesh.faces.cpu(), attrs=mesh.attrs.cpu(), coords=mesh.coords.cpu(), layout=mesh.layout, voxel_size=mesh.voxel_size), os.path.join(a.out, "state.pt"))     # re-export without regenerating (export_trellis.py)
    torch.cuda.empty_cache()
    try: mesh.simplify(16777216)                                    # the 1536 meshes are big: free the cache first; if it still does not fit, keep the full mesh
    except RuntimeError as e: print('simplify skipped:', str(e).splitlines()[-1], flush=True)
    import trimesh
    trimesh.Trimesh(vertices=mesh.vertices.cpu().numpy(), faces=mesh.faces.cpu().numpy(), process=False).export(os.path.join(a.out, "raw_shape.glb")); log["raw_faces"] = int(mesh.faces.shape[0])
    if not a.no_glb:
        t2 = time.time()
        glb = o_voxel.postprocess.to_glb(vertices=mesh.vertices, faces=mesh.faces, attr_volume=mesh.attrs, coords=mesh.coords, attr_layout=mesh.layout, voxel_size=mesh.voxel_size, aabb=[[-0.5, -0.5, -0.5], [0.5, 0.5, 0.5]],
                                         decimation_target=a.faces, texture_size=a.texture, remesh=True, remesh_band=1, remesh_project=0, verbose=True)
        glb.export(os.path.join(a.out, "textured.glb")); log["glb_s"] = round(time.time() - t2, 1)

    print('seed', seed, 'done in', round(time.time() - t0s, 1), 's', flush=True)
log["total_s"] = round(time.time() - t0, 1); log["peak_vram_gb_total"] = round(torch.cuda.max_memory_allocated() / 1e9, 1); json.dump(log, open(os.path.join(a.out, "timing.json"), "w"), indent=1); print("DONE", log, flush=True)
