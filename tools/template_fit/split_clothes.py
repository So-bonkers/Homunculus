"""Run inside the live Blender (MCP: exec(open(path).read())): the fitted template as a body underneath plus a top and a bottom garment, all skinned to the Mixamo rig `mx_rig` with the template's weights.
Reads FITDIR/mixamo.npz and FITDIR/cloth_labels.npz (tools/template_fit/cloth_labels.py). The body is pushed in under the cloth (by part: torso 2 % of the height, thighs 1.2 %, upper arms 0.5 %, feathered), the garment is the labelled faces of the fit pushed out by 0.1 of its thickness. Set FITDIR before exec."""
import bpy, numpy as np
d = np.load(FITDIR + "mixamo.npz"); L = np.load(FITDIR + "cloth_labels.npz")["labels"]
conv = lambda a: np.stack([a[:, 0], -a[:, 2], a[:, 1]], axis=1)                       # glTF y-up -> Blender z-up
V = conv(d["verts"]); F = d["faces"]; names = [str(n) for n in d["names"]]; Wt = d["weights"]; H = V[:, 2].max() - V[:, 2].min()
fn = np.cross(V[F[:, 1]] - V[F[:, 0]], V[F[:, 2]] - V[F[:, 0]]); N = np.zeros_like(V)
for k in range(3): np.add.at(N, F[:, k], fn)
N /= np.linalg.norm(N, axis=1)[:, None] + 1e-12
E = np.r_[F[:, [0, 1]], F[:, [1, 2]], F[:, [2, 0]]]; E = np.r_[E, E[:, ::-1]]; deg = np.bincount(E[:, 0], minlength=len(V)).astype(float)
def nbmean(x): s = np.zeros_like(x); np.add.at(s, E[:, 0], x[E[:, 1]]); return s / np.maximum(deg, 1)
T = {1: 0.0055 * H, 2: 0.0065 * H}                                                    # garment thickness (top, bottom)
# the fit follows the (baggy) cloth, so the body under it is pushed in, by how much depending on the part: the torso carries the loosest cloth, the upper arms inside the sleeves hardly any (a lean child's arm fills its sleeve)
dom = np.array(names)[d["weights"].argmax(1)]; INSET = {"Hips": 0.020, "Spine": 0.022, "Spine1": 0.022, "Spine2": 0.020, "LeftUpLeg": 0.012, "RightUpLeg": 0.012, "LeftArm": 0.005, "RightArm": 0.005, "LeftShoulder": 0.008, "RightShoulder": 0.008}
bo = np.array([INSET.get(n, 0.004) for n in dom]) * H * (L > 0)
for _ in range(4): bo = 0.5 * bo + 0.5 * nbmean(bo)
body_V = V - N * bo[:, None]
def make(name, verts, faces, col, src):
    me = bpy.data.meshes.new(name); me.from_pydata(verts.tolist(), [], faces.tolist()); me.update(); ob = bpy.data.objects.new(name, me); bpy.context.scene.collection.objects.link(ob)
    for p in me.polygons: p.use_smooth = True
    for i, n in enumerate(names):
        vg = ob.vertex_groups.new(name="mixamorig:" + n)
        for j, v in enumerate(src):
            if Wt[v, i] > 0.001: vg.add([j], float(Wt[v, i]), "REPLACE")
    mat = bpy.data.materials.new(name + "_mat"); mat.diffuse_color = col; ob.data.materials.append(mat); return ob
for n in ("lila_body", "lila_top", "lila_bottom"):
    o = bpy.data.objects.get(n)
    if o: bpy.data.objects.remove(o, do_unlink=True)
parts = [make("lila_body", body_V, F, (0.85, 0.6, 0.45, 1), list(range(len(V))))]
for g, nm, col in ((1, "lila_top", (0.55, 0.55, 0.57, 1)), (2, "lila_bottom", (0.38, 0.38, 0.43, 1))):
    Fg = F[np.nonzero((L[F] == g).all(1))[0]]; used = np.unique(Fg); remap = -np.ones(len(V), int); remap[used] = np.arange(len(used))
    parts.append(make(nm, V[used] + N[used] * T[g] * 0.1, remap[Fg], col, list(used)))
rig = bpy.data.objects["mx_rig"]
for ob in parts: ob.parent = rig; m = ob.modifiers.new("Armature", "ARMATURE"); m.object = rig
print("split:", {o.name: len(o.data.vertices) for o in parts})
