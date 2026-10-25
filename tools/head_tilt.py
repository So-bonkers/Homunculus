"""Head tilt of a front picture, in degrees (positive: the character's head leans toward the picture's right... see the sign note below): the angle of the line through the two eyes/brows (dark pixels of the face, left half against right half), and the angle of the head's long axis (bald heads only).
    .venv/bin/python tools/head_tilt.py front.png [more.png ...]"""
import sys, numpy as np
from PIL import Image
from scipy import ndimage as ndi
for f in sys.argv[1:]:
    im = np.asarray(Image.open(f).convert("RGB")).astype(float); bg = np.median(im[:20].reshape(-1, 3), axis=0); fg = np.abs(im - bg).max(2) > 25
    ys, xs = np.nonzero(fg); top, bot = ys.min(), ys.max(); H = bot - top
    sk = fg & (im[..., 0] > im[..., 2] + 25) & (np.arange(im.shape[0])[:, None] < top + 0.17 * H)             # skin above the chin
    lab, n = ndi.label(ndi.binary_opening(sk, iterations=2)); big = np.argmax(ndi.sum(sk, lab, range(1, n + 1))) + 1; head = lab == big
    hy, hx = np.nonzero(head); cx = hx.mean()
    dark = head & (im.max(2) < 85); dark = ndi.binary_closing(dark, iterations=1)
    row0 = hy.min() + 0.25 * (hy.max() - hy.min()); row1 = hy.min() + 0.75 * (hy.max() - hy.min()); yy, xx = np.nonzero(dark); sel = (yy > row0) & (yy < row1); yy, xx = yy[sel], xx[sel]
    L = xx < cx; R = ~L
    ang = np.degrees(np.arctan2(yy[R].mean() - yy[L].mean(), xx[R].mean() - xx[L].mean())) if L.any() and R.any() else float("nan")
    # long axis of the head blob without the ears: columns within 40 % of the width around the centre
    w = hx.max() - hx.min(); core = np.abs(hx - cx) < 0.32 * w; cov = np.cov(np.vstack([hx[core], hy[core]])); ev, evec = np.linalg.eigh(cov); v = evec[:, 1]; ax = np.degrees(np.arctan2(v[0], v[1]))
    ax = (ax + 90) % 180 - 90
    print(f"{f}: eye-line {ang:+.1f} deg, head axis {ax:+.1f} deg from vertical")
