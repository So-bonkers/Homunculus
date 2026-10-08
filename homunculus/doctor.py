"""System check: is everything the pipeline needs there and healthy?   python -m homunculus.doctor [--json]
Each check is ok / warn (optional or degraded) / fail (a stage cannot run), with the way to fix it."""
import json, os, shutil, subprocess, sys
from pathlib import Path
from . import config as C

PKG = __package__.split(".")[0]


def _http(url, timeout=3):
    import urllib.request
    try: return urllib.request.urlopen(url, timeout=timeout).read().decode()[:400]
    except Exception: return None


def _exists(p, min_bytes=1):
    p = Path(p); return p.exists() and (p.stat().st_size >= min_bytes if p.is_file() else True)


def checks():
    R = []
    def add(name, status, detail, fix=""): R.append({"name": name, "status": status, "detail": detail, "fix": fix})
    # Studio (Qwen-Image + the judges)
    h = _http(C.STUDIO + "/api/health")
    add("Unsloth Studio (image model + judges)", "ok" if h and "healthy" in h else "fail", "answering on " + C.STUDIO if h and "healthy" in h else "not answering on " + C.STUDIO,
        "start it: unsloth studio --api-only -H 127.0.0.1 -p 8888   (as the user unit 'unsloth-api'); if it stalls: systemctl --user restart unsloth-api")
    # GPU
    try:
        tot = int((C.CARD / "mem_info_vram_total").read_text()) / 1024 ** 3; used = int((C.CARD / "mem_info_vram_used").read_text()) / 1024 ** 3
        add("GPU memory", "ok" if tot >= 23 else "warn", f"{used:.1f} of {tot:.1f} GB in use" + ("" if tot >= 23 else "; the pipeline is tuned for 24 GB"), "close GPU-heavy apps" if used > 6 else "")
    except Exception: add("GPU memory", "warn", "could not read it (set HOMUNCULUS_CARD / HOMUNCULUS_CARD to /sys/class/drm/cardN/device)", "")
    lk = C.RUNS / (".%s.lock" % PKG)
    try:
        import fcntl
        f = open(lk, "a+")
        try: fcntl.flock(f, fcntl.LOCK_EX | fcntl.LOCK_NB); fcntl.flock(f, fcntl.LOCK_UN); add("GPU job lock", "ok", "free: no GPU job is running", "")
        except BlockingIOError: f.seek(0); add("GPU job lock", "ok", "busy: " + (f.read().strip()[:80] or "a GPU job is running") + " (new GPU jobs queue behind it)", "")
    except Exception: add("GPU job lock", "ok", "free", "")
    # Blender
    b = C.BLENDER
    try:
        v = subprocess.run([b, "--version"], capture_output=True, text=True, timeout=30).stdout.splitlines()[0]; add("Blender", "ok", v, "")
    except Exception: add("Blender", "fail", f"not found ({b})", "install Blender and put it on PATH, or set BLENDER=/path/to/blender")
    # ComfyUI + Pixal3D + upscalers
    cu = C.COMFY_UI; add("ComfyUI", "ok" if _exists(cu / "main.py") else "fail", str(cu), f"./setup.sh comfy")
    m = cu / "models"
    for label, rel, big in (("Pixal3D weights (bf16)", "diffusion_models/pixal3d_bf16.safetensors", 5e9), ("DINOv3 encoder", "clip_vision/dino_v3_L_naf_fp32.safetensors", 5e8),
                            ("Pixal3D shape VAE", "vae/trellis_2_shape_vae_bf16.safetensors", 5e8), ("Pixal3D texture VAE", "vae/trellis_2_texture_vae_bf16.safetensors", 5e8)):
        add(label, "ok" if _exists(m / rel, big) else "fail", rel, "bash comfy/dl.sh")
    mv = [f for f in ("pixal3d_multiview_bf16.safetensors", "pixal3d_multiview_int8_convrot.safetensors") if _exists(m / "diffusion_models" / f, 4e9)]
    add("Pixal3D multiview weights (turnaround sheets)", "ok" if mv else "warn", mv[0] if mv else "optional", "bash comfy/dl.sh (only needed for runs started from a turnaround sheet)")
    for n in set(C.UPSCALERS.values()): add("Upscaler " + n, "ok" if _exists(m / "upscale_models" / n, 1e6) else "warn", n, "./setup.sh comfy (4x-UltraSharp is a manual download)")
    py = C.COMFY_PY; add("ComfyUI Python env", "ok" if _exists(py) else "fail", str(py), "./setup.sh comfy")
    # rigging, animation, T-pose
    add("Make-It-Animatable", "ok" if _exists(C.MIA_REPO / "output" / "best" / "new") and _exists(C.MIA_PY) else "fail", str(C.MIA_REPO), "./setup.sh mia")
    ck = C.ROOT / "unimate" / "outputs" / "unimate_uniml3d_f60_v3_preview" / "checkpoints" / "checkpoint_step_100000.pt"
    add("UniMate (animation)", "ok" if _exists(ck, 1e8) and _exists(C.ROOT / "unimate" / ".venv" / "bin" / "python") else "warn", "checkpoint + environment", "./setup.sh unimate (animation prompts are skipped without it)")
    add("SkinTokens (T-pose for posed 3D models)", "ok" if _exists(C.ROOT / "riggers" / "skintokens" / "build" / "bin" / "skintokens-cli") else "warn", "optional", "./setup.sh skintokens (only needed for 3D models that are not in a T-pose)")
    # python deps
    for mod in ("numpy", "PIL", "scipy", "cv2", "mediapipe", "requests", "rembg"):
        try: __import__(mod); add("python: " + mod, "ok", "", "")
        except Exception: add("python: " + mod, "fail" if mod in ("numpy", "PIL", "requests") else "warn", "not installed in this environment", "uv pip install -r requirements.txt")
    add("face landmark model", "ok" if _exists(C.ROOT / "models" / "face_landmarker.task", 1e6) else "warn", "models/face_landmarker.task", "it ships with the repository")
    # system
    free = shutil.disk_usage(C.RUNS if C.RUNS.exists() else C.ROOT).free / 1e9
    add("disk space", "ok" if free > 40 else "warn", f"{free:.0f} GB free (a run keeps 1-5 GB)", "delete old runs from the website")
    add("systemd user services", "ok" if subprocess.run(["systemctl", "--user", "is-system-running"], capture_output=True).returncode in (0, 1) else "warn", "runs are background units", "needed for background runs")
    add("node (preset previews only)", "ok" if shutil.which("node") else "warn", "optional", "only python -m %s.preset_clips needs it" % PKG)
    return R


def main():
    R = checks()
    if "--json" in sys.argv: print(json.dumps(R, indent=1)); return
    icon = {"ok": "ok  ", "warn": "warn", "fail": "FAIL"}
    for r in R: print(f"[{icon[r['status']]}] {r['name']}" + (f": {r['detail']}" if r["detail"] else "") + (f"\n        fix: {r['fix']}" if r["status"] != "ok" and r["fix"] else ""))
    bad = [r for r in R if r["status"] == "fail"]; print(f"\n{len(R) - len(bad)} of {len(R)} fine, {len(bad)} need attention" if bad else f"\nall {len(R)} checks passed or only optional parts are missing")
    sys.exit(1 if bad else 0)


if __name__ == "__main__":
    main()
