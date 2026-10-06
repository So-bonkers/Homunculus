"""Put a rigged humanoid into a T-pose and bake that pose into its mesh.

blender -b --python blender_tpose.py -- rigged.glb out_static.glb [--frame N]

Works with any humanoid skeleton: the body parts (spine, neck/head, both arms, both legs) are found by name when the bones are Mixamo-named,
else from the skeleton's shape (the pelvis is the root, the chest is where three limbs branch, arms leave it sideways, legs go down).
Then, parents first, every limb bone is rotated about its head so that the direction JOINT -> NEXT JOINT matches the T-pose target: spine, neck
and head up, arms sideways (the character's left = +X, facing -Y), legs down. Directions come from joint positions, never from bone tails
(importers guess tails). The armature deformation is then applied to a copy of the mesh (UVs and materials kept) and exported as a static GLB.
Prints [tpose] lines; exit code 2 when no humanoid structure is found.
"""
import bpy, sys
from mathutils import Matrix, Vector

argv = sys.argv[sys.argv.index("--") + 1:]
src, out = argv[0], argv[1]
frame = int(argv[argv.index("--frame") + 1]) if "--frame" in argv else None
bpy.ops.wm.read_factory_settings(use_empty=True)
bpy.ops.import_scene.gltf(filepath=src)
arm = next((o for o in bpy.data.objects if o.type == "ARMATURE"), None)
meshes = [o for o in bpy.data.objects if o.type == "MESH" and any(m.type == "ARMATURE" for m in o.modifiers)]      # skinned meshes only
if arm is None or not meshes:
    print("[tpose] no armature or skinned mesh in the file"); sys.exit(2)
if frame is not None: bpy.context.scene.frame_set(frame)
bpy.context.view_layer.objects.active = arm
W = arm.matrix_world
pose = {b.name: b for b in arm.pose.bones}


def head(b):
    return (W @ b.matrix).translation.copy()


def kids(b):
    return list(b.children)


# ------------------------------------------------------------------ find the body parts
def short(n):
    return n.split(":")[-1].replace("mixamorig", "")


def by_mixamo_names():
    p = {short(b.name): b for b in arm.pose.bones}
    if not all(n in p for n in ("Hips", "Spine", "Head", "LeftArm", "LeftForeArm", "RightArm", "RightForeArm", "LeftUpLeg", "LeftLeg", "RightUpLeg", "RightLeg")): return None
    g = lambda *names: [p[n] for n in names if n in p]
    return {"spine": g("Hips", "Spine", "Spine1", "Spine2"), "neck": g("Neck", "Neck1", "Head"),
            "armL": g("LeftShoulder", "LeftArm", "LeftForeArm", "LeftHand"), "armR": g("RightShoulder", "RightArm", "RightForeArm", "RightHand"),
            "legL": g("LeftUpLeg", "LeftLeg", "LeftFoot", "LeftToeBase"), "legR": g("RightUpLeg", "RightLeg", "RightFoot", "RightToeBase")}


def by_shape():
    roots = [b for b in arm.pose.bones if b.parent is None]
    root = max(roots, key=lambda b: len(b.children_recursive))
    if len(root.children) < 3 and root.children:
        # a root above the pelvis: descend to the first bone with three children
        cur = root
        while len(cur.children) == 1: cur = cur.children[0]
        root = cur
    ups = [c for c in root.children if head(c).z > head(root).z + 0.02]; downs = [c for c in root.children if c.name not in [u.name for u in ups]]
    if len(ups) != 1 or len(downs) != 2: return None
    spine = [root]; cur = ups[0]
    while True:
        spine.append(cur)
        if len(cur.children) != 1: break
        cur = cur.children[0]
    chest = spine[-1]
    if len(chest.children) < 3: return None
    limbs = sorted(chest.children, key=lambda b: head(b).z)       # arms start lower than the neck/head chain
    neck_start = max(chest.children, key=lambda b: (head(b).z + 5 * (0 if abs(head(b).x - head(chest).x) > 0.06 else 1)))
    arms = [c for c in chest.children if c.name != neck_start.name]
    if len(arms) != 2: return None
    def chain(b):
        out = [b]
        while out[-1].children: out.append(max(out[-1].children, key=lambda c: len(c.children_recursive)))
        return out
    left = max(arms, key=lambda b: head(b).x); right = min(arms, key=lambda b: head(b).x)
    legL = max(downs, key=lambda b: head(b).x); legR = min(downs, key=lambda b: head(b).x)
    return {"spine": spine, "neck": chain(neck_start), "armL": chain(left), "armR": chain(right), "legL": chain(legL), "legR": chain(legR)}


parts = by_mixamo_names() or by_shape()
if parts is None:
    print("[tpose] no humanoid structure found in the skeleton"); sys.exit(2)
print("[tpose] parts:", {k: [b.name for b in v] for k, v in parts.items()})

UP, DOWN, LEFT, RIGHT = Vector((0, 0, 1)), Vector((0, 0, -1)), Vector((1, 0, 0)), Vector((-1, 0, 0))


def rotate_about_head(b, rot3):
    """Rotate pose bone b by the world-space rotation rot3 about its own head (descendants follow)."""
    m = W @ b.matrix; h = m.translation.copy()
    new = Matrix.Translation(h) @ rot3.to_4x4() @ Matrix.Translation(-h) @ m
    b.matrix = W.inverted() @ new
    bpy.context.view_layer.update()


def align(b, nxt, t):
    """Rotate b so that the direction from its head to nxt's head points along t."""
    cur = head(nxt) - head(b)
    if cur.length < 1e-6: return False
    ang = cur.normalized().angle(t)
    if ang < 0.01: return False
    rotate_about_head(b, cur.normalized().rotation_difference(t).to_matrix()); return True


moved = 0
chains = [("spine", UP, True), ("neck", UP, True), ("armL", LEFT, False), ("armR", RIGHT, False), ("legL", DOWN, False), ("legR", DOWN, False)]
for name, t, vertical in chains:
    ch = parts[name]
    last = len(ch) - 1
    for i, b in enumerate(ch):
        if i == last: break                       # a chain's last bone (hand, toe, head, chest top) follows its parent
        if name.startswith("leg") and i >= 2: break    # feet and toes keep their own shape relative to the straightened leg
        if name.startswith("arm") and i == last - 1 and last >= 1: pass  # forearm: aligned like the rest, the hand follows it
        moved += bool(align(b, ch[i + 1], t))
print(f"[tpose] aligned {moved} bones")

# ------------------------------------------------------------------ bake the deformation into a copy of the mesh
dg = bpy.context.evaluated_depsgraph_get()
new_objs = []
for o in meshes:
    ev = o.evaluated_get(dg); me = bpy.data.meshes.new_from_object(ev, preserve_all_data_layers=True, depsgraph=dg)
    no = bpy.data.objects.new(o.name + "_tpose", me); bpy.context.scene.collection.objects.link(no); no.matrix_world = o.matrix_world.copy(); new_objs.append(no)
for o in list(bpy.data.objects):
    if o not in new_objs: bpy.data.objects.remove(o, do_unlink=True)
bpy.ops.object.select_all(action="DESELECT")
for o in new_objs: o.select_set(True)
bpy.context.view_layer.objects.active = new_objs[0]
bpy.ops.export_scene.gltf(filepath=out, export_format="GLB", use_selection=True)
print("[tpose] wrote", out)
