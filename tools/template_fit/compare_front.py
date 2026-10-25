"""How the fitted template compares with the front picture, in picture pixels: crown/chin/joint heights and silhouette widths at fixed fractions of the height (the template is registered as in cloth_labels.py).
    gvhmr/.venv/bin/python tools/template_fit/compare_front.py FITDIR FRONT.png   (needs mixamo.npz and cloth_labels.npz in FITDIR)"""
import sys, os, numpy as np
from PIL import Image
from scipy import ndimage as ndi
d, img = sys.argv[1:3]; Z = np.load(os.path.join(d, "mixamo.npz")); V, W, names, J = Z["verts"], Z["weights"], [str(n) for n in Z["names"]], Z["joints"]
L = np.load(os.path.join(d, "cloth_labels.npz")); s, top = float(L["scale"]), float(L["top"]); ymax = V[:, 1].max(); px = lambda y: top + (ymax - y) * s
im = np.asarray(Image.open(img).convert("RGB")).astype(float); bg = np.median(im[:20].reshape(-1, 3), axis=0); fg = np.abs(im - bg).max(2) > 25; ys, xs = np.nonzero(fg); H = ys.max() - ys.min()
hv = np.nonzero(np.argmax(W, 1) == names.index("Head"))[0]; chin = V[hv][:, 1].min()
print(f"model head: crown {px(ymax):.0f} chin {px(chin):.0f} -> {(px(chin) - px(ymax)) / H * 100:.1f} % of the height; neck joint {px(J[names.index('Neck')][1]):.0f}, shoulder {px(J[names.index('LeftArm')][1]):.0f}, hips {px(J[names.index('Hips')][1]):.0f}, knee {px(J[names.index('LeftLeg')][1]):.0f}, ankle {px(J[names.index('LeftFoot')][1]):.0f}")
hs = np.nonzero(fg[: int(top + 0.25 * H)].any(1))[0]
for name, frac in (("head", 0.05), ("neck", 0.19), ("chest", 0.27), ("waist", 0.43), ("hip", 0.50), ("thigh", 0.60), ("knee", 0.74), ("calf", 0.82), ("ankle", 0.95)):
    r = int(top + frac * H); lab, n = ndi.label(fg[r]); segs = [int(np.ptp(np.nonzero(lab == i)[0])) for i in range(1, n + 1)]
    y = ymax - (r - top) / s; sel = np.abs(V[:, 1] - y) < 0.004; x = np.sort(V[sel, 0]); parts = np.split(x, np.nonzero(np.diff(x) > 0.03)[0] + 1)
    print(f"{name:6s} picture {segs}  model {[int(np.ptp(p) * s) for p in parts if len(p) > 2]}")
