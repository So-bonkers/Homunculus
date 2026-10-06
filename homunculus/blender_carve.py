"""Silhouette carve: Pixal3D's shape lines up with its input picture from the front, so geometry that falls outside the character's
outline (seen from the front) is an artefact - fins past the fingertips, plates beside the hands, floaters. Delete it.

blender -b --python blender_carve.py -- in.glb mask.npy out.glb [margin_frac]
mask.npy: the character's cut-out (bool, image pixels) of the picture the mesh was made from.
"""
import bpy, bmesh, sys, numpy as np
argv = sys.argv[sys.argv.index("--") + 1:]
glb_in, mask_p, glb_out = argv[:3]; margin = float(argv[3]) if len(argv) > 3 else 0.025
bpy.ops.wm.read_factory_settings(use_empty=True); bpy.ops.import_scene.gltf(filepath=glb_in)
ob = [o for o in bpy.data.objects if o.type == "MESH"][0]
for o in list(bpy.data.objects):
    if o.type != "MESH": bpy.data.objects.remove(o, do_unlink=True)
bpy.context.view_layer.objects.active = ob; ob.select_set(True)
bpy.ops.object.transform_apply(location=True, rotation=True, scale=True)
me = ob.data; n = len(me.vertices); V = np.empty(n * 3, np.float32); me.vertices.foreach_get("co", V); V = V.reshape(-1, 3)

fg = np.load(mask_p); H, W = fg.shape
rows = np.nonzero(fg.any(1))[0]; top_i, bot_i = rows.min(), rows.max()
zmin, zmax = V[:, 2].min(), V[:, 2].max(); s = (bot_i - top_i) / (zmax - zmin)
band = (V[:, 2] > zmin + 0.55 * (zmax - zmin)) & (V[:, 2] < zmin + 0.70 * (zmax - zmin)); xc_m = np.median(V[band, 0])
r0, r1 = int(top_i + 0.30 * (bot_i - top_i)), int(top_i + 0.45 * (bot_i - top_i))
xc_i = float(np.median([np.mean(np.nonzero(fg[r])[0]) for r in range(r0, r1) if fg[r].any()]))
u = (V[:, 0] - xc_m) * s + xc_i; v = (zmax - V[:, 2]) * s + top_i

# widen the outline (the projection is not perfectly orthographic at the far ends of the arms), then test every vertex
rad = max(2, int(margin * (bot_i - top_i)))
grow = fg.copy()
for _ in range(rad):        # binary dilation without scipy (Blender's Python has none)
    g = grow.copy(); g[1:] |= grow[:-1]; g[:-1] |= grow[1:]; g[:, 1:] |= grow[:, :-1]; g[:, :-1] |= grow[:, 1:]; grow = g
ui = np.clip(u.astype(int), 0, W - 1); vi = np.clip(v.astype(int), 0, H - 1)
inside = grow[vi, ui] & (u >= 0) & (u < W) & (v >= 0) & (v < H)
out_idx = np.nonzero(~inside)[0]
if len(out_idx):
    bm = bmesh.new(); bm.from_mesh(me); bm.verts.ensure_lookup_table()
    bmesh.ops.delete(bm, geom=[bm.verts[i] for i in out_idx], context="VERTS"); bm.to_mesh(me); bm.free()
bpy.ops.export_scene.gltf(filepath=glb_out, export_format="GLB", export_yup=True)
print(f"[carve] removed {len(out_idx)} of {n} vertices outside the outline (margin {rad}px)")
