"""The charkit stages (Ren's hand-made run of 2026-10-24/25 as a pipeline). Each stage: a deterministic job -> numeric gates -> the judges only where numbers cannot decide ->
at most MAX_REROLLS re-rolls (new seeds plus sentences from the FIXED tweak menu in prompts.py) -> if still unresolved, an entry in needs_review.json and the run goes on with the
best candidate. Heavy work is batched per stage (all pictures of a stage in one ComfyUI session, one judge session per round, one TRELLIS run per seed set).

prep       4x upscale (4x-UltraSharp, spandrel) + background cut (rembg birefnet-general; isnet-general-use as the fallback of the menu)
describe   a judge lists the character's parts: garments (with a region), shoes, hair, accessories -> the item list of the kit
head       head-and-shoulders crop of the 4x picture -> 8 Qwen redraws (straight on, no glasses, no ink) -> eye-line tilt + mirror symmetry -> the judges pick the likeness
body       full-body redraw of the picture with the approved head as a second reference -> framing (head and feet in), one figure -> the judges check framing, hands, style
pictures   one picture per item (bald base body; garments on a ghost mannequin; shoes as a pair; hair as a hairpiece; accessories as products) -> foreground / single object -> the judges
           reject mannequins and people -> background cut of each pick (and of the clean body picture: the dressed reference)
trellis    TRELLIS.2 on the dressed reference and every item, 2 seeds -> mesh gates (loads, faces, outline aspect, open edges, garment lids) -> thumbnails -> the judges pick a seed
place      tools/ren_graft/align_item.py of each item onto its region of the dressed reference -> residual <= 0.5 % of the height and a sane scale; a fixed menu of search settings
assemble   tools/ren_graft/assemble_kit.py (lids removed, the body tucked under the garments) -> poke-through ray test -> a render the judges look at
rig, bake  TODO (hooks only: rigging and texture baking onto the retopology come later)
report     the final contact sheet and a summary of the open review entries"""
import glob, json, os, shutil
import numpy as np
from PIL import Image
from .. import config as C
from . import gates as G, prompts as P
from .pipeline import contact_sheet, glb_bounds

MAX_REROLLS = 2                                                            # after the first round: at most two more (never loop forever)
SEEDS = {"head": (940, 8), "body": (960, 8), "pictures": (980, 4)}        # first seed and seeds per round (Ren's: 940-947, 960-967, 980-983); round r uses first + r * n ...
TRELLIS_SEEDS = [[42, 7], [123, 2024], [5, 77]]                            # TRELLIS seeds per round
SHOW = {"head": 8, "body": 8, "pictures": 4, "trellis": 2}                 # at most this many (numerically passing) candidates per judge question; for the head ALL of them:
                                                                           # likeness is the judges' call, the numbers only gate (Ren's picked 941 ranks 5th of 8 by the numbers)
REMBG_MENU = ["birefnet-general", "isnet-general-use"]
PLACE_MENU = [{"axes": "upright", "yaw_steps": 12, "frac": 0.7}, {"axes": "all", "yaw_steps": 12, "frac": 0.7}, {"axes": "upright", "yaw_steps": 24, "frac": 0.6}]
SCALE_OK = (0.4, 1.7)                                                      # placed item height / its region's height
GAP_MENU = [0.004, 0.008]                                                  # assemble: how far the body is tucked under the garments; a second try with more if it pokes through

def _short(f): return os.path.join(os.path.basename(os.path.dirname(f)), os.path.basename(f)) if os.path.basename(f) == "textured.glb" else os.path.basename(f)

def _rank(c):
    v = (c.get("vlm") or {}).get("pass")
    return (0 if v is True else 1 if v is None else 2, 0 if c["num"]["ok"] else 1, len((c.get("vlm") or {}).get("issues") or []) + len(c["num"]["issues"]), c["num"].get("score", 9))

def _label(c):
    n = c["num"]; v = c.get("vlm"); nums = " ".join(f"{k[0]}{n[k]}" for k in ("tilt", "sym", "fg", "residual") if k in n)
    verdict = "judge: -" if not v else "judge: pass" if v.get("pass") else "judge: " + ",".join(v.get("issues") or ["fail"])
    return f"{_short(c['file'])} r{c['round']}\n{'ok' if n['ok'] else ','.join(n['issues'])} {nums}\n{verdict}"

