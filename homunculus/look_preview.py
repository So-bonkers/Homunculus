"""One redraw per target look for an existing run, as a preview to choose a look before forking.
python -m homunculus.look_preview <run> [look ...]     ->  runs/<run>/looks/<look>.png + looks.json (shown on the run page)
Waits for the GPU pipeline lock, so it can be queued while a run is still going."""
import fcntl, json, os, shutil, sys, time
from . import config as C, gpu, prompts, notify
from .stages import edit


def main():
    run = sys.argv[1]; looks = sys.argv[2:] or list(prompts.LOOK)
    d = C.RUNS / run; S = json.load(open(d / "state.json"))
    out = d / "looks"; out.mkdir(exist_ok=True)
    logf = open(out / "looks.log", "a")
    def log(m):
        line = time.strftime("%H:%M:%S ") + m; print(line, flush=True); logf.write(line + "\n"); logf.flush()
    meta_p = out / "looks.json"
    meta = json.load(open(meta_p)) if meta_p.exists() else {}
    meta.update({"status": "queued", "looks": meta.get("looks", {}), "raw": S["artifacts"].get("input")}); json.dump(meta, open(meta_p, "w"), indent=1)

    lockf = open(C.RUNS / ".homunculus.lock", "a+")
    try: fcntl.flock(lockf, fcntl.LOCK_EX | fcntl.LOCK_NB)
    except BlockingIOError:
        log("waiting for the GPU pipeline to finish its current run"); fcntl.flock(lockf, fcntl.LOCK_EX)
    lockf.seek(0); lockf.truncate(); lockf.write(f"homunculus look previews for '{run}' (pid {os.getpid()})"); lockf.flush()

    plan = S["vlm"]["plan"]; src = S["artifacts"].get("upscaled") or S["artifacts"]["input"]
    outfit = S.get("outfit", "keep"); hands = C.DEFAULT_POSE
    meta["status"] = "running"; json.dump(meta, open(meta_p, "w"), indent=1)
    notify.need_studio(log, what="the look previews")
    gpu.free_all(log, keep="studio"); gpu.wait_for_headroom("qwen_image", log)
    try:
        for i, look in enumerate(looks):
            t0 = time.time()
            prompt = prompts.edit_prompt(plan, S.get("human_notes", ""), hands=hands, outfit=outfit, look=look)
            res, _ = edit.run(src, str(out / "_tmp"), prompt, f"look_{look}", log, n=1, size=C.EDIT_SIZE[hands], keep_loaded=i < len(looks) - 1)
            if not res: log(f"{look}: no image"); continue
            dst = out / f"{look}.png"; shutil.move(res[0], dst)
            meta["looks"][look] = {"label": prompts.LOOK_LABEL[look], "file": f"looks/{look}.png", "time": time.strftime("%H:%M:%S"), "prompt": prompt}
            json.dump(meta, open(meta_p, "w"), indent=1); log(f"{look}: done in {time.time() - t0:.0f}s")
    finally:
        shutil.rmtree(out / "_tmp", ignore_errors=True)
        gpu.free_all(log)
        meta["status"] = "done"; json.dump(meta, open(meta_p, "w"), indent=1)
    notify.send(f"homunculus · {run}: look previews ready", f"{len(meta['looks'])} looks to compare. Open http://127.0.0.1:8765/#/run/{run}")


if __name__ == "__main__":
    main()
