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

FPS, SIZE, CHUNK_SECONDS = 25, 512, 5               # default frames per second, picture side in px, seconds of video per request (a request is always this long, whatever the fps: 125 frames at 25 fps, 62 at 12.5 fps)
CTX, MAX_TOKENS = 65536, 26000                     # the model's context (it holds 35 000 tokens of pictures plus the thinking) and the most it may write per request
TEMPERATURE = 0.6                                  # how freely the model samples; lower repeats itself more


def model_name(fps, thinking, model="qwen38", temperature=TEMPERATURE): return f"{MODELS[model]['label']} ({fps:g} fps, thinking {'on' if thinking else 'off'}{'' if temperature == TEMPERATURE else f', temperature {temperature:g}'})"
_lock = threading.Lock(); _stop = {}
CORE = {"fing": ["open", "relaxed", "fist", "point", "grip", "thumbs_up", "pinch", "claw", "spread"], "wrist": ["neutral", "flex_40", "ext_40", "radial_20", "ulnar_30"]}      # the small vocabulary (vocab="core"): the nine finger poses pinned in the editor, five wrist positions, the palm directions as they are
MODELS = {"qwen38": {"label": "Qwen3.8 27B", "model": C.VLM_MODEL, "variant": C.VLM_VARIANT},
          "qwen36": {"label": "Qwen3.6 35B-A3B", "model": "unsloth/Qwen3.6-35B-A3B-MTP-GGUF", "variant": "UD-IQ4_NL"}}      # the vision-language models that can label a clip (all in Unsloth Studio)
_TIMING = C.RUNS / ".hands_llm_timing2.json"      # seconds the model took per frame sent, per model and mode ("qwen38:on"), from the jobs that finished here (a running mean); seeded from the first measurements
_DEFAULT = {"qwen38:on": {"s": 1.33, "n": 1}, "qwen38:off": {"s": 0.93, "n": 2}, "qwen36:on": {"s": 1.85, "n": 2}, "qwen36:off": {"s": 0.62, "n": 2}}


def timing():
    """{"qwen38:on": {s, n}, ...}: seconds per frame sent for each model and thinking mode; n = how many jobs the figure comes from."""
    try: t = json.load(open(_TIMING))
    except Exception: t = {}
    return {k: t.get(k) or v for k, v in _DEFAULT.items()}


def _record(model, thinking, per_frame):
    t = timing(); k = f"{model}:{'on' if thinking else 'off'}"; a = t[k]; n = a["n"] + 1; t[k] = {"s": round((a["s"] * a["n"] + per_frame) / n, 3), "n": n}
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


def start(run, clip, fps=FPS, thinking=True, model="qwen38", temperature=TEMPERATURE, chunking="seconds", expect=None, bpm=None, vocab="full"):
    """Start the annotation in the background. Raises ValueError when it cannot (no such clip, no video, another annotation running)."""
    clip = os.path.basename(clip); c = hands._clip(run, clip)
    if c is None: raise ValueError("no such clip")
    if model not in MODELS: raise ValueError("unknown model " + str(model))
    if not c.get("ref") or not (C.RUNS / run / c["ref"]).exists(): raise ValueError("this clip has no reference video to look at")
    if not _lock.acquire(blocking=False): raise ValueError("another clip is being annotated; wait for it to finish")
    temperature = float(temperature); fps = float(fps); v = hands.video_info(run, clip)
    if v and fps > v["fps"] + 0.01: fps = v["fps"]              # the video has no more frames than its own rate
    if not (2 <= fps <= 60): _lock.release(); raise ValueError("fps must be between 2 and 60")
    if not (0 <= temperature <= 1.5): _lock.release(); raise ValueError("temperature must be between 0 and 1.5")
    if chunking not in ("seconds", "bar"): _lock.release(); raise ValueError("chunking is seconds or bar")
    if vocab not in ("full", "core"): _lock.release(); raise ValueError("vocab is full or core")
    expect = None if expect in (None, "", False, 0) else float(expect); bpm = None if bpm in (None, "", 0) else float(bpm)
    _stop.pop((run, clip), None); _set(run, clip, "running", chunk=0, chunks=0, started=time.time(), fps=fps, thinking=bool(thinking), model=model, temperature=temperature, chunking=chunking, expect=expect, vocab=vocab)
    threading.Thread(target=_job, args=(run, clip, C.RUNS / run / c["ref"], fps, bool(thinking), model, temperature, chunking, expect, bpm, vocab), daemon=True).start()


