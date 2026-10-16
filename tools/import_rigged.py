"""Make a run of a ready-made rigged character (a game model, a community model), so it shows in the web app and can be animated:

    python tools/import_rigged.py --name yoru --model Yoru.glb [--skeleton valorant] [--textures <folder>] [--picture front.png]

The model (GLB or FBX with the skeleton and the textures inside) is converted by Blender to <run>/07_rig/<name>_rigged.glb and .fbx; --textures: a folder of pictures to attach to materials whose pictures are missing (matched by name).
state.json gets the artifacts the app reads, and "skeleton": the name of the bone map tools/retarget_bvh.py --target uses when a dance is copied onto this run.  The stages are marked done ("imported").
--picture: the thumbnail (default: a render of the model from the front)."""
import os, sys, json, shutil, argparse, subprocess, time
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__))); sys.path.insert(0, ROOT)
from homunculus import config as C
ap = argparse.ArgumentParser(); ap.add_argument("--name", required=True); ap.add_argument("--model", required=True); ap.add_argument("--skeleton", default="valorant", help="valorant: rebuilt as the 52-bone Mixamo skeleton; any other name: kept as it is, retargeting uses that bone map (retarget_bvh.py --target)"); ap.add_argument("--textures", default="", help="folder of pictures, optionally |m0=file,m1=file (a mesh, by order, gets that picture)"); ap.add_argument("--picture", default="")
a = ap.parse_args(); run = C.RUNS / a.name; os.makedirs(run / "07_rig", exist_ok=True); os.makedirs(run / "00_input", exist_ok=True); glb = run / "07_rig" / f"{a.name}_rigged.glb"; fbx = glb.with_suffix(".fbx"); pic = run / "00_input" / "input.png"
r = subprocess.run([C.BLENDER, "-b", "--python", os.path.join(ROOT, "tools", "convert_rigged.py"), "--", a.model, str(glb), str(fbx), a.textures, a.picture or str(pic), a.skeleton if a.skeleton == "valorant" else ""], capture_output=True, text=True)
if not glb.exists(): sys.exit("conversion failed: " + (r.stdout + r.stderr)[-600:])
print(r.stdout.strip().splitlines()[-1] if r.stdout.strip() else "")
if a.picture: shutil.copy(a.picture, pic)
stages = {s: {"status": "done", "seconds": 0, "note": "imported rigged character"} for s in ("ingest", "upscale", "plan", "edit", "pick", "upscale_edit", "views", "mesh", "mesh_check", "color", "rig", "rig_check", "animate", "texture", "report")}
S = {"name": a.name, "input": str(pic), "stages": stages, "skeleton": "" if a.skeleton == "valorant" else a.skeleton, "imported_from": os.path.basename(a.model), "t_start": time.time(), "t_total": 1,
     "artifacts": {"input": str(pic), "chosen_edit": str(pic), "mesh_glb": str(glb), "colored_glb": str(glb), "rig_glb": str(glb), "rig_fbx": str(fbx) if fbx.exists() else None, "final_glb": str(glb), "textured_glb": str(glb)}}
json.dump(S, open(run / "state.json", "w"), indent=1); print(f"run '{a.name}' written: {run}")
