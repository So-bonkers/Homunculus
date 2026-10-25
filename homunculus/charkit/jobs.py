"""The heavy jobs of charkit, each in its own memory-capped systemd user unit (the machine has 60 GB and an OOM takes VS Code with it) or, for the Qwen-Image redraws, in-process
through stages/qwen_turbo.py under the GPU lock (one ComfyUI session for a whole batch of pictures). Jobs: the real thing. ReplayJobs (--dry-run): Ren's recorded outputs instead,
from a fixture; with cpu=True (--dry-run-cpu) the CPU-only jobs (background cut, mesh gates, thumbnails in Cycles on the CPU, placement, poke test) run for real.
    .venv/bin/python -m homunculus.charkit.jobs rembg IN.png OUT.png [--session birefnet-general]      (the background cut, also used as a unit's command)"""
import glob, json, os, shutil, subprocess, sys, time
from pathlib import Path
from .. import config as C

TRELLIS_DIR = Path(os.environ.get("CHARKIT_TRELLIS", Path.home() / "trellis2_test"))      # the working TRELLIS.2 install (patched venv; tools/trellis2 has copies of the scripts)
TRELLIS_PY = TRELLIS_DIR / "venv/bin/python"
GRAFT = C.ROOT / "tools/ren_graft"
HERE = Path(__file__).resolve().parent
MEM = {"default": "12G", "trellis": "38G", "assemble": "16G"}      # MemoryMax per unit: TRELLIS keeps ~30 GB in RAM while it exports (memory note of 2026-10-24); Blender with four 1M-face meshes ~10 GB
TRELLIS_ARGS = ["--type", "1024_cascade", "--texture", "4096"]

def sysrun(K, tag, cmd, log, mem="default", cwd=C.ROOT, env=None, pipe=False):
    """cmd (a list) in a transient systemd user unit with a memory cap, waiting for it; its output goes to `log` (or is returned with pipe=True). Returns (exit code, output)."""
    unit = f"charkit-{K.name}-{tag}-{int(time.time()) % 100000}"
    sr = ["systemd-run", "--user", "--quiet", "--wait", "--collect", f"--unit={unit}", "-p", f"MemoryMax={MEM.get(mem, mem)}", f"--working-directory={cwd}"]
    sr += [f"--setenv={k}={v}" for k, v in (env or {}).items()]
    K.log(f"unit {unit} ({MEM.get(mem, mem)}): {' '.join(map(str, cmd))[:300]}")
    if pipe:
        r = subprocess.run(sr + ["--pipe"] + [str(c) for c in cmd], capture_output=True, text=True)
        open(log, "a").write(r.stdout + r.stderr); return r.returncode, r.stdout
    line = " ".join("'" + str(c).replace("'", "'\\''") + "'" for c in cmd)
    r = subprocess.run(sr + ["/bin/sh", "-c", f"exec {line} >> '{log}' 2>&1 < /dev/null"], capture_output=True, text=True)
    return r.returncode, ""


