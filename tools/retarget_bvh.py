"""Retarget a BVH mocap clip (CMU and similar) onto a rigged Mixamo-skeleton character, and export it as GLB and FBX.

blender -b --python tools/retarget_bvh.py -- <rigged_character.fbx|glb> <clip.bvh> <out_dir> <name> [--fps 60] [--map cmu|mixamo] [--start N] [--end N] [--floor-lock] [--src-fps N] [--src-scale S]

How it works (world-space, no add-on):
  * Every mapped bone of the character is given the WORLD orientation of its source bone:  R_target(f) = D(f) * C * R_target_rest,  D(f) = R_source(f) * R_source_rest^-1.
    Because it works with world orientations, a source bone that the character does not have (the CMU skeleton has two neck joints and a hip joint more) is simply skipped, and bones with different
    roll or parent frames need no special case.
  * C corrects the REST POSE for the limb bones (arm, forearm, thigh, shin, foot): the rotation that turns the character's rest bone direction onto the source's. Without it a character whose rest pose is
    not the source's (Mixamo: arms ~15 degrees below horizontal, feet pointing ~55 degrees down; CMU: a T-pose with flat feet) keeps that difference in every frame (toes always pointing down).
  * The hips follow the source's root path, scaled by the ratio of standing hip heights (so it works at any unit: the Thriller character is 0.009 m tall in glTF units), starting at the character's own place.
  * Fingers, and any bone not mapped, stay at their rest pose. Foot sliding is not corrected (--floor-lock is only a report of how much the feet slide).
Prints the facts it measured; writes <out_dir>/<name>.glb and .fbx (one animation each)."""
import bpy, sys, os, math, numpy as np
from mathutils import Matrix, Vector, Quaternion

argv = sys.argv[sys.argv.index("--") + 1:]
def opt(flag, default=None, cast=str):
    if flag in argv: i = argv.index(flag); v = argv[i + 1]; del argv[i:i + 2]; return cast(v)
    return default
OUT_FPS = opt("--fps", 60, int); MAP_NAME = opt("--map", "cmu"); F_START = opt("--start", None, int); SRC_FPS_OPT = opt("--src-fps", None, int); SRC_UNIT = opt("--src-scale", None, float); F_END = opt("--end", None, int); REPORT_ONLY_FLOOR = "--floor-lock" in argv
if "--floor-lock" in argv: argv.remove("--floor-lock")
target_path, bvh_path, out_dir, name = argv[:4]; os.makedirs(out_dir, exist_ok=True)

# target bone (without the "mixamorig:" prefix) <- source bone
MAPS = {
    "cmu": {"Hips": "Hips", "Spine": "LowerBack", "Spine1": "Spine", "Spine2": "Spine1", "Neck": "Neck", "Head": "Head",
            "LeftShoulder": "LeftShoulder", "LeftArm": "LeftArm", "LeftForeArm": "LeftForeArm", "LeftHand": "LeftHand",
            "RightShoulder": "RightShoulder", "RightArm": "RightArm", "RightForeArm": "RightForeArm", "RightHand": "RightHand",
            "LeftUpLeg": "LeftUpLeg", "LeftLeg": "LeftLeg", "LeftFoot": "LeftFoot", "LeftToeBase": "LeftToeBase",
            "RightUpLeg": "RightUpLeg", "RightLeg": "RightLeg", "RightFoot": "RightFoot", "RightToeBase": "RightToeBase"},
}
MAPS["smpl"] = {"Hips": "Pelvis", "Spine": "Spine1", "Spine1": "Spine2", "Spine2": "Spine3", "Neck": "Neck", "Head": "Head",                  # SMPL as written by tools/smpl_to_bvh.py (AIST++, FineDance)
                "LeftShoulder": "L_Collar", "LeftArm": "L_Shoulder", "LeftForeArm": "L_Elbow", "LeftHand": "L_Wrist",
                "RightShoulder": "R_Collar", "RightArm": "R_Shoulder", "RightForeArm": "R_Elbow", "RightHand": "R_Wrist",
                "LeftUpLeg": "L_Hip", "LeftLeg": "L_Knee", "LeftFoot": "L_Ankle", "LeftToeBase": "L_Foot",
                "RightUpLeg": "R_Hip", "RightLeg": "R_Knee", "RightFoot": "R_Ankle", "RightToeBase": "R_Foot"}
