"""Turn the dancers of tools/group_scene.py into clips on a rigged character, one colour each, registered in a run's Animate tab:

    .venv/bin/python tools/register_group.py --dir <group dir> --run jabawockeez --rig runs/jabawockeez/07_rig/jabawockeez_rigged.fbx --video original.mp4 --start 13 --seconds 110 --prefix wdb \
        --textures red,green,blue,purple,orange,cyan --titles "black tee, sunglasses|plaid shirt|grey vest, bucket hat|purple print tee|black long sleeve|white tee, cap"

Per dancer k: <dir>/scene/d<k>_gravity.npz -> BVH (tools/smpl_to_bvh.py, gvhmr format) -> the rig with the k-th recoloured texture (runs/<run>/07_rig/variants/tex_<colour>.png, see tools/retarget_bvh.py --texture)
-> <run>/09_animate/clips/video_<prefix>_d<k>.glb/.fbx; the reference is the dancer's 4K crop video (<dir>/crops/d<k>.mp4, its own frame rate) with the original's sound; the clip's entry in animations.json gets
valid_ranges (seconds: where the dancer is really in the picture, the only stretches the LLM annotation looks at).  Writes <dir>/scene/scales.json (the retargeting's scale per dancer, which tools/render_group.py needs)."""
import os, sys, json, re, shutil, subprocess, argparse, time
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__))); sys.path.insert(0, ROOT)
from homunculus import config as C
ap = argparse.ArgumentParser(); ap.add_argument("--dir", required=True); ap.add_argument("--run", required=True); ap.add_argument("--rig", required=True); ap.add_argument("--video", required=True)
ap.add_argument("--start", type=float, required=True); ap.add_argument("--seconds", type=float, required=True); ap.add_argument("--prefix", default="wdb"); ap.add_argument("--textures", default="", help="colours of the recoloured textures, one per dancer; none: the rig keeps its own"); ap.add_argument("--titles", default=""); ap.add_argument("--title", default="Group dance")
ap.add_argument("--target", default="", help="the rig's skeleton (retarget_bvh.py --target), e.g. valorant"); ap.add_argument("--yaw", type=float, default=0.0); ap.add_argument("--only", default="", help="comma-separated dancer numbers")
a = ap.parse_args(); D = os.path.abspath(a.dir); sc = json.load(open(os.path.join(D, "scene", "scene.json"))); cols = a.textures.split(",") if a.textures else [""]; titles = a.titles.split("|") if a.titles else []
runs = C.RUNS / a.run; clips = runs / "09_animate" / "clips"; os.makedirs(clips, exist_ok=True); work = os.path.join(D, "scene", "retarget"); os.makedirs(work, exist_ok=True); py = os.path.join(ROOT, ".venv", "bin", "python")
mp = runs / "09_animate" / "animations.json"; scales_p = os.path.join(D, "scene", "scales.json" if a.prefix == "wdb" else f"scales_{a.prefix}.json"); scales = json.load(open(scales_p)) if os.path.exists(scales_p) else {}
only = {int(x) for x in a.only.split(",") if x}; lifts_p = scales_p.replace("scales", "lifts"); lifts = json.load(open(lifts_p)) if os.path.exists(lifts_p) else {}
for d in sc["dancers"]:
    k = d["k"]
    if only and k not in only: continue
    cid = f"video_{a.prefix}_d{k}"; tex = str(runs / "07_rig" / "variants" / f"tex_{cols[(k - 1) % len(cols)]}.png") if a.textures else ""; bvh = os.path.join(work, f"d{k}.bvh")
    subprocess.run([py, "-I", os.path.join(ROOT, "tools", "smpl_to_bvh.py"), os.path.join(D, "scene", f"d{k}_gravity.npz"), bvh, "--format", "gvhmr", "--fps", "30", "--yaw", f"{a.yaw:g}"], check=True, capture_output=True)
    r = subprocess.run([C.BLENDER, "-b", "--python", os.path.join(ROOT, "tools", "retarget_bvh.py"), "--", a.rig, bvh, os.path.join(work, f"rt{k}"), cid, "--map", "smpl", "--fps", "30", *(["--texture", tex] if tex else []), *(["--target", a.target] if a.target else [])], capture_output=True, text=True)
    glb = os.path.join(work, f"rt{k}", cid + ".glb"); fbx = os.path.join(work, f"rt{k}", cid + ".fbx")
    if not os.path.exists(glb): sys.exit(f"retargeting dancer {k} failed: " + (r.stdout + r.stderr)[-500:])
    m = re.search(r"-> scale ([0-9.]+)", r.stdout); scales[str(k)] = float(m.group(1)) if m else 1.0
    fz = re.search(r"target floor z (-?[0-9.]+)", r.stdout); lifts[str(k)] = -float(fz.group(1)) if fz else 0.0                  # the floor's height below the clip's origin: render_group.py's lift
    shutil.copy(glb, clips / f"{cid}.glb"); shutil.copy(fbx, clips / f"{cid}.fbx") if os.path.exists(fbx) else None
    ref = clips / f"{cid}_ref.mp4"
    subprocess.run(["ffmpeg", "-v", "error", "-y", "-i", os.path.join(D, "crops", f"d{k}.mp4"), "-ss", str(a.start), "-t", str(a.seconds), "-i", a.video, "-map", "0:v", "-map", "1:a?", "-c:v", "copy", "-c:a", "aac", "-b:a", "160k", "-shortest", "-movflags", "+faststart", str(ref)], check=True)
    try: M = json.load(open(mp))
    except Exception: M = {"status": "done", "error": None, "clips": []}
    M["clips"] = [c for c in M["clips"] if c["id"] != cid] + [{"id": cid, "prompt": f"{a.title}: dancer {k} ({titles[k - 1] if k - 1 < len(titles) else ''}), {cols[(k - 1) % len(cols)] or a.run} model", "rep": 0, "source": "video", "glb": f"09_animate/clips/{cid}.glb",
        "fbx": f"09_animate/clips/{cid}.fbx" if os.path.exists(clips / f"{cid}.fbx") else None, "thumb": None, "ref": f"09_animate/clips/{cid}_ref.mp4", "valid_ranges": [[round(s / 30, 3), round(e / 30, 3)] for s, e in d["valid_ranges"]], "time": time.strftime("%H:%M:%S")}]
    M["status"] = "done"; json.dump(M, open(mp, "w"), indent=1); print(f"[register_group] dancer {k}: {cid}, scale {scales[str(k)]:.4f}, {len(d['valid_ranges'])} verified ranges", flush=True)
json.dump(scales, open(scales_p, "w"), indent=1); json.dump(lifts, open(lifts_p, "w"), indent=1)