def select(K, stage, groups, generate, measure, question, prepare=None, show=4, rounds=1 + MAX_REROLLS):
    """The shared loop. groups: names (one per thing to choose). generate({g: {"round", "tweak", "tweak_keys"}}) -> {g: [candidate files]} (ONE batch for all groups);
    measure({g: [files]}) -> {file: gate}; prepare({g: [files]}) -> {file: picture for the judges} (thumbnails of meshes); question(g, files, pictures) -> {"prompt", "images", "labels"}.
    Returns {g: chosen file or None}; the candidates, verdicts and choices are kept in state["stages"][stage]["groups"]."""
    st = K.state["stages"][stage].setdefault("groups", {})
    for g in groups: st[g] = {"cands": [], "tweaks": [], "last_issues": [], "resolved": False, "pick": None, "how": None, "prompts": {}}
    for r in range(rounds):
        todo = [g for g in groups if not st[g]["resolved"]]
        if not todo: break
        reqs = {}
        for g in todo:
            keys, text = ([], "") if r == 0 else P.tweak_text(st[g]["last_issues"], st[g]["tweaks"])
            st[g]["tweaks"] += keys; reqs[g] = {"round": r, "tweak": text, "tweak_keys": keys}
            if r: K.decide(stage, g, action="reroll", round=r, tweaks=keys, because=sorted(set(st[g]["last_issues"])))
        new = generate(reqs)
        fresh = {g: [f for f in new.get(g, []) if f not in {c["file"] for c in st[g]["cands"]}] for g in todo}
        nums = measure({g: fs for g, fs in fresh.items() if fs}) if any(fresh.values()) else {}
        for g in todo: st[g]["cands"] += [{"file": f, "round": r, "num": nums.get(f) or {"ok": False, "issues": ["other"], "score": 9.0, "note": "not measured"}} for f in fresh[g]]
        K.save()
        shown = {g: sorted([c for c in st[g]["cands"] if c["round"] == r and c["num"]["ok"]], key=lambda c: c["num"]["score"])[:show] for g in todo}
        pics = prepare({g: [c["file"] for c in cs] for g, cs in shown.items() if cs}) if prepare and any(shown.values()) else {}
        for g, cs in shown.items():
            for c in cs: c["shown"] = pics.get(c["file"], c["file"])
        qs = [{**question(g, [c["file"] for c in cs], [c["shown"] for c in cs]), "key": f"{stage}:{g}:r{r}", "kind": "pick", "n": len(cs), "files": [c["file"] for c in cs]} for g, cs in shown.items() if cs]
        ans = K.judge.session(qs) if qs else {}
        for g in todo:
            cs = shown[g]; s = st[g]
            if not fresh[g]: K.decide(stage, g, action="no_new_candidates", round=r); continue        # the issues of the last real round stay: the next re-roll's tweaks come from them
            s["last_issues"] = [i for c in s["cands"] if c["round"] == r for i in c["num"]["issues"]]
            if not cs: K.decide(stage, g, action="all_failed_numbers", round=r, issues=sorted(set(s["last_issues"]))); continue
            a = ans.get(f"{stage}:{g}:r{r}")
            if a is None:          # no usable judge answer: the numbers decide, and a person should look
                s.update(resolved=True, pick=cs[0]["file"], how="numbers (judges gave no usable answer)")
                K.review(stage, g, "the judges gave no usable answer; picked the numerically best candidate", [_cinfo(c) for c in cs], cs[0]["file"], images=[c["shown"] for c in cs])
            else:
                for c, v in zip(cs, a["candidates"]): c["vlm"] = v; s["last_issues"] += v["issues"] if v.get("pass") is False else []
                if a["pick"] is not None: s.update(resolved=True, pick=cs[a["pick"]]["file"], how=f"judges (round {r})")
            K.decide(stage, g, action="pick" if s["resolved"] else "none_acceptable", round=r, pick=s["pick"] and _short(s["pick"]), shown=[_short(c["file"]) for c in cs],
                     verdicts=a and [{"pass": v.get("pass"), "issues": v.get("issues")} for v in a["candidates"]])
        K.save()
    out = {}
    for g in groups:
        s = st[g]
        if not s["resolved"]:
            if s["cands"]:
                best = min(s["cands"], key=_rank); s.update(pick=best["file"], how=f"best of {len(s['cands'])} after {rounds} rounds (unresolved)")
                seen = sorted({i for c in s["cands"] for i in c["num"]["issues"] + ((c.get("vlm") or {}).get("issues") or [])})
                K.review(stage, g, f"no candidate passed after {rounds} rounds (issues seen: {', '.join(seen) or 'none named'}; tweaks tried: {', '.join(s['tweaks']) or 'none'}); continuing with the best",
                         [_cinfo(c) for c in sorted(s["cands"], key=_rank)[:8]], best["file"], reasons=seen, images=[c.get("shown", c["file"]) for c in sorted(s["cands"], key=_rank)[:8]])
            else: K.review(stage, g, "no candidates were produced at all", [], None)
        cs = s["cands"]
        if cs: s["sheet"] = contact_sheet([c.get("shown", c["file"]) for c in cs], [_label(c) for c in cs], K.p("sheets", f"{stage}_{g}.png"),
                                          pick=next((c.get("shown", c["file"]) for c in cs if c["file"] == s["pick"]), None), bad=[c.get("shown", c["file"]) for c in cs if (c.get("vlm") or {}).get("pass") is False or not c["num"]["ok"]])
        out[g] = s["pick"]
    K.save(); return out