MAPS["mixamo"] ={k: k for k in MAPS["cmu"]}                                  # a BVH made from a Mixamo skeleton (names with or without the prefix)
LIMB = ("LeftArm", "LeftForeArm", "RightArm", "RightForeArm", "LeftUpLeg", "LeftLeg", "RightUpLeg", "RightLeg", "LeftFoot", "RightFoot")      # bones whose rest DIRECTION is well defined on both sides
MAP = MAPS[MAP_NAME]

# ---- target
bpy.ops.wm.read_factory_settings(use_empty=True)
(bpy.ops.import_scene.gltf if target_path.lower().endswith((".glb", ".gltf")) else bpy.ops.import_scene.fbx)(filepath=target_path)
T = next(o for o in bpy.data.objects if o.type == "ARMATURE")
for o in [o for o in bpy.data.objects if o.type == "MESH" and o.name == "Icosphere"]: bpy.data.objects.remove(o, do_unlink=True)        # the glTF importer's bone-shape helper
if T.animation_data: T.animation_data.action = None
for a in list(bpy.data.actions): bpy.data.actions.remove(a)
PFX = "mixamorig:" if T.data.bones.get("mixamorig:Hips") else ""
tb = {k: T.data.bones.get(PFX + k) for k in MAP}
missing = [k for k, b in tb.items() if b is None]
if missing: sys.exit(f"the character lacks bones {missing}: it needs a Mixamo-style skeleton")
Tw = T.matrix_world; Tr = Tw.to_quaternion().to_matrix(); Tr_inv = Tr.inverted()

# ---- source
SRC_FBX = bvh_path.lower().endswith((".fbx", ".glb", ".gltf"))              # the source can also be a rigged Mixamo character with an animation (e.g. the Thriller clips): --map mixamo, --src-fps N
before = set(bpy.data.objects)
if SRC_FBX:
    (bpy.ops.import_scene.gltf if bvh_path.lower().endswith((".glb", ".gltf")) else bpy.ops.import_scene.fbx)(filepath=bvh_path)
    new = [o for o in bpy.data.objects if o not in before]; S = next(o for o in new if o.type == "ARMATURE"); sc = bpy.context.scene
    for o in new:
        if o.type == "MESH": bpy.data.objects.remove(o, do_unlink=True)                          # the source's body is not wanted, only its motion
    act = S.animation_data.action
    for cb in [cb for ly in act.layers for st in ly.strips for cb in st.channelbags]:
        for fc in [fc for fc in cb.fcurves if not fc.data_path.startswith("pose.")]: cb.fcurves.remove(fc)       # an FBX action can animate the armature object itself (scale): drop that, keep the bones
    S.scale = (0.01, 0.01, 0.01) if SRC_UNIT is None else (SRC_UNIT,) * 3
    SRC_FPS = SRC_FPS_OPT or round(sc.render.fps)
else:
    bpy.ops.import_anim.bvh(filepath=bvh_path, axis_forward="-Z", axis_up="Y", global_scale=1.0, rotate_mode="NATIVE", update_scene_fps=False, use_fps_scale=False)
    S = bpy.context.object; sc = bpy.context.scene; act = S.animation_data.action
    SRC_FPS = round(1.0 / float(open(bvh_path).read().split("Frame Time:")[1].split()[0]))
f0, f1 = int(round(act.frame_range[0])), int(round(act.frame_range[1])); f0 = F_START if F_START is not None else f0; f1 = F_END if F_END is not None else f1
sb = {}
for k, sn in MAP.items():
    b = S.data.bones.get(sn) or S.data.bones.get("mixamorig:" + sn)
    if b is None: sys.exit(f"the BVH lacks bone '{sn}' (target {k}); pass --map with a matching preset")
    sb[k] = b
Sw = S.matrix_world; Sr = Sw.to_quaternion().to_matrix()

