"""Qwen-Image-2.1 re-pose/clean-up redraws (several seeds), via Unsloth Studio with the VRAM watchdog."""
import io, os, subprocess, sys, threading, time, requests
from PIL import Image
from .. import config as C, gpu
sys.path.insert(0, str(C.ROOT))
import qwen_edit as q   # ensure_loaded(), watchdog(), to_b64(), post()

def _pad_to(path, EW, EH):
    im = Image.open(path).convert("RGB"); W, H = im.size; tw = int(H * EW / EH)
    if tw > W:   # too narrow: pad left/right with grey
        canvas = Image.new("RGB", (tw, H), (200, 200, 202)); canvas.paste(im, ((tw - W) // 2, 0)); im = canvas
    else:        # too wide: pad top/bottom
        th = int(W * EH / EW); canvas = Image.new("RGB", (W, th), (200, 200, 202)); canvas.paste(im, (0, (th - H) // 2)); im = canvas
    return im.resize((EW, EH), Image.LANCZOS)

def run(src, out_dir, prompt, round_idx, log, n=C.EDIT_SEEDS, on_saved=None, size=(C.EDIT_W, C.EDIT_H), keep_loaded=False):
    gpu.free_all(log, keep="studio")
    os.makedirs(out_dir, exist_ok=True)
    EW, EH = size; b64 = q.to_b64(_pad_to(src, EW, EH))
    q.ensure_loaded(); log(f"Qwen-Image loaded, VRAM {gpu.vram_gb():.1f} GB")
    stop, state = threading.Event(), {"peak": 0.0}
    th = threading.Thread(target=q.watchdog, args=(stop, state), daemon=True); th.start()
    outs = []
    try:
        for k in range(1, n + 1):
            out = os.path.join(out_dir, f"edit_r{round_idx}_s{k}.png")
            if os.path.exists(out): outs.append(out); continue
            for attempt in range(3):
                try:
                    r = q.post("/api/inference/images/generate", timeout=900, json={
                        "prompt": prompt, "init_image": b64, "workflow": "edit", "width": EW, "height": EH,
                        "steps": 30, "seed": (int("".join(ch for ch in str(round_idx) if ch.isdigit()) or 0) * 37 + 100 * (ord(str(round_idx)[-1]) % 7) + k + 7000 * attempt) % 2**31, "reference_resolution": 512})
                    if r.status_code != 200:
                        log(f"edit error {r.status_code}: {r.text[:120]}")
                        if "No diffusion model is loaded" in r.text or "cancelled" in r.text:
                            gpu.wait_for_headroom("qwen_image", log); q.ensure_loaded()   # the watchdog unloaded it: reload once memory is free
                        time.sleep(5); continue
                    iid = r.json()["images"][0]["id"]
                    img = requests.get(f"{q.API}/api/inference/images/gallery/{iid}/file", timeout=300).content
                    Image.open(io.BytesIO(img)).convert("RGB").save(out); outs.append(out)
                    log(f"saved {os.path.basename(out)} (peak {state['peak']:.1f} GB)")
                    if on_saved: on_saved(list(outs))
                    break
                except Exception as e:
                    log(f"edit exception {type(e).__name__}: {str(e)[:100]}; restarting Studio and retrying")
                    subprocess.run(["systemctl", "--user", "restart", "unsloth-api"], capture_output=True); time.sleep(40); q.ensure_loaded()
    finally:
        stop.set(); th.join()
        if not keep_loaded:      # manual one-at-a-time keeps it for the next try (nothing else needs the GPU while you decide)
            try: q.post("/api/inference/images/unload")
            except Exception: pass
    return outs, state["peak"]


def refine_face(src, out_png, prompt, log, size=C.FACE_SIZE):
    """Redraw the head region of `src` at high resolution with the same framing, and paste it back.
    Returns (enhanced_full_image_path, (crop_before, crop_after))."""
    import numpy as np
    from scipy import ndimage as ndi
    from rembg import remove, new_session
    im = Image.open(src).convert("RGB"); W, H = im.size
    m = ndi.binary_fill_holes(np.asarray(remove(im, session=new_session("u2net")))[..., 3] > 128)
    rows = np.nonzero(m.any(1))[0]; top = rows.min(); body_h = rows.max() - top
    hb = int(0.135 * body_h)                                       # head height ~ 1/7.5 of the body
    cols = np.nonzero(m[top:top + hb].any(0))[0]; cx = int(cols.mean()); cy = top + hb // 2
    side = int(1.7 * hb); x0 = max(0, cx - side // 2); y0 = max(0, cy - side // 2); x1 = min(W, x0 + side); y1 = min(H, y0 + side)
    crop = im.crop((x0, y0, x1, y1)); cw, ch = crop.size
    gpu.free_all(log, keep="studio"); gpu.wait_for_headroom("qwen_image", log); q.ensure_loaded()
    for attempt in range(3):     # a cancel left over from the previous job makes the first request fail: ask again
        r = q.post("/api/inference/images/generate", timeout=900, json={"prompt": prompt, "init_image": q.to_b64(crop.resize((size, size), Image.LANCZOS)),
                   "workflow": "edit", "width": size, "height": size, "steps": 30, "seed": 4242, "reference_resolution": 1024})
        if r.status_code == 200 or "cancelled" not in r.text: break
        time.sleep(3); q.ensure_loaded()
    try: q.post("/api/inference/images/unload")
    except Exception: pass
    if r.status_code != 200: raise RuntimeError(f"face refine failed: {r.status_code} {r.text[:120]}")
    iid = r.json()["images"][0]["id"]
    face = Image.open(io.BytesIO(requests.get(f"{q.API}/api/inference/images/gallery/{iid}/file", timeout=300).content)).convert("RGB")
    # paste back with a feathered edge so the seam is invisible
    face_s = face.resize((cw, ch), Image.LANCZOS)
    yy, xx = np.mgrid[0:ch, 0:cw]; edge = np.minimum.reduce([xx, yy, cw - 1 - xx, ch - 1 - yy]).astype(np.float32)
    alpha = Image.fromarray((np.clip(edge / (0.12 * cw), 0, 1) * 255).astype(np.uint8))
    out = im.copy(); out.paste(face_s, (x0, y0), alpha); out.save(out_png)
    before = out_png[:-4] + "_crop_before.png"; after = out_png[:-4] + "_crop_after.png"
    crop.save(before); face.save(after)
    log(f"face refined: crop {cw}x{ch} at ({x0},{y0}) -> {size}x{size} redraw, pasted back")
    return out_png, (before, after)


def _paste_hand(old, new, direction):
    """Combine the original hand crop and its redraw without ghosts or a doubled cuff:
    - the redraw is used only on the fingertip side of a cut across the arm, placed where the two images agree most (usually the
      sleeve or bracer just behind the redrawn part), with a short blend;
    - on that side, pixels that were the OLD hand but are not the new one become plain background (no faint old fingers);
    - the arm side of the cut stays exactly the original. direction: +1 = fingertips on the left of the crop, -1 = on the right."""
    import numpy as np
    from scipy import ndimage as ndi
    from rembg import remove, new_session
    o = np.asarray(old.convert("RGB")).astype(np.float32); n = np.asarray(new.convert("RGB")).astype(np.float32); h, w = o.shape[:2]
    ses = new_session("u2net")
    fo = np.asarray(remove(old.convert("RGB"), session=ses))[..., 3] > 128; fn = np.asarray(remove(new.convert("RGB"), session=ses))[..., 3] > 128
    border = np.concatenate([o[:6].reshape(-1, 3), o[-6:].reshape(-1, 3)]); bg = np.median(border, 0)
    # cut column: in the arm-side 45% of the crop, where both images show the arm and agree best
    xs = np.arange(w); arm = xs >= int(0.55 * w) if direction == 1 else xs <= int(0.45 * w)
    diff = np.abs(o - n).sum(2); both = fo & fn
    score = np.full(w, np.inf)
    for x in xs[arm]:
        col = both[:, x]
        if col.sum() > 3: score[x] = diff[col, x].mean()
    cut = int(np.argmin(score)) if np.isfinite(score).any() else (int(0.8 * w) if direction == 1 else int(0.2 * w))
    ramp = max(4, int(0.03 * w))
    wgt = np.clip(((cut - xs) if direction == 1 else (xs - cut)) / ramp + 0.5, 0, 1)[None, :]      # 1 on the fingertip side
    soft = ndi.gaussian_filter(fn.astype(np.float32), 1.0)[..., None]
    fo_soft = ndi.gaussian_filter(ndi.binary_dilation(fo, iterations=3).astype(np.float32), 1.5)[..., None]
    behind = fo_soft * bg + (1 - fo_soft) * o           # original background, with the old fingers painted out
    tip = soft * n + (1 - soft) * behind                # new hand on top: no ghosts, no visible box
    res = wgt[..., None] * tip + (1 - wgt[..., None]) * o
    return Image.fromarray(np.clip(res, 0, 255).astype(np.uint8))

def refine_hands(src, out_png, prompt, log, size=1024):
    """Redraw each hand of a T/A-pose image as a sharp close-up (five separated fingers) at the same place and size, and paste it back:
    small or fused fingers in the picture become paddle-shaped, fused hands in the 3D model. Returns (path, [(before, after), ...])."""
    import numpy as np
    from scipy import ndimage as ndi
    from rembg import remove, new_session
    im = Image.open(src).convert("RGB"); W, H = im.size
    m = ndi.binary_fill_holes(np.asarray(remove(im, session=new_session("u2net")))[..., 3] > 128)
    rows = np.nonzero(m.any(1))[0]; top = rows.min(); bh = rows.max() - top
    band = m[top + int(0.10 * bh): top + int(0.62 * bh)]           # arm height (the hands are the outermost points there in a T/A-pose)
    cols = np.nonzero(band.any(0))[0]; side = int(0.13 * bh); out = im.copy(); pairs = []
    gpu.free_all(log, keep="studio"); gpu.wait_for_headroom("qwen_image", log); q.ensure_loaded()
    try:
        for k, (tip, direction) in enumerate(((cols.min(), 1), (cols.max(), -1))):
            ys = np.nonzero(band[:, tip])[0]; cy = top + int(0.10 * bh) + int(np.median(ys)) if len(ys) else top + bh // 3
            cx = int(tip + direction * 0.42 * side)                   # the box reaches from the fingertips back to the wrist
            x0, y0 = max(0, cx - side // 2), max(0, cy - side // 2); x1, y1 = min(W, x0 + side), min(H, y0 + side)
            crop = im.crop((x0, y0, x1, y1)); cw, ch = crop.size
            for attempt in range(3):
                r = q.post("/api/inference/images/generate", timeout=900, json={"prompt": prompt, "init_image": q.to_b64(crop.resize((size, size), Image.LANCZOS)),
                           "workflow": "edit", "width": size, "height": size, "steps": 30, "seed": 4343 + k, "reference_resolution": 1024})
                if r.status_code == 200 or "cancelled" not in r.text: break
                time.sleep(3); q.ensure_loaded()
            if r.status_code != 200: log(f"hand close-up {k + 1} failed: {r.status_code}"); continue
            iid = r.json()["images"][0]["id"]
            hand = Image.open(io.BytesIO(requests.get(f"{q.API}/api/inference/images/gallery/{iid}/file", timeout=300).content)).convert("RGB")
            hs = hand.resize((cw, ch), Image.LANCZOS)
            out.paste(_paste_hand(crop, hs, direction), (x0, y0))
            b_ = out_png[:-4] + f"_hand{k + 1}_before.png"; a_ = out_png[:-4] + f"_hand{k + 1}_after.png"; crop.save(b_); hand.save(a_); pairs.append((b_, a_))
    finally:
        try: q.post("/api/inference/images/unload")
        except Exception: pass
    out.save(out_png); log(f"hands refined: {len(pairs)} close-up(s) at {side}px, pasted back")
    return out_png, pairs