def _cinfo(c): return {"file": c["file"], "shown": c.get("shown"), "round": c["round"], "numeric": c["num"], "judges": c.get("vlm")}

def _ask_pick(prompt, refs, ref_labels, pics):
    return {"prompt": prompt, "images": list(refs) + list(pics), "labels": list(ref_labels) + [f"Picture {len(refs) + i + 1} = candidate {i}" for i in range(len(pics))]}

def _desc(K): return K.state.get("describe") or {}
def _items(K): return K.state.get("items") or []
def _redraw_gen(K, key, src, prompt, refs=(), stage=None):
    """generate() for one redrawn group: round r = SEEDS[stage] shifted by r * n, prompt + the round's tweak."""
    first, n = SEEDS[stage or key]
    def gen(reqs):
        batch = []
        for g, q in reqs.items():
            sp = src(g) if callable(src) else src; pr = (prompt(g) if callable(prompt) else prompt) + (" " + q["tweak"] if q["tweak"] else "")
            K.state["stages"][stage or key]["groups"][g]["prompts"][str(q["round"])] = pr
            batch.append({"key": f"{stage or key}/{g}", "round": q["round"], "src": sp, "prompt": pr, "refs": list(refs(g) if callable(refs) else refs), "seeds": list(range(first + q["round"] * n, first + (q["round"] + 1) * n)),
                          "out_dir": K.p(stage or key, g if stage else "", "x").rsplit("/", 1)[0]})
        return {k.split("/", 1)[1]: v for k, v in K.jobs.redraw(batch).items()}      # jobs key by "stage/group": the body stage and the base-body item are both "body"
    return gen


# ------------------------------------------------------------------------------------------------------------------------------------------------------------------
def st_prep(K):
    src = K.state["input"]; x4 = K.p("prep", "x4.png")
    if not K.jobs.upscale(src, x4): raise RuntimeError("4x upscale failed (see the log in the runs folder)")
    w, h = Image.open(src).size; W, H = Image.open(x4).size
    if (W, H) != (4 * w, 4 * h): K.review("prep", "upscale", f"the 4x picture is {W}x{H}, expected {4 * w}x{4 * h}", chosen=x4)
    rgba = K.p("prep", "figure_rgba.png"); gate = None
    for sess in REMBG_MENU:
        if K.jobs.rembg(x4, rgba, sess, key="figure"):
            gate = G.alpha(rgba, "base"); K.decide("prep", "figure", action="cut", session=sess, gate=gate)
            if gate["ok"]: break
    if gate is None: raise RuntimeError("background cut failed")
    if not gate["ok"]: K.review("prep", "figure", f"background cut: {', '.join(gate['issues'])}", [gate], rgba, images=[rgba])
    a = np.asarray(Image.open(rgba).convert("RGBA"))[..., 3] > 128; ys, xs = np.nonzero(a)
    K.state["figure_box"] = [float(xs.min() / a.shape[1]), float(ys.min() / a.shape[0]), float(xs.max() / a.shape[1]), float(ys.max() / a.shape[0])]
    K.picks.update(x4=x4, figure_rgba=rgba); return f"4x {W}x{H}, cut fg {gate['fg']:.3f}"

