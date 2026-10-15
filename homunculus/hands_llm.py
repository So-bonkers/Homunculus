"""Hand labels from a vision-language model: Qwen3.8-27B (thinking on) watches the clip's reference video and proposes all six lanes of the hand timeline (fingers, wrist, palm; left and right).

Every frame of the clip at 25 fps goes to the model, 5 s (125 frames at 512 px, about 35 000 tokens) per request, each frame announced by its number; the model answers one row per frame with names from the
hand library (all 48 finger poses, 15 wrist positions, 7 palm directions, each with its description). About 3 minutes of GPU per 5 s of video.
runs/<run>/09_animate/hands/<clip>.llm.json         {"tracks": {...}, "meta": {...}, "final": bool, "upto": seconds labelled so far, "chunk": n, "finished": time}   what the model proposed, rewritten after every 5 s it has labelled
                                                    (the editor takes each part as it arrives); nothing of the person's own labels is touched
runs/<run>/09_animate/hands/<clip>.llmstatus.json   {"status": "running" | "done" | "failed" | "stopped", "chunk", "chunks", ...}
runs/<run>/09_animate/hands/<clip>.draft.json       the same proposal, kept apart so 'model vs you' can measure later edits against it (hands.agreement)
Measured on one clip (Kinjaz, 19 s) against a person's own labels: no better than guessing the commonest label, yet the person judged it closer to the video than their own (docs/VIDEO_MOTION.md)."""
import base64, json, os, re, shutil, subprocess, tempfile, threading, time
import requests
from . import config as C, gpu, handpose, handshapes, hands, vlm

FPS, SIZE, CHUNK = 25, 512, 125                    # default frames per second, picture side in px, frames per request (at 12.5 fps a request covers 10 s instead of 5 s)
CTX, MAX_TOKENS = 65536, 26000                     # the model's context (it holds 35 000 tokens of pictures plus the thinking) and the most it may write per request
def model_name(fps, thinking, model="qwen38"): return f"{MODELS[model]['label']} ({fps:g} fps, thinking {'on' if thinking else 'off'})"
_lock = threading.Lock(); _stop = {}
MODELS = {"qwen38": {"label": "Qwen3.8 27B", "model": C.VLM_MODEL, "variant": C.VLM_VARIANT},
          "qwen36": {"label": "Qwen3.6 35B-A3B", "model": "unsloth/Qwen3.6-35B-A3B-MTP-GGUF", "variant": "UD-IQ4_NL"}}      # the vision-language models that can label a clip (all in Unsloth Studio)
_TIMING = C.RUNS / ".hands_llm_timing.json"       # seconds the model took per request of CHUNK frames, per model and mode ("qwen38:on"), from the jobs that finished here (a running mean); the defaults are guesses until the first job
_DEFAULT = {"qwen38:on": {"s": 175.0, "n": 0}, "qwen38:off": {"s": 120.0, "n": 0}, "qwen36:on": {"s": 90.0, "n": 0}, "qwen36:off": {"s": 60.0, "n": 0}}


def timing():
    """{"qwen38:on": {s, n}, ...}: seconds per request for each model and thinking mode; n = how many jobs the figure comes from (0: a guess)."""
    try: t = json.load(open(_TIMING))
    except Exception: t = {}
    for old in ("on", "off"):                       # figures written before there was a choice of model
        if old in t: t.setdefault("qwen38:" + old, t.pop(old))
    return {k: t.get(k) or v for k, v in _DEFAULT.items()}


def _record(model, thinking, per_request):
    t = timing(); k = f"{model}:{'on' if thinking else 'off'}"; a = t[k]; n = a["n"] + 1; t[k] = {"s": round((a["s"] * a["n"] + per_request) / n, 1), "n": n}
    try: _dump(_TIMING, t)
    except OSError: pass


def _files(run, clip):
    d = hands._dir(run) / "hands"; clip = os.path.basename(clip)
    return d / f"{clip}.llm.json", d / f"{clip}.llmstatus.json", d / f"{clip}.draft.json"


def status(run, clip):
    _, sp, _ = _files(run, clip)
    try: st = json.load(open(sp))
    except Exception: return {"status": "idle"}
    if st.get("status") == "running" and time.time() - os.path.getmtime(sp) > 1500: st = {**st, "status": "failed", "error": "the annotation stopped answering"}
    try: r = json.load(open(_files(run, clip)[0])); st["finished"] = r.get("finished"); st["upto"] = r.get("upto")
    except Exception: pass
    return st


def result(run, clip):
    return json.load(open(_files(run, clip)[0]))


def stop(run, clip):
    _stop[(run, os.path.basename(clip))] = True


