"""A hand built the way hands are box-modelled in Blender, all quads, from hand_analysis.py's numbers:
  verts, faces = box_hand(V, h, H)         V: the source mesh's vertices (for the wrist and palm sizes), h: one hand from hand_analysis.analyse, H: body height; real units, world coordinates
The palm is a box lofted from the wrist (a ring of 42 vertices, round) to the knuckle line (a rectangle: 19 columns x 2 rows of faces on its front). On that front face four blocks of 4 x 2 faces are the roots of the
fingers (a column of faces between two blocks is the web); each block's boundary is a ring of 12 vertices that continues as the finger: rings at the joints (a loop at each joint, three phalanges), tapering,
rounding from the block's square to an ellipse, ending in a 4 x 2 grid cap. Fingers grow out of the palm's own edge loops: no seam, no web, one continuous surface. No tris, no n-gons except where the body joins.
Open at the wrist: the ring is at the wrist plane, ready to bridge to the body's ring."""
import numpy as np

COLS, ROWS, NS = 19, 2, 7                                  # palm front: 4 fingers x 4 columns + 3 web columns; two rows deep; seven rings from wrist to knuckle line
RU = (0.14, 0.30, 0.46, 0.61, 0.76, 0.88, 0.97)            # rings along a finger (0 = root, 1 = tip); 0.46 and 0.76 are the joints
BLOCK = [(m, 0) for m in range(5)] + [(4, 1), (4, 2)] + [(m, 2) for m in range(3, -1, -1)] + [(0, 1)]       # the 12-vertex boundary of a finger block, in grid steps


def _ring(cols=COLS, rows=ROWS):
    return [(j, 0) for j in range(cols + 1)] + [(cols, k) for k in range(1, rows + 1)] + [(j, rows) for j in range(cols - 1, -1, -1)] + [(0, k) for k in range(rows - 1, 0, -1)]


def _smooth(t): t = min(1.0, max(0.0, t)); return t * t * (3 - 2 * t)


def _round(x, y, w):
    """Blend a point of the square [-1,1]^2 toward the circle, by w (0 = square, 1 = circle)."""
    return x + (x * np.sqrt(1 - y * y / 2) - x) * w, y + (y * np.sqrt(1 - x * x / 2) - y) * w


