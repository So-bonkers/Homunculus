"""Where a character's hands, wrists and fingers are, found from the mesh itself with ratios, no measured distances. numpy only (milliseconds).
  analyse(V) -> {"height": H, "R": hand, "L": hand}     V: Nx3 vertices, z up, arms out to the sides (+x = "R", -x = "L"; an A- or T-pose).
A hand is a dict: wrist_point, axis (wrist -> fingertip), lat (across the hand), palm_normal, centre, hand_len, slit_lats, slit_start, fingers {name: [lo, hi]} (lateral ranges, from the thumb: thumb, index, middle, ring, pinky), ok, notes.
Every length is a fraction of the body height H (the only scale) or of the hand length found from the wrist:
  - arm / hand region: the outer 45 % of the lateral extent; the arm axis is that part's first principal axis; the fingertip is its farthest point along the axis;
  - wrist: the narrowest cross-section (sqrt of the covariance determinant) between 0.07 H and 0.17 H behind the fingertip (a hand is ~0.11 H long);
  - fingers: bins of 0.0022 H across the hand; each bin's reach along the axis; the peaks (at least 0.0088 H apart: a finger is that wide) are the fingers, the valleys between them the gaps; five peaks expected,
    the thumb is the end peak that reaches less far (a quarter to a half of the others'); the order from it is thumb, index, middle, ring, pinky;
  - slots between the fingers start where a real hand's web ends: the palm is ~55 % of the hand, the first finger segment ~40 % of the rest, the web ends a third of the way along it (0.55 + 0.3 * 0.4 * 0.45 = 0.604 of the hand length).
Source hands are often webbed or fused further out than that: that is why the slots are cut, not read from where the gaps are."""
import numpy as np

PALM = 0.55; SEGMENT = 0.40; WEB = 0.30             # palm / hand, first finger segment / finger, web depth / first segment (standard hand proportions)
NAMES = ("thumb", "index", "middle", "ring", "pinky")
ARCH = {"index": 0.03, "middle": 0.0, "ring": 0.03, "pinky": 0.07}      # how far behind the middle finger's root each finger's root is, as a fraction of the hand length: the knuckles lie on an arch, not a line


def _area(P):
    """Cross-section size of a point set: sqrt(det of the 2x2 covariance in the plane of the two main axes)."""
    if len(P) < 8: return 0.0
    c = P - P.mean(0); s = np.linalg.svd(c, compute_uv=False)
    return float(s[0] * s[1]) / len(P)


def _smooth(a): return np.convolve(np.pad(a, 1, mode="edge"), [0.25, 0.5, 0.25], mode="valid")


