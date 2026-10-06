"""Sharpen the head texture by projecting the (upscaled) front image onto the Pixal3D mesh (see blender_face_project.py)."""
import os, shutil, subprocess, time, numpy as np
from PIL import Image
from scipy import ndimage as ndi
from .. import config as C

_SCRIPT = os.path.join(os.path.dirname(os.path.dirname(__file__)), "blender_face_project.py")

FRAME = None      # mesh-first runs: frame.json of the grey front render (exact camera); None = estimate from the silhouette

def _bl(*args, angle=0, prev=(), region="head"):
    env = dict(os.environ, FACEPROJ_ANGLE=str(angle), FACEPROJ_PREV=",".join(str(a) for a in prev), FACEPROJ_REGION=region)
    if FRAME: env["FACEPROJ_FRAME"] = str(FRAME)
    r = subprocess.run([C.BLENDER, "-b", "--python", _SCRIPT, "--", *map(str, args)], capture_output=True, text=True, timeout=1500, env=env)
    return r.stdout + r.stderr

def _qwen_edit(img, prompt, size, seed, log):
    """One image edit with the already-loaded Qwen-Image (the caller loads and unloads). img: PIL image at `size` (w, h)."""
    import io, requests
    from . import edit as E
    for attempt in range(3):          # Studio can still carry a cancel from the previous job: ask again
        r = E.q.post("/api/inference/images/generate", timeout=900, json={"prompt": prompt, "init_image": E.q.to_b64(img), "reference_resolution": 1024,
                     "workflow": "edit", "width": size[0], "height": size[1], "steps": 30, "seed": seed})
        if r.status_code == 200 or "cancelled" not in r.text: break
        time.sleep(3); E.q.ensure_loaded()
    if r.status_code != 200: raise RuntimeError(f"edit failed: {r.status_code} {r.text[:120]}")
    return Image.open(io.BytesIO(requests.get(f"{E.q.API}/api/inference/images/gallery/{r.json()['images'][0]['id']}/file", timeout=300).content)).convert("RGB")

def _qwen_on(log):
    from . import edit as E
    from .. import gpu
    gpu.free_all(log, keep="studio"); gpu.wait_for_headroom("qwen_image", log); E.q.ensure_loaded()

def _qwen_off():
    from . import edit as E
    try: E.q.post("/api/inference/images/unload")
    except Exception: pass

def _agreement(new_rgb, mesh_rgb, tol=60.0, blur=6.0):
    """1 where the new image roughly agrees in colour with what the mesh already shows (Lab distance after blurring both),
    fading to 0 where it clearly disagrees: misplaced edges (black coat painted onto a white shirt) are refused, real sharpening passes."""
    import cv2
    lab = lambda x: cv2.cvtColor(cv2.GaussianBlur(np.ascontiguousarray(x), (0, 0), blur), cv2.COLOR_RGB2LAB).astype(np.float32)
    d = np.linalg.norm(lab(new_rgb) - lab(mesh_rgb), axis=2)
    return np.clip((tol * 1.5 - d) / (tol * 0.5), 0, 1).astype(np.float32)

def _untextured(rgb):
    """Pixels showing the blank light-grey texture of a model that has not been painted there yet (mesh-first runs)."""
    import cv2
    x = cv2.GaussianBlur(np.ascontiguousarray(rgb), (0, 0), 2).astype(np.float32) / 255
    sat = x.max(2) - x.min(2); v = x.mean(2)
    return (np.clip((0.06 - sat) / 0.03, 0, 1) * np.clip((v - 0.40) / 0.06, 0, 1) * np.clip((0.86 - v) / 0.06, 0, 1)).astype(np.float32)

def _eyes_real(rgb, L):
    """Landmarks on a featureless render are a guess. Real eyes are darker and more contrasted than the cheeks around them."""
    import cv2
    g = cv2.cvtColor(np.ascontiguousarray(rgb), cv2.COLOR_RGB2GRAY).astype(np.float32); H, W = g.shape
    def region(idx):
        m = np.zeros((H, W), np.uint8); cv2.fillPoly(m, [cv2.convexHull(L[idx].astype(np.int32))], 1); return m.astype(bool)
    eyes = region(EYES[0]) | region(EYES[1])
    cheek = region([50, 101, 118, 117, 123, 187, 205, 36]) | region([280, 330, 347, 346, 352, 411, 425, 266])
    if eyes.sum() < 20 or cheek.sum() < 20: return False
    ge = g[eyes]; dark = (ge < g[cheek].mean() - 40).mean(); bright = (ge > np.percentile(ge, 50) + 35).mean()
    # real eyes: dark pupils/lashes AND lighter whites/irises next to them; hair over the eyes is dark all over
    return (g[cheek].mean() - ge.mean() > 18) and ge.std() > 18 and dark > 0.08 and bright > 0.08 and ge.max() - np.percentile(ge, 10) > 70

