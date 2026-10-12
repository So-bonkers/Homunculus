"""Fill the texels no view of a turnaround sheet painted (the sole of a boot, the inside of an arm, the top of the shoulders...): they keep the flat base colour, which shows as one-coloured patches.
Every texel gets a 3D position (blender_fill_texture.py); an unpainted texel takes the colour of the painted surface nearest to it IN 3D (so it carries across UV seams), averaged over a few neighbours.
Where a view painted only partly (blend weight a < 1) the baked colour is  a * painted + (1 - a) * base,  so the base share is swapped for the fill:  result = baked + (1 - a) * (fill - base).
Everything is solved at 1024 x 1024 (the fill is smooth) and added to the full-size texture, so painted detail is never touched."""
import io, json, os, struct, subprocess, numpy as np
from PIL import Image
from scipy import ndimage as ndi
from scipy.spatial import cKDTree
from .. import config as C

_SCRIPT = os.path.join(os.path.dirname(os.path.dirname(__file__)), "blender_fill_texture.py")
SOLVE = 1024            # working resolution of the fill
SURE = 0.9              # blend weight from which a texel counts as painted by a view (a source of colour)
K = 24                  # painted neighbours per filled texel; their MEDIAN colour is used, so a logo next to a patch of suit does not leak into it


def _bl(*args):
    r = subprocess.run([C.BLENDER, "-b", "--python", _SCRIPT, "--", *map(str, args)], capture_output=True, text=True, timeout=1500)
    return r.stdout + r.stderr


def glb_base_image(path):
    """The base colour image of a glb's first material, straight from the file (no colour conversion)."""
    b = open(path, "rb").read(); n = struct.unpack("<I", b[12:16])[0]; js = json.loads(b[20:20 + n]); off = 20 + n + 8
    tex = js["materials"][0]["pbrMetallicRoughness"]["baseColorTexture"]["index"]; im = js["images"][js["textures"][tex]["source"]]; bv = js["bufferViews"][im["bufferView"]]
    return Image.open(io.BytesIO(b[off + bv.get("byteOffset", 0): off + bv.get("byteOffset", 0) + bv["byteLength"]])).convert("RGB")


def fill(glb_base, glb_painted, coverage, out_glb, work, log):
    """glb_base: the mesh before any view was projected (its base colour is what unpainted texels still show); glb_painted: after all views (needs <name>_basecolor.png next to it);
    coverage: float array (h, w), the largest blend weight any view had per texel. Returns {painted, filled} shares, writes out_glb and <out_glb minus .glb>_basecolor.png."""
    os.makedirs(work, exist_ok=True); pre = os.path.join(work, "fill")
    out = _bl("prep", glb_painted, pre, SOLVE)
    if "[texfill] baked" not in out: raise RuntimeError("could not bake texel positions: " + out[-300:])
    pos = np.load(pre + "_pos.npy"); mask = np.load(pre + "_mask.npy")
    baked = Image.open(glb_painted[:-4] + "_basecolor.png").convert("RGB"); W, H = baked.size
    small = lambda im: np.asarray(im.resize((SOLVE, SOLVE), Image.BOX), np.float32)
    P = small(baked); B = small(glb_base_image(glb_base).resize((W, H), Image.NEAREST))
    cov = np.clip(np.asarray(Image.fromarray(np.clip(coverage, 0, 1).astype(np.float32)).resize((SOLVE, SOLVE), Image.BOX), np.float32), 0, 1)
    src = mask & (cov >= SURE); dst = mask & (cov < SURE)
    share = float(src.sum()) / max(1, int(mask.sum())); log(f"[texfill] {share * 100:.0f} % of the texture is painted by a view, {float(dst.sum()) / max(1, int(mask.sum())) * 100:.0f} % gets filled")
    if not src.any() or not dst.any(): shutil_copy(glb_painted, out_glb); return dict(painted=share, filled=0.0)
    tree = cKDTree(pos[src]); d, i = tree.query(pos[dst], k=K, workers=-1)
    F = P.copy(); F[dst] = np.median(P[src][i], axis=1)                                 # painted colour of the neighbours (median per channel)
    F = np.where(dst[..., None], F, B)                                                    # painted texels: nothing to swap (fill = base -> delta 0)
    D = (F - B)                                                                           # what to add per unit of missing coverage
    near = ndi.distance_transform_edt(~dst, return_distances=False, return_indices=True); D = D[near[0], near[1]]       # carry it outward, so the upscaling below never blends it with zeros at the edge (the (1 - coverage) factor switches it off where a view painted)
    up = lambda a: np.asarray(Image.fromarray(a.astype(np.float32)).resize((W, H), Image.BILINEAR), np.float32)
    A = np.clip(up(cov), 0, 1)
    res = np.asarray(baked, np.float32) + (1 - A)[..., None] * np.stack([up(D[..., c]) for c in range(3)], -1)
    png = out_glb[:-4] + "_basecolor.png"; Image.fromarray(np.clip(res + 0.5, 0, 255).astype(np.uint8)).save(png)
    out = _bl("apply", glb_painted, png, out_glb)
    if "[texfill] wrote" not in out: raise RuntimeError("could not write the filled model: " + out[-300:])
    return dict(painted=share, filled=float(dst.sum()) / max(1, int(mask.sum())))


def shutil_copy(a, b):
    import shutil; shutil.copy(a, b); shutil.copy(a[:-4] + "_basecolor.png", b[:-4] + "_basecolor.png")
