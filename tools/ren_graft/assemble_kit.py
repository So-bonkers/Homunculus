"""Assemble a character kit in background Blender: base body + garments + parts (TRELLIS.2 GLBs) placed by align_item.py transforms, garment lids at the openings removed,
the body tucked GAP inside the garments (ray casts along the BODY's normals: garment normals are not reliable), saved as a .blend (one object per item).
    blender -b --python tools/ren_graft/assemble_kit.py -- KIT_DIR OUT.blend [--gap 0.004]
KIT_DIR holds <item>/s42/textured.glb and place_<item>.json for body, hoodie, joggers, hair (and any other item with a place file); garments = hoodie, joggers."""
import bpy, bmesh, json, sys, os, numpy as np
from mathutils import Matrix
from mathutils.bvhtree import BVHTree
argv = sys.argv[sys.argv.index("--") + 1:]; KIT, OUT = argv[:2]; GAP = float(argv[argv.index("--gap") + 1]) if "--gap" in argv else 0.004
GARMENTS = {"hoodie": ("bottom",), "joggers": ("bottom", "top")}
bpy.ops.wm.read_factory_settings(use_empty=True); C = np.array([[1, 0, 0, 0], [0, 0, -1, 0], [0, 1, 0, 0], [0, 0, 0, 1]], float); objs = {}
for f in sorted(os.listdir(KIT)):
    if not (f.startswith("place_") and f.endswith(".json")): continue
    it = f[6:-5]; glb = os.path.join(KIT, it, "s42", "textured.glb")
    if not os.path.exists(glb): continue
    before = set(bpy.data.objects); bpy.ops.import_scene.gltf(filepath=glb); o = [q for q in bpy.data.objects if q not in before and q.type == "MESH"][0]; o.name = f"kit_{it}"
    for q in [q for q in bpy.data.objects if q not in before and q is not o]: bpy.data.objects.remove(q, do_unlink=True)
    M = np.array(json.load(open(os.path.join(KIT, f)))["matrix"]); o.matrix_world = Matrix((C @ M @ np.linalg.inv(C)).tolist()) @ o.matrix_world
    o.data.transform(o.matrix_world); o.matrix_world = Matrix.Identity(4); objs[it] = o; print("loaded", it, len(o.data.polygons), flush=True)
def remove_lids(o, where):
    bm = bmesh.new(); bm.from_mesh(o.data); zs = [f.calc_center_median().z for f in bm.faces]; zmin, zmax = min(zs), max(zs); dead = []
    for f in bm.faces:
        c, n = f.calc_center_median(), f.normal
        if ("bottom" in where and n.z < -0.85 and c.z < zmin + 0.012) or ("top" in where and n.z > 0.85 and c.z > zmax - 0.012): dead.append(f)
    bmesh.ops.delete(bm, geom=dead, context="FACES"); bm.to_mesh(o.data); bm.free(); o.data.update(); return len(dead)
for g, where in GARMENTS.items():
    if g in objs: print(g, "lid faces removed:", remove_lids(objs[g], where), flush=True)
body = objs["body"]; bm = bmesh.new(); bm.from_mesh(body.data); bmesh.ops.recalc_face_normals(bm, faces=bm.faces); bm.to_mesh(body.data); bm.free(); body.data.update()
REACH = 0.05; moved = 0
for g in GARMENTS:
    if g not in objs: continue
    gb = bmesh.new(); gb.from_mesh(objs[g].data); bvh = BVHTree.FromBMesh(gb); zs = [v.co.z for v in gb.verts]; zlo, zhi = min(zs) - 0.005, max(zs) + 0.005; gb.free()
    for v in body.data.vertices:
        if not (zlo < v.co.z < zhi): continue
        n = v.normal; out = bvh.ray_cast(v.co, n, REACH)
        if out[0] is not None:
            if out[3] < GAP: v.co = v.co - n * (GAP - out[3]); moved += 1
            continue
        back = bvh.ray_cast(v.co, -n, REACH)
        if back[0] is not None: v.co = v.co - n * (back[3] + GAP); moved += 1
    print(g, "tucked so far:", moved, flush=True)
body.data.update(); bpy.ops.wm.save_as_mainfile(filepath=OUT); print("saved", OUT, flush=True)