def _dump(path, obj, **kw):
    """Written whole or not at all: the editor reads these files while the job is still writing them."""
    tmp = str(path) + ".tmp"; json.dump(obj, open(tmp, "w"), **kw); os.replace(tmp, path)


def _set(run, clip, st, **kw):
    _, sp, _ = _files(run, clip); os.makedirs(sp.parent, exist_ok=True); tmp = str(sp) + ".tmp"; json.dump({"status": st, **kw}, open(tmp, "w")); os.replace(tmp, sp)


def _vocab(vocab="full"):
    def lines(rows, keep=None): return "\n".join(f"- {r['key']}: {r['description']}" for r in rows if keep is None or r["key"] in keep)
    core = vocab == "core"
    return lines(handshapes.catalogue(), CORE["fing"] if core else None), lines(handshapes.wrist_catalogue(), CORE["wrist"] if core else None), lines([r for r in handshapes.palm_catalogue() if r["key"] != "as_clip"])


def _prompt(n, fps, thinking, expect=None, vocab="full"):
    fing, wrist, palm = _vocab(vocab)
    hint = "" if not expect else f"\n\nA person labelling these {n} frames by hand makes about {max(1, round(expect * n / fps))} changes per lane in these {n / fps:.1f} s (about {expect:.1f} per second for each hand and each of fingers, wrist and palm). Label a change only where the hand clearly changes, and aim for about that many."
    return f"""These {n} pictures are consecutive frames of a dance video, {fps:g} frames per second ({n / fps:.1f} s), cropped around one dancer. Each picture is preceded by its frame number (0 to {n - 1}). Look at all of them, in order, and label what the dancer's two hands do in EVERY frame. The hands are small and sometimes blurred or hidden by the body; when you cannot see a hand, use the movement of the arm over the neighbouring frames and the rhythm of the dance to make your best guess. Never leave a field empty. Use only the names below.{hint}

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


def _meta(dur, bad, fps, thinking, model, temperature=TEMPERATURE, chunking="seconds", expect=None, vocab="full"):
    return {"source": "draft", "model": model_name(fps, thinking, model, temperature), "duration": dur, "how": f"{MODELS[model]['label']} watched every frame of the clip at {fps:g} fps (thinking {'on' if thinking else 'off'}, {"one bar of the music" if chunking == "bar" else str(CHUNK_SECONDS) + " s of video"} per request{f", told to expect about {expect:g} changes per lane per second" if expect else ""}{", small vocabulary (9 finger poses, 5 wrist positions)" if vocab == "core" else ""}) and named a pose, wrist position and palm direction for each hand in each frame. {bad} answers were not in the library and were replaced by the previous label."}


def _ranges(video, N, fps, chunking, bpm=None):
    """[(first frame, end frame), ...]: what each request is shown. "seconds": CHUNK_SECONDS of video each; "bar": one bar of the music each (the sound of the video gives the beat grid; the stretch before the first bar and the one after the last are requests of their own)."""
    per = max(8, round(CHUNK_SECONDS * fps))
    if chunking == "bar":
        from . import beats
        g = beats.grid(video, bpm=bpm)
        if g:
            cuts = [0] + [round(b * fps) for b in beats.bar_boundaries(g, N / fps)] + [N]; cuts = sorted(set(c for c in cuts if 0 <= c <= N)); out = []
            for a, b in zip(cuts, cuts[1:]):
                if out and b - a < 6: out[-1] = (out[-1][0], b)             # a sliver is not worth a request
                elif b - a >= 1: out.append((a, b))
            if len(out) > 1 and out[0][1] - out[0][0] < 6: out[1] = (0, out[1][1]); out.pop(0)
            return out
    return [(a, min(N, a + per)) for a in range(0, N, per)]


def _job(run, clip, video, fps, thinking, model="qwen38", temperature=TEMPERATURE, chunking="seconds", expect=None, bpm=None, vocab="full"):
    global lane_names
    lane_names = {"fing": set(CORE["fing"] if vocab == "core" else handpose.LIB), "wrist": set(CORE["wrist"] if vocab == "core" else handshapes.WRISTS), "palm": set(handshapes.PALMS) - {"as_clip"}}
    cols = ("fing", "wrist", "palm", "fing", "wrist", "palm"); lanes = ("left", "left_wrist", "left_palm", "right", "right_wrist", "right_palm")
    tmp = tempfile.mkdtemp(prefix="hands_llm_"); t0 = time.time(); loaded = False; old_ctx = C.VLM_CTX
    try:
        frames = _frames(video, tmp, fps); N = len(frames)
        if not N: raise RuntimeError("no frames in the reference video")
        ranges = _ranges(video, N, fps, chunking, bpm); chunks = len(ranges); at = {}; bad = 0; log = lambda s: None
        _set(run, clip, "running", chunk=0, chunks=chunks, started=t0, frames=N, fps=fps, thinking=thinking, model=model)
        C.VLM_CTX = CTX; vlm.load(log, MODELS[model]["model"], MODELS[model]["variant"]); loaded = True
        for ci in range(chunks):
            if _stop.pop((run, clip), None): _set(run, clip, "stopped", chunk=ci, chunks=chunks, started=t0); return
            lo, hi = ranges[ci]; fs = frames[lo:hi]; n = len(fs); _set(run, clip, "running", chunk=ci, chunks=chunks, started=t0, frames=N)
            content = [{"type": "text", "text": _prompt(n, fps, thinking, expect, vocab)}]
            for k, f in enumerate(fs): content += [{"type": "text", "text": f"frame {k}"}, _img(os.path.join(tmp, f))]
            body = {"messages": [{"role": "user", "content": content}], "temperature": temperature, "top_p": 0.95, "max_tokens": MAX_TOKENS if thinking else 8000, "chat_template_kwargs": {"enable_thinking": bool(thinking)}}
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
                if 0 <= row[0] < n: at[lo + row[0]] = row[1:]
            bad += sum(v is None for row in rows for v in row[1:])
            if ci + 1 < chunks:                # what is labelled so far lands now: the editor takes each part as it arrives
                upto = round(hi / fps, 2); _dump(_files(run, clip)[0], {"tracks": _tracks(at, lanes, fps), "meta": _meta(round(N / fps, 2), bad, fps, thinking, model, temperature, chunking, expect, vocab), "finished": None, "final": False, "upto": upto, "chunk": ci + 1})
            _set(run, clip, "running", chunk=ci + 1, chunks=chunks, started=t0, frames=N)
        tracks = _tracks(at, lanes, fps); dur = round(N / fps, 2); meta = _meta(dur, bad, fps, thinking, model, temperature, chunking, expect, vocab)
        tp, sp, dp = _files(run, clip)
        _dump(tp, {"tracks": tracks, "meta": meta, "finished": time.time(), "final": True, "upto": dur, "chunk": chunks}, indent=1)
        _dump(dp, {"tracks": {k: v for k, v in tracks.items() if v}, "duration": dur, "model": meta["model"]}, indent=1)       # only the proposal: the person's own labels file is not touched
        _set(run, clip, "done", chunk=chunks, chunks=chunks, started=t0, seconds=round(time.time() - t0), fps=fps, thinking=thinking, model=model); _record(model, thinking, (time.time() - t0) / N)
    except Exception as e:
        _set(run, clip, "failed", error=f"{type(e).__name__}: {str(e)[:200]}", started=t0)
    finally:
        C.VLM_CTX = old_ctx
        if loaded:
            try: vlm.unload(lambda s: None)
            except Exception: pass
        shutil.rmtree(tmp, ignore_errors=True); _lock.release()
