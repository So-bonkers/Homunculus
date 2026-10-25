"""Run inside the live Blender (MCP: FITDIR = "...", exec(open(path).read())): builds the 52-bone Mixamo armature `mx_rig` from FITDIR/mixamo.npz (tools/template_fit/to_mixamo.py) with the bone roll of the app's Mixamo rigs:
arms, shoulders, hands and fingers: local X = the front-back axis (+Y for the left side, -Y for the right), Z = X x Y; spine, neck, head, hips and legs: Z = the back direction (-Y); feet and toes: Z = up.
Also builds `mx_mesh`, the whole template skinned to it. Frames: the template is glTF (y up); Blender gets (x, -z, y)."""
import bpy, numpy as np
from mathutils import Vector
d = np.load(FITDIR + "mixamo.npz"); conv = lambda a: np.stack([a[:, 0], -a[:, 2], a[:, 1]], axis=1)
V = conv(d["verts"]); J = conv(d["joints"]); names = [str(n) for n in d["names"]]; par = [str(p) for p in d["parents"]]; Wt = d["weights"]
for n in ("mx_mesh", "mx_rig"):
    o = bpy.data.objects.get(n)
    if o: bpy.data.objects.remove(o, do_unlink=True)
me = bpy.data.meshes.new("mx_mesh"); me.from_pydata(V.tolist(), [], d["faces"].tolist()); me.update(); ob = bpy.data.objects.new("mx_mesh", me); bpy.context.scene.collection.objects.link(ob)
for p in me.polygons: p.use_smooth = True
for i, n in enumerate(names):
    vg = ob.vertex_groups.new(name="mixamorig:" + n)
    for v in np.nonzero(Wt[:, i] > 0.001)[0]: vg.add([int(v)], float(Wt[v, i]), "REPLACE")
arm = bpy.data.armatures.new("mx_rig"); rig = bpy.data.objects.new("mx_rig", arm); bpy.context.scene.collection.objects.link(rig)
bpy.context.view_layer.objects.active = rig; bpy.ops.object.mode_set(mode="EDIT")
kids = {n: [names[i] for i in range(52) if par[i] == n] for n in names}
for i, n in enumerate(names):
    b = arm.edit_bones.new("mixamorig:" + n); b.head = Vector(J[i]); ch = kids[n]
    if ch: t = J[names.index("Spine")] if n == "Hips" else np.mean([J[names.index(c)] for c in ch], axis=0)
    else: t = J[i] + (J[i] - J[names.index(par[i])]) * 0.8
    if (Vector(t) - b.head).length < 1e-4: t = J[i] + np.array([0, 0, 0.01])
    b.tail = Vector(t)
for i, n in enumerate(names):
    if par[i]: arm.edit_bones["mixamorig:" + n].parent = arm.edit_bones["mixamorig:" + par[i]]
for b in arm.edit_bones:
    n = b.name.split(":")[-1]; y = (b.tail - b.head).normalized(); side = 1 if n.startswith("Left") else -1
    if n.startswith(("LeftShoulder", "RightShoulder", "LeftArm", "RightArm", "LeftForeArm", "RightForeArm", "LeftHand", "RightHand")):
        x = Vector((0, side, 0)); x = (x - y * x.dot(y)).normalized(); z = x.cross(y)
    elif "Foot" in n or "Toe" in n: z = Vector((0, 0, 1)); z = (z - y * z.dot(y)).normalized()
    else: z = Vector((0, -1, 0)); z = (z - y * z.dot(y)).normalized()
    b.align_roll(z)
bpy.ops.object.mode_set(mode="OBJECT"); ob.parent = rig; m = ob.modifiers.new("Armature", "ARMATURE"); m.object = rig
print("mx_rig: %d bones, mx_mesh: %d vertices" % (len(arm.bones), len(V)))
