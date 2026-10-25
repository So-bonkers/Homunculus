"""Which template vertices are under clothes: the front picture's grey cloth pixels (low saturation, darker than the background) are projected onto the fitted template.
    gvhmr/.venv/bin/python tools/template_fit/cloth_labels.py FITDIR FRONT.png
Writes FITDIR/cloth_labels.npz (label per vertex: 0 skin, 1 top, 2 bottom) and FITDIR/cloth_overlay.png (the picture with the template's vertices coloured by label, to check the registration).
The picture is registered by its figure's height (head top to soles) and the centre line of the bounding box; vertices on the far side of the body get the label of the pixel they hide behind (hems are horizontal, so the front view is enough for a T-shirt and shorts)."""
import sys, os, numpy as np
from PIL import Image
from scipy import ndimage as ndi
d, img = sys.argv[1:3]; V = np.load(os.path.join(d, "mixamo.npz"))["verts"]            # glTF frame: y up, the template faces +z, its left is +x
im = np.asarray(Image.open(img).convert("RGB")).astype(float); r, g, b = im[..., 0], im[..., 1], im[..., 2]
bg = np.median(im[:20].reshape(-1, 3), axis=0); fg = np.abs(im - bg).max(2) > 25
ys, xs = np.nonzero(fg); top, bot = ys.min(), ys.max(); cx = (xs.min() + xs.max()) / 2
s = (bot - top) / (V[:, 1].max() - V[:, 1].min())                                        # pixels per metre
sat = (im.max(2) - im.min(2)); cloth = fg & (sat < 22) & (im.max(2) > 70) & (im.max(2) < 190)
cloth = ndi.binary_opening(cloth, iterations=2); lab_im, n = ndi.label(cloth)
sizes = ndi.sum(cloth, lab_im, range(1, n + 1)); keep = [i + 1 for i in np.argsort(sizes)[::-1][:2]]; cloth = np.isin(lab_im, keep)
cloth = ndi.binary_closing(cloth, iterations=3); cloth = ndi.binary_fill_holes(cloth)
px = (cx - V[:, 0] * s).round().astype(int); py = (top + (V[:, 1].max() - V[:, 1]) * s).round().astype(int)
px = px.clip(0, im.shape[1] - 1); py = py.clip(0, im.shape[0] - 1)
lab = np.where(cloth[py, px], 1, 0)
# the two garments touch, so they are split at the T-shirt's hem: the row with the most dark outline pixels inside the cloth, in the middle of its height
ys_c = np.nonzero(cloth.any(1))[0]; y0, y1 = ys_c.min(), ys_c.max(); dark = (im.max(2) < 115) & ndi.binary_dilation(cloth, iterations=2)
rows = np.arange(int(y0 + 0.40 * (y1 - y0)), int(y0 + 0.70 * (y1 - y0))); hem = rows[np.argmax([dark[r_, int(cx) - 80:int(cx) + 80].sum() for r_ in rows])]
lab = np.where(cloth[py, px], np.where(py < hem, 1, 2), 0); print("hem row", hem)
# torso vertices that do not face the camera (the sides, hidden by the hanging arms in the picture) take the label of the front-facing torso vertices at the same height
Z = np.load(os.path.join(d, "mixamo.npz")); W, names, F = Z["weights"], [str(n) for n in Z["names"]], Z["faces"]
torso = np.isin(np.argmax(W, 1), [names.index(n) for n in ("Hips", "Spine", "Spine1", "Spine2")])
fn = np.cross(V[F[:, 1]] - V[F[:, 0]], V[F[:, 2]] - V[F[:, 0]]); N = np.zeros_like(V)
for k in range(3): np.add.at(N, F[:, k], fn)
N /= np.linalg.norm(N, axis=1)[:, None] + 1e-12; front = torso & (N[:, 2] > 0.5)
band = 0.006 * (V[:, 1].max() - V[:, 1].min())
for i in np.nonzero(torso & ~front)[0]:
    sel = front & (np.abs(V[:, 1] - V[i, 1]) < band)
    if sel.any(): lab[i] = np.bincount(lab[sel]).argmax()
# a vertex that only just misses the cloth pixels because of the registration: take the majority label of its mesh neighbours
for _ in range(2):
    nb = [[] for _ in V]
    for a, b_, c in F:
        for u, v, w in ((a, b_, c), (b_, c, a), (c, a, b_)): nb[u] += [lab[v], lab[w]]
    lab = np.array([np.bincount(nb[i]).argmax() if nb[i] else lab[i] for i in range(len(V))])
np.savez(os.path.join(d, "cloth_labels.npz"), labels=lab, scale=s, cx=cx, top=top)
ov = Image.open(img).convert("RGB"); a = np.asarray(ov).copy()
for i in range(len(V)): a[py[i], px[i]] = [(60, 200, 80), (230, 40, 40), (40, 80, 230)][lab[i]]
Image.fromarray(a).crop((100, 380, 700, 1150)).save(os.path.join(d, "cloth_overlay.png")); print("labels: skin %d, top %d, bottom %d; scale %.0f px/m" % ((lab == 0).sum(), (lab == 1).sum(), (lab == 2).sum(), s))
