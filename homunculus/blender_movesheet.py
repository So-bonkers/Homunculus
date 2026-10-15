"""Pictures of the hand moves: each move of static/hands/moves.json played on a rig's left hand, eight moments from the first key to just after the last, each from the side and from above.
blender -b --python blender_movesheet.py -- rig.glb|rig.fbx spec.json out_dir      spec.json: {"lib", "wrist_lib", "palm_lib", "moves": [...]}; writes out_dir/<key>_<i>_side.png, _top.png and out_dir/times.json ({key: [seconds from the hit, ...]}).
The moments are evaluated with the same curve code that bakes a timeline into a clip (blender_handpose.py), so what is drawn is what the clip gets."""
import bpy, sys, os, json, math
from mathutils import Vector
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import blender_handpose as H

glb, spec_p, out = sys.argv[sys.argv.index("--") + 1:][:3]; spec = json.load(open(spec_p)); lib, wlib, plib = spec["lib"], spec["wrist_lib"], spec["palm_lib"]; os.makedirs(out, exist_ok=True)
bpy.ops.wm.read_factory_settings(use_empty=True)
if glb.lower().endswith(".fbx"): bpy.ops.import_scene.fbx(filepath=glb)
else: bpy.ops.import_scene.gltf(filepath=glb)
arm = next(o for o in bpy.data.objects if o.type == "ARMATURE"); arm.animation_data_clear()
for a in list(bpy.data.actions): bpy.data.actions.remove(a)
F = H.Fingers(arm, lib); sc = bpy.context.scene
sc.render.engine = "BLENDER_WORKBENCH"; sc.display.shading.light = "STUDIO"; sc.display.shading.color_type = "TEXTURE"; sc.render.resolution_x = sc.render.resolution_y = 320
w = bpy.data.worlds.new("w"); w.color = (0.62, 0.62, 0.65); sc.world = w
cam = bpy.data.objects.new("c", bpy.data.cameras.new("c")); sc.collection.objects.link(cam); sc.camera = cam; cam.data.lens = 70
hand = next(b for b in arm.pose.bones if b.name.endswith("LeftHand")); tip = next(b for b in arm.pose.bones if b.name.endswith("LeftHandMiddle3"))
mw = arm.matrix_world; rest_head = mw @ hand.head; axis = (mw @ tip.tail - rest_head); hl = axis.length; axis.normalize()
side = axis.cross(Vector((0, 0, 1))).normalized()
if side.y > 0: side = -side
cam.data.clip_start = hl * 0.1; cam.data.clip_end = hl * 100
i1 = next(b for b in arm.pose.bones if b.name.endswith("LeftHandIndex1")); p1 = next(b for b in arm.pose.bones if b.name.endswith("LeftHandPinky1"))
knuckles = (mw @ i1.head + mw @ p1.head) / 2 - rest_head; across = knuckles - axis * knuckles.dot(axis)           # the middle of the hand's width, as an offset from the wrist line (as in blender_handlib.py)
centre = rest_head + axis * (hl * 0.5) + across; N = 8
for m in spec["moves"]:
    lanes = m["lanes"]; ts = [k["dt"] for ks in lanes.values() for k in ks]; t0 = min(ts) - 0.1; t1 = max(ts) + 0.12
    tr = {ln: [[round(k["dt"] - t0, 4), k["pose"], {x: k[x] for x in ("curve", "d") if k.get(x) is not None}] for k in sorted(ks, key=lambda k: k["dt"])] for ln, ks in lanes.items()}
    if "fingers" not in tr: tr["fingers"] = [[0, "relaxed"]]
    if "wrist" not in tr: tr["wrist"] = [[0, "neutral"]]
    times = [round(t0 + 0.1 - 0.03 + (t1 - (t0 + 0.1) + 0.03) * i / (N - 1), 3) for i in range(N)]          # from just before the first key to just after the last
    for i, tt in enumerate(times):
        t = tt - t0
        pb_roll = None
        for sd in ("Left",):
            if sd in F.roll:                      # the palm direction: roll the forearm (reset first: every picture starts from the rest pose)
                pb = arm.pose.bones[F.roll[sd][0]]; pb.rotation_mode = "QUATERNION"; pb.rotation_quaternion = (1, 0, 0, 0)
        bpy.context.view_layer.update()
        if "palm" in tr and "Left" in F.roll:
            a, b, u = H.palm_at(tr["palm"], t); da, db = plib.get(a), plib.get(b); va = F.direction(da, "Left") if da else None; vb = F.direction(db, "Left") if db else None; wgt = 1.0
            if va is None and vb is None: tgt = None
            elif va is None: tgt, wgt = vb, u
            elif vb is None: tgt, wgt = va, 1.0 - u
            else: tgt = va * (1 - u) + vb * u
            th = F.roll_angle("Left", tgt) if tgt is not None and tgt.length > 1e-6 else None
            if th is not None:
                pb = arm.pose.bones[F.roll["Left"][0]]; pb.rotation_mode = "QUATERNION"; pb.rotation_quaternion = pb.rotation_quaternion @ F.Q(F.roll["Left"][2], math.radians(th * wgt))
        bpy.context.view_layer.update()
        ang = H.angles_at(lib, tr["fingers"], t)
        for name, (sd, *_r) in F.bones.items():
            if sd != "Left": continue
            pb = arm.pose.bones[name]; pb.rotation_mode = "QUATERNION"; pb.rotation_quaternion = F.quat(name, ang)
        if "Left" in F.wrist:
            pb = arm.pose.bones[F.wrist["Left"][0]]; pb.rotation_mode = "QUATERNION"; pb.rotation_quaternion = F.wrist_quat("Left", H.wrist_at(wlib, tr["wrist"], t))
        bpy.context.view_layer.update()
        for view, off in (("side", side * hl * 3.0), ("top", Vector((0, 0, 1)) * hl * 3.0)):
            cam.location = centre + off; cam.rotation_euler = (centre - cam.location).to_track_quat("-Z", "Y").to_euler()
            sc.render.filepath = os.path.join(out, f"{m['key']}_{i}_{view}.png"); bpy.ops.render.render(write_still=True)
    json.dump({**(json.load(open(os.path.join(out, "times.json"))) if os.path.exists(os.path.join(out, "times.json")) else {}), m["key"]: times}, open(os.path.join(out, "times.json"), "w"))
print(f"[movesheet] {len(spec['moves'])} moves")