def build_items(d):
    """The kit's items from the description (the order they are drawn and judged in)."""
    its = [{"key": "body", "kind": "base", "region": "body", "source": "body", "description": "base body"}]
    its += [{"key": g["key"], "kind": "garment", "region": g["region"], "source": "body", "description": g["description"]} for g in d.get("garments", [])]
    if d.get("shoes", {}).get("present"): its.append({"key": "shoes", "kind": "shoes", "region": "feet", "source": "body", "description": d["shoes"]["description"]})
    if d.get("hair", {}).get("present"): its.append({"key": "hair", "kind": "hair", "region": "hair", "source": "head", "description": d["hair"]["description"]})
    its += [{"key": a["key"], "kind": "accessory", "region": a["region"], "description": a["description"],          # glasses come from the original (the clean redraws have none); head/neck things from the head
             "source": "original" if a["region"] == "face" else "head" if a["region"] in ("head", "neck") else "body"} for a in d.get("accessories", [])]
    return its

DEFAULT_DESCRIPTION = {"sex": "male", "age": "adult", "who": "character", "garments": [{"key": "top", "region": "upper", "description": "top"}, {"key": "trousers", "region": "lower", "description": "trousers"}],
                       "shoes": {"present": True, "description": "shoes"}, "hair": {"present": True, "description": "hair"}, "accessories": []}

def st_describe(K):
    from . import judge as J
    if K.opts.get("describe"): d = J.clean_describe(json.load(open(K.opts["describe"]))); how = "given (--describe)"
    else:
        q = {"key": "describe", "kind": "describe", "prompt": P.DESCRIBE, "images": [K.state["input"]], "labels": ["the character"], "n": 0, "files": []}
        d = K.judge.session([q]).get("describe"); how = "judges"
        if d is None:
            d = J.clean_describe(DEFAULT_DESCRIPTION); how = "default (judges gave no usable answer)"
            K.review("describe", "character", "the judges could not describe the character; a generic item list (top, trousers, shoes, hair) is used: correct it with --describe FILE and re-run --from describe", chosen="default")
    try:
        from ..kit import BUILDS
        if BUILDS.get(K.name): d["build"] = BUILDS[K.name]       # the design sheet's words for known characters beat the judge's
    except Exception: pass
    K.state["describe"] = d; K.state["items"] = build_items(d); K.decide("describe", "character", action="describe", how=how, items=[i["key"] for i in K.state["items"]])
    return f"{how}: " + ", ".join(f"{i['key']}({i['kind']})" for i in K.state["items"])

def head_crop(x4, box, out, out_h=992):
    """Head and shoulders from the 4x picture: from a little above the crown down 27 % of the figure's height, as wide as Ren's crop (0.935 of its height), centred on the head;
    scaled to out_h pixels high with the width a multiple of 32 (Qwen sizes)."""
    im = Image.open(x4).convert("RGB"); W, H = im.size; x0, y0, x1, y1 = box[0] * W, box[1] * H, box[2] * W, box[3] * H; Hf = y1 - y0
    top = y0 - 0.025 * Hf; ch = 0.295 * Hf; cw = 0.935 * ch
    a = np.asarray(im).astype(float); bg = np.median(a[:8].reshape(-1, 3), 0); fg = np.abs(a - bg).sum(2) > 40
    rows = fg[int(y0):int(y0 + 0.12 * Hf)]; cx = np.nonzero(rows)[1].mean() if rows.any() else (x0 + x1) / 2
    canvas = Image.new("RGB", (int(cw), int(ch)), tuple(int(v) for v in bg)); canvas.paste(im.crop((int(cx - cw / 2), int(top), int(cx + cw / 2), int(top + ch))), (0, 0))
    ow = max(32, int(round(out_h * cw / ch / 32)) * 32); canvas.resize((ow, out_h), Image.LANCZOS).save(out); return out

