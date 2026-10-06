"""Desktop alerts for things you need to know about while a run goes on (an app it depends on went away, the run stopped,
the run finished). Alerts also show as a banner on the run page (state["alert"])."""
import subprocess, time, requests
from . import config as C


def send(title, msg, critical=False, icon=None):
    cmd = ["notify-send", "-a", "homunculus"] + (["-u", "critical"] if critical else []) + (["-i", str(icon)] if icon else []) + [title, msg]
    try: subprocess.run(cmd, capture_output=True, timeout=5)
    except Exception: pass


CURRENT = {"R": None}     # the run in this process, so alerts raised deep inside (e.g. vlm.load) still reach its page


def _set(R, msg):
    R = R or CURRENT["R"]
    if R is None: return
    if msg: R.state["alert"] = {"msg": msg, "time": time.strftime("%H:%M:%S")}
    else: R.state.pop("alert", None)
    R.save()


def studio_up():
    try: return requests.get(C.STUDIO + "/api/inference/status", timeout=5).ok
    except requests.RequestException: return False


def need_studio(log, R=None, what="the redraws and the judges", max_wait_s=3600):
    """Unsloth Studio is the one app the pipeline can't start itself. If it is gone, tell the user and wait for it."""
    if studio_up(): return
    R = R or CURRENT["R"]; name = R.state["name"] if R else "run"
    msg = (f"Unsloth Studio isn't answering; {name} needs it for {what}. Open Unsloth Studio "
           f"(or run: systemctl --user restart unsloth-api). The run continues by itself once it is back.")
    log("!! " + msg); _set(R, msg); send(f"homunculus · {name}: Unsloth Studio is needed", msg, critical=True)
    t0 = time.time()
    while not studio_up():
        if time.time() - t0 > max_wait_s: raise RuntimeError("Unsloth Studio did not come back within an hour")
        time.sleep(10)
    log(f"Unsloth Studio is back after {time.time() - t0:.0f}s, continuing"); _set(R, None)
    send(f"homunculus · {name}", "Unsloth Studio is back; the run continues.")


def stopped(R, stage, err):
    """The run stopped on an error: say what happened in plain words and how to continue."""
    e = str(err)
    if any(k in e for k in ("-9", "-15", "Killed", "SIGKILL", "SIGTERM", "terminated", "returned non-zero exit status -")):
        why = "a helper program (Blender / ComfyUI) was closed or killed while it was working"
    elif "Connection refused" in e or "Max retries" in e:
        why = "a local service stopped answering (Unsloth Studio or ComfyUI)"
    elif "VRAM" in e or "out of memory" in e.lower():
        why = "the graphics card ran out of memory"
    else:
        why = e.strip().splitlines()[-1][:160] if e.strip() else type(err).__name__
    msg = f"Stopped at '{stage}': {why}. Open the run page and use Fork to restart from this stage (or rerun the same command)."
    _set(R, msg); send(f"homunculus · {R.state['name']} stopped", msg, critical=True)
