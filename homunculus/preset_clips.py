"""Preview clips for the preset prompt library: every preset animated by UniMate on a neutral CC0 mannequin.

python -m homunculus.preset_clips [--reps 2] [--batch 30] [--only "walks forward" ...]

Writes homunculus/static/presets/clips/<hash>_<take>.glb and homunculus/static/presets/manifest.json ({"clips": {prompt: [relative paths]}}),
which the web app's Preset library uses to play a preview. Resumable (existing clips are skipped); waits for the GPU pipeline lock.
"""
import argparse, fcntl, hashlib, json, os, shutil, subprocess, sys, time
from . import config as C, gpu, notify
from .stages import animate as A

PRE = C.ROOT / "presets"; OUT = C.ROOT / "homunculus" / "static" / "presets"; MANIFEST = OUT / "manifest.json"
# the two preview characters. fbx = what UniMate preprocesses; "rig_from" = an unrigged mesh that Make-It-Animatable rigs first.
MODELS = {
    "male": {"label": "Male", "title": "miles Morales spiderman rigged", "author": "J.azali", "url": "https://skfb.ly/p8wOX", "fbx": PRE / "male" / "miles.fbx"},
    "female": {"label": "Female", "title": "Spider Gwen Low Poly", "author": "So7ion", "url": "https://skfb.ly/oxwZX", "rig_from": PRE / "female" / "gwen.glb", "fbx": PRE / "female" / "gwen_rigged.fbx"},
}
LICENSE = {"name": "Creative Commons Attribution 4.0", "url": "http://creativecommons.org/licenses/by/4.0/"}


def library():
    """The prompt list of static/prompt_library.js (the single source of truth), read with node."""
    js = (C.ROOT / "homunculus" / "static" / "prompt_library.js").read_text(); tmp = OUT / "_lib.mjs"; OUT.mkdir(parents=True, exist_ok=True); tmp.write_text(js)
    r = subprocess.run(["node", "-e", f"import('{tmp}').then(m=>console.log(JSON.stringify(m.LIBRARY)))"], capture_output=True, text=True); tmp.unlink(missing_ok=True)
    if r.returncode: raise RuntimeError("could not read the prompt library: " + r.stderr[-300:])
    return json.loads(r.stdout)


def pid(prompt): return hashlib.sha1(prompt.encode()).hexdigest()[:10]


def one_model(key, spec, prompts, a, M, log, t0):
    import re
    asset = PRE / key / "asset"; E = M["models"][key]
    if not spec["fbx"].exists() and spec.get("rig_from"):
        from .stages import rig
        log(f"{key}: rigging {spec['rig_from'].name} with Make-It-Animatable"); gpu.free_all(log)
        out = rig.run(spec["rig_from"], str(PRE / key / "rig"), key, log); shutil.copy(out, spec["fbx"])
        gpu.free_all(log)
    if not (asset / "cond.npy").exists():
        log(f"{key}: preparing the character for UniMate"); shutil.rmtree(asset, ignore_errors=True)
        A._run([str(A.UM_PY), "-m", "data_process.rig_preprocess", "run", "--input", str(spec["fbx"]), "--output_dir", str(asset), "--no_review", "--annotate", "rule", "--name", key], log, "rig preprocessing", 900)
    todo = [p for p in prompts if len(E["clips"].get(p, [])) < a.reps]
    log(f"{key}: {len(prompts) - len(todo)} of {len(prompts)} presets already done; generating {len(todo)}")
    (OUT / "clips" / key).mkdir(parents=True, exist_ok=True)
    for i in range(0, len(todo), a.batch):
        chunk = todo[i:i + a.batch]; batch = OUT / f"_batch_{key}_{i}"; shutil.rmtree(batch, ignore_errors=True)
        log(f"{key} batch {i // a.batch + 1}: sampling {len(chunk)} prompts x {a.reps}")
        A._run([str(A.UM_PY), "-m", "unimate.inference.sample", "--exp_dir", str(A.CKPT), "--asset", str(asset), "--prompt", *[A.prompt_text(p) for p in chunk], "--num_repetitions", str(a.reps),
                "--cfg_scale", "3", "--output_dir", str(batch), "--only_save_motion"], log, "UniMate sampling", 3600)
        A._run(["bash", "scripts/run_animate_motion.sh", str(batch)], log, "animating the character", 7200)
        for f in sorted((batch / "animated").glob("*.glb")):
            m = re.match(rf"{key}-(.+)-rep_(\d+)-(\d+)$", f.stem)
            if not m or int(m.group(3)) >= len(chunk): continue
            p = chunk[int(m.group(3))]; dst = OUT / "clips" / key / f"{pid(p)}_{int(m.group(2)) + 1}.glb"; shutil.move(str(f), dst)
            E["clips"].setdefault(p, []); rel = f"clips/{key}/{dst.name}"
            if rel not in E["clips"][p]: E["clips"][p].append(rel)
        shutil.rmtree(batch, ignore_errors=True)
        E["done"] = sum(1 for p in prompts if E["clips"].get(p)); json.dump(M, open(MANIFEST, "w"), indent=1)
        log(f"{key}: {E['done']} / {len(prompts)} presets have clips ({(time.time() - t0) / 60:.1f} min)")


def main():
    ap = argparse.ArgumentParser(); ap.add_argument("--reps", type=int, default=2); ap.add_argument("--batch", type=int, default=30); ap.add_argument("--only", nargs="*")
    ap.add_argument("--model", nargs="*", choices=list(MODELS), default=list(MODELS))
    a = ap.parse_args(); log = lambda m: print(time.strftime("%H:%M:%S ") + m, flush=True)
    lib = library(); prompts = [p for c in lib for p in c["prompts"]]
    if a.only: prompts = [p for p in prompts if p in a.only]
    M = json.load(open(MANIFEST)) if MANIFEST.exists() else {}
    M.pop("clips", None); M.pop("model", None); M.setdefault("models", {})
    for k, s in MODELS.items():
        M["models"].setdefault(k, {"clips": {}}).update(label=s["label"], title=s["title"], author=s["author"], url=s["url"], license=LICENSE["name"], license_url=LICENSE["url"])
    M.update(reps=a.reps, total=len(prompts), status="queued"); json.dump(M, open(MANIFEST, "w"), indent=1)
    lockf = open(C.RUNS / ".homunculus.lock", "a+")
    try: fcntl.flock(lockf, fcntl.LOCK_EX | fcntl.LOCK_NB)
    except BlockingIOError: log("waiting for the GPU pipeline to finish its current run"); fcntl.flock(lockf, fcntl.LOCK_EX)
    lockf.seek(0); lockf.truncate(); lockf.write(f"homunculus preset clips (pid {os.getpid()})"); lockf.flush()
    t0 = time.time()
    try:
        gpu.free_all(log); gpu.wait_for_headroom("unimate", log); M["status"] = "running"
        for k in a.model: one_model(k, MODELS[k], prompts, a, M, log, t0)
        M["status"] = "done"; json.dump(M, open(MANIFEST, "w"), indent=1)
        notify.send("homunculus: preset previews ready", " · ".join(f"{k}: {M['models'][k].get('done', 0)} of {len(prompts)}" for k in a.model))
    except Exception as e:
        M["status"] = "failed"; M["error"] = str(e)[:300]; json.dump(M, open(MANIFEST, "w"), indent=1); notify.send("homunculus: preset previews failed", str(e)[:200], critical=True); raise


if __name__ == "__main__":
    main()