def st_head(K):
    d = _desc(K); src = head_crop(K.picks["x4"], K.state["figure_box"], K.p("head", "src.png"))
    gen = _redraw_gen(K, "head", src, lambda g: P.head(d))
    pick = select(K, "head", ["head"], gen, lambda fs: {f: G.head(f) for f in sum(fs.values(), [])},
                  lambda g, files, pics: _ask_pick(P.ask_head(d, len(pics)), [src], ["Picture 1 = the reference crop"], pics), show=SHOW["head"])["head"]
    if not pick: raise RuntimeError("no head redraw at all")
    K.picks["head"] = pick; return f"head: {_short(pick)} ({K.state['stages']['head']['groups']['head']['how']})"

def st_body(K):
    d = _desc(K); orig = K.state["input"]; head = K.picks["head"]
    gen = _redraw_gen(K, "body", orig, lambda g: P.body(d), refs=[head])
    pick = select(K, "body", ["body"], gen, lambda fs: {f: G.body(f) for f in sum(fs.values(), [])},
                  lambda g, files, pics: _ask_pick(P.ask_body(d, len(pics)), [orig, head], ["Picture 1 = the original", "Picture 2 = the approved head"], pics), show=SHOW["body"])["body"]
    if not pick: raise RuntimeError("no body redraw at all")
    K.picks["body"] = pick; return f"body: {_short(pick)} ({K.state['stages']['body']['groups']['body']['how']})"

def _cut(K, stage, key, picture, kind):
    """Background cut of a chosen picture (the menu of rembg sessions), gated; a failed cut goes to review with the best result kept."""
    out = K.p("items", f"{key}_rgba.png"); best = None
    for sess in REMBG_MENU:
        if not K.jobs.rembg(picture, out, sess, key=key): continue
        g = G.alpha(out, kind); K.decide(stage, key, action="cut", session=sess, gate=g); best = g
        if g["ok"]: return out
    if best is None: K.review(stage, key, "background cut produced nothing", chosen=None); return None
    K.review(stage, key, f"background cut: {', '.join(best['issues'])}", [best], out, images=[out]); return out

def st_pictures(K):
    d = _desc(K); its = {i["key"]: i for i in _items(K)}; build = d.get("build") or ""
    srcs = {"body": K.picks["body"], "head": K.picks["head"], "original": K.state["input"]}
    gen = _redraw_gen(K, "pictures", lambda g: srcs[its[g]["source"]], lambda g: P.base_body(d, build) if its[g]["kind"] == "base" else P.item(its[g], d),
                      refs=lambda g: [K.picks["head"]] if its[g]["kind"] == "base" else [], stage="pictures")
    picks = select(K, "pictures", list(its), gen, lambda fs: {f: G.item(f, its[g]["kind"]) for g, l in fs.items() for f in l},
                   lambda g, files, pics: _ask_pick(P.ask_item(its[g], len(pics)), [srcs[its[g]["source"]]], ["Picture 1 = the reference"], pics), show=SHOW["pictures"])
    items = K.picks.setdefault("items", {})
    for k, f in picks.items():
        items[k] = {"picture": f, "rgba": _cut(K, "pictures", k, f, its[k]["kind"]) if f else None}
    items["dressed"] = {"picture": K.picks["body"], "rgba": _cut(K, "pictures", "dressed", K.picks["body"], "base")}
    K.save(); return "; ".join(f"{k}: {_short(v['picture']) if v['picture'] else '-'}" for k, v in items.items())

def st_trellis(K):
    its = {i["key"]: i for i in _items(K)}; its["dressed"] = {"key": "dressed", "kind": "dressed", "region": "body", "description": "whole dressed character"}
    items = K.picks["items"]; groups = [g for g in ["dressed", *[k for k in its if k != "dressed"]] if items.get(g, {}).get("rgba")]
    def gen(reqs):
        out = {}
        for r in sorted({q["round"] for q in reqs.values()}):
            seeds = TRELLIS_SEEDS[r]; res = K.jobs.trellis([(g, items[g]["rgba"], K.r("trellis", g, "x").rsplit("/", 1)[0]) for g, q in reqs.items() if q["round"] == r], seeds)
            for g, by_seed in res.items(): out[g] = [by_seed[s] for s in seeds if s in by_seed]
        return out
    def measure(fs):
        return K.jobs.mesh_gates([{"glb": f, "kind": its[g]["kind"], "region": its[g]["region"], "picture": items[g]["rgba"]} for g, l in fs.items() for f in l])
    def prepare(fs):
        return K.jobs.thumbs([{"glb": f, "out": K.p("thumbs", g, os.path.basename(os.path.dirname(f))), "views": ["front", "side", "back", "below"] if its[g]["kind"] == "garment" else ["front", "side", "back"]}
                              for g, l in fs.items() for f in l])
    picks = select(K, "trellis", groups, gen, measure, lambda g, files, pics: _ask_pick(P.ask_mesh(its[g], len(pics)), [items[g]["rgba"]], ["Picture 1 = the item's picture"], pics),
                   prepare=prepare, show=SHOW["trellis"])
    for g, f in picks.items(): items[g]["glb"] = f
    K.save(); return "; ".join(f"{g}: {_short(f) if f else '-'}" for g, f in picks.items())