def start(run, clip, fps=FPS, thinking=True, model="qwen38"):
    """Start the annotation in the background. Raises ValueError when it cannot (no such clip, no video, another annotation running)."""
    clip = os.path.basename(clip); c = hands._clip(run, clip)
    if c is None: raise ValueError("no such clip")
    if model not in MODELS: raise ValueError("unknown model " + str(model))
    if not c.get("ref") or not (C.RUNS / run / c["ref"]).exists(): raise ValueError("this clip has no reference video to look at")
    if not _lock.acquire(blocking=False): raise ValueError("another clip is being annotated; wait for it to finish")
    fps = float(fps); v = hands.video_info(run, clip)
    if v and fps > v["fps"] + 0.01: fps = v["fps"]              # the video has no more frames than its own rate
    if not (2 <= fps <= 60): _lock.release(); raise ValueError("fps must be between 2 and 60")
    _stop.pop((run, clip), None); _set(run, clip, "running", chunk=0, chunks=0, started=time.time(), fps=fps, thinking=bool(thinking), model=model)
    threading.Thread(target=_job, args=(run, clip, C.RUNS / run / c["ref"], fps, bool(thinking), model), daemon=True).start()


def _dump(path, obj, **kw):
    """Written whole or not at all: the editor reads these files while the job is still writing them."""
    tmp = str(path) + ".tmp"; json.dump(obj, open(tmp, "w"), **kw); os.replace(tmp, path)


def _set(run, clip, st, **kw):
    _, sp, _ = _files(run, clip); os.makedirs(sp.parent, exist_ok=True); tmp = str(sp) + ".tmp"; json.dump({"status": st, **kw}, open(tmp, "w")); os.replace(tmp, sp)


def _vocab():
    def lines(rows): return "\n".join(f"- {r['key']}: {r['description']}" for r in rows)
    return lines(handshapes.catalogue()), lines(handshapes.wrist_catalogue()), lines([r for r in handshapes.palm_catalogue() if r["key"] != "as_clip"])


def _prompt(n, fps, thinking):
    fing, wrist, palm = _vocab()
    return f"""These {n} pictures are consecutive frames of a dance video, {fps:g} frames per second ({n / fps:.1f} s), cropped around one dancer. Each picture is preceded by its frame number (0 to {n - 1}). Look at all of them, in order, and label what the dancer's two hands do in EVERY frame. The hands are small and sometimes blurred or hidden by the body; when you cannot see a hand, use the movement of the arm over the neighbouring frames and the rhythm of the dance to make your best guess. Never leave a field empty. Use only the names below.

LEFT means the dancer's own left (when the dancer faces the camera it is on the viewer's right), RIGHT the dancer's own right.

FINGERS (the shape of the hand):
{fing}

WRIST (how the hand bends on the forearm):
{wrist}

PALM (which way the palm faces, relative to the dancer's own body; the forearm's roll):
{palm}

{"Think it through, but keep your reasoning short enough to finish: you have to write " + str(n) + " rows. End your answer with ONLY this JSON" if thinking else "Answer with ONLY this JSON"}, one row per frame, in this column order [frame, left_fingers, left_wrist, left_palm, right_fingers, right_wrist, right_palm]:
{{"rows":[[0,"open","neutral","palm_in","relaxed","neutral","palm_down"], ... ]}}"""


def _frames(video, out, fps):
    subprocess.run(["ffmpeg", "-v", "error", "-y", "-i", str(video), "-vf", f"fps={fps:g},scale={SIZE}:{SIZE}:force_original_aspect_ratio=decrease,pad={SIZE}:{SIZE}:(ow-iw)/2:(oh-ih)/2", "-q:v", "3", os.path.join(out, "f%05d.jpg")], check=True)
    return sorted(f for f in os.listdir(out) if f.endswith(".jpg"))


def _img(p):
    return {"type": "image_url", "image_url": {"url": "data:image/jpeg;base64," + base64.b64encode(open(p, "rb").read()).decode()}}


def _rows(txt, names):
    """[[frame, six names], ...] from the model's answer; a name that is not in the library is None (the lane keeps what it had)."""
    out = []
    for g in re.findall(r"\[\s*\d+\s*(?:,\s*\"[A-Za-z_0-9 ]+\"\s*){6}\]", txt):
        a = json.loads(g); row = [int(a[0])]
        for col, nm in zip(a[1:7], names):
            v = str(col).strip().lower().replace(" ", "_"); lane = nm
            if lane == "palm" and v in ("down", "up", "forward", "back", "in", "out"): v = "palm_" + v
            row.append(v if v in lane_names[lane] else None)
        out.append(row)
    return out


lane_names = {}


def _wait_loaded(limit=240):
    """After a crash: wait until Studio has a model loaded again (it restarts the model server by itself)."""
    t0 = time.time(); time.sleep(10)
    while time.time() - t0 < limit:
        try:
            if gpu.studio_llms_loaded(): time.sleep(5); return
        except Exception: pass
        time.sleep(5)


def _tracks(at, lanes, fps):
    """{lane: [[seconds, name], ...]} from {frame: [six names]}: a key where the label changes, the first at 0."""
    tracks = {}
    for j, lane in enumerate(lanes):
        keys, prev = [], None
        for f in sorted(at):
            v = at[f][j] or prev
            if v is None: continue
            if v != prev: keys.append([round(f / fps, 3) if keys else 0.0, v]); prev = v
        tracks[lane] = keys[:hands.MAX_KEYS]
    return tracks


