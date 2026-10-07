"""Generate animation clips for an existing run (queued from the web app).  python -m homunculus.animate <run> --prompt "walks forward" [--prompt ...] [--reps 2]
Waits for the GPU pipeline lock, so it can be queued while a run is still going."""
import argparse, fcntl, json, os
from . import config as C, notify
from .orchestrate import Run
from .stages import animate


def main():
    ap = argparse.ArgumentParser(); ap.add_argument("run"); ap.add_argument("--prompt", action="append", default=[]); ap.add_argument("--hands", action="store_true", help="only apply the hand-pose layer to the clips that already exist"); ap.add_argument("--reps", type=int, default=2)
    a = ap.parse_args()
    if not a.hands and not a.prompt: ap.error("give --prompt, or --hands")
    S = json.load(open(C.RUNS / a.run / "state.json")); R = Run(S["input"], a.run)
    if a.hands:      # CPU only: no GPU lock, no queue
        try: n = animate.relayer(R)
        except Exception as e: notify.send(f"homunculus · {a.run}: hand poses failed", str(e)[:200], critical=True); raise
        notify.send(f"homunculus · {a.run}", f"Hand poses set on {n} clip(s)."); print("hand poses set on", n, "clip(s)"); return
    M = animate._manifest(R); M["status"] = "queued"; animate._save(R, M)
    lockf = open(C.RUNS / ".homunculus.lock", "a+")
    try: fcntl.flock(lockf, fcntl.LOCK_EX | fcntl.LOCK_NB)
    except BlockingIOError:
        R.log("[animate] waiting for the GPU pipeline to finish its current run"); fcntl.flock(lockf, fcntl.LOCK_EX)
    lockf.seek(0); lockf.truncate(); lockf.write(f"homunculus animation for '{a.run}' (pid {os.getpid()})"); lockf.flush()
    R = Run(S["input"], a.run)         # re-read the state: the run that held the lock may have changed it
    R.state["anim_prompts"] = (R.state.get("anim_prompts") or []) + [p for p in a.prompt if p not in (R.state.get("anim_prompts") or [])]; R.save()
    try: new = animate.generate(R, a.prompt, a.reps)
    except Exception as e:
        notify.send(f"homunculus · {a.run}: animation failed", str(e)[:200], critical=True); raise
    notify.send(f"homunculus · {a.run}", f"{len(new)} animation clip(s) ready. Open http://127.0.0.1:8765/#/run/{a.run}")


if __name__ == "__main__":
    main()