def rest_rot(obj_w, bone): return (obj_w @ bone.matrix_local).to_3x3().normalized()
Rs0 = {k: rest_rot(Sw, sb[k]) for k in MAP}; Rt0 = {k: rest_rot(Tw, tb[k]) for k in MAP}
def rest_dir(obj_w, bone): return (obj_w.to_3x3() @ (bone.tail_local - bone.head_local)).normalized()
Ccorr = {k: (rest_dir(Tw, tb[k]).rotation_difference(rest_dir(Sw, sb[k])).to_matrix() if k in LIMB else Matrix.Identity(3)) for k in MAP}
swing = {k: math.degrees(rest_dir(Tw, tb[k]).angle(rest_dir(Sw, sb[k]))) for k in LIMB}
print("[retarget] rest-pose direction difference corrected (degrees): " + ", ".join(f"{k} {v:.0f}" for k, v in swing.items()), flush=True)

# scale: standing hip height above the soles, target against source
def floor_z(obj, w, names): return min((w @ obj.data.bones[n].tail_local).z for n in names if n in obj.data.bones)
t_feet = [b.name for b in T.data.bones if "Toe" in b.name or "Foot" in b.name]; s_feet = [sb[k].name for k in ("LeftFoot", "RightFoot", "LeftToeBase", "RightToeBase")]
fl_s = floor_z(S, Sw, s_feet)
fl_t = min((Tw @ T.data.bones[n].head_local).z for n in t_feet)      # the lowest foot or toe JOINT (heads mean the same in an FBX and in a glTF rig; bone tails of a glTF rig do not, and an FBX mesh's own bounding box is not where its skinned body stands)
hips_t0 = (Tw @ tb["Hips"].head_local); h_t = hips_t0.z - fl_t; h_s = (Sw @ sb["Hips"].head_local).z - fl_s
K = h_t / h_s
print(f"[retarget] source {SRC_FPS} fps, frames {f0}-{f1}; standing hip height target {h_t:.5f} source {h_s:.3f} -> scale {K:.6f}; target floor z {fl_t:.5f}", flush=True)

# ---- sample the source
def hips_world():
    pb = S.pose.bones[sb["Hips"].name]; return (Sw @ pb.matrix).translation.copy()
step = SRC_FPS / OUT_FPS; frames = [int(round(f0 + i * step)) for i in range(int((f1 - f0) / step) + 1) if f0 + i * step <= f1]
sc.frame_set(f0); p0 = hips_world(); samples = []
for f in frames:
    sc.frame_set(f); R = {k: (Sw @ S.pose.bones[sb[k].name].matrix).to_3x3().normalized() for k in MAP}; samples.append((R, hips_world()))
print(f"[retarget] {len(frames)} output frames at {OUT_FPS} fps = {len(frames) / OUT_FPS:.2f} s", flush=True)

