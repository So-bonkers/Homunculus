"""Turnaround sheet in, multiview Pixal3D views out. A sheet is one picture with the same character four times (front, left, right, back); it comes from you (ChatGPT, a 3D render, ...).

split()  cuts the four figures out of the sheet;  frame()  puts them on black in 1024 px squares at ONE shared scale (what Pixal3DMultiViewConditioning expects).
"left" means the camera sees the character's LEFT side, so in the left view the character faces the left edge of the picture.
"""
import os
import numpy as np
from PIL import Image

NAMES = ("front", "left", "back", "right")
SIZE = 1024
ORDERS = {"lfrb": ("left", "front", "right", "back"), "flbr": ("front", "left", "back", "right")}     # left-to-right order of the figures in the sheet; the default is lfrb


def _cutout(im):
    from rembg import remove, new_session
    return np.asarray(remove(im, session=new_session("u2net")))[..., 3] > 128


def split(sheet, out_dir, order="lfrb", log=print):
    """Cut a sheet into <name>_raw.png (one connected figure each, cropped with a margin). Returns {name: path}. Raises if it does not find four figures."""
    from scipy import ndimage as ndi
    names = ORDERS.get(order) or tuple(order.split(","))
    os.makedirs(out_dir, exist_ok=True)
    im = Image.open(sheet).convert("RGB"); m = _cutout(im)
    lab, n = ndi.label(ndi.binary_dilation(m, iterations=3))
    area = [(i, int((lab == i).sum())) for i in range(1, n + 1)]
    big = [(ndi.center_of_mass(lab == i)[1], i) for i, a in area if a > 0.01 * m.size]          # figures; captions and specks are smaller than 1% of the sheet
    big.sort()
    if len(big) != 4: raise RuntimeError(f"expected four figures in the turnaround sheet, found {len(big)} (figures that touch each other count as one)")
    out = {}
    for (_, i), name in zip(big, names):
        own = ndi.binary_dilation(lab == i, iterations=6); ys, xs = np.nonzero((lab == i) & m); pad = 20
        a = np.asarray(im).copy(); bgc = np.median(np.concatenate([a[:8].reshape(-1, 3), a[-8:].reshape(-1, 3)]), axis=0).astype(np.uint8)
        a[~own] = bgc                                       # the crop's margin can reach into a neighbouring figure (a hand tip, a helmet): keep only this figure
        p = os.path.join(out_dir, f"{name}_raw.png")
        Image.fromarray(a).crop((max(0, xs.min() - pad), max(0, ys.min() - pad), min(im.width, xs.max() + pad), min(im.height, ys.max() + pad))).save(p); out[name] = p
    log(f"turnaround sheet split into {', '.join(names)}")
    return out


def front_reference(raw_front, dst):
    """The front figure as a square picture on its own background colour: this is what the rest of the pipeline sees as 'the picture'."""
    im = Image.open(raw_front).convert("RGB"); w, h = im.size; s = max(w, h)
    a = np.asarray(im); bg = tuple(int(x) for x in np.median(np.concatenate([a[:6].reshape(-1, 3), a[-6:].reshape(-1, 3), a[:, :6].reshape(-1, 3), a[:, -6:].reshape(-1, 3)]), axis=0))
    c = Image.new("RGB", (s, s), bg); c.paste(im, ((s - w) // 2, (s - h) // 2)); c.save(dst); return dst


def frame(raw, out_dir, log=print):
    """raw: {name: path}. Cut every view out, use one scale for all (the largest extent of any view), keep the front's vertical centre for all, centre each view horizontally on its own box.
    Writes <name>.png (1024 px, black background) and returns {name: path}."""
    ims, boxes = {}, {}
    for n in NAMES:
        if n not in raw: continue
        im = Image.open(raw[n]).convert("RGB"); m = _cutout(im); ys, xs = np.nonzero(m)
        boxes[n] = (xs.min(), ys.min(), xs.max() + 1, ys.max() + 1); ims[n] = (im, m)
    ext = max(max(b[2] - b[0], b[3] - b[1]) for b in boxes.values()); k = SIZE / (ext * 1.1)
    cy = (boxes["front"][1] + boxes["front"][3]) / 2
    out = {}
    for n, (im, m) in ims.items():
        b = boxes[n]; cx = (b[0] + b[2]) / 2; arr = np.asarray(im).copy(); arr[~m] = 0
        canvas = Image.new("RGB", (SIZE, SIZE)); src = Image.fromarray(arr).resize((round(im.width * k), round(im.height * k)), Image.LANCZOS)
        canvas.paste(src, (round(SIZE / 2 - cx * k), round(SIZE / 2 - cy * k)))
        p = os.path.join(out_dir, f"{n}.png"); canvas.save(p); out[n] = p
    log(f"views framed at one scale: {', '.join(out)}")
    return out


def sheet_image(views, out):
    """Contact sheet of the framed views for the progress page."""
    ims = [Image.open(views[n]).convert("RGB").resize((420, 420)) for n in NAMES if n in views]
    s = Image.new("RGB", (420 * len(ims), 420))
    for i, im in enumerate(ims): s.paste(im, (i * 420, 0))
    s.save(out); return out
