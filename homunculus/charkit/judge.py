"""The local judges for charkit: questions are BATCHED (one load of each judge answers every queued question, then it is unloaded, so the 24 GB card swaps as few times as possible),
every answer is JSON, parsed leniently and cleaned against a fixed shape, and cached in the kit state by a hash of the question and its pictures (a resumed run never asks twice).

A query: {"key": "pictures:hoodie:r0", "kind": "pick" | "check" | "describe", "prompt": str, "images": [paths], "labels": [str], "n": number of candidates, "files": [candidate paths]}.
An answer (kind pick):  {"pick": int | None, "candidates": [{"index", "pass", "issues": [...]}], "votes": {judge: raw answer}}; None when no judge gave a usable answer.
Live judges: homunculus.vlm (Unsloth Studio, models in config.JUDGES); the panel is the majority of the judges that answered (a tie keeps the first judge's call).
StubJudge (--dry-run): answers from a fixture file of recorded decisions (file names, not indices), else 'every candidate passes, the first is picked'.
    .venv/bin/python -m homunculus.charkit.judge --selftest       checks the parser on malformed answers (no GPU)"""
import hashlib, json, os, re
from collections import Counter
from . import prompts as P

def _balanced(txt, start):
    """The JSON object starting at txt[start] == '{' (strings and escapes respected), or None."""
    depth, ins, esc = 0, False, False
    for i in range(start, len(txt)):
        c = txt[i]
        if ins:
            if esc: esc = False
            elif c == "\\": esc = True
            elif c == '"': ins = False
        elif c == '"': ins = True
        elif c == "{": depth += 1
        elif c == "}":
            depth -= 1
            if depth == 0: return txt[start:i + 1]
    return None

def parse_json(txt):
    """The last well-formed JSON object in a model's reply (thinking text, ``` fences, trailing commas, single quotes, True/False are tolerated), else None."""
    if not txt: return None
    txt = re.sub(r"<think>.*?</think>", "", txt, flags=re.S).replace("```json", "```")
    found = []
    for m in re.finditer(r"\{", txt):
        s = _balanced(txt, m.start())
        if not s: continue
        for cand in (s, re.sub(r",\s*([}\]])", r"\1", s), re.sub(r",\s*([}\]])", r"\1", s).replace("'", '"').replace("True", "true").replace("False", "false").replace("None", "null")):
            try: found.append((len(s), json.loads(cand))); break
            except ValueError: pass
    if not found: return None
    return max(found, key=lambda f: f[0])[1]      # the outermost (longest) object: inner candidate objects parse too

def clean_issues(v):
    out = []
    for i in (v if isinstance(v, list) else [v] if v else []):
        w = re.sub(r"[^a-z_]", "", str(i).strip().lower().replace(" ", "_").replace("-", "_"))
        w = {"mannequin": "mannequin_visible", "person": "person_visible", "outline": "ink_outlines", "outlines": "ink_outlines", "line_art": "ink_outlines", "tilt": "tilted",
             "crop": "cropped", "hands": "bad_hands", "face": "different_face", "pokethrough": "poke_through"}.get(w, w)
        out.append(w if w in P.ISSUES else "other")
    return sorted(set(out))

def clean_pick(d, n):
    """A pick answer in its fixed shape, or None if it has no usable content. A 'pick' outside 0..n-1 (e.g. -1) is None; a candidate missing from the list counts as not judged."""
    if not isinstance(d, dict): return None
    try: pick = int(d.get("pick"))
    except (TypeError, ValueError): pick = None
    pick = pick if pick is not None and 0 <= pick < n else None
    cands = {}
    for c in d.get("candidates") or []:
        if not isinstance(c, dict): continue
        try: i = int(c.get("index"))
        except (TypeError, ValueError): continue
        if 0 <= i < n: cands[i] = {"index": i, "pass": bool(c.get("pass")) if not isinstance(c.get("pass"), str) else c["pass"].strip().lower() in ("true", "yes", "pass"), "issues": clean_issues(c.get("issues"))}
    if pick is None and not cands: return None
    if pick is not None and pick in cands and not cands[pick]["pass"]: cands[pick]["pass"] = True      # a model that picks a candidate it failed: trust the pick (it is told to pick only passing ones)
    return {"pick": pick, "candidates": [cands.get(i, {"index": i, "pass": None, "issues": []}) for i in range(n)]}

def clean_check(d):
    if not isinstance(d, dict) or "pass" not in d: return None
    p = d["pass"]; p = p.strip().lower() in ("true", "yes", "pass") if isinstance(p, str) else bool(p)
    return {"pass": p, "issues": clean_issues(d.get("issues")), "note": str(d.get("note", ""))[:300]}

