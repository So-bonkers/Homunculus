"""Remesh the parts of a character with the headless Blender script, each under a timeout and with other voxel sizes when Quadriflow hangs or refuses.
  python tools/retopo_parts/run_parts.py MODEL.glb OUT_DIR [--parts full,R,L]
Writes OUT_DIR/full.ply, R.ply, L.ply and hands.json. Nothing character-specific is passed: voxel sizes are fractions of the body height and the hands, wrists, fingers and slots are found by hand_analysis.py."""
import argparse, os, subprocess, sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
BLENDER = os.environ.get("BLENDER", "/snap/bin/blender")
# part: (voxel sizes to try in order, as fractions of the body height; target quads; timeout s)
PARTS = {"full": ([0.0011, 0.0014, 0.0018], 60000, 400), "R": ([0.0005, 0.00044, 0.00055, 0.00047, 0.00039], 16000, 120), "L": ([0.00044, 0.0005, 0.00055, 0.00047, 0.00039], 16000, 120)}
# a hand whose five fingers the analysis could not find (a relaxed, bunched or curled hand, not an open spread one) is NOT rebuilt: it is kept as generated (plain mode), with coarser voxel sizes (Quadriflow refuses the fine ones there)
PLAIN = ([0.0008, 0.0010, 0.0013, 0.0016], 14000, 150)


def run(src, out_dir, part):
    voxels, target, tmo = PARTS[part]; out = Path(out_dir) / f"{part}.ply"; env_extra = {}
    hj = Path(out_dir) / "hands.json"
    if part in ("R", "L") and hj.exists():
        import json
        if not json.load(open(hj))[part]["ok"]:
            voxels, target, tmo = PLAIN; env_extra = {"RETOPO_FINGERS": "plain"}; print(f"[{part}] the analysis did not find five fingers: the hand is kept as generated (plain mode)", flush=True)
    for v in voxels:
        cmd = [BLENDER, "-b", "--python", str(HERE / "remesh_part.py"), "--", part, str(v), str(target), str(out)]
        try: r = subprocess.run(cmd, capture_output=True, text=True, timeout=tmo, env={**os.environ, "RETOPO_SRC": str(src), **env_extra}, stdin=subprocess.DEVNULL)
        except subprocess.TimeoutExpired: print(f"[{part}] voxel {v}: timed out after {tmo}s (Quadriflow hang); trying the next size", flush=True); continue
        lines = [l for l in r.stdout.splitlines() if l.startswith(f"[{part}]")]
        if r.returncode == 0 and out.exists(): print("\n".join(lines[-3:]), flush=True); return str(out)
        print(f"[{part}] voxel {v}: Quadriflow refused ({lines[-1] if lines else r.stdout[-200:]}); trying the next size", flush=True)
    raise SystemExit(f"[{part}] no voxel size worked: {voxels}")


if __name__ == "__main__":
    ap = argparse.ArgumentParser(); ap.add_argument("model"); ap.add_argument("out_dir")
    ap.add_argument("--parts", default="full,R,L"); a = ap.parse_args()
    os.makedirs(a.out_dir, exist_ok=True)
    for p in a.parts.split(","): run(a.model, a.out_dir, p)