def region_box(region, lo, hi):
    """align_item.py --box for a region of the dressed reference (prompts.REGIONS, fractions of its height)."""
    hx, f0, f1, hz = P.REGIONS[region]; H = hi[1] - lo[1]; cx, cz = (lo[0] + hi[0]) / 2, (lo[2] + hi[2]) / 2
    return [cx - hx * H, cx + hx * H, lo[1] + f0 * H, lo[1] + f1 * H, cz - hz * H, cz + hz * H]

def st_place(K):
    its = {i["key"]: i for i in _items(K)}; items = K.picks["items"]
    ref = K.opts.get("dressed_ref") or items.get("dressed", {}).get("glb")
    if not ref or not os.path.exists(ref): raise RuntimeError("no dressed reference model to place the items on")
    lo, hi = glb_bounds(ref); H = hi[1] - lo[1]; K.state["place_reference"] = ref; done = []
    for k, it in its.items():
        glb = items.get(k, {}).get("glb")
        if not glb: K.review("place", k, "no mesh to place", chosen=None); continue
        box = region_box(it["region"], lo, hi); ih = glb_bounds(glb); ih = ih[1][1] - ih[0][1]; tries = []
        for m, opt in enumerate(PLACE_MENU):
            res = K.jobs.align(k, glb, ref, K.r("place", f"place_{k}_t{m}.json"), box, **opt)
            if res is None: tries.append({"menu": m, **opt, "result": None}); continue
            ratio = res["scale"] * ih / (box[3] - box[2]); ok = res["residual"] <= G.RESIDUAL_MAX and SCALE_OK[0] <= ratio <= SCALE_OK[1]
            tries.append({"menu": m, **opt, "residual": round(res["residual"], 5), "scale_ratio": round(ratio, 3), "ok": ok, "file": K.r("place", f"place_{k}_t{m}.json")})
            if ok: break
        good = [t for t in tries if t.get("residual") is not None]; best = min(good, key=lambda t: (not t["ok"], t["residual"])) if good else None
        K.decide("place", k, action="place", box=[round(b, 4) for b in box], tries=tries, chosen=best and best["menu"])
        if best:
            shutil.copy(best["file"], K.r("place", f"place_{k}.json")); items[k]["place"] = K.r("place", f"place_{k}.json"); items[k]["place_residual"] = best["residual"]; done.append(k)
        if not best or not best["ok"]:
            K.review("place", k, ("no placement result" if not best else f"residual {best['residual'] * 100:.2f} % of the height (max {G.RESIDUAL_MAX * 100:.1f} %), scale ratio {best['scale_ratio']}") + f" after {len(tries)} menu entries",
                     tries, best and items[k]["place"], reasons=["misplaced_item"])
    K.save(); return f"placed {len(done)}/{len(its)}: " + ", ".join(f"{k} {items[k]['place_residual'] * 100:.2f}%" for k in done)

