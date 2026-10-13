"""Camera motion of a video from its background: pan / tilt / roll and zoom per frame, relative to frame 0.

    gvhmr/.venv/bin/python tools/track_camera.py <clip.mp4> <out.npz> [--bbx gvhmr/work/out/<clip>/preprocess/bbx.pt] [--focal PX] [--step N]

Sparse optical flow (Lucas-Kanade, checked backwards) on corner features OUTSIDE the dancer's box, a homography per frame pair (RANSAC), chained over the clip.
The camera is treated as turning about its own centre (pan, tilt, roll) and zooming: H = K_t R K_0^-1 with K = [f 0 cx; 0 f cy; 0 0 1], so for every chained homography the focal f_t is the
one that makes K_t^-1 H K_0 closest to a rotation, and R is that rotation. Hand-held translation shows up as a little extra rotation, which is what is wanted for re-framing a render.
Writes: R (N, 3, 3) camera rotation relative to frame 0 in the image convention (x right, y down, z forward): a ray d0 of frame 0 is d_t = R_t d0, f (N,) focal length in pixels, f0, size (w, h),
ok (N,) False where too few background features were found (the previous frame's motion was kept). The focal length of frame 0 is a guess (GVHMR's 1468 px at 1280x720 unless --focal)."""
import sys, numpy as np, cv2
a = sys.argv[1:]
def opt(flag, default, cast=str):
    if flag in a: i = a.index(flag); v = a[i + 1]; del a[i:i + 2]; return cast(v)
    return default
bbx_path = opt("--bbx", None); f0 = opt("--focal", None, float); STEP = opt("--step", 1, int)
src, dst = a[0], a[1]
cap = cv2.VideoCapture(src); W0 = int(cap.get(3)); H0 = int(cap.get(4)); N = int(cap.get(7)); SC = 0.5; w, h = int(W0 * SC), int(H0 * SC)
f0 = (f0 or 1468.6 * W0 / 1280.0) * SC; cx, cy = w / 2, h / 2
bbx = None
if bbx_path:
    import torch; bbx = torch.load(bbx_path, map_location="cpu", weights_only=False)["bbx_xyxy"].numpy() * SC
def K(f): return np.array([[f, 0, cx], [0, f, cy], [0, 0, 1.0]])
def person_mask(i):
    m = np.full((h, w), 255, np.uint8)
    if bbx is not None:
        x0, y0, x1, y1 = bbx[min(i, len(bbx) - 1)]; pw, ph = (x1 - x0) * 0.25, (y1 - y0) * 0.15
        m[max(0, int(y0 - ph)):int(y1 + ph) + 1, max(0, int(x0 - pw)):int(x1 + pw) + 1] = 0
    m[:int(h * 0.04)] = 0; m[-int(h * 0.04):] = 0; m[:, :int(w * 0.02)] = 0; m[:, -int(w * 0.02):] = 0                      # frame borders (vignette, letterbox)
    return m
def gray(fr): return cv2.GaussianBlur(cv2.cvtColor(cv2.resize(fr, (w, h), interpolation=cv2.INTER_AREA), cv2.COLOR_BGR2GRAY), (3, 3), 0)
lk = dict(winSize=(21, 21), maxLevel=3, criteria=(cv2.TERM_CRITERIA_EPS | cv2.TERM_CRITERIA_COUNT, 30, 0.01))
ok_, fr = cap.read(); prev = gray(fr); Hs = [np.eye(3)]; good = [True]; acc = np.eye(3); last = np.eye(3)
for i in range(1, N):
    ok_, fr = cap.read()
    if not ok_: break
    cur = gray(fr)
    p0 = cv2.goodFeaturesToTrack(prev, 600, 0.01, 8, mask=person_mask(i - 1))
    Hd = None
    if p0 is not None and len(p0) > 30:
        p1, s1, _ = cv2.calcOpticalFlowPyrLK(prev, cur, p0, None, **lk); pb, s2, _ = cv2.calcOpticalFlowPyrLK(cur, prev, p1, None, **lk)
        k = (s1[:, 0] == 1) & (s2[:, 0] == 1) & (np.linalg.norm(p0 - pb, axis=-1)[:, 0] < 0.5)
        if k.sum() > 30:
            Hm, inl = cv2.findHomography(p0[k], p1[k], cv2.RANSAC, 1.5)
            if Hm is not None and inl.sum() > 25: Hd = Hm
    good.append(Hd is not None); Hd = last if Hd is None else Hd; last = Hd; acc = Hd @ acc; Hs.append(acc.copy()); prev = cur
    if i % 600 == 0: print(f"[track_camera] {i}/{N}", flush=True)
Hs = np.array(Hs); n = len(Hs); Rs = np.zeros((n, 3, 3)); fs = np.zeros(n); K0i = K(f0)
for i, Hm in enumerate(Hs):
    best = None
    for f in np.geomspace(f0 * 0.5, f0 * 2.5, 241):
        A = np.linalg.inv(K(f)) @ Hm @ K0i; A /= np.cbrt(np.linalg.det(A)); e = np.linalg.norm(A.T @ A - np.eye(3))
        if best is None or e < best[0]: best = (e, f, A)
    _, f, A = best; U, _, Vt = np.linalg.svd(A); R = U @ Vt
    if np.linalg.det(R) < 0: R = -R
    Rs[i] = R; fs[i] = f
np.savez(dst, R=Rs, f=fs / SC, f0=f0 / SC, size=np.array([W0, H0]), ok=np.array(good))
from scipy.spatial.transform import Rotation as Rot
e = Rot.from_matrix(Rs).as_euler("YXZ", degrees=True)
print(f"[track_camera] {n} frames; background found in {np.mean(good) * 100:.0f}% of the pairs; pan range {np.ptp(e[:, 0]):.1f} deg, tilt {np.ptp(e[:, 1]):.1f} deg, roll {np.ptp(e[:, 2]):.1f} deg, zoom x{fs.min() / fs[0]:.2f}..x{fs.max() / fs[0]:.2f} -> {dst}")