class Jobs:
    stub = False
    def __init__(self, K): self.K = K

    def upscale(self, src, dst):
        """4x-UltraSharp through spandrel in the ComfyUI venv, on the GPU under the lock (everything else unloaded first)."""
        from .. import gpu
        with self.K.gpu_phase("4x upscale"):
            gpu.free_all(self.K.log); gpu.wait_for_headroom("upscale", self.K.log)
            code, _ = sysrun(self.K, "upscale", [C.COMFY_PY, HERE / "upscale_x4.py", src, dst, "--model", C.COMFY_UI / "models/upscale_models/4x-UltraSharp.pth"], self.K.r("logs", "upscale.log"))
        return code == 0 and os.path.exists(dst)

    def rembg(self, src, dst, session="birefnet-general", key=None):
        code, _ = sysrun(self.K, "rembg", [C.ROOT / ".venv/bin/python", "-m", "homunculus.charkit.jobs", "rembg", src, dst, "--session", session], self.K.r("logs", "rembg.log"))
        return code == 0 and os.path.exists(dst)

    def redraw(self, batch):
        """batch: [{"key", "round", "src", "prompt", "refs": [...], "seeds": [...], "out_dir"}] -> {key: [new picture paths]}. One ComfyUI session (Qwen-Image 2.1 Turbo edit,
        as tools/redraw_front.py does it: the picture at its own size, reference resolution 1024) for the whole batch; a picture already on disk is not drawn again."""
        from PIL import Image
        from ..stages import qwen_turbo as Q
        out = {j["key"]: [] for j in batch}
        if not batch: return out
        with self.K.gpu_phase(f"redraws ({sum(len(j['seeds']) for j in batch)} pictures)"):
            Q.up(self.K.log)
            try:
                for j in batch:
                    im = Image.open(j["src"]).convert("RGB"); refs = [Image.open(r).convert("RGB") for r in j.get("refs", [])]; os.makedirs(j["out_dir"], exist_ok=True)
                    for sd in j["seeds"]:
                        f = os.path.join(j["out_dir"], f"front_s{sd}.png")
                        if not os.path.exists(f):
                            try: Q.edit_image(im, j["prompt"], sd, im.size, 1024, self.K.log, refs=refs).save(f)
                            except Exception as e: self.K.log(f"redraw {j['key']} seed {sd} failed: {str(e)[:160]}"); continue
                        out[j["key"]].append(f)
                    json.dump({"prompt": j["prompt"], "refs": j.get("refs", []), "src": j["src"]}, open(os.path.join(j["out_dir"], f"prompt_r{j['round']}.json"), "w"), indent=1)
            finally: Q.down()
        return out

    def trellis(self, jobs, seeds):
        """jobs: [(key, rgba picture, out dir)]: TRELLIS.2 on all of them in ONE run (the models load once), each seed into <out dir>/s<seed>. Returns {key: {seed: textured.glb}}."""
        from .. import gpu
        todo = [(k, im, od) for k, im, od in jobs if not all(os.path.exists(os.path.join(od, f"s{s}", "textured.glb")) for s in seeds)]
        if todo:
            bf = self.K.r("trellis", f"batch_{'_'.join(map(str, seeds))}.txt"); open(bf, "w").write("".join(f"{os.path.abspath(im)} {os.path.abspath(od)}\n" for _, im, od in todo))
            with self.K.gpu_phase(f"TRELLIS.2 ({len(todo)} pictures x {len(seeds)} seeds)"):
                gpu.free_all(self.K.log); gpu.NEED_GB.setdefault("trellis", 17.0); gpu.wait_for_headroom("trellis", self.K.log)       # 1024_cascade peaked at ~15 GB allocated (runs/ren_trellis logs)
                sysrun(self.K, "trellis", [TRELLIS_PY, TRELLIS_DIR / "run_trellis.py", todo[0][1], self.K.r("trellis", "_batch_out", ".keep").rsplit("/", 1)[0], "--batch", bf,
                                           "--seeds", ",".join(map(str, seeds)), *TRELLIS_ARGS], self.K.r("logs", "trellis.log"), mem="trellis", cwd=TRELLIS_DIR)
        return {k: {s: os.path.join(od, f"s{s}", "textured.glb") for s in seeds if os.path.exists(os.path.join(od, f"s{s}", "textured.glb"))} for k, _, od in jobs}

    def mesh_gates(self, jobs):
        """jobs: [{"glb", "kind", "region", "picture"}] -> {glb: gate result}; trimesh lives in the TRELLIS venv, so the gates run there (one unit for all)."""
        if not jobs: return {}
        jf = self.K.r("gates", f"mesh_{int(time.time())}.json"); json.dump(jobs, open(jf, "w"))
        code, txt = sysrun(self.K, "meshgates", [TRELLIS_PY, "-m", "homunculus.charkit.gates", "batch", jf], self.K.r("logs", "gates.log"), pipe=True)
        try: return json.loads(txt.strip().splitlines()[-1])
        except Exception: self.K.log(f"mesh gates gave no result (exit {code})"); return {}

    def thumbs(self, jobs, engine=None):
        """jobs: [{"glb", "out": prefix, "views"}] -> {glb: strip png}: one headless Blender for all, the views joined into one strip per model."""
        from PIL import Image
        if not jobs: return {}
        engine = engine or self.K.opts.get("thumb_engine", "workbench"); jf = self.K.r("thumbs", f"jobs_{int(time.time())}.json"); json.dump(jobs, open(jf, "w"))
        sysrun(self.K, "thumbs", [C.BLENDER, "-b", "--factory-startup", "--python", HERE / "blender_thumbs.py", "--", jf, "--engine", engine, "--size", "320"], self.K.r("logs", "thumbs.log"))
        out = {}
        for j in jobs:
            ims = [Image.open(f"{j['out']}_{v}.png").convert("RGB") for v in j["views"] if os.path.exists(f"{j['out']}_{v}.png")]
            if not ims: continue
            s = Image.new("RGB", (sum(i.width for i in ims), ims[0].height)); x = 0
            for i in ims: s.paste(i, (x, 0)); x += i.width
            s.save(j["out"] + "_strip.png"); out[j["glb"]] = j["out"] + "_strip.png"
        return out

    def align(self, key, item_glb, ref_glb, out_json, box, axes="upright", yaw_steps=12, frac=0.7):
        """tools/ren_graft/align_item.py (similarity ICP of the item onto a box of the reference). Returns its JSON (matrix, scale, residual) or None."""
        cmd = [TRELLIS_PY, GRAFT / "align_item.py", item_glb, ref_glb, out_json, "--box", *[f"{b:.4f}" for b in box], "--axes", axes, "--yaw-steps", str(yaw_steps), "--frac", str(frac)]
        code, _ = sysrun(self.K, f"align-{key}", cmd, self.K.r("logs", "place.log"))
        return json.load(open(out_json)) if code == 0 and os.path.exists(out_json) else None

    def assemble(self, kit_dir, out_blend, garments):
        env = {"CHARKIT_GARMENTS": json.dumps(garments)}
        code, _ = sysrun(self.K, "assemble", [C.BLENDER, "-b", "--factory-startup", "--python", HERE / "blender_assemble.py", "--", kit_dir, out_blend], self.K.r("logs", "assemble.log"), mem="assemble", env=env)
        return code == 0 and os.path.exists(out_blend)

    def pokes(self, blend, out_json, prefix, garments):
        sysrun(self.K, "pokes", [C.BLENDER, "-b", blend, "--python", HERE / "blender_pokes.py", "--", out_json, prefix, "--garments", ",".join(garments), "--engine", self.K.opts.get("thumb_engine", "workbench")],
               self.K.r("logs", "pokes.log"), mem="assemble")
        return json.load(open(out_json)) if os.path.exists(out_json) else None


