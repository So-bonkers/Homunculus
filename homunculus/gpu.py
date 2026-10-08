"""One-heavy-model-at-a-time GPU control: VRAM readout, unload everything, ComfyUI start/stop, watchdog."""
import subprocess, threading, time, requests
from contextlib import contextmanager
from . import config as C

def vram_gb():
    return int((C.CARD / "mem_info_vram_used").read_text()) / 1024 ** 3

def _post(path, **kw):
    try: return requests.post(C.STUDIO + path, timeout=kw.pop("timeout", 60), **kw)
    except requests.RequestException: return None

def studio_llms_loaded():
    try: s = requests.get(C.STUDIO + "/api/inference/status", timeout=10).json()
    except Exception: return []
    return list(s.get("loaded") or []) + ([s["active_model"]] if s.get("active_model") else [])

def unload_llms(timeout=150):
    """Unload the planner and every judge, and make sure it happened: Studio ignores an unload while a model is still
    answering (e.g. a judge you cut short), so keep asking until nothing is loaded."""
    t0 = time.time()
    while True:
        for m in {C.VLM_MODEL, *(j[0] for j in getattr(C, "ALL_JUDGES", getattr(C, "JUDGES", [])))}:
            _post("/api/inference/unload", json={"model_path": m})
        if not studio_llms_loaded() or time.time() - t0 > timeout: return
        time.sleep(4)

def unload_studio():
    _post("/api/inference/images/generate/cancel")
    _post("/api/inference/images/unload")
    unload_llms()      # planner + every judge (a stopped run may leave any loaded)

def comfy_running():
    try: return requests.get(C.COMFY_API + "/system_stats", timeout=3).ok
    except requests.RequestException: return False

def comfy_stop():
    subprocess.run(["systemctl", "--user", "stop", C.COMFY_UNIT], capture_output=True)

def comfy_start(log):
    if comfy_running(): return
    env = ["--setenv=PYTHONUNBUFFERED=1", "--setenv=UV_CPU=1", "--setenv=TORCH_ROCM_AOTRITON_ENABLE_EXPERIMENTAL=1",
           "--setenv=TORCH_BLAS_PREFER_HIPBLASLT=0", "--setenv=PYTORCH_ROCM_ARCH=gfx1100"]
    cmd = ["systemd-run", "--user", f"--unit={C.COMFY_UNIT}", "--collect", f"--working-directory={C.COMFY_UI}",
           "-p", "CPUQuota=800%", "-p", "Nice=5", *env, "bash", "-c",
           f"exec {C.COMFY_PY} main.py --listen 127.0.0.1 --port 8188 --use-pytorch-cross-attention > {C.COMFY}/server.log 2>&1"]
    subprocess.run(cmd, capture_output=True)
    for _ in range(80):
        if comfy_running(): log("ComfyUI up"); return
        time.sleep(3)
    raise RuntimeError("ComfyUI did not start (see comfy/server.log)")

def total_gb():
    return int((C.CARD / "mem_info_vram_total").read_text()) / 1024 ** 3

def free_all(log, keep=None):
    """Unload everything except `keep` ('studio' | 'comfy') and wait until the VRAM stops dropping (unloads are async)."""
    if keep != "studio": unload_studio()
    else:   # keep the Studio server but drop its LLMs (the image model is loaded by the caller)
        unload_llms()
    if keep != "comfy": comfy_stop()
    t0 = time.time(); last = vram_gb()
    while time.time() - t0 < 90:
        time.sleep(3); now = vram_gb()
        if now < C.IDLE_GB or abs(now - last) < 0.1: break
        last = now
    log(f"GPU freed (keep={keep}); VRAM {vram_gb():.1f} GB")

NEED_GB = {"qwen_image": 17.5, "vlm": 17.5, "pixal3d": 19.5, "upscale": 16.0, "mia": 8.0, "unimate": 6.0, "skintokens": 5.0}   # observed peak incl. ~1.5 GB desktop baseline

def comfy_free():
    """Ask a running ComfyUI to drop its cached models (it keeps the upscaler/Pixal3D weights otherwise)."""
    try: requests.post(C.COMFY_API + "/free", json={"unload_models": True, "free_memory": True}, timeout=30); time.sleep(3)
    except requests.RequestException: pass

def wait_for_headroom(job, log, notify=None, max_wait_s=3600):
    """Block until `job` fits under the hard limit; other apps (games, browsers) may be holding VRAM."""
    if job in ("pixal3d", "upscale") and comfy_running(): comfy_free()   # our own server's cache is not "another app"
    need = NEED_GB[job]; t0 = time.time(); warned = False
    while True:
        used = vram_gb(); room = C.SOFT_LIMIT_GB - used
        if comfy_running() and job in ("pixal3d", "upscale"): room += 1.0   # an idle ComfyUI keeps ~1 GB that the job reuses
        if room >= need - 1.5:         # `need` is a peak measured with the ~1.5 GB desktop baseline included
            if warned: log(f"VRAM available again ({used:.1f} GB used), continuing {job}")
            return
        if not warned and time.time() - t0 > 25:     # our own ComfyUI takes a few seconds to hand its cache back; only shout if it's someone else
            msg = (f"Waiting for GPU memory: {job} needs ~{need:.0f} GB but {used:.1f} GB of {total_gb():.0f} GB is in use by other apps. "
                   "Close games / 3D apps / GPU-heavy browser tabs; the run continues automatically.")
            log("!! " + msg); warned = True
            if notify: notify(msg)
            else: subprocess.run(["notify-send", "-a", "homunculus", "-u", "critical", "homunculus: waiting for GPU memory", msg], capture_output=True)
        if time.time() - t0 > max_wait_s: raise RuntimeError(f"not enough free VRAM for {job} after {max_wait_s//60} min")
        time.sleep(3 if time.time() - t0 < 30 else 10)

@contextmanager
def watchdog(log, on_soft=None, on_hard=None):
    """Samples VRAM every 0.5 s; calls on_soft above SOFT_LIMIT_GB and on_hard above HARD_LIMIT_GB (once each)."""
    st = {"peak": 0.0, "soft": False, "hard": False}; stop = threading.Event()
    def run():
        while not stop.is_set():
            u = vram_gb(); st["peak"] = max(st["peak"], u)
            if u > C.HARD_LIMIT_GB and not st["hard"]:
                st["hard"] = True; log(f"!! VRAM {u:.1f} GB > hard limit"); (on_hard or (lambda: None))()
            elif u > C.SOFT_LIMIT_GB and not st["soft"]:
                st["soft"] = True; log(f"!! VRAM {u:.1f} GB > soft limit"); (on_soft or (lambda: None))()
            stop.wait(0.5)
    th = threading.Thread(target=run, daemon=True); th.start()
    try: yield st
    finally: stop.set(); th.join()
