"""Blender: drop small floating pieces (< 0.5% of the vertices) from a GLB, keep materials/UVs, export GLB.
Connectivity is by position (glTF import splits vertices along UV seams, which must not count as separate pieces)."""
import bpy, sys, numpy as np
glb, out = sys.argv[sys.argv.index("--") + 1:][:2]
bpy.ops.wm.read_factory_settings(use_empty=True); bpy.ops.import_scene.gltf(filepath=glb)
ob = [o for o in bpy.data.objects if o.type == "MESH"][0]; me = ob.data; n = len(me.vertices)
V = np.empty(n * 3, np.float32); me.vertices.foreach_get("co", V); V = V.reshape(-1, 3)
_, weld = np.unique(np.round(V / 1e-5).astype(np.int64), axis=0, return_inverse=True); weld = weld.ravel()
par = np.arange(weld.max() + 1)
def find(a):
    r = a
    while par[r] != r: r = par[r]
    while par[a] != r: par[a], a = r, par[a]
    return r
E_ = np.empty(len(me.edges) * 2, np.int32); me.edges.foreach_get("vertices", E_); E_ = weld[E_.reshape(-1, 2)]
for a, b in E_:
    ra, rb = find(a), find(b)
    if ra != rb: par[ra] = rb
roots = np.array([find(w) for w in weld]); ids, cnt = np.unique(roots, return_counts=True)
small = set(ids[cnt < 0.005 * n].tolist()); drop = np.nonzero(np.isin(roots, list(small)))[0]
import bmesh
bm = bmesh.new(); bm.from_mesh(me); bm.verts.ensure_lookup_table()
bmesh.ops.delete(bm, geom=[bm.verts[i] for i in drop], context="VERTS"); bm.to_mesh(me); bm.free()
bpy.ops.export_scene.gltf(filepath=out, export_format="GLB")
print(f"[clean] {len(ids)} pieces, removed {len(small)} small ones ({len(drop)} verts)")