_KEY = re.compile(r"[^a-z0-9_]")
def clean_describe(d):
    """The character's item list: garment/accessory keys made unique snake_case words, regions from the fixed list (unknown -> upper / neck)."""
    if not isinstance(d, dict) or not isinstance(d.get("garments"), list): return None
    def key(s, used):
        k = _KEY.sub("", str(s or "item").lower().replace(" ", "_").replace("-", "_"))[:24] or "item"; b, i = k, 2
        while k in used or k in ("body", "dressed", "shoes", "hair"): k = f"{b}{i}"; i += 1
        used.add(k); return k
    used = set(); out = {k: d.get(k) for k in ("sex", "age", "who", "build", "skin")}
    out["sex"] = out["sex"] if out["sex"] in ("male", "female") else "male"; out["age"] = out["age"] if out["age"] in ("child", "teen", "adult", "older") else "adult"
    out["garments"] = [{"key": key(g.get("key"), used), "region": g.get("region") if g.get("region") in ("upper", "lower", "full", "outer") else "upper", "description": str(g.get("description") or g.get("key"))}
                       for g in d["garments"] if isinstance(g, dict)]
    out["accessories"] = [{"key": key(a.get("key"), used), "region": a.get("region") if a.get("region") in ("head", "face", "neck", "wrist", "waist", "hand") else "neck", "description": str(a.get("description") or a.get("key"))}
                          for a in d.get("accessories") or [] if isinstance(a, dict)]
    for k in ("hair", "shoes"):
        v = d.get(k) if isinstance(d.get(k), dict) else {}; out[k] = {"present": bool(v.get("present")), "description": str(v.get("description") or k)}
    return out

def combine(kind, answers, n):
    """Majority of the judges that answered. pick: per candidate pass = majority of its votes (ties pass), pick = commonest pick among the judges (tie: the first judge's);
    issues = those named by at least half of the judges that failed the candidate. check: majority pass. describe: the first judge's answer."""
    ok = [a for a in answers if a]
    if not ok: return None
    if kind == "describe": return ok[0]
    if kind == "check":
        yes = sum(a["pass"] for a in ok); iss = Counter(i for a in ok if not a["pass"] for i in a["issues"])
        return {"pass": yes * 2 >= len(ok), "issues": sorted(i for i, c in iss.items() if c * 2 >= max(1, len(ok) - yes)), "note": ok[0].get("note", "")}
    cands = []
    for i in range(n):
        vs = [a["candidates"][i] for a in ok if a["candidates"][i]["pass"] is not None]; yes = sum(v["pass"] for v in vs); no = len(vs) - yes
        iss = Counter(x for v in vs if not v["pass"] for x in v["issues"])
        cands.append({"index": i, "pass": (yes >= no) if vs else None, "issues": sorted(x for x, c in iss.items() if c * 2 >= max(1, no)), "votes": f"{yes}-{no}"})
    picks = Counter(a["pick"] for a in ok if a["pick"] is not None)
    pick = None
    if picks:
        top = max(picks.values()); pick = next(a["pick"] for a in ok if a["pick"] is not None and picks[a["pick"]] == top)
    if pick is not None and cands[pick]["pass"] is False: pick = next((c["index"] for c in cands if c["pass"]), None)     # the panel failed the commonest pick
    return {"pick": pick, "candidates": cands}

CLEAN = {"pick": lambda d, q: clean_pick(d, q["n"]), "check": lambda d, q: clean_check(d), "describe": lambda d, q: clean_describe(d)}
RETRY = "\n\nYour previous reply could not be read. Reply with ONLY the JSON object, exactly in the requested shape."

def qhash(q):
    h = hashlib.sha1((q["kind"] + q["prompt"] + "|".join(q.get("labels") or [])).encode())
    for p in q.get("images", []):
        st = os.stat(p); h.update(f"{os.path.abspath(p)}:{st.st_size}:{int(st.st_mtime)}".encode())
    return h.hexdigest()[:16]


class Judge:
    """Live judges through Unsloth Studio. judges: [(model, variant), ...] (config.SHEET_JUDGES = Qwen3.8 alone by default; --panel = config.JUDGES, the three-judge majority)."""
    stub = False
    def __init__(self, K, judges):
        self.K, self.judges = K, judges

    def session(self, queries):
        """Answer every query; returns {key: answer or None}. Cached answers (same question, same pictures) are reused without loading anything."""
        K = self.K; cache = K.state.setdefault("vlm", {}); out, todo = {}, []
        for q in queries:
            c = cache.get(q["key"])
            if c and c.get("hash") == qhash(q): out[q["key"]] = c["answer"]
            else: todo.append(q)
        if not todo: return out
        from .. import vlm, gpu
        raw = {q["key"]: [] for q in todo}
        with K.gpu_phase(f"judges ({len(todo)} questions)"):
            for model, variant in self.judges:
                name = model.split("/")[-1].replace("-GGUF", ""); got = {}
                try:
                    vlm.load(K.log, model, variant)
                    try:
                        for q in todo: got[q["key"]] = self._ask(vlm, q)
                    finally: vlm.unload(K.log)
                except Exception as e: K.log(f"judge {name} failed: {type(e).__name__}: {str(e)[:160]}")
                for q in todo: raw[q["key"]].append((name, got.get(q["key"])))
            gpu.unload_llms()
        for q in todo:
            ans = combine(q["kind"], [a for _, a in raw[q["key"]]], q.get("n", 0))
            if ans is not None: ans["votes"] = {n: a for n, a in raw[q["key"]]}
            out[q["key"]] = ans; cache[q["key"]] = {"hash": qhash(q), "answer": ans}
        K.save(); return out

    def _ask(self, vlm, q):
        for attempt in range(3):          # the same question again with a firmer ending when the reply is not usable JSON
            try: txt = vlm.ask(q["prompt"] + (RETRY if attempt else ""), q.get("images", []), max_tokens=3000 if q["kind"] == "describe" else 1500, labels=q.get("labels"))
            except Exception as e: self.K.log(f"judge request failed ({type(e).__name__}); retrying"); continue
            ans = CLEAN[q["kind"]](parse_json(txt), q)
            if ans is not None: return ans
            self.K.log(f"{q['key']}: reply not usable (attempt {attempt + 1}): {txt[:160]!r}")
        return None