# ---- apply to the target
sc.render.fps = OUT_FPS
for pb in T.pose.bones: pb.rotation_mode = "QUATERNION"
order = [b.name for b in T.data.bones]                                 # armature bone order is parent-first
mapped_by_name = {tb[k].name: k for k in MAP}
act_new = bpy.data.actions.new(name); T.animation_data_create(); T.animation_data.action = act_new
rest_hips_arm = Vector(tb["Hips"].head_local)
heights = []; foot_tracks = {"L": [], "R": []}
for i, (R, hp) in enumerate(samples):
    frame = i + 1
    M_pose = {}
    for bn in order:
        bone = T.data.bones[bn]; pb = T.pose.bones[bn]
        if bone.parent is None or bone.parent.name not in M_pose: Mp_pose = None
        else: Mp_pose = M_pose[bone.parent.name]
        k = mapped_by_name.get(bn)
        if bone.parent is None:
            head = rest_hips_arm.copy()
            if k == "Hips":      # the root path, in armature space
                w = Vector((hips_t0.x + K * (hp.x - p0.x), hips_t0.y + K * (hp.y - p0.y), fl_t + K * hp.z)); head = Tw.inverted() @ w
        else:
            rel = bone.parent.matrix_local.inverted() @ bone.matrix_local; head = (M_pose[bone.parent.name] @ rel).translation if bone.parent.name in M_pose else None
        if k is None:
            if head is None: continue
            rel = bone.parent.matrix_local.inverted() @ bone.matrix_local if bone.parent else Matrix.Identity(4)
            M_pose[bn] = (M_pose[bone.parent.name] @ rel) if bone.parent and bone.parent.name in M_pose else bone.matrix_local.copy()      # follows its parent at rest
            pb.rotation_quaternion = (1, 0, 0, 0); continue
        D = R[k] @ Rs0[k].inverted(); Rt = D @ Ccorr[k] @ Rt0[k]; Ra = Tr_inv @ Rt
        M = Matrix.Translation(head if head is not None else bone.head_local) @ Ra.to_4x4()
        rel_rest = bone.matrix_local if bone.parent is None else bone.parent.matrix_local.inverted() @ bone.matrix_local
        base = M_pose[bone.parent.name] @ rel_rest if bone.parent is not None else rel_rest        # where the bone would be with no pose of its own (the parent matrices are not refreshed while we fill them in, so pb.matrix cannot be used)
        B = base.inverted() @ M; pb.rotation_quaternion = B.to_quaternion(); M_pose[bn] = M
        pb.keyframe_insert("rotation_quaternion", frame=frame)
        if k == "Hips": pb.location = B.translation; pb.keyframe_insert("location", frame=frame); heights.append(((Tw @ M).translation.z - fl_t))
    for lr, nm in (("L", "LeftFoot"), ("R", "RightFoot")):
        foot_tracks[lr].append((Tw @ M_pose[tb[nm].name]).translation.copy())
sc.frame_start, sc.frame_end = 1, len(samples)
for fc in act_new.layers[0].strips[0].channelbags[0].fcurves:
    for kp in fc.keyframe_points: kp.interpolation = "LINEAR"

# ---- report: how plausible is the result
h = np.array(heights); print(f"[retarget] hips height above the floor: min {h.min() / h_t:.2f} max {h.max() / h_t:.2f} of the standing height", flush=True)
for lr in ("L", "R"):
    P = np.array(foot_tracks[lr]); z = (P[:, 2] - fl_t) / h_t; v = np.linalg.norm(np.diff(P[:, :2], axis=0), axis=1) * OUT_FPS / h_t       # horizontal speed in standing heights per second
    low = z[1:] < (np.percentile(z, 10) + 0.04); print(f"[retarget] {lr} foot: lowest {z.min():.3f}, highest {z.max():.2f} standing heights above the floor; when it is low it slides at {np.median(v[low]) if low.any() else 0:.2f} heights/s (median)", flush=True)
print("[retarget] unmapped bones (fingers, end bones) stay at rest", flush=True)

# ---- remove the BVH, export
bpy.data.objects.remove(S, do_unlink=True)
for o in [o for o in bpy.data.objects if o.type not in ("ARMATURE", "MESH")]: bpy.data.objects.remove(o, do_unlink=True)
bpy.ops.object.select_all(action="DESELECT")
for o in bpy.data.objects:
    if o.type in ("ARMATURE", "MESH"): o.select_set(True)
bpy.context.view_layer.objects.active = T
base = os.path.join(out_dir, name)
bpy.ops.export_scene.gltf(filepath=base + ".glb", export_format="GLB", use_selection=True, export_animations=True, export_animation_mode="ACTIVE_ACTIONS", export_force_sampling=True, export_frame_range=False)
bpy.ops.export_scene.fbx(filepath=base + ".fbx", use_selection=True, object_types={"ARMATURE", "MESH"}, add_leaf_bones=False, bake_anim=True, bake_anim_use_all_actions=False, bake_anim_use_nla_strips=False,
                         bake_anim_step=1.0, bake_anim_simplify_factor=0.0, path_mode="COPY", embed_textures=True, apply_scale_options="FBX_SCALE_ALL")
print(f"[retarget] wrote {base}.glb ({os.path.getsize(base + '.glb') / 1048576:.1f} MB) and .fbx ({os.path.getsize(base + '.fbx') / 1048576:.1f} MB)", flush=True)
