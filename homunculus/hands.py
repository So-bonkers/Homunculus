"""Hand timelines for the clips of a run (the Animate tab's editor): which pose each hand has at each moment of a dance, baked into a copy of the clip.

runs/<run>/09_animate/hands/<clip>.json         {"tracks": {"left": [[seconds, pose], ...], "right": [...]}, "updated": time}   what the editor saves (the training labels of a later classifier)
runs/<run>/09_animate/hands/<clip>.status.json  {"status": "running" | "done" | "failed", "error": ...}
runs/<run>/09_animate/clips/<clip>_hands.glb    the clip with the fingers set (blender_handpose.py), made from the textured clip when there is one; the original clip is never touched.
The clip's entry in animations.json gets hands_glb (and hands_fbx); api.py serves those instead of the plain clip once they exist. An empty timeline removes them again."""
import json, os, shutil, subprocess, threading, time
from . import config as C, handpose, handshapes

MAX_KEYS = 400
CURVES = ("smooth", "quick", "snap", "linear", "hold")
_locks = {}


def _dir(run): return C.RUNS / os.path.basename(run) / "09_animate"
def _paths(run, clip):
    d = _dir(run); clip = os.path.basename(clip); return d / "hands" / f"{clip}.json", d / "hands" / f"{clip}.status.json"


def _manifest(run):
    try: return json.load(open(_dir(run) / "animations.json"))
    except Exception: return None


def _clip(run, clip):
    M = _manifest(run)
    return next((c for c in (M or {}).get("clips", []) if c.get("id") == clip), None)


def clean(tracks):
    """Validated tracks: {"left": [[seconds, pose], ...], "right": [...]} sorted by time (raises ValueError)."""
    if not isinstance(tracks, dict): raise ValueError("tracks must be {left: [...], right: [...]}")
    out = {}
    for side in ("left", "right", "left_wrist", "right_wrist", "left_palm", "right_palm"):
        ks = tracks.get(side) or []
        names = handshapes.WRISTS if side.endswith("_wrist") else handshapes.PALMS if side.endswith("_palm") else handpose.LIB
        if not isinstance(ks, list) or len(ks) > MAX_KEYS: raise ValueError(f"{side}: a list of at most {MAX_KEYS} poses")
        rows = []
        for k in ks:
            try: t, pose = float(k[0]), str(k[1])
            except (TypeError, ValueError, IndexError): raise ValueError(f"{side}: each entry is [seconds, pose] or [seconds, pose, {{curve, d}}]")
            if pose not in names: raise ValueError(f"{side}: unknown {'wrist position' if side.endswith('_wrist') else 'palm direction' if side.endswith('_palm') else 'pose'} '{pose}' (use {', '.join(names)})")
            if not (0 <= t <= 3600): raise ValueError(f"{side}: time {t} out of range")
            row = [round(t, 3), pose]
            if len(k) > 2 and isinstance(k[2], dict) and k[2]:      # how the change arrives: curve (smooth | quick | snap | linear | hold) and its length d in seconds
                o = {}
                if k[2].get("curve") is not None:
                    if k[2]["curve"] not in CURVES: raise ValueError(f"{side}: unknown transition '{k[2]['curve']}' (use {', '.join(CURVES)})")
                    o["curve"] = k[2]["curve"]
                if k[2].get("d") is not None:
                    try: d = float(k[2]["d"])
                    except (TypeError, ValueError): raise ValueError(f"{side}: d must be a number of seconds")
                    if not (0.005 <= d <= 3): raise ValueError(f"{side}: d must be between 0.005 and 3 seconds")
                    o["d"] = round(d, 3)
                if o: row.append(o)
            rows.append(row)
        out[side] = sorted(rows, key=lambda r: r[0])
    return out


_video = {}


def video_info(run, clip):
    """{"fps", "duration"} of the clip's reference video (the one the model is shown), from ffprobe; None if there is none."""
    c = _clip(run, clip); p = C.RUNS / run / c["ref"] if c and c.get("ref") else None
    if not p or not p.exists(): return None
    key = (str(p), p.stat().st_mtime)
    if key not in _video:
        try:
            o = subprocess.run(["ffprobe", "-v", "error", "-select_streams", "v:0", "-show_entries", "stream=avg_frame_rate:format=duration", "-of", "json", str(p)], capture_output=True, text=True, timeout=20).stdout; j = json.loads(o)
            a, b = (j["streams"][0]["avg_frame_rate"] + "/1").split("/")[:2]; _video[key] = {"fps": round(float(a) / float(b or 1), 3), "duration": round(float(j["format"]["duration"]), 2)}
        except Exception: _video[key] = None
    return _video[key]


def info(run, clip):
    """What the editor needs: the poses, the saved tracks and the state of the last bake."""
    clip = os.path.basename(clip); tp, sp = _paths(run, clip); c = _clip(run, clip)
    if c is None: raise ValueError("no such clip")
    try: saved = json.load(open(tp))
    except Exception: saved = {"tracks": {"left": [], "right": []}, "updated": None}
    saved["tracks"] = {**{k: [] for k in ("left", "right", "left_wrist", "right_wrist", "left_palm", "right_palm")}, **saved["tracks"]}
    try: st = json.load(open(sp))
    except Exception: st = {"status": "idle", "error": None}
    if st.get("status") == "running" and time.time() - os.path.getmtime(sp) > 900: st = {"status": "failed", "error": "the bake stopped answering"}
    from . import hands_llm
    return {"clip": clip, "llm": hands_llm.status(run, clip), "video": video_info(run, clip), "llm_timing": hands_llm.timing(), "llm_models": [{"key": k, "label": v["label"]} for k, v in hands_llm.MODELS.items()], "chunk_frames": hands_llm.CHUNK, "poses": list(handpose.LIB), "tracks": saved["tracks"], "updated": saved.get("updated"), "meta": saved.get("meta"), "agreement": agreement(run, clip, saved["tracks"]), **st, "applied": bool(c.get("hands_glb"))}