def box_hand(V, h, H):
    Pw = np.array(h["wrist_point"]); ax = np.array(h["axis"]); lat = np.array(h["lat"]); pn = np.array(h["palm_normal"]); L = h["hand_len"]; sk = h["knuckle_s"]
    d = V - Pw; s_ = d @ ax; l_ = d @ lat; z_ = d @ pn; tube = np.linalg.norm(d - np.outer(s_, ax), axis=1) < h["tube_radius"]
    pos = lambda l, s, z: Pw + lat * l + ax * s + pn * z
    fl = h["finger_lines"]; sp = fl[0]["spacing"]; bases = [f["m0"] + f["m1"] * sk for f in fl]; lk = float(np.mean(bases)); zk = float(np.mean([f["depth"] for f in fl]))
    fw = 0.90 * sp; cw = fw / 4
    m = (np.abs(s_) < 0.04 * L) & tube; lw = l_[m].mean(); Ww = np.ptp(np.percentile(l_[m], [2, 98])); m = m & (np.abs(l_ - lw) < 0.5 * Ww); zw = z_[m].mean()
    Dw = min(np.ptp(np.percentile(z_[m], [5, 95])), 2.0 * fw)                         # a wrist is about two finger-widths deep (the source's rough surface and the thumb would make it more)
    mk = (np.abs(s_ - sk) < 0.04 * L) & tube & (l_ > min(bases) - fw) & (l_ < max(bases) + fw)       # across the four finger bases only (not the thumb)
    Tk = min(np.ptp(np.percentile(z_[mk], [5, 95])), 1.5 * fw)                        # a palm is about one and a half finger-widths thick at the knuckles
    xs = np.array([(bases[k] - lk) + (-fw / 2 + mm * cw) for k in range(4) for mm in range(5)]); xhalf = float(np.abs(xs).max()); xn = xs / xhalf       # the 20 grid columns at the knuckle line
    verts = []; faces = []; ring = _ring()
    # palm rings: seven from the wrist (round, uniform) to the knuckle line (the rectangle with the finger blocks)
    uni = np.linspace(-1, 1, COLS + 1); rings = []
    for i in range(NS):
        t = _smooth(i / NS); lc = lw + (lk - lw) * t; zc = zw + (zk - zw) * t; hw = Ww / 2 + (xhalf - Ww / 2) * t; hd = Dw / 2 + (Tk / 2 - Dw / 2) * t; w = 1 - t; s = sk * i / NS
        idx = []
        for (j, y) in ring:
            x_, y_ = _round(uni[j] + (xn[j] - uni[j]) * t, float(y - 1), w); idx.append(len(verts)); verts.append(pos(lc + x_ * hw, s, zc + y_ * hd))
        rings.append(idx)
    grid = {}
    for j in range(COLS + 1):                                                                # the front grid at the knuckle line: boundary and interior
        for y in range(ROWS + 1): grid[(j, y)] = len(verts); verts.append(pos(lk + xn[j] * xhalf, sk, zk + (y - 1) * Tk / 2))
    last = [grid[p] for p in ring]; rings.append(last)
    for i in range(NS):
        a, b = rings[i], rings[i + 1]
        for q in range(len(a)): faces.append((a[q], a[(q + 1) % len(a)], b[(q + 1) % len(a)], b[q]))
    for k in range(3):                                                                       # the web faces on the front, between two finger blocks
        j = 5 * k + 4
        for y in range(ROWS): faces.append((grid[(j, y)], grid[(j + 1, y)], grid[(j + 1, y + 1)], grid[(j, y + 1)]))
    # fingers
    for k, f in enumerate(fl):
        scale_w = 0.9 if f["name"] == "pinky" else 1.0; Tf = 0.9 * fw * scale_w
        B = np.array([bases[k], sk, f["depth"]]); T = np.array([f["m0"] + f["m1"] * f["reach"], f["reach"], f["depth"]]); axis_ = T - B
        dw = pos(*T) - pos(*B); dl = np.linalg.norm(dw); dw /= dl; ew = np.cross(pn, dw); ew /= np.linalg.norm(ew); en = np.cross(dw, ew)
        centre = lambda u: pos(*(B + axis_ * u))
        prev = [grid[(5 * k + mm, y)] for (mm, y) in BLOCK]
        for u in list(RU) + [1.0]:
            tip = u == 1.0; taper = 1 - 0.28 * u; wr = 0.6 if tip else 1.0
            hw_ = fw / 2 * scale_w * taper * wr; hd_ = (Tk / 2 + (Tf / 2 - Tk / 2) * _smooth(u / 0.2)) * (1 - 0.30 * u) * wr * (scale_w if scale_w < 1 else 1.0); wf = _smooth(u / 0.25)
            cur = []
            for (mm, y) in BLOCK:
                x_, y_ = _round((mm - 2) / 2.0, float(y - 1), wf); cur.append(len(verts)); verts.append(centre(u) + ew * x_ * hw_ + en * y_ * hd_)
            for q in range(12): faces.append((prev[q], prev[(q + 1) % 12], cur[(q + 1) % 12], cur[q]))
            prev = cur
        capg = {}                                                                            # the 4 x 2 grid cap: the last ring is its boundary, three interior vertices bulge out
        for q, p in enumerate(BLOCK): capg[p] = prev[q]
        for mm in (1, 2, 3):
            x_ = (mm - 2) / 2.0; capg[(mm, 1)] = len(verts); verts.append(centre(1.0) + ew * x_ * hw_ * 0.8 + en * 0.0 + dw * (0.45 * hd_ * (1 - 0.3 * abs(x_))))
        for mm in range(4):
            for y in range(2): faces.append((capg[(mm, y)], capg[(mm + 1, y)], capg[(mm + 1, y + 1)], capg[(mm, y + 1)]))
    info = {"wrist_width": Ww, "wrist_depth": Dw, "palm_depth_at_knuckles": Tk, "finger_width": fw, "finger_spacing": sp, "palm_width_at_knuckles": 2 * xhalf, "palm_length": sk, "finger_lengths": [f["reach"] - sk for f in fl]}
    return np.array(verts), faces, info
