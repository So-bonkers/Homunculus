"""Hand-pose layer, Blender side: set the finger bones of an animated clip to a hand pose (fist, open, grip ...), every frame, and write GLB + FBX back.
blender -b --python blender_handpose.py -- clip.glb spec.json
spec: {"left": "fist", "right": "relaxed", "lib": {pose: {finger: [base, middle, tip] degrees, ...}}, "ramp": 6}
Each finger joint curls toward the palm. The curl axis comes from the skeleton itself: bone direction x palm-normal (the rest pose has palms down), converted to the bone's own
local space, so it works for any rig with Mixamo-style finger names (Left/Right Hand Thumb/Index/Middle/Ring/Pinky 1-4). The first `ramp` frames ease in from the clip's own fingers."""
import bpy, sys, re, json, math
from mathutils import Vector, Quaternion

glb, spec_p = sys.argv[sys.argv.index("--") + 1:][:2]; spec = json.load(open(spec_p)); LIB = spec["lib"]; ramp = int(spec.get("ramp", 6))
bpy.ops.wm.read_factory_settings(use_empty=True); bpy.ops.import_scene.gltf(filepath=glb)
arm = next((o for o in bpy.data.objects if o.type == "ARMATURE"), None)
if arm is None: print("[handpose] no armature"); sys.exit(2)
RX = re.compile(r"^(?:.*:)?(Left|Right)Hand(Thumb|Index|Middle|Ring|Pinky)([1-4])$"); chains = {}
for b in arm.data.bones:
    m = RX.match(b.name)
    if m: chains.setdefault((m.group(1), m.group(2).lower()), {})[int(m.group(3))] = b
if not chains: print("[handpose] no finger bones found (names)"); sys.exit(2)
down = (arm.matrix_world.to_3x3().inverted() @ Vector((0, 0, -1))).normalized()                # palms down in the rest pose, in armature space


def local_axis(b, nxt, world_axis):
    M = b.matrix_local.to_3x3().normalized(); return (M.inverted() @ world_axis).normalized()


plan = {}                                                                                       # bone name -> (axis in bone space, [(joint, side-pose-angle)]
for (side, finger), ch in chains.items():
    pose = spec["left" if side == "Left" else "right"]; ang = LIB[pose][finger]
    for j in (1, 2, 3):
        b = ch.get(j)
        if b is None: continue
        nxt = ch.get(j + 1); d = ((nxt.head_local - b.head_local) if nxt else (b.tail_local - b.head_local)).normalized()
        axis = d.cross(down)
        if axis.length < 1e-6: continue
        q = Quaternion(local_axis(b, nxt, axis.normalized()), math.radians(ang[j - 1]))
        if finger == "thumb" and j == 1 and LIB[pose].get("thumb_out"):                           # thumbs up: the thumb sticks out sideways, away from the index finger
            idx = chains.get((side, "index"), {}).get(1)
            best = None
            for sgn in (1, -1):
                rot = Quaternion(down, math.radians(sgn * LIB[pose]["thumb_out"])); dd = rot @ d
                score = dd.dot((idx.tail_local - idx.head_local).normalized()) if idx else 0
                if best is None or score < best[0]: best = (score, sgn)
            q = Quaternion(local_axis(b, nxt, down), math.radians(best[1] * LIB[pose]["thumb_out"])) @ q
        plan[b.name] = q

acts = list(bpy.data.actions); f0 = int(min(a.frame_range[0] for a in acts)) if acts else 1; f1 = int(max(a.frame_range[1] for a in acts)) if acts else 1
bpy.context.view_layer.objects.active = arm
for f in range(f0, f1 + 1):
    bpy.context.scene.frame_set(f); t = min(1.0, (f - f0 + 1) / max(1, ramp)); t = t * t * (3 - 2 * t)
    for name, q in plan.items():
        pb = arm.pose.bones[name]; pb.rotation_mode = "QUATERNION"
        cur = pb.rotation_quaternion.copy(); pb.rotation_quaternion = cur.slerp(q, t) if ramp else q
        pb.keyframe_insert("rotation_quaternion", frame=f)
fbx = glb[:-4] + ".fbx"
bpy.ops.export_scene.gltf(filepath=glb, export_format="GLB", export_animations=True)
bpy.ops.export_scene.fbx(filepath=fbx, add_leaf_bones=False, bake_anim=True, path_mode="COPY", embed_textures=True)
print(f"[handpose] {spec['left']} / {spec['right']}: {len(plan)} finger bones over {f1 - f0 + 1} frames")