class ReplayJobs(Jobs):
    """Dry run on recorded outputs. fixture["artifacts"]: where the earlier hand-made run left each result (paths relative to the repository; globs allowed); a re-roll (round > 0)
    finds nothing recorded and returns no new candidates, so the escalation path is exercised. Nothing is written outside the test folders: recorded files are read in place."""
    stub = True
    def __init__(self, K, fixture, cpu=False):
        super().__init__(K); self.A = (fixture or {}).get("artifacts", {}); self.cpu = cpu

    def _p(self, rel): return str(C.ROOT / rel) if rel and not os.path.isabs(rel) else rel

    def _link(self, src, dst):
        if not src or not os.path.exists(src): return False
        if os.path.lexists(dst): os.remove(dst)
        os.symlink(os.path.abspath(src), dst); return True

    def upscale(self, src, dst):
        self.K.log("[dry run] upscale skipped: using the recorded 4x picture"); return self._link(self._p(self.A.get("x4")), dst)

    def rembg(self, src, dst, session="birefnet-general", key=None):
        if self.cpu: return super().rembg(src, dst, session, key)        # onnxruntime here is CPU-only: no GPU
        rec = self._p(self.A.get("rgba", {}).get(key or "", ""))
        self.K.log(f"[dry run] background cut of {os.path.basename(src)} skipped: {'recorded ' + os.path.basename(rec) if rec else 'nothing recorded'}"); return self._link(rec, dst)

    def redraw(self, batch):
        out = {}
        for j in batch:
            pat = self.A.get("candidates", {}).get(j["key"])
            out[j["key"]] = sorted(glob.glob(self._p(pat))) if pat and j["round"] == 0 else []
            os.makedirs(j["out_dir"], exist_ok=True); json.dump({"prompt": j["prompt"], "refs": j.get("refs", []), "src": j["src"], "seeds": j["seeds"], "dry_run": True}, open(os.path.join(j["out_dir"], f"prompt_r{j['round']}.json"), "w"), indent=1)
            self.K.log(f"[dry run] redraw {j['key']} round {j['round']}: {len(out[j['key']])} recorded candidates (would draw seeds {j['seeds'][0]}..{j['seeds'][-1]})")
        return out

    def trellis(self, jobs, seeds):
        out = {}
        for k, im, od in jobs:
            d = self._p(self.A.get("trellis", {}).get(k)); out[k] = {s: os.path.join(d, f"s{s}", "textured.glb") for s in seeds if d and os.path.exists(os.path.join(d, f"s{s}", "textured.glb"))}
            self.K.log(f"[dry run] TRELLIS {k} seeds {seeds}: recorded {sorted(out[k])}")
        return out

    def mesh_gates(self, jobs):
        if self.cpu or self.K.opts.get("dry_mesh_gates", True): return super().mesh_gates(jobs)      # CPU only (trimesh), ~5 s a mesh
        return {}

    def thumbs(self, jobs, engine=None):
        if self.cpu: return super().thumbs(jobs, engine="cycles")
        from PIL import Image, ImageDraw
        out = {}
        for j in jobs:
            im = Image.new("RGB", (320 * len(j["views"]), 320), (200, 200, 200)); ImageDraw.Draw(im).text((10, 150), f"dry run: no render of {os.path.relpath(j['glb'], C.ROOT)}", fill=(0, 0, 0))
            os.makedirs(os.path.dirname(j["out"]), exist_ok=True); im.save(j["out"] + "_strip.png"); out[j["glb"]] = j["out"] + "_strip.png"
        return out

    def align(self, key, item_glb, ref_glb, out_json, box, axes="upright", yaw_steps=12, frac=0.7):
        if self.cpu: return super().align(key, item_glb, ref_glb, out_json, box, axes, yaw_steps, frac)
        rec = self._p(self.A.get("place", {}).get(key)) if axes == "upright" and yaw_steps == 12 else None      # the recorded run used the first menu entry only
        self.K.log(f"[dry run] place {key} ({axes}, {yaw_steps} yaw steps): {'recorded ' + os.path.basename(rec) if rec and os.path.exists(rec) else 'nothing recorded'}")
        if rec and os.path.exists(rec): shutil.copy(rec, out_json); return json.load(open(out_json))
        return None

    def assemble(self, kit_dir, out_blend, garments):
        rec = self._p(self.A.get("assembled"))
        self.K.log(f"[dry run] assemble skipped (garments {garments}): {'recorded ' + rec if rec and os.path.exists(rec) else 'nothing recorded'}")
        return self._link(rec, out_blend) if rec and os.path.exists(rec) else False

    def pokes(self, blend, out_json, prefix, garments):
        if self.cpu: return super().pokes(blend, out_json, prefix, garments)
        return None


def _rembg_main(a):
    from rembg import new_session, remove
    from PIL import Image
    im = Image.open(a[0]).convert("RGB"); s = new_session(a[a.index("--session") + 1] if "--session" in a else "birefnet-general")
    remove(im, session=s).save(a[1]); print("cut", a[0], "->", a[1])

if __name__ == "__main__":
    if sys.argv[1] == "rembg": _rembg_main(sys.argv[2:])
