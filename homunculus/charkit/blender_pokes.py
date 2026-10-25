"""Poke-through count of an assembled kit (the .blend from assemble_kit.py) and a render of it for the judge.
    blender -b KIT.blend --python homunculus/charkit/blender_pokes.py -- OUT.json RENDER_PREFIX [--garments hoodie,joggers] [--step 7] [--engine cycles|workbench]
For every `step`-th vertex of kit_body inside a garment's height range: a ray along the body's normal (the body's normals are reliable, the garments' are not) that finds the garment
within REACH means the skin is under it (fine); no hit outward but a hit inward means the skin is OUTSIDE the garment: a poke-through. OUT.json: per garment tested / poked, and the total fraction."""
import bpy, bmesh, json, os, sys
from mathutils.bvhtree import BVHTree
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import blender_thumbs as T
argv = sys.argv[sys.argv.index("--") + 1:]; OUT, PREFIX = argv[:2]; opt = lambda k, d: argv[argv.index(k) + 1] if k in argv else d
STEP = int(opt("--step", "7")); REACH = 0.05; garments = [g for g in opt("--garments", "").split(",") if g]
body = bpy.data.objects.get("kit_body"); res = {"garments": {}, "tested": 0, "poked": 0}
if body is None: raise SystemExit("no kit_body in the .blend")
for g in garments:
    o = bpy.data.objects.get(f"kit_{g}")
    if o is None: res["garments"][g] = {"missing": True}; continue
    bm = bmesh.new(); bm.from_mesh(o.data); bm.transform(o.matrix_world); bvh = BVHTree.FromBMesh(bm); zs = [v.co.z for v in bm.verts]; zlo, zhi = min(zs) + 0.01, max(zs) - 0.01; bm.free()
    t = p = 0; M = body.matrix_world; N = M.to_3x3().inverted().transposed()
    for v in body.data.vertices[::STEP]:
        co = M @ v.co
        if not (zlo < co.z < zhi): continue
        n = (N @ v.normal).normalized()
        if bvh.ray_cast(co, n, REACH)[0] is not None: t += 1; continue
        if bvh.ray_cast(co, -n, REACH)[0] is not None: t += 1; p += 1
    res["garments"][g] = {"tested": t, "poked": p}; res["tested"] += t; res["poked"] += p; print(g, "tested", t, "poked", p, flush=True)
res["fraction"] = res["poked"] / max(1, res["tested"])
T.setup(opt("--engine", "cycles"), 512)
if opt("--engine", "cycles") == "cycles":
    import math
    sun = bpy.data.objects.new("sun", bpy.data.lights.new("sun", "SUN")); sun.data.energy = 3; sun.rotation_euler = (math.radians(50), 0, math.radians(30)); bpy.context.scene.collection.objects.link(sun)
res["renders"] = T.render_views([o for o in bpy.data.objects if o.type == "MESH" and o.name.startswith("kit_")], PREFIX, ["front", "three_q", "back"])
json.dump(res, open(OUT, "w"), indent=1); print("pokes:", json.dumps(res), flush=True)
