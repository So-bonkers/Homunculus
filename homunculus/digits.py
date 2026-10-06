"""Count each hand's digits from its multi-view grey renders: in the most open view (largest silhouette), the deep notches
between digits are convexity defects of the hand outline; digits = notches + 1. Exact for open/spread hands and immune
to the VLM's miscounting.  usage: python digits.py <render_dir> <tag>  -> {"right": n, "left": n, ...}"""
import sys, os, json, numpy as np, cv2

def hand_digits(png):
    im = cv2.imread(png); g = cv2.cvtColor(im, cv2.COLOR_BGR2GRAY)
    bg = np.median(np.concatenate([g[:5].ravel(), g[-5:].ravel(), g[:, :5].ravel(), g[:, -5:].ravel()]))
    m = (np.abs(g.astype(int) - int(bg)) > 6).astype(np.uint8) * 255
    m = cv2.morphologyEx(m, cv2.MORPH_OPEN, np.ones((5, 5), np.uint8))
    cs, _ = cv2.findContours(m, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_NONE)
    if not cs: return 0, 0, 0
    c = max(cs, key=cv2.contourArea); area = cv2.contourArea(c)
    (_, _), (w, h), _ = cv2.minAreaRect(c); size = max(w, h)
    hull = cv2.convexHull(c, returnPoints=False)
    try: defects = cv2.convexityDefects(c, hull)
    except cv2.error: defects = None
    deep = 0
    if defects is not None:
        for s, e, f, depth in defects.reshape(-1, 4):
            if depth / 256.0 < 0.06 * size: continue
            a, b, p = c[s][0], c[e][0], c[f][0]
            v1, v2 = a - p, b - p
            ang = np.degrees(np.arccos(np.clip(np.dot(v1, v2) / (np.linalg.norm(v1) * np.linalg.norm(v2) + 1e-9), -1, 1)))
            if ang < 95: deep += 1                     # notch between two digits is a sharp V
    # the sleeve/forearm edge can add at most one wide, shallow notch which the angle test removes
    return deep + 1, area, deep

def count(render_dir, tag="mesh"):
    out = {}
    for side, h in (("right", "handR"), ("left", "handL")):
        vf = os.path.join(render_dir, f"{tag}_{h}_views.txt")
        views = open(vf).read().split(",") if os.path.exists(vf) else []
        best = None
        for v in views:
            n, area, _ = hand_digits(os.path.join(render_dir, f"{tag}_{h}_{v}.png"))
            if best is None or area > best[1]: best = (n, area, v)
        out[side] = best[0] if best else 0; out[side + "_view"] = best[2] if best else None
    return out

if __name__ == "__main__":
    print(json.dumps(count(sys.argv[1], sys.argv[2] if len(sys.argv) > 2 else "mesh")))
