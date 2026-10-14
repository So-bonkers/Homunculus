"""Build the pictures and the catalogue of the hand library the timeline editor shows:  python -m homunculus.hand_library [rig.glb]
Renders every pose (homunculus/blender_handlib.py, on a T-posed rig: a run's rigged GLB) into homunculus/static/hands/<pose>.jpg (side view next to top view) and writes catalogue.json."""
import json, os, subprocess, sys, tempfile, shutil
from PIL import Image
from . import config as C, handpose, handshapes

OUT = os.path.join(os.path.dirname(__file__), "static", "hands")


def rig_glb():
    for d in sorted(os.listdir(C.RUNS), key=lambda n: (n != "kinjaz_center", n)):      # the dancer first, then any rigged run
        p = C.RUNS / d / "07_rig" / f"{d}_rigged.glb"
        if p.exists(): return str(p)
    raise SystemExit("no rigged run to draw the hands on; pass a rigged GLB")


def main():
    rig = sys.argv[1] if len(sys.argv) > 1 else rig_glb(); os.makedirs(OUT, exist_ok=True); tmp = tempfile.mkdtemp(); lib_p = os.path.join(tmp, "lib.json")
    json.dump({k: {**v, "splay": v.get("splay", {})} for k, v in handpose.LIB.items()}, open(lib_p, "w"))
    r = subprocess.run([C.BLENDER, "-b", "--python", os.path.join(os.path.dirname(__file__), "blender_handlib.py"), "--", rig, lib_p, tmp], capture_output=True, text=True, timeout=1800)
    if "[handlib]" not in r.stdout: raise SystemExit((r.stdout + r.stderr)[-600:])
    cat = handshapes.catalogue()
    for row in cat:
        k = row["key"]; a, b = (Image.open(os.path.join(tmp, f"{k}_{v}.png")).convert("RGB") for v in ("side", "top"))
        im = Image.new("RGB", (a.width + b.width, a.height)); im.paste(a, (0, 0)); im.paste(b, (a.width, 0)); im.save(os.path.join(OUT, f"{k}.jpg"), quality=82); row["image"] = f"/static/hands/{k}.jpg"
    json.dump(cat, open(os.path.join(OUT, "catalogue.json"), "w"), indent=1); shutil.rmtree(tmp, ignore_errors=True); print(f"{len(cat)} poses drawn into {OUT}")


if __name__ == "__main__":
    main()