class StubJudge:
    """--dry-run: no model. Answers come from fixture["answers"][key-without-round] (recorded decisions by file name: {"pick": "front_s941.png", "fail": {"front_s981.png": ["mannequin_visible"]}}
    or a literal describe/check answer, or {"unusable": true}); a query without a recorded answer gets 'every candidate passes, the first (numerically best) is picked'."""
    stub = True
    def __init__(self, K, fixture):
        self.K, self.rec = K, (fixture or {}).get("answers", {})

    def session(self, queries):
        out = {}
        for q in queries:
            r = self.rec.get(q["key"].rsplit(":r", 1)[0]) if q["kind"] != "describe" else self.rec.get("describe")
            if isinstance(r, dict) and r.get("unusable"): out[q["key"]] = None          # a recorded 'the judge gave nothing usable' (tests the numbers-decide path)
            elif q["kind"] == "describe": out[q["key"]] = clean_describe(r)
            elif q["kind"] == "check": out[q["key"]] = clean_check(r or {"pass": True, "issues": [], "note": "stub"})
            else:
                files = q["files"]; fail = (r or {}).get("fail", {}); want = (r or {}).get("pick")          # recorded by path suffix: "front_s941.png", "s42/textured.glb"
                hit = lambda f: next((v for k, v in fail.items() if f.endswith(k)), None)
                cands = [{"index": i, "pass": hit(f) is None, "issues": clean_issues(hit(f) or [])} for i, f in enumerate(files)]
                pick = next((i for i, f in enumerate(files) if want and f.endswith(want) and cands[i]["pass"]), None)
                if pick is None: pick = next((c["index"] for c in cands if c["pass"]), None)
                out[q["key"]] = {"pick": pick, "candidates": cands, "votes": {"stub": "recorded" if r else "default"}}
            self.K.log(f"[stub judge] {q['key']}: {json.dumps({k: v for k, v in (out[q['key']] or {}).items() if k != 'votes'})[:220]}")
        return out


def _selftest():
    n = 3
    cases = [('{"pick": 1, "candidates": [{"index":0,"pass":false,"issues":["mannequin"]},{"index":1,"pass":true,"issues":[]},{"index":2,"pass":true,"issues":[]}]}', 1),
             ('Sure! ```json\n{"pick": 2, "candidates": [{"index": 2, "pass": "yes", "issues": ["Ink outlines"]},]}\n``` hope that helps', 2),
             ("<think>candidate {0} looks odd</think> {'pick': 0, 'candidates': [{'index': 0, 'pass': True, 'issues': []}]}", 0),
             ('{"pick": -1, "candidates": [{"index": 0, "pass": false, "issues": ["glasses", "banana"]}]}', None),
             ("no json at all", "none"), ('{"pick": 7}', "none")]
    for txt, want in cases:
        a = clean_pick(parse_json(txt), n); got = "none" if a is None else a["pick"]
        assert got == want, (txt, a); print("ok", repr(txt[:50]), "->", got, a and [c["issues"] for c in a["candidates"]])
    v = combine("pick", [clean_pick(parse_json(cases[0][0]), n), clean_pick({"pick": 2, "candidates": [{"index": 0, "pass": False, "issues": ["mannequin_visible"]}, {"index": 1, "pass": False, "issues": ["lid"]}, {"index": 2, "pass": True}]}, n),
                         clean_pick({"pick": 1, "candidates": [{"index": 1, "pass": True}]}, n)], n)
    assert v["pick"] == 1 and v["candidates"][0]["pass"] is False and v["candidates"][0]["issues"] == ["mannequin_visible"], v; print("ok panel", v)
    d = clean_describe({"sex": "M", "garments": [{"key": "Hoodie", "region": "top"}, {"key": "hoodie"}], "accessories": [{"key": "body"}], "hair": {"present": 1}})
    assert [g["key"] for g in d["garments"]] == ["hoodie", "hoodie2"] and d["accessories"][0]["key"] == "body2" and d["garments"][0]["region"] == "upper" and d["sex"] == "male", d; print("ok describe", d)
    print("selftest passed")

if __name__ == "__main__":
    import sys
    if "--selftest" in sys.argv: _selftest()
