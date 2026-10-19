"""Sharpen the head texture by projecting the (upscaled) front image onto the Pixal3D mesh (see blender_face_project.py)."""
import os, shutil, subprocess, time, numpy as np
from PIL import Image
from scipy import ndimage as ndi
from .. import config as C

_SCRIPT = os.path.join(os.path.dirname(os.path.dirname(__file__)), "blender_face_project.py")

FRAME = None      # mesh-first runs: frame.json of the grey front render (exact camera); None = estimate from the silhouette

def _bl(*args, angle=0, prev=(), region="head", view=None, fit="height", coverage=None):
    env = dict(os.environ, FACEPROJ_ANGLE=str(angle), FACEPROJ_PREV=",".join(str(a) for a in prev), FACEPROJ_REGION=region, FACEPROJ_FIT=fit)
    if view: env["FACEPROJ_VIEW"] = ",".join(str(x) for x in view)
    if coverage: env["FACEPROJ_COVERAGE"] = str(coverage)      # also write where this pass painted (blend weight per texel)
    if FRAME: env["FACEPROJ_FRAME"] = str(FRAME)
    r = subprocess.run([C.BLENDER, "-b", "--python", _SCRIPT, "--", *map(str, args)], capture_output=True, text=True, timeout=1500, env=env)
    return r.stdout + r.stderr

def _qwen_edit(img, prompt, size, seed, log):
    """One image edit with the already-loaded image model (the caller calls _qwen_on and _qwen_off). img: PIL image at `size` (w, h)."""
    from . import imagegen
    return imagegen.edit(img, prompt, seed, size, 1024, log)

def _qwen_on(log):
    from . import imagegen
    imagegen.on(log)

def _qwen_off():
    from . import imagegen
    imagegen.off()

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

# the character is turned about the vertical axis so the side that a real view shows faces the front camera: the LEFT view (camera sees the character's left side, +x) needs -90
SHEET_ANGLES = (("front", 0), ("back", 180), ("left", -90), ("right", 90))
SHEET_UP_DOWN = (("top", (0, 0, 1)), ("bottom", (0, 0, -1)))      # extra pictures, projected from above and from below (registered by their width, not their height)

def _union(acc, png):
    """largest blend weight any pass had per texel (png: grayscale-ish, written by blender_face_project.py); a missing file leaves it unchanged"""
    if not os.path.exists(png): return acc
    a = np.asarray(Image.open(png).convert("RGB"), np.float32)[..., 0] / 255.0
    return a if acc is None else np.maximum(acc, a)

def project_sheet(glb_in, raw, glb_out, preview_dir, log, fill=False):
    """Texture from a turnaround sheet: every real view is projected onto the surfaces that face it (front first, then back, left, right), each registered on its own silhouette like the front
    projection; where two views overlap the one that sees the surface better wins (FACEPROJ_PREV). raw: {name: path of the cut-out figure picture}. No image model is involved.
    fill: afterwards, texels that no view painted take the colour of the nearest painted surface instead of the flat base colour (stages/texfill.py); the unfilled model stays as sheet_unfilled.glb."""
    os.makedirs(preview_dir, exist_ok=True); cur = glb_in; done = []; covall = None
    for name, ang in SHEET_ANGLES:
        if name not in raw: continue
        npy = os.path.join(preview_dir, f"{name}_dist.npy"); mnpy = os.path.join(preview_dir, f"{name}_mask.npy"); an = os.path.join(preview_dir, f"{name}_agree.npy")
        fg = _distmap(raw[name], npy, mnpy); np.save(an, np.ones(fg.shape, np.float32))      # a real view is trusted everywhere it faces
        nxt = os.path.join(preview_dir, f"sheet_{name}.glb")
        cp = os.path.join(preview_dir, f"{name}_cov.png")
        out = _bl(cur, raw[name], nxt, "-", npy, "project", "-", mnpy, an, angle=ang, prev=done, region="full", coverage=cp if fill else None)
        if "[faceproj] wrote" not in out: log(f"[texture] {name} view: projection failed: {out[-300:]}"); continue
        covall = _union(covall, cp); cur = nxt; done.append(ang); log(f"[texture] {name} view of the sheet projected")
    for name, d in SHEET_UP_DOWN:                    # the pictures from above and below: the surfaces that face none of the four sides (the top of the head, the shoulders, the tops and the soles of the feet)
        if name not in raw: continue
        npy = os.path.join(preview_dir, f"{name}_dist.npy"); mnpy = os.path.join(preview_dir, f"{name}_mask.npy"); an = os.path.join(preview_dir, f"{name}_agree.npy")
        fg = _distmap(raw[name], npy, mnpy); np.save(an, np.ones(fg.shape, np.float32)); nxt = os.path.join(preview_dir, f"sheet_{name}.glb")
        cp = os.path.join(preview_dir, f"{name}_cov.png")
        out = _bl(cur, raw[name], nxt, "-", npy, "project", "-", mnpy, an, prev=done, region="full", view=d, fit="bbox", coverage=cp if fill else None)
        if "[faceproj] wrote" not in out: log(f"[texture] {name} view: projection failed: {out[-300:]}"); continue
        covall = _union(covall, cp); cur = nxt; done.append(":".join(str(x) for x in d)); log(f"[texture] {name} picture projected")
    if cur == glb_in: raise RuntimeError("no view of the sheet could be projected")
    if fill and covall is not None:
        unfilled = os.path.join(preview_dir, "sheet_unfilled.glb"); shutil.copy(cur, unfilled); shutil.copy(cur[:-4] + "_basecolor.png", unfilled[:-4] + "_basecolor.png")
        try:
            from . import texfill
            filled = os.path.join(preview_dir, "sheet_filled.glb"); r = texfill.fill(glb_in, cur, covall, filled, os.path.join(preview_dir, "fill"), log)
            cur = filled; log(f"[texture] unpainted surfaces filled from their painted neighbours ({r['filled'] * 100:.0f} % of the texture)")
        except Exception as e: log(f"[texture] fill skipped ({type(e).__name__}: {str(e)[:160]}); the unpainted surfaces keep the base colour")
    shutil.copy(cur, glb_out); shutil.copy(cur[:-4] + "_basecolor.png", glb_out[:-4] + "_basecolor.png")
    return glb_out

