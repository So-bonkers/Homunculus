"""Hand-pose layer, Blender side: set the finger bones of an animated clip to hand poses (fist, open, grip ...), every frame, and write GLB + FBX back.
blender -b --python blender_handpose.py -- clip.glb spec.json
spec, one pose for the whole clip:  {"left": "fist", "right": "relaxed", "lib": {pose: {finger: [base, middle, tip] degrees, ...}}, "ramp": 6}
spec, a timeline per hand:          {"tracks": {"left": [[0, "open"], [1.6, "fist"], [3.0, "point"]], "right": [...]}, "ease": 0.13, "lib": {...}, "ramp": 6}
  A track is [[seconds, pose], ...] from the start of the clip (seconds, not frames: Blender reads a 30 fps clip at its own 24 fps): the first pose holds from the start, every later one is
  reached at its time (the change is eased over `ease` seconds centred on it, so it does not snap), and held until the next. Poses with thumb_out (thumbs up) ease their thumb too.
Each finger joint curls toward the palm. The curl axis comes from the skeleton itself: bone direction x palm-normal (the rest pose has palms down), converted to the bone's own
local space, so it works for any rig with Mixamo-style finger names (Left/Right Hand Thumb/Index/Middle/Ring/Pinky 1-4). The first `ramp` frames ease in from the clip's own fingers."""
import bpy, sys, re, json, math
from mathutils import Vector, Quaternion

glb, spec_p = sys.argv[sys.argv.index("--") + 1:][:2]; spec = json.load(open(spec_p)); LIB = spec["lib"]; ramp = int(spec.get("ramp", 6)); EASE = max(1e-3, float(spec.get("ease", 0.13)))
TRACKS = spec.get("tracks") or {"left": [[0, spec["left"]]], "right": [[0, spec["right"]]]}          # one pose for the whole clip is a track with one key
bpy.ops.wm.read_factory_settings(use_empty=True); bpy.ops.import_scene.gltf(filepath=glb)
arm = next((o for o in bpy.data.objects if o.type == "ARMATURE"), None)
if arm is None: print("[handpose] no armature"); sys.exit(2)
RX = re.compile(r"^(?:.*:)?(Left|Right)Hand(Thumb|Index|Middle|Ring|Pinky)([1-4])$"); chains = {}
for b in arm.data.bones:
    m = RX.match(b.name)
    if m: chains.setdefault((m.group(1), m.group(2).lower()), {})[int(m.group(3))] = b
if not chains: print("[handpose] no finger bones found (names)"); sys.exit(2)
down = (arm.matrix_world.to_3x3().inverted() @ Vector((0, 0, -1))).normalized()                # palms down in the rest pose, in armature space
FINGERS = ("thumb", "index", "middle", "ring", "pinky")


def local_axis(b, nxt, world_axis):
    M = b.matrix_local.to_3x3().normalized(); return (M.inverted() @ world_axis).normalized()


def angles(pose):
    """{finger: (base, middle, tip), "thumb_out": degrees} of a library pose."""
    P = LIB[pose]; return {**{f: tuple(P[f]) for f in FINGERS}, "thumb_out": float(P.get("thumb_out", 0))}


def blend(a, b, t):
    return {**{f: tuple(x + (y - x) * t for x, y in zip(a[f], b[f])) for f in FINGERS}, "thumb_out": a["thumb_out"] + (b["thumb_out"] - a["thumb_out"]) * t}


def angles_at(track, f):
    """The finger angles of one hand at time f (seconds): the first pose holds from the start; each later key eases in over EASE seconds centred on its time."""
    ks = sorted(track, key=lambda k: k[0]); cur = angles(ks[0][1])
    for k, pose in ks[1:]:
        t = (f - (k - EASE / 2)) / EASE
        if t <= 0: break
        t = min(1.0, t); t = t * t * (3 - 2 * t); cur = blend(cur, angles(pose), t)
    return cur


# per finger bone: the curl axis in its own space (and, for the first thumb joint, the sideways axis and which way is away from the index finger)
bones = {}
for (side, finger), ch in chains.items():
    for j in (1, 2, 3):
        b = ch.get(j)
        if b is None: continue
        nxt = ch.get(j + 1); d = ((nxt.head_local - b.head_local) if nxt else (b.tail_local - b.head_local)).normalized()
        axis = d.cross(down)
        if axis.length < 1e-6: continue
        out = None
        if finger == "thumb" and j == 1:                                                         # thumbs up: the thumb sticks out sideways, away from the index finger
            idx = chains.get((side, "index"), {}).get(1); best = None
            for sgn in (1, -1):
                dd = Quaternion(down, math.radians(sgn * 60)) @ d; score = dd.dot((idx.tail_local - idx.head_local).normalized()) if idx else 0
                if best is None or score < best[0]: best = (score, sgn)
            out = (local_axis(b, nxt, down), best[1])
        bones[b.name] = (side, finger, j, local_axis(b, nxt, axis.normalized()), out)


def pose_quat(name, ang):
    side, finger, j, ax, out = bones[name]; q = Quaternion(ax, math.radians(ang[finger][j - 1]))
    if out and ang["thumb_out"]: q = Quaternion(out[0], math.radians(out[1] * ang["thumb_out"])) @ q
    return q


FPS = bpy.context.scene.render.fps / bpy.context.scene.render.fps_base
acts = list(bpy.data.actions); f0 = int(min(a.frame_range[0] for a in acts)) if acts else 1; f1 = int(max(a.frame_range[1] for a in acts)) if acts else 1
bpy.context.view_layer.objects.active = arm
for f in range(f0, f1 + 1):
    bpy.context.scene.frame_set(f); t = min(1.0, (f - f0 + 1) / max(1, ramp)); t = t * t * (3 - 2 * t)
    ts = (f - f0) / FPS; ang = {"Left": angles_at(TRACKS["left"], ts), "Right": angles_at(TRACKS["right"], ts)}      # track times count from the first frame of the clip
    for name, (side, *_rest) in bones.items():
        q = pose_quat(name, ang[side]); pb = arm.pose.bones[name]; pb.rotation_mode = "QUATERNION"
        cur = pb.rotation_quaternion.copy(); pb.rotation_quaternion = cur.slerp(q, t) if ramp else q
        pb.keyframe_insert("rotation_quaternion", frame=f)
fbx = glb[:-4] + ".fbx"
bpy.ops.export_scene.gltf(filepath=glb, export_format="GLB", export_animations=True)
if spec.get("fbx", True): bpy.ops.export_scene.fbx(filepath=fbx, add_leaf_bones=False, bake_anim=True, path_mode="COPY", embed_textures=True)
print(f"[handpose] {FPS:g} fps in Blender; " + " / ".join(f"{h}: {len(TRACKS[h])} pose(s)" for h in ("left", "right")) + f": {len(bones)} finger bones over {f1 - f0 + 1} frames")
