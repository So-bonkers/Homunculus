"""Join Mixamo clips that were applied to the same character: each clip as its own GLB and FBX, plus one joined clip, with a short blend at every seam.

blender -b --python tools/join_clips.py -- <out_dir> <name> <blend_seconds> <clip1.fbx> <clip2.fbx> ...
  out_dir/<name>_Part_N.glb|fbx   one file per input (the mesh, the skeleton and that clip)
  out_dir/<name>_Joined.glb|fbx   all clips one after the other as ONE animation
The inputs must share one skeleton and one mesh (Mixamo downloads of the same character do). The mesh and the skeleton come from the first file. At a seam the next clip's first frames are blended
from the previous clip's last pose to its own (smoothstep), so a small difference between the end of one part and the start of the next does not pop. Every channel is sampled once per frame (the
clips are keyed per frame already), so nothing is simplified."""
import bpy, sys, os, math, numpy as np
argv = sys.argv[sys.argv.index("--") + 1:]; out_dir, name, blend_s = argv[0], argv[1], float(argv[2]); files = argv[3:]
os.makedirs(out_dir, exist_ok=True)
bpy.ops.wm.read_factory_settings(use_empty=True)
bpy.ops.import_scene.fbx(filepath=files[0])
A = next(o for o in bpy.data.objects if o.type == "ARMATURE"); sc = bpy.context.scene; FPS = sc.render.fps
actions = [A.animation_data.action]; actions[0].use_fake_user = True
for f in files[1:]:      # the other clips: only their animation is kept
    before_objs = set(bpy.data.objects); before_act = set(bpy.data.actions)
    bpy.ops.import_scene.fbx(filepath=f)
    new_act = [a for a in bpy.data.actions if a not in before_act][0]; new_act.use_fake_user = True; actions.append(new_act)
    for o in [o for o in bpy.data.objects if o not in before_objs]: bpy.data.objects.remove(o, do_unlink=True)
for i, a in enumerate(actions): a.name = f"{name}_Part_{i + 1}"
print(f"[join] {len(actions)} clips, {FPS} fps: " + ", ".join(f"{a.name} {a.frame_range[0]:.0f}-{a.frame_range[1]:.0f}" for a in actions), flush=True)

def fcurves_of(act):
    """Blender 5.x keeps animation in layered actions (layer > strip > channelbag); the classic action.fcurves is gone."""
    return act.layers[0].strips[0].channelbags[0].fcurves


def sample(act):
    """{(data_path, index): array of values for frame_start..frame_end}"""
    f0, f1 = int(round(act.frame_range[0])), int(round(act.frame_range[1])); fr = np.arange(f0, f1 + 1); ch = {}
    for fc in fcurves_of(act): ch[(fc.data_path, fc.array_index)] = np.array([fc.evaluate(float(x)) for x in fr], np.float32)
    return ch, len(fr)

def export(path_noext, label):
    bpy.ops.object.select_all(action="DESELECT")
    for o in bpy.data.objects:
        if o.type in ("ARMATURE", "MESH"): o.select_set(True)
    bpy.context.view_layer.objects.active = A
    bpy.ops.export_scene.gltf(filepath=path_noext + ".glb", export_format="GLB", use_selection=True, export_animations=True, export_animation_mode="ACTIVE_ACTIONS", export_force_sampling=True, export_frame_range=False)      # only the active action goes into the file (the default writes every action in the .blend, clipped to the scene range)
    bpy.ops.export_scene.fbx(filepath=path_noext + ".fbx", use_selection=True, object_types={"ARMATURE", "MESH"}, add_leaf_bones=False, bake_anim=True, bake_anim_use_all_actions=False,
                             bake_anim_use_nla_strips=False, bake_anim_step=1.0, bake_anim_simplify_factor=0.0, path_mode="COPY", embed_textures=True, apply_scale_options="FBX_SCALE_ALL")
    print(f"[join] wrote {label}: " + ", ".join(f"{e} {os.path.getsize(path_noext + '.' + e) / 1048576:.1f} MB" for e in ("glb", "fbx")), flush=True)

# 1) individual clips
for i, a in enumerate(actions):
    A.animation_data.action = a; A.animation_data.action_slot = a.slots[0]; sc.frame_start, sc.frame_end = int(round(a.frame_range[0])), int(round(a.frame_range[1])); export(os.path.join(out_dir, a.name), a.name)

# 2) the joined clip
data = [sample(a) for a in actions]; keys = list(data[0][0].keys()); N = max(2, int(round(blend_s * FPS)))
for ch, n in data[1:]:
    assert set(ch.keys()) == set(keys), "the clips do not share one skeleton (different animated channels)"
total = sum(n for _, n in data); joined = {k: np.empty(total, np.float32) for k in keys}; off = 0; seams = []
quat_groups = {}
for (dp, idx) in keys:
    if dp.endswith("rotation_quaternion"): quat_groups.setdefault(dp, {})[idx] = (dp, idx)
for p, (ch, n) in enumerate(data):
    for k in keys: joined[k][off:off + n] = ch[k]
    if p > 0:      # blend the first N frames of this clip from the previous clip's last pose to its own
        prev_end = {k: joined[k][off - 1] for k in keys}; w = np.array([(lambda t: t * t * (3 - 2 * t))((j + 1) / (N + 1)) for j in range(N)], np.float32)
        worst = 0.0
        for dp, ids in quat_groups.items():
            own = np.stack([joined[ids[c]][off:off + N] for c in range(4)], 1); pe = np.array([prev_end[ids[c]] for c in range(4)], np.float32)
            if float(np.dot(pe, own[-1])) < 0: pe = -pe                         # the same rotation: take the short way round
            b = (1 - w)[:, None] * pe[None, :] + w[:, None] * own; b /= np.maximum(np.linalg.norm(b, axis=1, keepdims=True), 1e-9)
            for c in range(4): joined[ids[c]][off:off + N] = b[:, c]
            worst = max(worst, float(2 * math.degrees(math.acos(min(1.0, abs(float(np.dot(pe, own[0]))))))))
        for (dp, idx) in keys:
            if not dp.endswith("rotation_quaternion"):
                joined[(dp, idx)][off:off + N] = (1 - w) * prev_end[(dp, idx)] + w * joined[(dp, idx)][off:off + N]
        seams.append((off, worst))
    off += n
for s_, worst in seams: print(f"[join] seam at frame {s_ + 1}: largest joint jump before blending {worst:.1f} degrees, blended over {N} frames", flush=True)
bpy.context.preferences.edit.keyframe_new_interpolation_type = "LINEAR"      # new keyframes are linear (dense per-frame keys: no handles to overshoot)
J = bpy.data.actions.new(f"{name}_Joined"); J.use_fake_user = True; frames = np.arange(1, total + 1, dtype=np.float32)
slot = J.slots.new(id_type="OBJECT", name=A.name); cb = J.layers.new("Layer").strips.new(type="KEYFRAME").channelbag(slot, ensure=True)
for (dp, idx), vals in joined.items():
    fc = cb.fcurves.new(dp, index=idx); fc.keyframe_points.add(total); co = np.empty(total * 2, np.float32); co[0::2] = frames; co[1::2] = vals
    fc.keyframe_points.foreach_set("co", co); fc.update()
A.animation_data.action = J; A.animation_data.action_slot = slot; sc.frame_start, sc.frame_end = 1, total
print(f"[join] joined action: {total} frames = {total / FPS:.2f} s", flush=True)
export(os.path.join(out_dir, f"{name}_Joined"), f"{name}_Joined")
