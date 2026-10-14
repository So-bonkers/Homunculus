"""Hand-pose layer, Blender side: set the finger bones of an animated clip to hand poses (fist, open, grip, claw, snap ...), every frame, and write GLB + FBX back.
blender -b --python blender_handpose.py -- clip.glb spec.json
spec, one pose for the whole clip:  {"left": "fist", "right": "relaxed", "lib": {pose: {...}}, "ramp": 6}
spec, a timeline per hand:          {"tracks": {"left": [[0, "open"], [1.6, "fist"], [3.0, "point", {"curve": "snap"}]], "right": [...]}, "ease": 0.13, "lib": {...}, "ramp": 6}
  A track is [[seconds, pose], ...] or [seconds, pose, {"curve": ..., "d": seconds}], from the start of the clip (seconds, not frames: Blender reads a 30 fps clip at its own 24 fps).
  The first pose holds from the start, every later one is reached at its time; the change is eased over d seconds centred on that time and held until the next. A change after a short
  pose is shortened to 60 % of the gap so a quick accent still arrives. curve: smooth (default, minimum jerk, d 0.13 s) | quick (fast start, soft landing, 0.07 s) | snap (fast and a little
  overshoot, 0.05 s) | linear (0.13 s) | hold (a cut).
A library pose: {"index": [base, middle, tip], ..., "thumb": [...], "thumb_out": degrees (the thumb turns sideways), "splay": {finger: degrees away from the middle finger}}.
Each finger joint curls toward the palm. The curl axis comes from the skeleton itself: bone direction x palm-normal (the rest pose has palms down), converted to the bone's own
local space, so it works for any rig with Mixamo-style finger names (Left/Right Hand Thumb/Index/Middle/Ring/Pinky 1-4). The first `ramp` frames ease in from the clip's own fingers.
Import it as a module (blender_handlib.py does) to set poses on a rig without a clip."""
import math, re, json, sys

FINGERS = ("thumb", "index", "middle", "ring", "pinky")
CURVES = {"smooth": (0.13, lambda u: u ** 3 * (10 - 15 * u + 6 * u * u)), "quick": (0.07, lambda u: 1 - (1 - u) ** 3), "linear": (0.13, lambda u: u),
          "snap": (0.05, lambda u: 1 + 2.70158 * (u - 1) ** 3 + 1.70158 * (u - 1) ** 2), "hold": (0.001, lambda u: 1.0 if u >= 0.5 else 0.0)}


def angles(lib, pose):
    """{finger: (base, middle, tip), "thumb_out": degrees, "splay": {finger: degrees}} of a library pose."""
    P = lib[pose]; return {**{f: tuple(P[f]) for f in FINGERS}, "thumb_out": float(P.get("thumb_out", 0)), "splay": {f: float(P.get("splay", {}).get(f, 0)) for f in FINGERS[1:]}}


def blend(a, b, t):
    """a + (b - a) * t for every number (t may pass 1: the overshoot of a snap); finger curls stay within a human range."""
    cl = lambda x: max(-25.0, min(112.0, x))
    return {**{f: tuple(cl(x + (y - x) * t) for x, y in zip(a[f], b[f])) for f in FINGERS}, "thumb_out": a["thumb_out"] + (b["thumb_out"] - a["thumb_out"]) * t,
            "splay": {f: a["splay"][f] + (b["splay"][f] - a["splay"][f]) * t for f in a["splay"]}}


def angles_at(lib, track, f, ease=0.13):
    """The finger angles of one hand at time f (seconds). Keys: [seconds, pose] or [seconds, pose, {"curve": name, "d": seconds}]."""
    ks = sorted(track, key=lambda k: k[0]); cur = angles(lib, ks[0][1])
    for i in range(1, len(ks)):
        k = ks[i]; opt = k[2] if len(k) > 2 and isinstance(k[2], dict) else {}; d0, fn = CURVES.get(opt.get("curve", "smooth"), CURVES["smooth"])
        d = float(opt["d"]) if opt.get("d") else (ease if opt.get("curve", "smooth") == "smooth" else d0)
        d = max(1e-3, min(d, 0.6 * (k[0] - ks[i - 1][0]) if k[0] > ks[i - 1][0] else d))          # a quick accent after a short pose still arrives
        u = (f - (k[0] - d / 2)) / d
        if u <= 0: break
        cur = blend(cur, angles(lib, k[1]), fn(min(1.0, u)))
    return cur


