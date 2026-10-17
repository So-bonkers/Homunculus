"""Every dancer who is big enough in a list of shots: track (tools/multi_track.py), then GVHMR on each big track (tools/video_to_smpl.py -s):

    python tools/extract_tracks.py --shots gvhmr/work/choreo/jw2_00.mp4 gvhmr/work/choreo/jw2_01.mp4 ... [--min-height 0.35] [--min-frames 60]

Each shot must be 30 fps and one continuous stretch (cut with ffmpeg first).  Per shot <shot>/ gets tracks.json, overlay.mp4 and t<id>/ for each track; a track with GVHMR's result already is skipped, so it can be stopped and started again.  Progress is appended to <out>/extract_progress.txt (next to the shots)."""
import os, sys, json, time, subprocess, argparse
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__))); PY = os.path.join(ROOT, "gvhmr", ".venv", "bin", "python")
ap = argparse.ArgumentParser(); ap.add_argument("--shots", nargs="+", required=True); ap.add_argument("--min-height", type=float, default=0.35); ap.add_argument("--min-frames", type=int, default=60); ap.add_argument("--link-seconds", type=float, default=5.0); a = ap.parse_args()
def clips_of(T, min_height, min_frames):
    """[(name, first frame, frames)] of the clips big enough: one per stretch of a track (tools/multi_track.py --link-seconds), or the single kept stretch of an older tracks.json"""
    out = []
    for t in T["tracks"]:
        cl = t.get("clips") or ([{"name": str(t["id"]), "from": t["kept"]["from"], "frames": t["kept"]["frames"], "height_frac": t["height_frac"]}] if t.get("kept") else [])
        out += [(c["name"], c["from"], c["frames"]) for c in cl if c.get("height_frac", t["height_frac"]) >= min_height and c["frames"] >= min_frames]
    return out
log = open(os.path.join(os.path.dirname(os.path.abspath(a.shots[0])), "extract_progress.txt"), "a")
def say(m): log.write(f"{time.strftime('%H:%M:%S')} {m}\n"); log.flush(); print(m, flush=True)
for shot in a.shots:
    shot = os.path.abspath(shot); out = shot[:-4]
    if not os.path.exists(os.path.join(out, "tracks.json")):
        r = subprocess.run([PY, os.path.join(ROOT, "tools", "multi_track.py"), "--video", shot, "--out", out, "--link-seconds", str(a.link_seconds)], capture_output=True, text=True)
        if not os.path.exists(os.path.join(out, "tracks.json")): say(f"{os.path.basename(out)}: tracking FAILED {(r.stderr or r.stdout)[-200:]}"); continue
    T = json.load(open(os.path.join(out, "tracks.json"))); big = clips_of(T, a.min_height, a.min_frames)
    say(f"{os.path.basename(out)}: {len(T['tracks'])} tracks, {len(big)} clips big enough ({sum(c[2] for c in big) / 30:.0f} s): " + ", ".join(f"t{c[0]}" for c in big))
    for c in big:
        d = os.path.join(out, f"t{c[0]}")
        if os.path.exists(os.path.join(d, "clip", "smpl_global.npz")): continue
        t0 = time.time(); r = subprocess.run([PY, os.path.join(ROOT, "tools", "video_to_smpl.py"), "--video", os.path.join(d, "clip.mp4"), "--output_root", d, "-s"], capture_output=True, text=True)
        ok = os.path.exists(os.path.join(d, "clip", "smpl_global.npz")); say(f"{os.path.basename(out)} t{c[0]}: {'ok' if ok else 'FAILED ' + (r.stderr or r.stdout)[-200:]} ({time.time() - t0:.0f} s)")
say("ALL DONE")
