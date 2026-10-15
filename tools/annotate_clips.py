"""Label the hands of several clips with the vision-language model, one after another, through the web app's own job (/api/hands/llm), and keep each result as the clip's saved labels:

    .venv/bin/python tools/annotate_clips.py --run jabawockeez --clips video_wdb_d1,video_wdb_d2 --fps native --chunk-seconds 3 --size 704 --thinking on [--model qwen38] [--temperature 0.6]

The web app must be running (the job runs inside it).  The clips' own reference videos are used (and their `valid_ranges` in animations.json, if any, so that only stretches where the person is really in the picture are looked at).
A clip that already has a result of this job (hands/<clip>.llm.json, final) is saved without being asked again; progress is appended to runs/<run>/09_animate/hands/annotate_progress.txt."""
import os, sys, json, time, argparse
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__))); sys.path.insert(0, ROOT)
import requests
from homunculus import config as C, hands, hands_llm
ap = argparse.ArgumentParser(); ap.add_argument("--run", required=True); ap.add_argument("--clips", required=True); ap.add_argument("--fps", default="native"); ap.add_argument("--chunk-seconds", type=float, default=None); ap.add_argument("--size", type=int, default=None)
ap.add_argument("--thinking", default="on"); ap.add_argument("--model", default="qwen38"); ap.add_argument("--temperature", type=float, default=0.6); ap.add_argument("--api", default="http://127.0.0.1:8765"); a = ap.parse_args()
log = open(C.RUNS / a.run / "09_animate" / "hands" / "annotate_progress.txt", "a"); say = lambda s: (log.write(time.strftime("%H:%M:%S ") + s + "\n"), log.flush(), print(s, flush=True))
for clip in a.clips.split(","):
    info = requests.get(f"{a.api}/api/hands/{a.run}/{clip}").json(); v = info.get("video") or {}; fps = v.get("fps", 30.0) if a.fps == "native" else float(a.fps)
    st = info.get("llm") or {}
    if not (st.get("status") == "done" and (hands_llm.result(a.run, clip).get("final"))):
        body = {"run": a.run, "clip": clip, "fps": fps, "thinking": a.thinking == "on", "model": a.model, "temperature": a.temperature, "chunk_seconds": a.chunk_seconds, "size": a.size}
        r = requests.post(f"{a.api}/api/hands/llm", json={k: x for k, x in body.items() if x is not None}); say(f"{clip}: start {r.status_code} {r.text[:100]} (fps {fps:.3f})")
        if r.status_code != 200: continue
        t0 = time.time()
        while True:
            time.sleep(30); st = requests.get(f"{a.api}/api/hands/{a.run}/{clip}").json().get("llm") or {}
            if st.get("status") in ("done", "failed", "stopped"): break
        say(f"{clip}: {st.get('status')} after {(time.time() - t0) / 60:.0f} min, {st.get('chunks')} requests {st.get('error', '')}")
        if st.get("status") != "done": continue
    res = hands_llm.result(a.run, clip); hands.save(a.run, clip, res["tracks"], meta=res["meta"], wait=True); say(f"{clip}: labels saved ({sum(len(v) for v in res['tracks'].values())} keys) and baked: {hands.info(a.run, clip)['status']}")
say("ALL DONE")