class Fingers:
    """The finger bones of an armature and how each one curls (and spreads) in its own space."""
    def __init__(self, arm, lib):
        from mathutils import Vector, Quaternion
        self.Q, self.arm, self.lib = Quaternion, arm, lib; rx = re.compile(r"^(?:.*:)?(Left|Right)Hand(Thumb|Index|Middle|Ring|Pinky)([1-4])$"); chains = {}
        for b in arm.data.bones:
            m = rx.match(b.name)
            if m: chains.setdefault((m.group(1), m.group(2).lower()), {})[int(m.group(3))] = b
        if not chains: raise RuntimeError("no finger bones found (names)")
        down = (arm.matrix_world.to_3x3().inverted() @ Vector((0, 0, -1))).normalized()               # palms down in the rest pose, in armature space
        def local_axis(b, world_axis): return (b.matrix_local.to_3x3().normalized().inverted() @ world_axis).normalized()
        self.bones = {}
        for (side, finger), ch in chains.items():
            for j in (1, 2, 3):
                b = ch.get(j)
                if b is None: continue
                nxt = ch.get(j + 1); d = ((nxt.head_local - b.head_local) if nxt else (b.tail_local - b.head_local)).normalized(); axis = d.cross(down)
                if axis.length < 1e-6: continue
                out = abd = None
                if finger == "thumb" and j == 1:                                                      # thumbs up: the thumb sticks out sideways, away from the index finger
                    idx = chains.get((side, "index"), {}).get(1); best = None
                    for sgn in (1, -1):
                        dd = self.Q(down, math.radians(sgn * 60)) @ d; score = dd.dot((idx.tail_local - idx.head_local).normalized()) if idx else 0
                        if best is None or score < best[0]: best = (score, sgn)
                    out = (local_axis(b, down), best[1])
                if finger not in ("thumb", "middle") and j == 1:                                      # spread: the knuckle turns about the palm normal, away from the middle finger
                    mid = chains.get((side, "middle"), {}).get(1)
                    if mid is not None:
                        lat = (b.head_local - mid.head_local).normalized(); best = None
                        for sgn in (1, -1):
                            sc = (self.Q(down, math.radians(sgn * 10)) @ d).dot(lat)
                            if best is None or sc > best[0]: best = (sc, sgn)
                        abd = (local_axis(b, down), best[1])
                self.bones[b.name] = (side, finger, j, local_axis(b, axis.normalized()), out, abd)

    def quat(self, name, ang):
        side, finger, j, ax, out, abd = self.bones[name]; q = self.Q(ax, math.radians(ang[finger][j - 1]))
        if out and ang["thumb_out"]: q = self.Q(out[0], math.radians(out[1] * ang["thumb_out"])) @ q
        if abd and ang["splay"].get(finger): q = self.Q(abd[0], math.radians(abd[1] * ang["splay"][finger])) @ q
        return q

    def set_static(self, left, right):
        """Pose the fingers of a rig without a clip (library pictures): left / right are library pose names."""
        ang = {"Left": angles(self.lib, left), "Right": angles(self.lib, right)}
        for name, (side, *_r) in self.bones.items():
            pb = self.arm.pose.bones[name]; pb.rotation_mode = "QUATERNION"; pb.rotation_quaternion = self.quat(name, ang[side])


def main():
    import bpy
    glb, spec_p = sys.argv[sys.argv.index("--") + 1:][:2]; spec = json.load(open(spec_p)); lib = spec["lib"]; ramp = int(spec.get("ramp", 6)); ease = max(1e-3, float(spec.get("ease", 0.13)))
    tracks = spec.get("tracks") or {"left": [[0, spec["left"]]], "right": [[0, spec["right"]]]}        # one pose for the whole clip is a track with one key
    bpy.ops.wm.read_factory_settings(use_empty=True); bpy.ops.import_scene.gltf(filepath=glb)
    arm = next((o for o in bpy.data.objects if o.type == "ARMATURE"), None)
    if arm is None: print("[handpose] no armature"); sys.exit(2)
    try: F = Fingers(arm, lib)
    except RuntimeError as e: print("[handpose]", e); sys.exit(2)
    fps = bpy.context.scene.render.fps / bpy.context.scene.render.fps_base
    acts = list(bpy.data.actions); f0 = int(min(a.frame_range[0] for a in acts)) if acts else 1; f1 = int(max(a.frame_range[1] for a in acts)) if acts else 1
    bpy.context.view_layer.objects.active = arm
    for f in range(f0, f1 + 1):
        bpy.context.scene.frame_set(f); t = min(1.0, (f - f0 + 1) / max(1, ramp)); t = t * t * (3 - 2 * t)
        ts = (f - f0) / fps; ang = {"Left": angles_at(lib, tracks["left"], ts, ease), "Right": angles_at(lib, tracks["right"], ts, ease)}      # track times count from the first frame of the clip
        for name, (side, *_r) in F.bones.items():
            q = F.quat(name, ang[side]); pb = arm.pose.bones[name]; pb.rotation_mode = "QUATERNION"
            cur = pb.rotation_quaternion.copy(); pb.rotation_quaternion = cur.slerp(q, t) if ramp else q
            pb.keyframe_insert("rotation_quaternion", frame=f)
    fbx = glb[:-4] + ".fbx"
    bpy.ops.export_scene.gltf(filepath=glb, export_format="GLB", export_animations=True)
    if spec.get("fbx", True): bpy.ops.export_scene.fbx(filepath=fbx, add_leaf_bones=False, bake_anim=True, path_mode="COPY", embed_textures=True)
    print(f"[handpose] {fps:g} fps in Blender; " + " / ".join(f"{h}: {len(tracks[h])} pose(s)" for h in ("left", "right")) + f": {len(F.bones)} finger bones over {f1 - f0 + 1} frames")


if __name__ == "__main__":
    main()