def _render_fg(rgb):
    bgc = np.median(np.concatenate([rgb[:10].reshape(-1, 3), rgb[:, :10].reshape(-1, 3), rgb[:, -10:].reshape(-1, 3)]), 0).astype(np.float32)
    return ndi.binary_fill_holes(_mask(rgb, bgc, 12))

def _head_box(fg, scale=1.25, cy_frac=0.55):
    rows = np.nonzero(fg.any(1))[0]; top = rows.min(); bh = rows.max() - top; hb = int(0.135 * bh)
    cx = int(np.nonzero(fg[top:top + hb].any(0))[0].mean()); cy = top + int(cy_frac * hb); side = int(scale * hb)
    H, W = fg.shape; x0, y0 = max(0, cx - side // 2), max(0, cy - side // 2)
    return x0, y0, min(W, x0 + side), min(H, y0 + side)

_SESSION = None
def _fgmask(img_path):
    """Person cut-out with rembg (backgrounds are gradients/floors, so colour differencing is unreliable)."""
    global _SESSION
    from rembg import remove, new_session
    if _SESSION is None: _SESSION = new_session("u2net")
    a = np.asarray(remove(Image.open(img_path).convert("RGB"), session=_SESSION))[..., 3]
    return ndi.binary_fill_holes(a > 128)

def _distmap(img_path, out_npy, mask_npy):
    fg = _fgmask(img_path); H = fg.shape[0]; np.save(mask_npy, fg)
    np.save(out_npy, ndi.distance_transform_edt(ndi.binary_erosion(fg, iterations=int(0.004 * H) + 2)).astype(np.float32))
    return fg

def _mask(img, bgc, thr=30):
    return np.abs(img.astype(np.float32) - bgc).sum(2) > thr

def _coarse(render_rgb, img_fg):
    """Similarity (scale + shift) that maps render pixels onto image pixels, fitted on the head-and-shoulders silhouette."""
    rbg = np.median(np.concatenate([render_rgb[:10].reshape(-1, 3), render_rgb[:, :10].reshape(-1, 3)]), 0).astype(np.float32)
    mi = img_fg; mr = ndi.binary_fill_holes(_mask(render_rgb, rbg, 12))
    def band(m):
        rows = np.nonzero(m.any(1))[0]; top = rows.min(); hgt = rows.max() - top
        return top, hgt
    ti, hi = band(mi); tr, hr = band(mr)
    H, W = mi.shape; best = (-1, None)
    ys_i = np.arange(ti, ti + int(0.30 * hi)); ys_i = ys_i[ys_i < H]
    cxr = np.nonzero(mr[tr:tr + int(0.12 * hr)].any(0))[0].mean(); cxi = np.nonzero(mi[ti:ti + int(0.12 * hi)].any(0))[0].mean()
    for k in np.arange(0.70, 1.45, 0.01):
        # image pixel (x, y) <- render pixel ((x - cxi)/k + cxr, (y - ti)/k + tr)
        yy = ((ys_i - ti) / k + tr).astype(int); ok = (yy >= 0) & (yy < H)
        xs = np.arange(W); xx = ((xs - cxi) / k + cxr).astype(int); okx = (xx >= 0) & (xx < W)
        sub_r = np.zeros((len(ys_i), W), bool); sub_r[np.ix_(ok, okx)] = mr[np.ix_(yy[ok], xx[okx])]
        sub_i = mi[ys_i]; inter = (sub_r & sub_i).sum(); uni = (sub_r | sub_i).sum()
        iou = inter / max(uni, 1)
        if iou > best[0]: best = (iou, k)
    iou, k = best
    A = np.array([[k, 0, cxi - k * cxr], [0, k, ti - k * tr]], np.float64)     # image <- render
    return A, iou

def _align(render_png, img_path, out_json, log, img_fg):
    """Coarse silhouette fit (head & shoulders) then ECC refinement on the face, both as image<-render affines."""
    import cv2, json
    R_rgb = np.asarray(Image.open(render_png).convert("RGB")); I_rgb = np.asarray(Image.open(img_path).convert("RGB"))
    A0, iou = _coarse(R_rgb, img_fg); log(f"[faceproj] silhouette fit: scale {A0[0,0]:.3f}, IoU {iou:.2f}")
    H, W = I_rgb.shape[:2]
    # warp the render with the coarse fit so ECC only has to fix the remaining small error
    R_w = cv2.warpAffine(cv2.cvtColor(R_rgb, cv2.COLOR_RGB2GRAY), A0.astype(np.float32), (W, H), borderValue=int(np.median(I_rgb[:20])))
    I_g = cv2.cvtColor(I_rgb, cv2.COLOR_RGB2GRAY)
    fg = img_fg
    top = int(np.nonzero(fg.any(1))[0].min()); y0, y1 = max(0, top - 10), min(H, top + int(0.16 * H))
    cols = np.nonzero(fg[y0:y1].any(0))[0]; x0, x1 = max(0, cols.min() - 10), min(W, cols.max() + 10)
    prep = lambda g: cv2.GaussianBlur(g.astype(np.float32), (0, 0), 3.0)
    T = prep(I_g[y0:y1, x0:x1]); S = prep(R_w[y0:y1, x0:x1])
    refine = np.eye(3)
    for mode in (cv2.MOTION_AFFINE, cv2.MOTION_EUCLIDEAN, cv2.MOTION_TRANSLATION):
        w0 = np.eye(2, 3, dtype=np.float32)
        try:
            cc, w0 = cv2.findTransformECC(T, S, w0, mode, (cv2.TERM_CRITERIA_EPS | cv2.TERM_CRITERIA_COUNT, 300, 1e-6), None, 5)
        except cv2.error: continue
        Wm = np.vstack([w0, [0, 0, 1]]).astype(np.float64); off = np.array([[1, 0, x0], [0, 1, y0], [0, 0, 1]], np.float64)
        cand = off @ np.linalg.inv(Wm) @ np.linalg.inv(off)                 # image <- coarse-warped render
        sx, sy = np.linalg.norm(cand[:2, 0]), np.linalg.norm(cand[:2, 1])
        if cc > 0.5 and 0.9 < sx < 1.1 and 0.9 < sy < 1.1 and abs(cand[0, 2]) < 0.04 * W + 0.1 * W * abs(1 - sx) and abs(cand[1, 2]) < 0.04 * H + 0.1 * H * abs(1 - sy):
            refine = cand; log(f"[faceproj] ECC refinement cc={cc:.3f}"); break
    full = refine @ np.vstack([A0, [0, 0, 1]])
    json.dump({"image_from_render": full[:2].tolist(), "silhouette_iou": float(iou)}, open(out_json, "w"))
    return out_json

# ---------------------------------------------------------------- landmark-based fit (MediaPipe face landmarker, CPU)
LM_MODEL = C.ROOT / "models" / "face_landmarker.task"
FACE_OVAL = [10, 338, 297, 332, 284, 251, 389, 356, 454, 323, 361, 288, 397, 365, 379, 378, 400, 377, 152, 148, 176, 149, 150, 136,
             172, 58, 132, 93, 234, 127, 162, 21, 54, 103, 67, 109]
EYES = [[33, 7, 163, 144, 145, 153, 154, 155, 133, 173, 157, 158, 159, 160, 161, 246], [263, 249, 390, 373, 374, 380, 381, 382, 362, 398, 384, 385, 386, 387, 388, 466]]
BROWS = [[70, 63, 105, 66, 107, 55, 65, 52, 53, 46], [300, 293, 334, 296, 336, 285, 295, 282, 283, 276]]
LIPS = [61, 146, 91, 181, 84, 17, 314, 405, 321, 375, 291, 409, 270, 269, 267, 0, 37, 39, 40, 185]
_DET = None

def _landmarks(rgb, fg):
    """478 face landmarks in pixel coords, or None. The face is small in a full-body frame, so detect on an upscaled head crop."""
    global _DET
    import cv2, mediapipe as mp
    from mediapipe.tasks.python import vision, BaseOptions
    if _DET is None:
        _DET = vision.FaceLandmarker.create_from_options(vision.FaceLandmarkerOptions(base_options=BaseOptions(model_asset_path=str(LM_MODEL)),
                                                         num_faces=1, min_face_detection_confidence=0.1, min_face_presence_confidence=0.1))
    rows = np.nonzero(fg.any(1))[0]; top, bot = rows.min(), rows.max(); hb = bot - top
    cx = int(np.nonzero(fg[top:top + int(0.1 * hb)].any(0))[0].mean()); s = int(0.16 * hb)
    x0, y0 = max(0, cx - s // 2), max(0, top - int(0.02 * hb)); x1, y1 = min(rgb.shape[1], x0 + s), min(rgb.shape[0], y0 + s)
    crop = np.ascontiguousarray(rgb[y0:y1, x0:x1]); k = 512 / crop.shape[1]
    big = np.ascontiguousarray(cv2.resize(crop, (512, int(crop.shape[0] * k)), interpolation=cv2.INTER_CUBIC))
    r = _DET.detect(mp.Image(image_format=mp.ImageFormat.SRGB, data=big))
    if not r.face_landmarks: return None
    return np.array([[l.x * big.shape[1] / k + x0, l.y * big.shape[0] / k + y0] for l in r.face_landmarks[0]], np.float64)

def _tps(P, Q, lam=1e-4):
    """Thin-plate spline P -> Q (n x 2 each). Returns f(points m x 2)."""
    c = P.mean(0); sc = np.abs(P - c).max() or 1.0; Pn = (P - c) / sc
    def U(r2): return np.where(r2 > 0, 0.5 * r2 * np.log(r2 + 1e-12), 0.0)
    n = len(P); d2 = ((Pn[:, None] - Pn[None]) ** 2).sum(-1)
    A = np.zeros((n + 3, n + 3)); A[:n, :n] = U(d2) + lam * np.eye(n); A[:n, n] = 1; A[:n, n + 1:] = Pn; A[n, :n] = 1; A[n + 1:, :n] = Pn.T
    b = np.zeros((n + 3, 2)); b[:n] = Q; W = np.linalg.solve(A, b)
    def f(X):
        Xn = (X - c) / sc; out = np.empty((len(X), 2))
        for i in range(0, len(X), 200000):
            xb = Xn[i:i + 200000]; k = U(((xb[:, None] - Pn[None]) ** 2).sum(-1))
            out[i:i + 200000] = k @ W[:n] + W[n] + xb @ W[n + 1:]
        return out
    return f

def _landmark_fit(render_png, img_path, preview_dir, log, img_fg):
    """Warp the image so its face features sit on the mesh's own features (as seen in the mesh render), keep only the inner face
    (feathered mask in render pixels) and match its skin tone to the mesh texture. Returns (warped_png, mask_npy) or None."""
    import cv2
    R_rgb = np.asarray(Image.open(render_png).convert("RGB")); I_rgb = np.asarray(Image.open(img_path).convert("RGB"))
    H, W = I_rgb.shape[:2]
    rbg = np.median(np.concatenate([R_rgb[:10].reshape(-1, 3), R_rgb[:, :10].reshape(-1, 3)]), 0).astype(np.float32)
    r_fg = ndi.binary_fill_holes(_mask(R_rgb, rbg, 12))
    Lr, Li = _landmarks(R_rgb, r_fg), _landmarks(I_rgb, img_fg)
    if Lr is not None and not _eyes_real(R_rgb, Lr):
        log("[faceproj] landmarks on the mesh render look like a guess (no real eyes there)"); Lr = None
    if Lr is None or Li is None:
        log(f"[faceproj] landmarks not found on the {'mesh render' if Lr is None else 'image'}; using the silhouette fit"); return None
    # control points: a spread of landmarks + a ring far outside the face that follows a plain similarity (smooth hand-over)
    S, _ = cv2.estimateAffinePartial2D(Lr.astype(np.float32), Li.astype(np.float32))
    # eyes: only the corners and the lid centres' midpoint, not the lid outlines - matching every lid point to a squinting mesh would
    # squeeze the picture's open eyes shut again (the mesh reshape before rigging is what opens the mesh's eyes)
    EYE_PTS = [33, 133, 263, 362, 468, 473] if len(Lr) > 473 else [33, 133, 263, 362]
    idx = sorted(set(FACE_OVAL + EYE_PTS + sum(BROWS, []) + LIPS + [1, 4, 5, 6, 168, 197, 195, 98, 327, 2]))
    P = Lr[idx]; Q = Li[idx]
    c = Lr[FACE_OVAL].mean(0); rad = np.abs(Lr[FACE_OVAL] - c).max(0) * 2.2
    ang = np.linspace(0, 2 * np.pi, 28, endpoint=False); ring = c + np.stack([np.cos(ang) * rad[0], np.sin(ang) * rad[1]], 1)
    P = np.vstack([P, ring]); Q = np.vstack([Q, ring @ S[:, :2].T + S[:, 2]])
    f = _tps(P, Q)
    # warped image in render pixels: TPS inside the ring's box, similarity elsewhere
    yy, xx = np.mgrid[0:H, 0:W].astype(np.float32)
    mapx = S[0, 0] * xx + S[0, 1] * yy + S[0, 2]; mapy = S[1, 0] * xx + S[1, 1] * yy + S[1, 2]
    bx0, by0 = np.maximum(0, (c - rad).astype(int)); bx1, by1 = np.minimum([W, H], (c + rad).astype(int))
    gx, gy = np.mgrid[bx0:bx1, by0:by1]; pts = np.stack([gx.ravel(), gy.ravel()], 1).astype(np.float64)
    m = f(pts); mapx[gy.ravel(), gx.ravel()] = m[:, 0]; mapy[gy.ravel(), gx.ravel()] = m[:, 1]
    warped = cv2.remap(I_rgb, mapx.astype(np.float32), mapy.astype(np.float32), cv2.INTER_CUBIC, borderMode=cv2.BORDER_REPLICATE)
    # inner-face mask on the mesh: the oval pulled in a little (more at the forehead, where the hairline differs), feathered;
    # skin = inside the oval but outside eyes, brows and lips (for the tone match)
    mask, skin = _face_mask(Lr, H, W)
    wl = cv2.cvtColor(warped, cv2.COLOR_RGB2LAB).astype(np.float32); rl = cv2.cvtColor(R_rgb, cv2.COLOR_RGB2LAB).astype(np.float32)
    # the new face has to meet the mesh's skin at the mask edge, so match the tones there (the mesh's own painted eyes and
    # brows in the middle would drag the average); drop dark outliers (shadow, stray hair) on both sides
    edge = skin & (mask > 0.15) & (mask < 0.75)
    def stats(lab, m):
        v = lab[m]; v = v[v[:, 0] > np.percentile(v[:, 0], 25)]
        return np.median(v, 0), v.std(0) + 1e-3
    mw, sw = stats(wl, edge); mr, sr = stats(rl, edge)
    gain = np.clip(1 + 0.35 * (sr / sw - 1), 0.85, 1.15)
    # a gentle correction only: the edge of the face can be beard, hair or collar, so a big shift would muddy the whole face (and the eye whites)
    shift = np.clip(0.85 * (mr - mw), [-12, -6, -6], [12, 6, 6])
    matched = np.clip((wl - mw) * gain + mw + shift, 0, 255).astype(np.uint8)
    warped = cv2.cvtColor(matched, cv2.COLOR_LAB2RGB)
    log(f"[faceproj] landmark fit: {len(idx)} points, skin tone shift L{shift[0]:+.0f} a{shift[1]:+.0f} b{shift[2]:+.0f}")
    wpng = os.path.join(preview_dir, "image_warped_to_mesh.png"); Image.fromarray(warped).save(wpng)
    mnpy = os.path.join(preview_dir, "facemask.npy"); np.save(mnpy, mask)
    vis = (R_rgb * 0.5 + warped * 0.5).astype(np.uint8)            # check image: mesh render and warped picture overlaid
    x0, y0 = np.maximum(0, (c - rad / 1.6).astype(int)); x1, y1 = np.minimum([W, H], (c + rad / 1.6).astype(int))
    Image.fromarray(vis[y0:y1, x0:x1]).save(os.path.join(preview_dir, "landmark_overlay.png"))
    return wpng, mnpy

def _face_mask(L, H, W):
    """Feathered inner-face mask from landmarks (render pixels) + the skin-only mask used for colour matching."""
    import cv2
    c = L[FACE_OVAL].mean(0); oval = L[FACE_OVAL].copy(); fw = np.ptp(oval[:, 0])
    shrink = np.where(oval[:, 1] < c[1] - 0.15 * np.ptp(oval[:, 1]), 0.80, 0.90)[:, None]
    poly = c + (oval - c) * shrink
    mask = np.zeros((H, W), np.uint8); cv2.fillPoly(mask, [poly.astype(np.int32)], 255)
    mask = np.clip(cv2.GaussianBlur(mask.astype(np.float32) / 255.0, (0, 0), 0.06 * fw) * 1.15, 0, 1).astype(np.float32)
    skin = np.zeros((H, W), np.uint8); cv2.fillPoly(skin, [poly.astype(np.int32)], 1)
    for part in EYES + BROWS + [LIPS]: cv2.fillPoly(skin, [cv2.convexHull(L[part].astype(np.int32))], 0)
    return mask, cv2.erode(skin, np.ones((5, 5), np.uint8)).astype(bool)

def _paint_features(render_png, preview_dir, log, style, face_desc):
    """Paint a face onto the render of the mesh's (blank) head, with NO reference image: with one, the model redraws the
    reference and ignores the render's layout. Returns (painted full-frame png, render fg mask)."""
    from .. import prompts
    R_rgb = np.asarray(Image.open(render_png).convert("RGB")); rfg = _render_fg(R_rgb)
    x0, y0, x1, y1 = _head_box(rfg); crop = Image.fromarray(R_rgb[y0:y1, x0:x1]); S = 1024
    _qwen_on(log)
    try: face = _qwen_edit(crop.resize((S, S), Image.LANCZOS), prompts.FACE_REPAINT.format(face=face_desc or "the character's face", style=style), (S, S), 5151, log)
    finally: _qwen_off()
    face.save(os.path.join(preview_dir, "repaint_crop.png")); crop.save(os.path.join(preview_dir, "render_crop.png"))
    full = R_rgb.copy(); full[y0:y1, x0:x1] = np.asarray(face.resize((x1 - x0, y1 - y0), Image.LANCZOS))
    painted = os.path.join(preview_dir, "mesh_render_painted.png"); Image.fromarray(full).save(painted)
    return painted, rfg

def _repaint_fit(render_png, img_path, preview_dir, log, style, face_desc="", img_fg=None):
    """For meshes whose face has no readable features: paint features onto the mesh render (they land where this mesh's face is),
    then warp the real reference face onto them with landmarks; if even that fails, use the painted face itself."""
    import cv2
    painted, rfg = _paint_features(render_png, preview_dir, log, style, face_desc)
    if img_fg is not None:
        try:
            fit = _landmark_fit(painted, img_path, preview_dir, log, img_fg)
            if fit: log("[faceproj] repaint located the features; reference face warped onto them"); return fit
        except Exception as e: log(f"[faceproj] warp onto the repaint failed ({type(e).__name__}); using the painted face itself")
    full = np.asarray(Image.open(painted).convert("RGB")); H, W = full.shape[:2]
    L = _landmarks(full, rfg)
    if L is not None:
        mask, _ = _face_mask(L, H, W); how = "landmarks on the repaint"
    else:      # no face found even on the repaint: a feathered ellipse over the lower part of the head box
        x0, y0, x1, y1 = _head_box(rfg); side = x1 - x0; cx = (x0 + x1) // 2
        mask = np.zeros((H, W), np.uint8); cv2.ellipse(mask, (cx, y0 + int(0.58 * side)), (int(0.26 * side), int(0.33 * side)), 0, 0, 360, 255, -1)
        mask = cv2.GaussianBlur(mask.astype(np.float32) / 255.0, (0, 0), 0.04 * side).astype(np.float32); how = "head ellipse"
    mnpy = os.path.join(preview_dir, "facemask.npy"); np.save(mnpy, mask)
    log(f"[faceproj] repaint fit: painted face used directly ({how} for the mask)")
    return painted, mnpy

def reshape(glb_in, img_path, glb_out, preview_dir, log, style="", face_desc=""):
    """Before rigging: move the mesh's face vertices (front-facing, inside the face, capped) so its eyes, nose and mouth sit where the
    reference image has them. Featureless faces are located by painting features onto a render first. Returns glb_out or None."""
    import cv2
    os.makedirs(preview_dir, exist_ok=True); npy = os.path.join(preview_dir, "fgdist.npy"); mnpy = os.path.join(preview_dir, "fgmask.npy")
    fg = _distmap(img_path, npy, mnpy)
    render = os.path.join(preview_dir, "mesh_front.png")
    out = _bl(glb_in, img_path, render, "-", "-", "render", "-", mnpy)
    if "[faceproj] rendered" not in out: raise RuntimeError(f"render failed: {out[-400:]}")
    R_rgb = np.asarray(Image.open(render).convert("RGB")); I_rgb = np.asarray(Image.open(img_path).convert("RGB")); H, W = R_rgb.shape[:2]
    Lr = _landmarks(R_rgb, _render_fg(R_rgb)); how = "mesh render"
    if Lr is not None and not _eyes_real(R_rgb, Lr): Lr = None
    if Lr is None:
        painted, rfg = _paint_features(render, preview_dir, log, style, face_desc)
        Lr = _landmarks(np.asarray(Image.open(painted).convert("RGB")), rfg); how = "features painted onto the render"
    Li = _landmarks(I_rgb, fg)
    if Lr is None or Li is None:
        log(f"[facefit] no face landmarks on the {'mesh' if Lr is None else 'image'}; mesh face left as is"); return None
    idx = sorted(set(FACE_OVAL + sum(EYES, []) + sum(BROWS, []) + LIPS + [1, 4, 5, 6, 168, 197, 195, 98, 327, 2]))
    c = Lr[FACE_OVAL].mean(0); fw = np.ptp(Lr[FACE_OVAL][:, 0]); rad = np.abs(Lr[FACE_OVAL] - c).max(0) * 1.8
    # the face sits where the head is: drop the global offset/scale, keep only how the features differ inside the face
    S, _ = cv2.estimateAffinePartial2D(Li.astype(np.float32), Lr.astype(np.float32)); Li_r = Li @ S[:, :2].T + S[:, 2]
    ang = np.linspace(0, 2 * np.pi, 24, endpoint=False); ring = c + np.stack([np.cos(ang) * rad[0], np.sin(ang) * rad[1]], 1)
    f = _tps(np.vstack([Lr[idx], ring]), np.vstack([Li_r[idx], ring]))
    bx0, by0 = np.maximum(0, (c - rad).astype(int)); bx1, by1 = np.minimum([W, H], (c + rad).astype(int))
    gx, gy = np.mgrid[bx0:bx1, by0:by1]; pts = np.stack([gx.ravel(), gy.ravel()], 1).astype(np.float64)
    D = f(pts) - pts; mag = np.linalg.norm(D, axis=1, keepdims=True); cap = 0.08 * fw
    D = D * np.minimum(1, cap / np.maximum(mag, 1e-6))
    disp = np.zeros((H, W, 2), np.float32); disp[gy.ravel(), gx.ravel()] = D
    mask = np.zeros((H, W), np.uint8); cv2.fillPoly(mask, [(c + (Lr[FACE_OVAL] - c) * 1.05).astype(np.int32)], 255)
    mask = cv2.GaussianBlur(mask.astype(np.float32) / 255.0, (0, 0), 0.08 * fw).astype(np.float32)
    dn = os.path.join(preview_dir, "disp.npy"); fmn = os.path.join(preview_dir, "reshape_mask.npy"); np.save(dn, disp); np.save(fmn, mask)
    out = _bl(glb_in, img_path, glb_out, "-", "-", "reshape", "-", mnpy, fmn, dn)
    if "[faceproj] wrote" not in out: raise RuntimeError(f"reshape failed: {out[-400:]}")
    log(f"[facefit] landmarks from the {how}; " + " ".join(l[11:] for l in out.splitlines() if l.startswith("[faceproj] reshaped")))
    return glb_out

def project_body(glb_in, img_path, glb_out, preview_dir, log, agree_check=True):
    """Front projection of the sharp redraw onto everything below the head (clothes, arms, legs): Pixal3D's mesh is pixel-aligned
    with its input, so the front gets the redraw's real detail. The head is left to the face passes."""
    os.makedirs(preview_dir, exist_ok=True); npy = os.path.join(preview_dir, "fgdist.npy"); mnpy = os.path.join(preview_dir, "fgmask.npy")
    _distmap(img_path, npy, mnpy)
    rpng = os.path.join(preview_dir, "body_render.png")
    out = _bl(glb_in, img_path, rpng, "-", "-", "render", "-", mnpy)
    if "[faceproj] rendered" not in out: raise RuntimeError(f"render failed: {out[-400:]}")
    I_rgb = np.asarray(Image.open(img_path).convert("RGB")); R_rgb = np.asarray(Image.open(rpng).convert("RGB").resize((I_rgb.shape[1], I_rgb.shape[0])))
    # with an exact camera (mesh-first) there is nothing to misplace, and a blank model would "disagree" with every colour
    agree = _agreement(I_rgb, R_rgb) if agree_check else np.ones(I_rgb.shape[:2], np.float32)
    agree = np.maximum(agree, _untextured(R_rgb)); an = os.path.join(preview_dir, "body_agree.npy"); np.save(an, agree)
    out = _bl(glb_in, img_path, glb_out, "-", npy, "project", "-", mnpy, an, region="body" if agree_check else "full")   # exact camera: head and hair too
    if "[faceproj] wrote" not in out: raise RuntimeError(f"body projection failed: {out[-400:]}")
    fg = np.load(mnpy); log(f"[texture] clothes and body: front of the redraw projected where it agrees with the mesh ({100 * agree[fg].mean():.0f}% of the figure)")
    return glb_out

def multiview(glb_in, img_path, glb_out, preview_dir, log, style="", desc="", views=None, paint_grey=False):
    """Turn the model, let the image model clean up each view's render (keeping its layout), project it back where that view sees
    the surface better than the views before it. Views whose outline the edit changed are skipped."""
    from .. import prompts
    os.makedirs(preview_dir, exist_ok=True); mnpy = os.path.join(preview_dir, "fgmask.npy")
    if not os.path.exists(mnpy): _distmap(img_path, os.path.join(preview_dir, "fgdist.npy"), mnpy)
    views = views or [(35, "head"), (-35, "head"), (60, "full"), (-60, "full"), (180, "full")]
    VIEW = {35: "from the front, turned about 35 degrees to one side", -35: "from the front, turned about 35 degrees to the other side",
            60: "turned about 60 degrees to one side", -60: "turned about 60 degrees to the other side", 180: "from behind"}
    WHAT = {"head": "the hair, ears, cheeks, jaw and neck", "full": "the hair and the clothing"}
    cur = glb_in; done = [0]; _qwen_on(log)
    try:
        for i, (ang, region) in enumerate(views):
            tag = f"v{'p' if ang >= 0 else 'm'}{abs(ang)}"; rpng = os.path.join(preview_dir, f"{tag}_render.png")
            out = _bl(cur, img_path, rpng, "-", "-", "render", "-", mnpy, angle=ang)
            if "[faceproj] rendered" not in out: log(f"[texture] view {ang}: render failed"); continue
            R_rgb = np.asarray(Image.open(rpng).convert("RGB")); rfg = _render_fg(R_rgb); H, W = rfg.shape
            if region == "head": x0, y0, x1, y1 = _head_box(rfg, scale=1.5, cy_frac=0.5)
            else:
                ys, xs = np.nonzero(rfg); pad = int(0.04 * H)
                x0, y0, x1, y1 = max(0, xs.min() - pad), max(0, ys.min() - pad), min(W, xs.max() + pad), min(H, ys.max() + pad)
            crop = Image.fromarray(R_rgb[y0:y1, x0:x1]); cw, ch = crop.size; k = 1152 / max(cw, ch)
            size = (max(64, int(cw * k) // 32 * 32), max(64, int(ch * k) // 32 * 32))
            shot = "a close-up crop of the head and shoulders" if region == "head" else "a full-body render"
            grey_share = float(_untextured(np.asarray(crop))[_render_fg(np.asarray(crop))].mean()) if _render_fg(np.asarray(crop)).any() else 0
            tmpl = prompts.VIEW_PAINT if (paint_grey or grey_share > 0.08) else prompts.VIEW_FIX
            fixed = _qwen_edit(crop.resize(size, Image.LANCZOS), tmpl.format(shot=shot, view=VIEW.get(ang, f"turned {ang} degrees"), what=WHAT[region],
                                                                             desc=desc, style=style), size, 6060 + i, log)
            fixed = fixed.resize((cw, ch), Image.LANCZOS); fixed.save(os.path.join(preview_dir, f"{tag}_fixed.png"))
            a = _render_fg(np.asarray(fixed)); b_ = rfg[y0:y1, x0:x1]; iou = (a & b_).sum() / max((a | b_).sum(), 1)
            if iou < 0.80: log(f"[texture] view {ang}: the edit changed the outline (IoU {iou:.2f}); skipped"); continue
            full = R_rgb.copy(); full[y0:y1, x0:x1] = np.asarray(fixed); fpng = os.path.join(preview_dir, f"{tag}_full.png"); Image.fromarray(full).save(fpng)
            dn = os.path.join(preview_dir, f"{tag}_dist.npy")
            np.save(dn, ndi.distance_transform_edt(ndi.binary_erosion(rfg, iterations=int(0.004 * H) + 2)).astype(np.float32))
            nxt = os.path.join(preview_dir, f"{tag}.glb")
            an = os.path.join(preview_dir, f"{tag}_agree.npy")
            np.save(an, np.maximum(_agreement(full, R_rgb, tol=45.0, blur=4.0), _untextured(R_rgb)))      # still-grey areas take the new paint
            out = _bl(cur, fpng, nxt, "-", dn, "project", "-", mnpy, an, angle=ang, prev=done, region=region if region == "full" else "headview")
            if "[faceproj] wrote" not in out: log(f"[texture] view {ang}: projection failed"); continue
            cur = nxt; done.append(ang); log(f"[texture] view {ang} ({region}): cleaned and projected (outline IoU {iou:.2f})")
    finally: _qwen_off()
    if cur == glb_in: return None
    shutil.copy(cur, glb_out); shutil.copy(cur[:-4] + "_basecolor.png", glb_out[:-4] + "_basecolor.png")
    return glb_out

def run(glb_in, img_path, glb_out, preview_dir, log, style="", method="auto", face_desc=""):
    os.makedirs(preview_dir, exist_ok=True); npy = os.path.join(preview_dir, "fgdist.npy"); mnpy = os.path.join(preview_dir, "fgmask.npy")
    fg = _distmap(img_path, npy, mnpy)
    bl = _bl
    render = os.path.join(preview_dir, "mesh_in_image_grid.png")
    out = bl(glb_in, img_path, render, "-", "-", "render", "-", mnpy)
    if "[faceproj] rendered" not in out: raise RuntimeError(f"face projection render failed: {out[-800:]}")
    fit = None
    if method in ("auto", "landmarks"):
        try: fit = _landmark_fit(render, img_path, preview_dir, log, fg)
        except Exception as e: log(f"[faceproj] landmark fit failed ({type(e).__name__}: {str(e)[:120]})")
    if not fit and method in ("auto", "repaint"):
        try: fit = _repaint_fit(render, img_path, preview_dir, log, style, face_desc, fg)
        except Exception as e: log(f"[faceproj] repaint fit failed ({type(e).__name__}: {str(e)[:120]}); using the silhouette fit")
    if fit:      # the warped image already lives in mesh-render pixels: no affine, inner-face mask only
        out = bl(glb_in, fit[0], glb_out, preview_dir, npy, "project", "-", mnpy, fit[1])
    else:
        aff = _align(render, img_path, os.path.join(preview_dir, "affine.json"), log, fg)
        out = bl(glb_in, img_path, glb_out, preview_dir, npy, "project", aff or "-", mnpy)
    if "[faceproj] wrote" not in out: raise RuntimeError(f"face projection failed: {out[-800:]}")
    log(" | ".join(l for l in out.splitlines() if l.startswith("[faceproj]")))
    return glb_out, os.path.join(preview_dir, "face_before.png"), os.path.join(preview_dir, "face_after.png")
