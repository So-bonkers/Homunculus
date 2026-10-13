"""Copy the dance of a video onto an existing run's rigged character (queued from the web app).
    python -m homunculus.video_motion <run> <video> --start 30 --end 50 [--title "my dance"] [--label "..."] [--yaw 180]
Waits for the GPU pipeline lock, so it can be queued while a run is still going. The clip appears in the run's Animate tab."""
import argparse, fcntl, json, os
from . import config as C, notify
from .orchestrate import Run
from .stages import animate, video_motion


def main():
    ap = argparse.ArgumentParser(); ap.add_argument("run"); ap.add_argument("video"); ap.add_argument("--start", type=float, default=0.0); ap.add_argument("--end", type=float, required=True)
    ap.add_argument("--title"); ap.add_argument("--label"); ap.add_argument("--yaw", type=float, default=180.0)
    a = ap.parse_args()
    S = json.load(open(C.RUNS / a.run / "state.json")); R = Run(S["input"], a.run)
    M = animate._manifest(R); M["status"] = "queued"; M["error"] = None; animate._save(R, M)
    ok, why = video_motion.available()
    if not ok:
        M["status"] = "failed"; M["error"] = "Dance from video is not available: " + why; animate._save(R, M); notify.send(f"homunculus · {a.run}: dance from video failed", why[:200], critical=True); raise SystemExit(why)
    lockf = open(C.RUNS / ".homunculus.lock", "a+")
    try: fcntl.flock(lockf, fcntl.LOCK_EX | fcntl.LOCK_NB)
    except BlockingIOError:
        R.log("[video] waiting for the GPU pipeline to finish its current run"); fcntl.flock(lockf, fcntl.LOCK_EX)
    lockf.seek(0); lockf.truncate(); lockf.write(f"homunculus dance from video for '{a.run}' (pid {os.getpid()})"); lockf.flush()
    R = Run(S["input"], a.run)         # re-read the state: the run that held the lock may have changed it
    try: c = video_motion.generate(R, a.video, a.start, a.end, label=a.label, title=a.title, yaw=a.yaw)
    except Exception as e:
        notify.send(f"homunculus · {a.run}: dance from video failed", str(e)[:200], critical=True); raise
    notify.send(f"homunculus · {a.run}", f"Dance copied from the video. Open http://127.0.0.1:8765/#/run/{a.run}")


if __name__ == "__main__":
    main()
