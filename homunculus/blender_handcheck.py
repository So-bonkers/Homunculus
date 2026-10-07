"""Do the hands of a T/A-posed model look broken?  (CPU, a few seconds)
blender -b --python blender_handcheck.py -- model.glb out.json
Cut-off or torn fingers leave open edges (holes in the surface); a healthy hand is closed. For the outer ~10.5 % of the height on each side (the hands) the open edges per 1000 vertices are counted
(only in small loops: a single large clean ring is a cut end, not damage) after welding the vertices the importer split at UV seams. Result per side: {"verts", "open_edges", "open_per_1000", "broken"} (broken above 8 per 1000: a healthy hand measured 0, torn
glove fingers 35). It does not see fingers that are fused but closed."""
import bpy, bmesh, sys, json
import numpy as np

src, out = sys.argv[sys.argv.index("--") + 1:][:2]
bpy.ops.wm.read_factory_settings(use_empty=True); bpy.ops.import_scene.gltf(filepath=src)
ms = [o for o in bpy.data.objects if o.type == "MESH" and len(o.data.vertices) > 500]
if not ms: json.dump({"error": "no mesh"}, open(out, "w")); sys.exit(2)
bpy.ops.object.select_all(action="DESELECT")
for o in ms: o.select_set(True)
bpy.context.view_layer.objects.active = ms[0]
if len(ms) > 1: bpy.ops.object.join()
ob = bpy.context.view_layer.objects.active; bpy.ops.object.transform_apply(location=True, rotation=True, scale=True)
bm = bmesh.new(); bm.from_mesh(ob.data); bmesh.ops.remove_doubles(bm, verts=bm.verts, dist=2e-5); bm.edges.ensure_lookup_table()
V = np.array([tuple(v.co) for v in bm.verts]); lo, hi = V.min(0), V.max(0); cx = (lo[0] + hi[0]) / 2; height = hi[2] - lo[2]; lim = (hi[0] - lo[0]) / 2 - 0.105 * height
res = {}
for side, sgn in (("left", 1), ("right", -1)):
    inside = lambda v: (v.co.x - cx) * sgn > lim
    n = sum(1 for v in bm.verts if inside(v)); be = [e for e in bm.edges if e.is_boundary and inside(e.verts[0]) and inside(e.verts[1])]
    parent = {}
    def find(x):
        while parent.setdefault(x, x) != x: parent[x] = parent[parent[x]]; x = parent[x]
        return x
    for e in be: parent[find(e.verts[0].index)] = find(e.verts[1].index)
    loops = {}
    for e in be: loops.setdefault(find(e.verts[0].index), []).append(e)
    ne = sum(len(l) for l in loops.values() if len(l) <= 150)            # many small holes (torn fingertips); a single big clean ring is a cut end (a repaired hand's cuff inside the arm), not damage
    per = 1000.0 * ne / max(1, n); res[side] = {"verts": n, "open_edges": ne, "open_per_1000": round(per, 1), "broken": bool(n > 200 and per > 8.0)}
    print(f"[handcheck] {side}: {n} vertices, {ne} open edges ({per:.1f} per 1000) -> {'BROKEN' if res[side]['broken'] else 'ok'}")
json.dump(res, open(out, "w"))
