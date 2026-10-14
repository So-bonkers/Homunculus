"""Hand-pose layer, Blender side: set the finger bones of an animated clip to hand poses (fist, open, grip, claw, snap ...), every frame, and write GLB + FBX back.
blender -b --python blender_handpose.py -- clip.glb spec.json
spec, one pose for the whole clip:  {"left": "fist", "right": "relaxed", "lib": {pose: {...}}, "ramp": 6}
spec, a timeline per hand:          {"tracks": {"left": [[0, "open"], [1.6, "fist"], [3.0, "point", {"curve": "snap"}]], "right": [...]}, "ease": 0.13, "lib": {...}, "ramp": 6}
  A track is [[seconds, pose], ...] or [seconds, pose, {"curve": ..., "d": seconds}], from the start of the clip (seconds, not frames: Blender reads a 30 fps clip at its own 24 fps).
  The first pose holds from the start, every later one is reached at its time; the change is eased over d seconds centred on that time and held until the next. A change after a short
  pose is shortened to 60 % of the gap so a quick accent still arrives. curve: smooth (default, minimum jerk, d 0.13 s) | quick (fast start, soft landing, 0.07 s) | snap (fast and a little
  overshoot, 0.05 s) | linear (0.13 s) | hold (a cut).
A library pose: {"index": [base, middle, tip], ..., "thumb": [...], "thumb_out": degrees (the thumb turns sideways), "splay": {finger: degrees away from the middle finger}}.
Each finger joint curls toward the palm. The curl axis comes from the skeleton itself: bone direction x palm-normal (the palm normal of each hand is worked out from its own bones, so any rest pose works), converted to the bone's own
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


def wrist_at(wlib, track, f, ease=0.13):
    """The wrist of one hand at time f (seconds): {"flex": degrees, "dev": degrees}; keys as for the fingers ([seconds, name] or [seconds, name, {"curve", "d"}])."""
    ks = sorted(track, key=lambda k: k[0]); cur = dict(wlib[ks[0][1]])
    for i in range(1, len(ks)):
        k = ks[i]; opt = k[2] if len(k) > 2 and isinstance(k[2], dict) else {}; d0, fn = CURVES.get(opt.get("curve", "smooth"), CURVES["smooth"])
        d = float(opt["d"]) if opt.get("d") else (ease if opt.get("curve", "smooth") == "smooth" else d0)
        d = max(1e-3, min(d, 0.6 * (k[0] - ks[i - 1][0]) if k[0] > ks[i - 1][0] else d)); u = (f - (k[0] - d / 2)) / d
        if u <= 0: break
        t = fn(min(1.0, u)); nxt = wlib[k[1]]; cur = {a: cur[a] + (nxt[a] - cur[a]) * t for a in ("flex", "dev")}
    return cur


def palm_at(track, f, ease=0.13):
    """(from, to, u): the direction codes of the palm track around time f (seconds) and how far the change has come (0-1, eased). Codes are None for "as the clip"."""
    ks = sorted(track, key=lambda k: k[0]); prev = nxt = ks[0][1]; u = 1.0
    for i in range(1, len(ks)):
        k = ks[i]; opt = k[2] if len(k) > 2 and isinstance(k[2], dict) else {}; d0, fn = CURVES.get(opt.get("curve", "smooth"), CURVES["smooth"])
        d = float(opt["d"]) if opt.get("d") else (ease if opt.get("curve", "smooth") == "smooth" else d0)
        d = max(1e-3, min(d, 0.6 * (k[0] - ks[i - 1][0]) if k[0] > ks[i - 1][0] else d)); x = (f - (k[0] - d / 2)) / d
        if x <= 0: break
        prev, nxt, u = ks[i - 1][1], k[1], fn(min(1.0, x))
    return prev, nxt, u


class Fingers:
    """The finger bones of an armature and how each one curls (and spreads) in its own space."""
    def __init__(self, arm, lib):
        from mathutils import Vector, Quaternion
        self.Q, self.arm, self.lib = Quaternion, arm, lib; rx = re.compile(r"^(?:.*:)?(Left|Right)Hand(Thumb|Index|Middle|Ring|Pinky)([1-4])$"); chains = {}
        for b in arm.data.bones:
            m = rx.match(b.name)
            if m: chains.setdefault((m.group(1), m.group(2).lower()), {})[int(m.group(3))] = b
        if not chains: raise RuntimeError("no finger bones found (names)")
        bone = {b.name.split(":")[-1]: b for b in arm.data.bones}; self._hand_frame = {}
        def palm_of(side):
            """The palm normal of a hand in the rest pose, in armature space, from the rig's own bones: the hand axis (wrist to the middle knuckle) x the way the thumb side lies (pinky knuckle to
            index knuckle), mirrored for the right hand. Rigs differ: a Mixamo T-pose has the palms down, a Make-It-Animatable one often forward with the thumbs up."""
            try:
                w, m1, i1, p1 = (bone[f"{side}Hand{n}"].head_local if n else bone[f"{side}Hand"].head_local for n in ("", "Middle1", "Index1", "Pinky1"))
            except KeyError: return None
            ax = (m1 - w).normalized(); ts = (i1 - p1); ts -= ax * ts.dot(ax)
            if ts.length < 1e-6 or ax.length < 1e-6: return None
            ts = ts.normalized(); n = ax.cross(ts).normalized(); n = n if side == "Left" else -n; self._hand_frame[side] = (ax, ts); return n
        fallback = (arm.matrix_world.to_3x3().inverted() @ Vector((0, 0, -1))).normalized()          # palms down, if the hand bones cannot say
        self.palm = {side: palm_of(side) or fallback for side in ("Left", "Right")}
        def local_axis(b, world_axis): return (b.matrix_local.to_3x3().normalized().inverted() @ world_axis).normalized()
        # the wrist: the hand bone turns about two axes of its own hand: flexion about (hand axis x palm normal) (positive: toward the palm), deviation about the palm normal (positive: toward the thumb)
        self.wrist = {}
        for side in ("Left", "Right"):
            hb = bone.get(f"{side}Hand")
            if hb is None or side not in self._hand_frame: continue
            ax, ts = self._hand_frame[side]; n = self.palm[side]; fa = ax.cross(n).normalized(); best = None
            for sgn in (1, -1):
                sc = (self.Q(n, math.radians(sgn * 10)) @ ax).dot(ts)
                if best is None or sc > best[0]: best = (sc, sgn)
            self.wrist[side] = (hb.name, local_axis(hb, fa), local_axis(hb, n), best[1])
        # the forearm roll: the forearm bone turns about its own length; the palm's normal is followed in the hand bone's frame, and the torso gives "forward"
        self.roll = {}
        for side in ("Left", "Right"):
            fb, hb = bone.get(f"{side}ForeArm"), bone.get(f"{side}Hand")
            if fb is None or hb is None: continue
            self.roll[side] = (fb.name, hb.name, local_axis(fb, (fb.tail_local - fb.head_local).normalized()), (hb.matrix_local.to_3x3().inverted() @ self.palm[side]).normalized())
        self.up = (arm.matrix_world.to_3x3().inverted() @ Vector((0, 0, 1))).normalized()
        ll, rl = bone.get("LeftUpLeg"), bone.get("RightUpLeg"); self.chest = next((bone[n] for n in ("Spine2", "Spine1", "Spine") if n in bone), None)
        self.fwd_rest = (ll.head_local - rl.head_local).normalized().cross(self.up).normalized() if ll is not None and rl is not None else None      # left x up: the way the character faces
        self.bones = {}
        for (side, finger), ch in chains.items():
            down = self.palm[side]
            dirs = {j: ((ch[j + 1].head_local - ch[j].head_local) if ch.get(j + 1) else (ch[j].tail_local - ch[j].head_local)).normalized() for j in (1, 2, 3) if ch.get(j) is not None}
            # "straight" is not the rest pose: a rig's hand rests slightly curled (Make-It-Animatable's about 35 degrees). The bend of each joint at rest, measured in the plane of the hand's axis and its palm
            # normal, becomes the zero of the curl, so a library curl of 0 is a straight finger on any rig.
            w, m1 = bone.get(f"{side}Hand"), bone.get(f"{side}HandMiddle1"); off = {}
            if w is not None and m1 is not None and finger != "thumb":
                a = (m1.head_local - w.head_local).normalized(); a = (a - down * a.dot(down)).normalized(); phi = {j: math.atan2(d.dot(down), d.dot(a)) for j, d in dirs.items()}
                prev = 0.0
                for j in (1, 2, 3):
                    if j in phi: off[j] = -math.degrees(phi[j] - prev); prev = phi[j]
            for j in (1, 2, 3):
                b = ch.get(j)
                if b is None: continue
                nxt = ch.get(j + 1); d = dirs[j]; axis = d.cross(down)
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
                self.bones[b.name] = (side, finger, j, local_axis(b, axis.normalized()), out, abd, off.get(j, 0.0))

    def quat(self, name, ang):
        side, finger, j, ax, out, abd, off = self.bones[name]; q = self.Q(ax, math.radians(ang[finger][j - 1] + off))
        if out and ang["thumb_out"]: q = self.Q(out[0], math.radians(out[1] * ang["thumb_out"])) @ q
        if abd and ang["splay"].get(finger): q = self.Q(abd[0], math.radians(abd[1] * ang["splay"][finger])) @ q
        return q

    def direction(self, code, side):
        """A palm direction code (down, up, forward, back, in, out) as a vector in armature space for this pose (forward and the sides follow the torso's heading)."""
        if code in ("down", "up"): return -self.up if code == "down" else self.up
        if self.chest is None or self.fwd_rest is None: return None
        pb = self.arm.pose.bones[self.chest.name]; R = pb.matrix.to_3x3() @ self.chest.matrix_local.to_3x3().inverted(); fw = R @ self.fwd_rest
        fw = (fw - self.up * fw.dot(self.up)); 
        if fw.length < 1e-6: return None
        fw.normalize(); left = self.up.cross(fw).normalized()                                       # the character's left, in armature space
        inward = -left if side == "Left" else left
        return {"forward": fw, "back": -fw, "in": inward, "out": -inward}.get(code)

    def roll_angle(self, side, target):
        """Degrees to roll the forearm about its length so the palm faces `target` (armature space), from the pose as it is now (None if the forearm points along the target)."""
        fname, hname, ax_local, n_loc = self.roll[side]; pf, ph = self.arm.pose.bones[fname], self.arm.pose.bones[hname]
        f = (ph.head - pf.head).normalized(); n = (ph.matrix.to_3x3() @ n_loc).normalized()
        n = n - f * n.dot(f); t = target - f * target.dot(f)
        if n.length < 1e-6 or t.length < 1e-3: return None
        n.normalize(); t.normalize(); return math.degrees(math.atan2(f.dot(n.cross(t)), n.dot(t)))

    def wrist_quat(self, side, ang):
        """The extra rotation of the hand bone for {"flex": degrees, "dev": degrees}: the bone's own frame, to be multiplied after the clip's rotation (q_clip @ q)."""
        name, fax, dax, sgn = self.wrist[side]; return self.Q(dax, math.radians(sgn * ang["dev"])) @ self.Q(fax, math.radians(ang["flex"]))

    def set_wrist_static(self, left, right, wlib):
        """Pose the wrists of a rig without a clip (library pictures): left / right are wrist library names."""
        for side, nm in (("Left", left), ("Right", right)):
            if side in self.wrist:
                pb = self.arm.pose.bones[self.wrist[side][0]]; pb.rotation_mode = "QUATERNION"; pb.rotation_quaternion = self.wrist_quat(side, wlib[nm])

    def set_static(self, left, right):
        """Pose the fingers of a rig without a clip (library pictures): left / right are library pose names."""
        ang = {"Left": angles(self.lib, left), "Right": angles(self.lib, right)}
        for name, (side, *_r) in self.bones.items():
            pb = self.arm.pose.bones[name]; pb.rotation_mode = "QUATERNION"; pb.rotation_quaternion = self.quat(name, ang[side])


def main():
    import bpy
    glb, spec_p = sys.argv[sys.argv.index("--") + 1:][:2]; spec = json.load(open(spec_p)); lib = spec["lib"]; ramp = int(spec.get("ramp", 6)); ease = max(1e-3, float(spec.get("ease", 0.13)))
    tracks = spec.get("tracks") or {"left": [[0, spec["left"]]], "right": [[0, spec["right"]]]}        # one pose for the whole clip is a track with one key
    wtracks = {s: t for s, t in (spec.get("wrist_tracks") or {}).items() if t}; wlib = spec.get("wrist_lib") or {}
    ptracks = {s: t for s, t in (spec.get("palm_tracks") or {}).items() if t}; plib = spec.get("palm_lib") or {}
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
        for side in ("Left", "Right"):                                                                # the palm direction: the forearm rolls (before the fingers and the wrist, which sit on top)
            tr = ptracks.get(side.lower())
            if tr and side in F.roll:
                a, b, u = palm_at(tr, (f - f0) / fps, ease); da, db = plib.get(a), plib.get(b)
                va, vb = (F.direction(da, side) if da else None), (F.direction(db, side) if db else None); w = 1.0
                if va is None and vb is None: continue
                if va is None: tgt, w = vb, u
                elif vb is None: tgt, w = va, 1.0 - u
                else: tgt = (va * (1 - u) + vb * u)
                th = F.roll_angle(side, tgt) if tgt is not None and tgt.length > 1e-6 else None
                if th is not None and abs(w) > 1e-3:
                    pb = arm.pose.bones[F.roll[side][0]]; pb.rotation_mode = "QUATERNION"; pb.rotation_quaternion = pb.rotation_quaternion @ F.Q(F.roll[side][2], math.radians(th * w))
                    pb.keyframe_insert("rotation_quaternion", frame=f)
        bpy.context.view_layer.update()
        ts = (f - f0) / fps; ang = {s: angles_at(lib, tracks[s.lower()], ts, ease) for s in ("Left", "Right") if tracks.get(s.lower())}      # track times count from the first frame of the clip; a hand with no track keeps the clip's own fingers
        for name, (side, *_r) in F.bones.items():
            if side not in ang: continue
            q = F.quat(name, ang[side]); pb = arm.pose.bones[name]; pb.rotation_mode = "QUATERNION"
            cur = pb.rotation_quaternion.copy(); pb.rotation_quaternion = cur.slerp(q, t) if ramp else q
            pb.keyframe_insert("rotation_quaternion", frame=f)
        for side in ("Left", "Right"):                                                                # the wrist: an extra bend of the hand bone on top of the clip's own rotation
            tr = wtracks.get(side.lower())
            if tr and side in F.wrist:
                pb = arm.pose.bones[F.wrist[side][0]]; pb.rotation_mode = "QUATERNION"; pb.rotation_quaternion = pb.rotation_quaternion @ F.wrist_quat(side, wrist_at(wlib, tr, ts, ease))
                pb.keyframe_insert("rotation_quaternion", frame=f)
    fbx = glb[:-4] + ".fbx"
    bpy.ops.export_scene.gltf(filepath=glb, export_format="GLB", export_animations=True)
    if spec.get("fbx", True): bpy.ops.export_scene.fbx(filepath=fbx, add_leaf_bones=False, bake_anim=True, path_mode="COPY", embed_textures=True)
    print(f"[handpose] {fps:g} fps in Blender; " + " / ".join(f"{h}: {len(tracks.get(h) or [])} pose(s)" for h in ("left", "right")) + f": {len(F.bones)} finger bones over {f1 - f0 + 1} frames" + (f"; wrists: {', '.join(wtracks)}" if wtracks else "") + (f"; palm direction: {', '.join(ptracks)}" if ptracks else ""))


if __name__ == "__main__":
    main()
