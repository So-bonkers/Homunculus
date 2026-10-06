"""Qwen3.8-27B (vision) via Unsloth Studio: load, ask with images, parse JSON, unload."""
import base64, io, json, re, time, requests
from PIL import Image
from . import config as C, gpu

_CUR = {"model": C.VLM_MODEL}

class Cancelled(Exception):
    """The human made the call while the judges were still voting."""

def load(log, model=None, variant=None):
    model = model or C.VLM_MODEL; variant = variant or C.VLM_VARIANT; _CUR["model"] = model
    from . import notify
    notify.need_studio(log, what="the planner and the judges")
    gpu.free_all(log); gpu.wait_for_headroom("vlm", log)
    log(f"loading VLM {model} ({variant})")
    r = requests.post(C.STUDIO + "/api/inference/load", timeout=120, json={
        "model_path": model, "gguf_variant": variant, "max_seq_length": C.VLM_CTX,
        "cache_type_kv": "q8_0", "n_parallel": 1})
    r.raise_for_status()
    t0 = time.time()
    while time.time() - t0 < 900:
        p = requests.get(C.STUDIO + "/api/inference/load-progress", timeout=10).json()
        if p.get("error"): raise RuntimeError(f"VLM load failed: {p['error']}")
        if p.get("phase") in ("ready", "loaded"): log(f"VLM ready in {time.time()-t0:.0f}s, VRAM {gpu.vram_gb():.1f} GB"); return
        time.sleep(3)
    raise RuntimeError("VLM load timed out")

def unload(log):
    try: requests.post(C.STUDIO + "/api/inference/unload", json={"model_path": _CUR["model"]}, timeout=60)
    except requests.RequestException: pass
    if gpu.studio_llms_loaded():      # still answering a request we stopped waiting for: Studio unloads it only once it's idle
        log("waiting for the judge to stop before unloading it"); gpu.unload_llms()
    log(f"VLM unloaded, VRAM {gpu.vram_gb():.1f} GB")

def _img(path, max_side=640):
    im = Image.open(path).convert("RGB"); im.thumbnail((max_side, max_side))
    buf = io.BytesIO(); im.save(buf, "JPEG", quality=90)
    return {"type": "image_url", "image_url": {"url": "data:image/jpeg;base64," + base64.b64encode(buf.getvalue()).decode()}}

def ask(prompt, images=(), max_tokens=3000, labels=None, cancel=None):
    """images: list of paths. labels: optional text shown before each image (e.g. 'Image 2 = candidate 1')."""
    content = [{"type": "text", "text": prompt}]
    for i, p in enumerate(images):
        if labels: content.append({"type": "text", "text": labels[i]})
        content.append(_img(p))
    body = {"messages": [{"role": "user", "content": content}], "temperature": 0.1, "max_tokens": max_tokens,
            "chat_template_kwargs": {"enable_thinking": False}}
    if cancel is None:
        r = requests.post(C.STUDIO + "/v1/chat/completions", timeout=1200, json=body)
    else:      # run the request aside so a human decision can cut the judge short (the caller then unloads the model)
        import threading
        box = {}
        def go():
            try: box["r"] = requests.post(C.STUDIO + "/v1/chat/completions", timeout=1200, json=body)
            except Exception as e: box["e"] = e
        th = threading.Thread(target=go, daemon=True); th.start()
        while th.is_alive():
            if cancel(): raise Cancelled()
            th.join(1.0)
        if "e" in box: raise box["e"]
        r = box["r"]
    r.raise_for_status()
    msg = r.json()["choices"][0]["message"]
    return msg.get("content") or msg.get("reasoning_content") or ""

def ask_json(prompt, images=(), required=(), retries=2, log=print, **kw):
    last = ""
    for a in range(retries + 1):
        txt = ask(prompt if a == 0 else prompt + "\n\nYour previous reply was not valid JSON with all required keys. Reply with ONLY the JSON object.", images, **kw)
        last = txt
        m = re.search(r"\{.*\}", txt, re.S)
        if m:
            try:
                d = json.loads(m.group(0))
                if all(k in d for k in required): return d
            except ValueError: pass
        log(f"VLM reply not usable (attempt {a+1}): {txt[:200]!r}")
    raise RuntimeError(f"VLM gave no valid JSON: {last[:300]!r}")


def panel(prompt, images=(), required=(), log=print, early_stop=True, human_notes="", cancel=None, **kw):
    """Ask every judge in C.JUDGES (loaded one at a time). Returns [(short_name, verdict_dict_or_None), ...].
    cancel(): checked before each judge and while it answers; True stops the panel (the human already decided)."""
    if human_notes: prompt = prompt + "\n\nThe human supervisor noted earlier (take this into account): " + human_notes
    out = []
    for i, (model, variant) in enumerate(C.JUDGES):
        if cancel and cancel(): log("you made the call; skipping the remaining judges"); break
        if early_stop and i == 2 and len([v for _, v in out if v]) == 2 and "pass" in required:
            a, b = [bool(v.get("pass")) for _, v in out if v]
            if a == b: log(f"first two judges agree ({'pass' if a else 'fail'}); skipping the third"); break
        name = model.split("/")[-1].replace("-GGUF", "")
        try:
            load(log, model, variant)
            try: out.append((name, ask_json(prompt, images, required=required, log=log, cancel=cancel, **kw)))
            finally: unload(log)
        except Cancelled:
            log(f"you made the call; stopped judge {name}"); break
        except Exception as e:
            log(f"judge {name} failed: {type(e).__name__}: {str(e)[:120]}"); out.append((name, None))
    return out

def panel_multi(queries, required=(), log=print, human_notes="", cancel=None, **kw):
    """queries: list of (prompt, images, labels). Each judge is loaded ONCE and answers every query.
    Returns a list (one per query) of [(judge_name, verdict_or_None), ...]."""
    res = [[] for _ in queries]
    for model, variant in C.JUDGES:
        name = model.split("/")[-1].replace("-GGUF", "")
        if cancel and cancel(): log("you made the call; skipping the remaining judges"); break
        try:
            load(log, model, variant)
            try:
                for qi, (prompt, images, labels) in enumerate(queries):
                    if human_notes: prompt = prompt + "\n\nThe human supervisor noted earlier (take this into account): " + human_notes
                    try: res[qi].append((name, ask_json(prompt, images, required=required, labels=labels, log=log, cancel=cancel, **kw)))
                    except Cancelled: raise
                    except Exception as e: log(f"judge {name} q{qi} failed: {str(e)[:100]}"); res[qi].append((name, None))
            finally: unload(log)
        except Cancelled:
            log(f"you made the call; stopped judge {name}"); break
        except Exception as e:
            log(f"judge {name} failed to load: {str(e)[:120]}"); [r.append((name, None)) for r in res]
    return res

def majority_pass(votes, log=print):
    """Majority of the judges that answered; ties pass (we only want to redo work when most judges see a real problem)."""
    ok = [v for _, v in votes if v]
    yes = sum(bool(v.get("pass")) for v in ok); no = len(ok) - yes
    passed = yes >= no if ok else True
    score = round(sum(float(v.get("score", 0) or 0) for v in ok) / max(len(ok), 1), 1)
    problems = []
    for n, v in votes:
        if v and not v.get("pass"): problems += [f"[{n}] {p}" for p in (v.get("problems") or [])]
    log(f"panel: {yes} pass / {no} fail -> {'PASS' if passed else 'FAIL'} (mean score {score})")
    return {"pass": passed, "score": score, "votes": {n: v for n, v in votes}, "problems": problems, "tally": f"{yes}-{no}"}