def agreement(run, clip, current):
    """How much of what a model proposed survives: per lane the share of time (sampled at 30 Hz over the clip) where the current label is the proposed one, and what always guessing the person's most common label would
    score on the same time. Only lanes the person has labelled count. None if no model draft was made for this clip."""
    tp, _ = _paths(run, clip); dp = str(tp)[:-5] + ".draft.json"
    try: dr = json.load(open(dp))
    except Exception: return None
    dur = float(dr.get("duration") or max([k[0] for v in current.values() for k in v] + [1]))
    def at(keys, t):
        p = None
        for k in sorted(keys, key=lambda k: k[0]):
            if p is None or k[0] <= t + 1e-9: p = k[1]
        return p
    out = {}
    for lane, dkeys in dr["tracks"].items():
        mine = current.get(lane) or []
        if not mine or json.dumps(mine) == json.dumps(dkeys): continue                 # not labelled yet (or untouched): nothing to compare
        ts = [i / 30 for i in range(int(dur * 30))]; yours = [at(mine, t) for t in ts]; prop = [at(dkeys, t) for t in ts]
        from collections import Counter
        out[lane] = {"agree": round(100 * sum(a == b for a, b in zip(yours, prop)) / len(ts)), "majority": round(100 * Counter(yours).most_common(1)[0][1] / len(ts)), "model": dr.get("model")}
    return out or None


def save(run, clip, tracks, meta=None, wait=False):
    """Write the timeline and bake it into a copy of the clip in the background. Returns at once; poll info(). meta: a note stored with it (a draft says where it came from; the editor's own saves have none,
    so the note goes away when a person saves). wait=True: return when the bake is done (scripts)."""
    clip = os.path.basename(clip); tracks = clean(tracks); tp, sp = _paths(run, clip)
    if _clip(run, clip) is None: raise ValueError("no such clip")
    os.makedirs(tp.parent, exist_ok=True)
    json.dump({"tracks": tracks, "updated": time.time(), **({"meta": meta} if meta else {})}, open(tp, "w"), indent=1)
    if meta and meta.get("source") == "draft" and meta.get("model"):      # what a model proposed, kept apart: later edits are measured against it (agreement())
        json.dump({"tracks": {k: v for k, v in tracks.items() if v}, "duration": meta.get("duration"), "model": meta["model"]}, open(str(tp)[:-5] + ".draft.json", "w"), indent=1)
    _status(sp, "running"); th = threading.Thread(target=_bake, args=(run, clip, tracks), daemon=True); th.start()
    if wait: th.join()


def _status(sp, status, error=None):
    tmp = str(sp) + ".tmp"; json.dump({"status": status, "error": error}, open(tmp, "w")); os.replace(tmp, sp)


def _bake(run, clip, tracks):
    lock = _locks.setdefault((run, clip), threading.Lock())
    with lock:
        tp, sp = _paths(run, clip); d = _dir(run)
        try:
            M = _manifest(run); c = next(c for c in M["clips"] if c["id"] == clip)
            if not any(tracks.values()):              # an empty timeline: back to the plain clip
                for k in ("hands_glb", "hands_fbx"):
                    p = c.pop(k, None)
                    if p:
                        try: os.remove(C.RUNS / run / p)
                        except OSError: pass
                json.dump(M, open(d / "animations.json", "w"), indent=1); _status(sp, "done"); return
            src = C.RUNS / run / (c.get("textured") or c["glb"]); dst = d / "clips" / f"{clip}_hands.glb"; part = d / "clips" / f"{clip}_hands_part.glb"
            shutil.copy(src, part); fbx_src = src.with_suffix(".fbx")
            want_fbx = bool(C.KEEP_FBX) and fbx_src.exists()
            if want_fbx: shutil.copy(fbx_src, part.with_suffix(".fbx"))
            spec = {"tracks": {"left": tracks["left"], "right": tracks["right"]}, "wrist_tracks": {"left": tracks.get("left_wrist", []), "right": tracks.get("right_wrist", [])}, "lib": handpose.LIB,
                    "wrist_lib": handshapes.wrist_lib(), "palm_tracks": {"left": tracks.get("left_palm", []), "right": tracks.get("right_palm", [])}, "palm_lib": handshapes.palm_lib(), "ease": 0.13, "ramp": 6, "fbx": want_fbx}; sj = d / "hands" / f"{clip}.spec.json"; json.dump(spec, open(sj, "w"))
            r = subprocess.run([C.BLENDER, "-b", "--python", str(C.ROOT / "homunculus" / "blender_handpose.py"), "--", str(part), str(sj)], capture_output=True, text=True, timeout=900)
            if r.returncode or "finger bones" not in r.stdout: raise RuntimeError(((r.stdout + r.stderr).strip().splitlines() or ["no output"])[-1][:200])
            os.replace(part, dst); c["hands_glb"] = os.path.relpath(dst, C.RUNS / run)
            if want_fbx: os.replace(part.with_suffix(".fbx"), dst.with_suffix(".fbx")); c["hands_fbx"] = os.path.relpath(dst.with_suffix(".fbx"), C.RUNS / run)
            M2 = _manifest(run); c2 = next(x for x in M2["clips"] if x["id"] == clip); c2.update({k: c[k] for k in ("hands_glb", "hands_fbx") if k in c})      # the manifest may have changed meanwhile
            json.dump(M2, open(d / "animations.json", "w"), indent=1); _status(sp, "done")
        except Exception as e:
            _status(sp, "failed", f"{type(e).__name__}: {str(e)[:200]}")
