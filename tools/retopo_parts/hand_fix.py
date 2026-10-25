"""Corrections to a hand mesh built from four generated views, before it is remeshed. numpy only. The hand is held with the fingers along +z, the palm facing -y (the way tools/hand_views.py draws it).
  thicken_fingers(V) -> V2, info      the edge-on views the image model draws are thinner than a real hand, so the fingers come out flattened (depth / width about 0.45; a finger is about 0.85).
Measured on the mesh itself: the fingers' depth-to-width ratio from cross-sections across them, the knuckle line from where the cross-section first splits into separate fingers; the finger zone is then stretched
along y (about each slice's own centre) by 0.85 / ratio, fading in over a band below the knuckle line so the palm is not torn. Ratios and bands are fractions of the hand's own length."""
import numpy as np

FINGER_RATIO = 0.85          # depth / width of a finger


def _runs(xs, gap):
    xs = np.sort(xs); br = np.where(np.diff(xs) > gap)[0]; st = np.r_[0, br + 1]; en = np.r_[br, len(xs) - 1]; return [(xs[s], xs[e]) for s, e in zip(st, en)]


def thicken_fingers(V, up=2, depth=1, across=0):
    V = np.asarray(V, np.float64); z = V[:, up]; zmax, zmin = z.max(), z.min(); span = zmax - zmin; gap = 0.006 * span
    split = None; ratios = []
    for zz in np.arange(zmax - 0.02 * span, zmin, -0.01 * span):                      # walk down from the fingertips to where the slice stops being separate fingers
        sl = V[np.abs(z - zz) < 0.004 * span]
        if len(sl) < 50: continue
        rr = [r for r in _runs(sl[:, across], gap) if r[1] - r[0] > 0.02 * span]
        if len(rr) >= 3:
            if zz < zmax - 0.08 * span:
                for x0, x1 in rr:
                    s = sl[(sl[:, across] >= x0) & (sl[:, across] <= x1)]; ratios.append(np.ptp(s[:, depth]) / (x1 - x0))
            split = zz
        elif split is not None: break
    r = float(np.median(ratios)); f = float(np.clip(FINGER_RATIO / r, 1.0, 2.2)); band = 0.09 * span
    t = np.clip((z - (split - band)) / (2 * band), 0, 1); w = 1 + (f - 1) * t * t * (3 - 2 * t)
    zb = np.floor((z - zmin) / (0.01 * span)).astype(int); cen = np.zeros(zb.max() + 1)
    for b in np.unique(zb): cen[b] = np.median(V[zb == b, depth])
    cen = np.convolve(np.pad(cen, 3, mode="edge"), np.ones(7) / 7, mode="valid")
    V2 = V.copy(); c = cen[zb]; V2[:, depth] = c + (V[:, depth] - c) * w
    return V2, {"measured_ratio": r, "factor": f, "knuckle_split_z": float(split), "band": band}


def add_relief(V, info, up=2, depth=1, across=0, palm_side=-1):
    """The relief a hand has and the generated one lacks (its edge-on views are flat): the mound at the base of the thumb and the pad on the little-finger side, a slight cup in the middle of the palm, the four knuckles
    and a shallow dome on the back. Gaussian bumps along the depth axis, each on its own side of the hand (the palm faces `palm_side` along `depth`). All positions come from the mesh: the knuckle line and the finger centres from the
    cross-sections (info from thicken_fingers), the wrist from the standard proportion (the palm is 55 % of the hand), the thumb side from the side the mesh sticks out on; all sizes are fractions of the palm width W."""
    V = np.asarray(V, np.float64); z = V[:, up]; x = V[:, across]; y = V[:, depth]; zmax, zmin = z.max(), z.min(); span = zmax - zmin; zs = info["knuckle_split_z"]
    sl = V[np.abs(z - (zs + 0.05 * span)) < 0.004 * span]; rr = [r for r in _runs(sl[:, across], 0.006 * span) if r[1] - r[0] > 0.02 * span]
    cx = [(a + b) / 2 for a, b in rr]; xl, xr = rr[0][0], rr[-1][1]; xc = (xl + xr) / 2; W = xr - xl; half = W / 2
    ts = 1.0 if (x.max() - xr) > (xl - x.min()) else -1.0                                  # which side the thumb is on
    zw = (zs - 0.55 * zmax) / 0.45; Lp = zs - zw; t = (z - zw) / Lp; u = (x - xc) / half   # t: 0 at the wrist, 1 at the knuckle line; u: -1..1 across the palm
    zb = np.floor((z - zmin) / (0.01 * span)).astype(int); cen = np.zeros(zb.max() + 1)
    for b in np.unique(zb): cen[b] = np.median(y[zb == b])
    cen = np.convolve(np.pad(cen, 3, mode="edge"), np.ones(7) / 7, mode="valid"); c = cen[zb]
    pal = np.clip(0.5 + ((y - c) * palm_side) / (0.04 * span), 0, 1)                          # palm side = the side the palm faces
    bak = 1 - pal
    g = lambda u0, t0, ru, rt: np.exp(-((u - u0) / ru) ** 2 - ((t - t0) / rt) ** 2)
    out = np.zeros(len(V))                                                                  # displacement away from the centre, positive = toward the palm side
    out += pal * (0.09 * W * g(ts * 0.72, 0.30, 0.42, 0.24) + 0.05 * W * g(-ts * 0.74, 0.36, 0.30, 0.22))      # thumb-base mound and the pad on the little-finger side
    out -= pal * 0.035 * W * g(0.0, 0.58, 0.45, 0.22)                                      # the cup in the middle of the palm
    out -= bak * 0.04 * W * np.clip(1 - u * u, 0, 1) * np.clip(np.sin(np.pi * np.clip((t - 0.05) / 0.95, 0, 1)), 0, 1)     # the back of the hand: a shallow dome
    for xk in cx: out -= bak * 0.07 * W * g((xk - xc) / half, 1.0, 0.20, 0.10)             # the four knuckles
    V2 = V.copy(); V2[:, depth] = y + out * palm_side
    return V2, {"palm_width": W, "thumb_side": ts, "wrist_z": zw, "knuckles": len(cx)}