def st_assemble(K):
    its = {i["key"]: i for i in _items(K)}; items = K.picks["items"]; kit = K.r("assemble", "kit", "x").rsplit("/", 1)[0]
    use = [k for k in its if items.get(k, {}).get("glb") and items[k].get("place")]
    if "body" not in use: K.review("assemble", "kit", "the base body has no mesh or placement: nothing to assemble", chosen=None); return "skipped: no base body"
    for f in glob.glob(os.path.join(kit, "place_*.json")): os.remove(f)
    for k in use:
        d = os.path.join(kit, k, "s42"); os.makedirs(d, exist_ok=True); ln = os.path.join(d, "textured.glb")       # assemble_kit.py reads <item>/s42/textured.glb: a link to the picked seed
        if os.path.lexists(ln): os.remove(ln)
        os.symlink(os.path.abspath(items[k]["glb"]), ln); shutil.copy(items[k]["place"], os.path.join(kit, f"place_{k}.json"))
    garments = {k: list(P.LIDS[its[k]["region"]]) for k in use if its[k]["kind"] == "garment"}; result = None
    for gap in GAP_MENU:
        blend = K.r("assemble", f"{K.name}_kit_gap{gap}.blend")
        if not K.jobs.assemble(kit, blend, garments) and not os.path.exists(blend):
            K.review("assemble", "kit", "assembly in Blender failed or was skipped", chosen=None, images=[]); return "assembly failed"
        pk = K.jobs.pokes(blend, K.r("assemble", f"pokes_gap{gap}.json"), K.r("assemble", f"render_gap{gap}"), list(garments))
        K.decide("assemble", "kit", action="assemble", gap=gap, items=use, garments=garments, pokes=pk and {k: pk[k] for k in ("tested", "poked", "fraction")})
        result = (gap, blend, pk)
        if pk is None or pk["fraction"] <= G.POKE_MAX: break
    gap, blend, pk = result; K.picks["assembled"] = blend
    if pk is None:
        K.review("assemble", "kit", "poke-through test and render not run (dry run or Blender failed): look at the .blend", chosen=blend); return f"assembled {blend} (not tested)"
    renders = pk.get("renders", [])
    a = K.judge.session([{"key": "assemble:kit", "kind": "check", "prompt": P.ask_assembled(len(use)), "images": renders[:2], "labels": ["front", "three-quarter"], "n": 0, "files": []}]).get("assemble:kit")
    K.decide("assemble", "kit", action="judged", verdict=a)
    if pk["fraction"] > G.POKE_MAX or (a and not a["pass"]):
        K.review("assemble", "kit", f"poke-through {pk['fraction'] * 100:.2f} % of tested body vertices (max {G.POKE_MAX * 100:.1f} %); judges: {a and (a['issues'] or a['pass'])}", [pk], blend,
                 reasons=(a or {}).get("issues", []), images=renders)
    return f"assembled {os.path.basename(blend)} (gap {gap}): poke-through {pk['fraction'] * 100:.2f} %"

def st_rig(K):
    """TODO: rig the assembled kit (one shared skeleton; garments skinned from the body). Hook only."""
    return "TODO"

def st_bake(K):
    """TODO: bake the TRELLIS colour voxels (state.pt) onto the retopologised meshes at 4K. Hook only."""
    return "TODO"

def st_report(K):
    items = K.picks.get("items", {}); files, labels = [], []
    for k, f in (("head", K.picks.get("head")), ("body", K.picks.get("body"))):
        if f: files.append(f); labels.append(f"{k}\n{_short(f)}")
    for k, v in items.items():
        if v.get("picture"): files.append(v["picture"]); labels.append(f"{k} picture\n{_short(v['picture'])}")
    sheet1 = contact_sheet(files, labels, K.p("sheets", "final_pictures.png"), h=280)
    thumbs = []
    for k, v in items.items():
        st = K.state["stages"].get("trellis", {}).get("groups", {}).get(k, {})
        c = next((c for c in st.get("cands", []) if c["file"] == v.get("glb")), None)
        if c: thumbs.append((c.get("shown", c["file"]), f"{k} {_short(c['file'])}\nplace {v.get('place_residual', 0) * 100:.2f}%" if v.get("place") else f"{k} {_short(c['file'])}\nnot placed"))
    sheet2 = contact_sheet([t[0] for t in thumbs], [t[1] for t in thumbs], K.p("sheets", "final_meshes.png"), h=200) if thumbs else None
    rev = K.open_reviews(); K.state["final_sheets"] = [s for s in (sheet1, sheet2) if s]
    K.log(f"final sheets: {K.state['final_sheets']}; {len(rev)} open review entries in {K.rp}")
    for e in rev: K.log(f"   review {e['stage']}/{e['item']}: {e['problem']}")
    return f"{len(rev)} open review entries; sheets {', '.join(os.path.basename(s) for s in K.state['final_sheets'])}"

STAGES = {s: globals()["st_" + s] for s in ["prep", "describe", "head", "body", "pictures", "trellis", "place", "assemble", "rig", "bake", "report"]}