def hand(V, sg, H):
    x = V[:, 0] * sg; xmax = x.max(); seed = V[np.argmax(x)]                         # the point farthest out to the side: on the hand
    tip = seed; ax = None
    for _ in range(2):                                                               # the arm's axis from what lies within 0.14 H of the fingertip (hand and wrist: legs and feet are never that close)
        near = V[np.linalg.norm(V - tip, axis=1) < 0.14 * H]; c = near.mean(0); a = np.linalg.svd(near - c, full_matrices=False)[2][0]
        if a @ ((seed - c) if ax is None else ax) < 0: a = -a                         # toward the fingertip; later passes keep the first pass's direction
        ax = a; tip = near[np.argmax(near @ ax)]
    d = V - tip; t = d @ ax; r = np.linalg.norm(d - np.outer(t, ax), axis=1)
    arm = (r < 0.1 * H) & (t <= 1e-9) & (t > -0.2 * H) & (x > 0.3 * xmax)           # a tube round the arm axis, from the fingertip back 0.2 H
    bw = H / 400; bins = np.floor(-t[arm] / bw).astype(int); A = arm.nonzero()[0]
    nb = bins.max() + 1; prof = np.zeros(nb)
    for b in range(nb):
        m = A[bins == b]; prof[b] = _area(V[m])
    prof = _smooth(_smooth(prof)); lo, hi = int(0.07 * H / bw), int(0.17 * H / bw)
    wb = lo + int(np.argmin(prof[lo:hi])); wrist_s = (wb + 0.5) * bw                  # distance of the wrist back from the fingertip
    Pw = tip - ax * wrist_s; hand_len = wrist_s
    m = arm & (-t < wrist_s); Hv = V[m]; cc = Hv.mean(0)
    pn = np.linalg.svd(Hv - cc, full_matrices=False)[2][2]; lat = np.cross(ax, pn); lat /= np.linalg.norm(lat)
    s = (Hv - Pw) @ ax; l = (Hv - Pw) @ lat
    far = s > 0.3 * hand_len                                                         # beyond the heel of the palm: the thumb's tip reaches a little past half the hand
    fb = 0.0022 * H; l0 = l[far].min(); idx = np.floor((l[far] - l0) / fb).astype(int); reach = np.zeros(idx.max() + 1)
    np.maximum.at(reach, idx, s[far]); reach = _smooth(reach)
    pk = [i for i in range(1, len(reach) - 1) if reach[i] >= reach[i - 1] and reach[i] > reach[i + 1] and reach[i] > 0.35 * reach.max()]
    mind = max(1, int(round(0.0088 * H / fb))); keep = []
    for i in sorted(pk, key=lambda i: -reach[i]):                                    # taller peaks first; drop any peak closer than a finger's width to a kept one
        if all(abs(i - j) >= mind for j in keep): keep.append(i)
    keep.sort(); notes = []; ok = len(keep) == 5
    if not ok: notes.append(f"found {len(keep)} fingers (expected 5)")
    out = {"wrist_point": Pw.tolist(), "axis": ax.tolist(), "lat": lat.tolist(), "palm_normal": pn.tolist(), "centre": cc.tolist(), "tip": tip.tolist(), "hand_len": float(hand_len),
           "tube_radius": 0.1 * H, "ok": ok, "notes": notes, "peaks": [[float(l0 + (i + 0.5) * fb), float(reach[i])] for i in keep]}
    if ok:
        valleys = [keep[k] + int(np.argmin(reach[keep[k]:keep[k + 1] + 1])) for k in range(4)]; vl = [float(l0 + (v + 0.5) * fb) for v in valleys]      # ascending along lat
        thumb_low = reach[keep[0]] < reach[keep[-1]]                                 # the thumb is the end peak that reaches less far
        order = NAMES if thumb_low else NAMES[::-1]; edges = [-1e9] + vl + [1e9]
        out["fingers"] = {order[k]: [edges[k], edges[k + 1]] for k in range(5)}
        out["slit_lats"] = vl[1:] if thumb_low else vl[:-1]                          # the three gaps between index, middle, ring and pinky (the thumb's gap is a joint, not a web)
        out["thumb_side"] = "low" if thumb_low else "high"
        # the slots follow the grooves: the fingers fan out, so a slot at one fixed lateral position drifts off the groove. Each finger's centre is tracked across cross-sections along the hand
        # (k-means on the lateral positions of the vertices in the slice, started from the fingertips), and a slot is the line midway between two neighbouring fingers' centres: lat = m0 + m1 * s.
        fi = keep[1:] if thumb_low else keep[:-1]; cen = [float(l0 + (i + 0.5) * fb) for i in fi]; rch = [float(reach[i]) for i in fi]
        step = 0.05 * hand_len; s_start = (PALM + WEB * SEGMENT * (1 - PALM)) * hand_len; track = [[] for _ in fi]
        sk = max(rch) - 0.5 * step
        while sk > s_start:
            lp = l[np.abs(s - sk) < 0.5 * step]; act = [k for k in range(4) if sk < rch[k] - 0.3 * step]
            if len(lp) > 30 and len(act) >= 2:
                c = np.array([cen[k] for k in act])
                for _ in range(4):
                    a_ = np.argmin(np.abs(lp[:, None] - c[None, :]), axis=1)
                    c = np.array([lp[a_ == q].mean() if (a_ == q).any() else c[q] for q in range(len(act))])
                for q, k in enumerate(act): cen[k] = float(c[q]); track[k].append((sk, float(c[q])))
            sk -= step
        lines = []
        for a_ in range(3):
            ta = dict(track[a_]); tb = dict(track[a_ + 1]); both = sorted(set(ta) & set(tb))
            if len(both) >= 3: m1, m0 = np.polyfit(both, [(ta[x] + tb[x]) / 2 for x in both], 1)
            else: m0, m1 = (cen[a_] + cen[a_ + 1]) / 2, 0.0
            if abs(m1) > 0.15: m1 = float(np.clip(m1, -0.15, 0.15)); m0 = float(np.mean([(ta[x] + tb[x]) / 2 - m1 * x for x in both])) if len(both) >= 3 else m0      # fingers fan by a few degrees, not 15: a steeper fit is the tracking, not the hand
            lines.append([float(m0), float(m1)])
        # each finger as a line from its base to its tip, for rebuilding the fingers from scratch. Tips: the peaks of the reach profile (reliable). Bases: the hand's width at the knuckle line (the thumb ends
        # below it) shared evenly between the four fingers, as a hand's four knuckles are about equally spaced. Names run from the thumb side; ascending along lat.
        names4 = ["index", "middle", "ring", "pinky"] if thumb_low else ["pinky", "ring", "middle", "index"]; fl = []
        sk_ = PALM * hand_len; band = np.abs(s - sk_) < 0.04 * hand_len
        lo_, hi_ = np.percentile(l[band], [1.5, 98.5]); wd = (hi_ - lo_) / 4
        for k in range(4):
            base = float(lo_ + (k + 0.5) * wd); tipl = cen[k] if False else float(l0 + (fi[k] + 0.5) * fb); reach_k = rch[k]
            m1 = (tipl - base) / (reach_k - sk_); m0 = base - m1 * sk_
            near = (np.abs(l - (m0 + m1 * s)) < 0.4 * wd) & (s > sk_) & (s < reach_k)
            fl.append({"name": names4[k], "m0": float(m0), "m1": float(m1), "reach": float(reach_k), "depth": float(((Hv - Pw) @ pn)[near].mean()) if near.sum() > 20 else float(((Hv - Pw) @ pn)[band].mean()), "spacing": float(wd), "root_offset": float(ARCH[names4[k]] * hand_len)})
        out["finger_lines"] = fl
        out["knuckle_s"] = float(PALM * hand_len)
        out["slits"] = lines if thumb_low else lines[::-1]                           # (m0, m1) per slot, in the same order as slit_lats
        out["slit_lats"] = sorted(out["slit_lats"]) if False else out["slit_lats"]
    out["slit_start"] = float((PALM + WEB * SEGMENT * (1 - PALM)) * hand_len)        # along the hand from the wrist
    return out


def analyse(V):
    V = np.asarray(V, np.float64); H = float(V[:, 2].max() - V[:, 2].min())
    return {"height": H, "R": hand(V, 1, H), "L": hand(V, -1, H)}


if __name__ == "__main__":
    import json, sys
    V = np.loadtxt(sys.argv[1]) if len(sys.argv) > 1 else None
    print(json.dumps(analyse(V), indent=1))
