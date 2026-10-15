"""Draw every hand move of static/hands/moves.json on a rig: python -m homunculus.move_pictures [rig.glb]
One picture per move, static/hands/moves/<key>.jpg: eight moments from just before the first key to just after the last, each from the side (above) and from the top (below), with the seconds from the hit under each."""
import json, os, subprocess, sys, tempfile, shutil
from PIL import Image, ImageDraw
from . import config as C, handpose, handshapes
from .hand_library import rig_glb, OUT

CELL, N = 150, 8


def main():
    rig = sys.argv[1] if len(sys.argv) > 1 else rig_glb(); moves = json.load(open(os.path.join(OUT, "moves.json")))["moves"]; tmp = tempfile.mkdtemp(); sp = os.path.join(tmp, "spec.json")
    json.dump({"lib": {k: {**v, "splay": v.get("splay", {})} for k, v in handpose.LIB.items()}, "wrist_lib": handshapes.wrist_lib(), "palm_lib": handshapes.palm_lib(), "moves": moves}, open(sp, "w"))
    r = subprocess.run([C.BLENDER, "-b", "--python", os.path.join(os.path.dirname(__file__), "blender_movesheet.py"), "--", rig, sp, tmp], capture_output=True, text=True, timeout=3600)
    if "[movesheet]" not in r.stdout: raise SystemExit((r.stdout + r.stderr)[-800:])
    times = json.load(open(os.path.join(tmp, "times.json"))); os.makedirs(os.path.join(OUT, "moves"), exist_ok=True)
    for m in moves:
        k = m["key"]; sheet = Image.new("RGB", (CELL * N, CELL * 2 + 16), (24, 26, 30)); d = ImageDraw.Draw(sheet)
        for i in range(N):
            for row, view in enumerate(("side", "top")): sheet.paste(Image.open(os.path.join(tmp, f"{k}_{i}_{view}.png")).convert("RGB").resize((CELL, CELL), Image.LANCZOS), (i * CELL, row * CELL))
            d.text((i * CELL + 4, CELL * 2 + 2), f"{times[k][i]:+.2f} s", fill=(200, 205, 215))
        sheet.save(os.path.join(OUT, "moves", f"{k}.jpg"), quality=82)
    shutil.rmtree(tmp, ignore_errors=True); print(f"{len(moves)} move pictures drawn into {os.path.join(OUT, 'moves')}")


if __name__ == "__main__":
    main()
