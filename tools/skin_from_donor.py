"""Skin a mesh without a rig from a rigged one of the same kind of body (the Valorant agents share one skeleton and one A-pose):

    blender -b --python tools/skin_from_donor.py -- <donor_rigged.glb> <mesh.glb> <out.glb> <out.fbx>

The donor is a rig made by tools/convert_rigged.py (52 Mixamo bones, hips at the origin, facing -Y); the mesh faces -Y, stands on z = 0, in metres, with its own materials and textures.  The donor is scaled to the mesh's height and put under it
(feet on the same level, legs' centre on the same spot), every vertex of the mesh takes the weights of the nearest point of the donor's surface (interpolated across that face), the mesh keeps its own shape, normals, UVs and textures. The result has the donor's
bones, scaled, with the hips at the origin, as every rig of the app.  Used for Raze, whose model came without a rig and whose Make-It-Animatable result lost its texture quality (flat shading, one re-baked atlas)."""
import bpy, sys, os, math
from mathutils import Vector, Matrix
from mathutils.bvhtree import BVHTree
from mathutils.interpolate import poly_3d_calc
donor, mesh, out_glb, out_fbx = sys.argv[sys.argv.index("--") + 1:][:4]
bpy.ops.wm.read_factory_settings(use_empty=True)
bpy.ops.import_scene.gltf(filepath=donor); D = next(o for o in bpy.data.objects if o.type == "ARMATURE"); DM = [o for o in bpy.data.objects if o.type == "MESH" and o.name != "Icosphere"]
before = set(bpy.data.objects); bpy.ops.import_scene.gltf(filepath=mesh); new = [o for o in bpy.data.objects if o not in before]; TM = [o for o in new if o.type == "MESH" and o.name != "Icosphere"]
for o in [o for o in bpy.data.objects if o.type == "MESH" and o.name == "Icosphere"]: bpy.data.objects.remove(o, do_unlink=True)
for o in new:
    if o.type == "ARMATURE": bpy.data.objects.remove(o, do_unlink=True)
def world_pts(objs): return [o.matrix_world @ v.co for o in objs for v in o.data.vertices]
dp, tp = world_pts(DM), world_pts(TM)
h_d = max(p.z for p in dp) - min(p.z for p in dp); h_t = max(p.z for p in tp) - min(p.z for p in tp); s = h_t / h_d
def leg_centre(pts):
    z0 = min(p.z for p in pts); h = max(p.z for p in pts) - z0; sel = [p for p in pts if z0 + 0.3 * h <= p.z <= z0 + 0.5 * h]; return Vector((sum(p.x for p in sel) / len(sel), sum(p.y for p in sel) / len(sel), z0))
cd, ct = leg_centre(dp), leg_centre(tp)
M = Matrix.Translation(ct) @ Matrix.Scale(s, 4) @ Matrix.Translation(-cd)                  # donor world -> mesh world
print(f"skin_from_donor: donor {h_d:.3f} m, mesh {h_t:.3f} m, scale {s:.3f}")
for o in TM + DM:
    for m in [m for m in o.modifiers if m.type == "ARMATURE"]: o.modifiers.remove(m)
    mw = o.matrix_world.copy(); o.parent = None; o.data.transform((M if o in DM else Matrix.Identity(4)) @ mw); o.matrix_world = Matrix.Identity(4)