def _meta(dur, bad, fps, thinking, model):
    return {"source": "draft", "model": model_name(fps, thinking, model), "duration": dur, "how": f"{MODELS[model]['label']} watched every frame of the clip at {fps:g} fps (thinking {'on' if thinking else 'off'}, {CHUNK} frames per request) and named a pose, wrist position and palm direction for each hand in each frame. {bad} answers were not in the library and were replaced by the previous label."}


def _job(run, clip, video, fps, thinking, model="qwen38"):
    global lane_names
    lane_names = {"fing": set(handpose.LIB), "wrist": set(handshapes.WRISTS), "palm": set(handshapes.PALMS) - {"as_clip"}}
    cols = ("fing", "wrist", "palm", "fing", "wrist", "palm"); lanes = ("left", "left_wrist", "left_palm", "right", "right_wrist", "right_palm")
    tmp = tempfile.mkdtemp(prefix="hands_llm_"); t0 = time.time(); loaded = False; old_ctx = C.VLM_CTX
    try:
        frames = _frames(video, tmp, fps); N = len(frames)
        if not N: raise RuntimeError("no frames in the reference video")
        chunks = (N + CHUNK - 1) // CHUNK; at = {}; bad = 0; log = lambda s: None
        _set(run, clip, "running", chunk=0, chunks=chunks, started=t0, frames=N, fps=fps, thinking=thinking, model=model)
        C.VLM_CTX = CTX; vlm.load(log, MODELS[model]["model"], MODELS[model]["variant"]); loaded = True
        for ci in range(chunks):
            if _stop.pop((run, clip), None): _set(run, clip, "stopped", chunk=ci, chunks=chunks, started=t0); return
            fs = frames[ci * CHUNK:(ci + 1) * CHUNK]; n = len(fs); _set(run, clip, "running", chunk=ci, chunks=chunks, started=t0, frames=N)
            content = [{"type": "text", "text": _prompt(n, fps, thinking)}]
            for k, f in enumerate(fs): content += [{"type": "text", "text": f"frame {k}"}, _img(os.path.join(tmp, f))]
            body = {"messages": [{"role": "user", "content": content}], "temperature": 0.6, "top_p": 0.95, "max_tokens": MAX_TOKENS if thinking else 8000, "chat_template_kwargs": {"enable_thinking": bool(thinking)}}
            rows = []
            for attempt in range(3):               # a retry when the answer is cut off or not valid, or when the model server fell over (some builds crash with speculative decoding; Studio reloads them without it)
                try:
                    r = requests.post(C.STUDIO + "/v1/chat/completions", json=body, timeout=7200); r.raise_for_status()
                except requests.RequestException:
                    if attempt == 2: raise
                    _wait_loaded(); continue
                rows = _rows(r.json()["choices"][0]["message"].get("content") or "", cols)
                if len(rows) >= 0.8 * n: break
            if len(rows) < 0.5 * n: raise RuntimeError(f"the model labelled only {len(rows)} of {n} frames in chunk {ci + 1}")
            for row in rows:
                if 0 <= row[0] < n: at[ci * CHUNK + row[0]] = row[1:]
            bad += sum(v is None for row in rows for v in row[1:])
            if ci + 1 < chunks:                # what is labelled so far lands now: the editor takes each part as it arrives
                upto = round((ci + 1) * CHUNK / fps, 2); _dump(_files(run, clip)[0], {"tracks": _tracks(at, lanes, fps), "meta": _meta(round(N / fps, 2), bad, fps, thinking, model), "finished": None, "final": False, "upto": upto, "chunk": ci + 1})
            _set(run, clip, "running", chunk=ci + 1, chunks=chunks, started=t0, frames=N)
        tracks = _tracks(at, lanes, fps); dur = round(N / fps, 2); meta = _meta(dur, bad, fps, thinking, model)
        tp, sp, dp = _files(run, clip)
        _dump(tp, {"tracks": tracks, "meta": meta, "finished": time.time(), "final": True, "upto": dur, "chunk": chunks}, indent=1)
        _dump(dp, {"tracks": {k: v for k, v in tracks.items() if v}, "duration": dur, "model": meta["model"]}, indent=1)       # only the proposal: the person's own labels file is not touched
        _set(run, clip, "done", chunk=chunks, chunks=chunks, started=t0, seconds=round(time.time() - t0), fps=fps, thinking=thinking, model=model); _record(model, thinking, (time.time() - t0) / chunks)
    except Exception as e:
        _set(run, clip, "failed", error=f"{type(e).__name__}: {str(e)[:200]}", started=t0)
    finally:
        C.VLM_CTX = old_ctx
        if loaded:
            try: vlm.unload(lambda s: None)
            except Exception: pass
        shutil.rmtree(tmp, ignore_errors=True); _lock.release()
