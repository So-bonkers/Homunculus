"""Put every extracted dancer (tools/extract_tracks.py) on a different agent, in turn, registered in that agent's run:

    gvhmr/.venv/bin/python tools/cast_clips.py --shots gvhmr/work/choreo/jw2_*.mp4 --prefix jw2 --agents yoru,miks,iso,... [--workers 3]

The tracks (in the order of the shots, then their ids) take the agents round-robin, so neighbouring dancers are never the same agent.  Each becomes the clip <prefix>_<shot number>_t<id> of the agent's run (tools/register_track_clip.py: the motion in place, the retargeted
clip, a crop of the dancer with the shot's sound as the reference).  Writes cast.json next to the shots: clip id -> agent."""
import os, sys, json, subprocess, argparse, concurrent.futures as cf
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__))); PY = os.path.join(ROOT, "gvhmr", ".venv", "bin", "python")
ap = argparse.ArgumentParser(); ap.add_argument("--shots", nargs="+", required=True); ap.add_argument("--prefix", required=True); ap.add_argument("--agents", required=True); ap.add_argument("--workers", type=int, default=3); ap.add_argument("--min-height", type=float, default=0.35); ap.add_argument("--min-frames", type=int, default=60); a = ap.parse_args()
agents = a.agents.split(","); jobs = []; k = 0
for shot in sorted(os.path.abspath(s) for s in a.shots):
    out = shot[:-4]; tj = os.path.join(out, "tracks.json")
    if not os.path.exists(tj): continue
    num = os.path.basename(out).split("_")[-1]
    T = json.load(open(tj)); lst = []
    for t in T["tracks"]:
        cl = t.get("clips") or ([{"name": str(t["id"]), "from": t["kept"]["from"], "frames": t["kept"]["frames"], "height_frac": t["height_frac"]}] if t.get("kept") else [])
        lst += [c for c in cl if c.get("height_frac", t["height_frac"]) >= a.min_height and c["frames"] >= a.min_frames]
    for c in lst:
        d = os.path.join(out, f"t{c['name']}")
        if not os.path.exists(os.path.join(d, "clip", "smpl_global.npz")): continue
        ag = agents[k % len(agents)]; k += 1; cid = f"video_{a.prefix}_{num}_t{c['name']}"
        jobs.append((cid, ag, [PY, os.path.join(ROOT, "tools", "register_track_clip.py"), "--track", d, "--shot", shot, "--start-frame", str(c["from"]), "--run", ag, "--id", cid, "--title", f"Jabbawockeez video, shot {num}, dancer {c['name']} ({ag})", "--rig", os.path.join(ROOT, "runs", ag, "07_rig", f"{ag}_rigged.glb")]))
cast = {j[0]: j[1] for j in jobs}; json.dump(cast, open(os.path.join(os.path.dirname(os.path.abspath(a.shots[0])), f"cast_{a.prefix}.json"), "w"), indent=1); print(len(jobs), "clips to register", flush=True)
def run(j):
    r = subprocess.run(j[2], capture_output=True, text=True); return j[0], r.returncode, (r.stdout.strip().splitlines() or [""])[-1] if r.returncode == 0 else (r.stderr or r.stdout)[-300:]
with cf.ThreadPoolExecutor(a.workers) as ex:
    for cid, rc, msg in ex.map(run, jobs): print(("ok  " if rc == 0 else "FAIL") + " " + cid + " " + msg, flush=True)
print("CASTDONE")