bpy.context.view_layer.objects.active = D; bpy.ops.object.select_all(action="DESELECT"); D.select_set(True)
mw = D.matrix_world.copy(); D.matrix_world = M @ mw; bpy.ops.object.transform_apply(location=True, rotation=True, scale=True)           # the donor's bones go where the scaled donor mesh is
names = [g.name for g in DM[0].vertex_groups]
# weights: the nearest point of the donor's surface, interpolated across its face
dm = DM[0]; bvh = BVHTree.FromObject(dm, bpy.context.evaluated_depsgraph_get()); dw = {}
for v in dm.data.vertices: dw[v.index] = {dm.vertex_groups[g.group].name: g.weight for g in v.groups}
dpoly = dm.data.polygons
for o in TM:
    for g in list(o.vertex_groups): o.vertex_groups.remove(g)
    vg = {n: o.vertex_groups.new(name=n) for n in names}
    for v in o.data.vertices:
        loc, nor, idx, dist = bvh.find_nearest(v.co)
        if idx is None: continue
        pv = list(dpoly[idx].vertices); w = poly_3d_calc([dm.data.vertices[i].co for i in pv], loc); acc = {}
        for i, wi in zip(pv, w):
            for n, ww in dw[i].items(): acc[n] = acc.get(n, 0.0) + ww * wi
        tot = sum(acc.values())
        for n, ww in acc.items():
            if ww > 1e-4 and tot > 0: vg[n].add([v.index], ww / tot, "REPLACE")
# a loose piece far from the donor's surface (a backpack plate, a strap) takes the weights of whatever point of the donor is nearest, perhaps a hand: it would then be dragged by that hand.  A weight on a limb bone counts only
# within reach of the bone itself; what is left goes to the nearest of the body's central bones
import numpy as np
seg = {}
for b in D.data.bones: seg["" + b.name] = (np.array(b.head_local[:]), np.array(b.tail_local[:]))
CORE = [n for n in seg if any(k in n for k in ("Hips", "Spine", "Neck", "Head"))]; REACH = {True: 0.55, False: 0.2}
def dist(P, n):
    a, b = seg[n]; ab = b - a; t = np.clip(((P - a) @ ab) / max(ab @ ab, 1e-12), 0, 1); return np.linalg.norm(P - (a + t[:, None] * ab), axis=1)
fixed = 0
for o in TM:
    P = np.array([v.co[:] for v in o.data.vertices]); names_ = [g.name for g in o.vertex_groups]; W = np.zeros((len(P), len(names_)), np.float32)
    for v in o.data.vertices:
        for g in v.groups: W[v.index, g.group] = g.weight
    for j, n in enumerate(names_):
        if n not in seg: continue
        reach = REACH[n in CORE]; far = dist(P, n) > reach; W[far, j] = 0
    empty = W.sum(1) < 1e-6; fixed += int(empty.sum())
    if empty.any():
        dc = np.stack([dist(P[empty], n) for n in CORE], 1); near = np.argmin(dc, 1)
        for k_, vi in enumerate(np.where(empty)[0]): W[vi, names_.index(CORE[near[k_]])] = 1.0
    W /= np.maximum(W.sum(1, keepdims=True), 1e-9)
    for g in list(o.vertex_groups): o.vertex_groups.remove(g)
    vg = {n: o.vertex_groups.new(name=n) for n in names_}
    for i in range(len(P)):
        for j in np.nonzero(W[i] > 1e-4)[0]: vg[names_[j]].add([i], float(W[i, j]), "REPLACE")
print(f"skin_from_donor: {fixed} vertices were out of reach of every bone they had a weight on")
for o in DM: bpy.data.objects.remove(o, do_unlink=True)
for o in TM:
    o.parent = D; mod = o.modifiers.new("Armature", "ARMATURE"); mod.object = D
# hips at the origin, as every rig of the app
hips = D.data.bones["mixamorig:Hips"].head_local.copy(); T = Matrix.Translation(-hips)
for o in TM: o.data.transform(T)
bpy.context.view_layer.objects.active = D; D.matrix_world = T @ D.matrix_world; bpy.ops.object.select_all(action="DESELECT"); D.select_set(True); bpy.ops.object.transform_apply(location=True, rotation=True, scale=True)
bpy.ops.object.select_all(action="SELECT")
bpy.ops.export_scene.gltf(filepath=out_glb, export_format="GLB", use_selection=True)
bpy.ops.export_scene.fbx(filepath=out_fbx, use_selection=True, object_types={"ARMATURE", "MESH"}, add_leaf_bones=False, path_mode="COPY", embed_textures=True)
print("skinned", out_glb)
