"""Blender: how well do six axis-aligned views see every texel of a mesh? (UltraTex paints six views, front / back / left / right / top / bottom; a surface none of them sees, for instance the side of the torso under an arm in an A-pose,
gets no real colour, and shows as soon as the rig moves the arm.)
blender -b --python blender_coverage.py -- mesh.glb texel_positions.npy out_coverage.npy
texel_positions.npy: the (n, n, 3) 3D position of every texel (blender_fill_texture.py prep, same mesh, same transform), NaN or all-zero where no surface is.  Writes (n, n) floats in 0..1: the largest of
(visible from the view) * cos(angle between the surface normal and the view) / 0.45 over the six views, clipped; 1 means seen at 63 degrees or better."""
import bpy, sys, numpy as np
from mathutils import Vector
from mathutils.bvhtree import BVHTree
glb, posf, outf = sys.argv[sys.argv.index("--") + 1:][:3]
bpy.ops.wm.read_factory_settings(use_empty=True); bpy.ops.import_scene.gltf(filepath=glb)
ob = [o for o in bpy.data.objects if o.type == "MESH" and o.data.materials][0]
for o in list(bpy.data.objects):
    if o is not ob: bpy.data.objects.remove(o, do_unlink=True)
bpy.context.view_layer.objects.active = ob; ob.select_set(True); bpy.ops.object.transform_apply(location=True, rotation=True, scale=True)
dg = bpy.context.evaluated_depsgraph_get(); bvh = BVHTree.FromObject(ob, dg)
me = ob.data; me.calc_loop_triangles(); V = np.empty(len(me.vertices) * 3, np.float32); me.vertices.foreach_get("co", V); V = V.reshape(-1, 3)
T = np.empty(len(me.loop_triangles) * 3, np.int32); me.loop_triangles.foreach_get("vertices", T); T = T.reshape(-1, 3)
vol = float(np.einsum("ij,ij->i", V[T[:, 0]], np.cross(V[T[:, 1]], V[T[:, 2]])).sum() / 6.0)
FLIP = -1.0 if vol < 0 else 1.0                                       # a mesh with its faces wound the other way (UltraTex's export) has its normals pointing inward: the signed volume says which way is out
print(f"[coverage] signed volume {vol:.4f}: normals {'inward, flipped' if FLIP < 0 else 'outward'}")
P = np.load(posf); n = P.shape[0]; cov = np.zeros((n, n), np.float32); flat = P.reshape(-1, 3); ok = np.isfinite(flat).all(1) & (np.abs(flat).sum(1) > 0)
dirs = [Vector(v) for v in ((1, 0, 0), (-1, 0, 0), (0, 1, 0), (0, -1, 0), (0, 0, 1), (0, 0, -1))]
out = np.zeros(len(flat), np.float32); eps = 1e-3
for i in np.nonzero(ok)[0]:
    p = Vector(flat[i]); loc, nor, idx, dist = bvh.find_nearest(p)
    if loc is None: continue
    nor = nor * FLIP
    best = 0.0
    for d in dirs:
        c = nor.dot(d)
        if c <= 0.05 or c <= best: continue                   # facing away, or no better than the best so far
        hit = bvh.ray_cast(loc + nor * eps + d * eps, d)
        if hit[0] is None: best = c
    out[i] = min(1.0, best / 0.45)
np.save(outf, out.reshape(n, n)); print(f"[coverage] {int(ok.sum())} texels, fully seen {float((out[ok] >= 0.9).mean()) * 100:.0f} %, not seen {float((out[ok] < 0.2).mean()) * 100:.0f} %")
