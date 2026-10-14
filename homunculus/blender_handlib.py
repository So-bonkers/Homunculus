"""Pictures of the hand library: every pose on a rig's left hand, from the side (the curl) and from above (the spread).
blender -b --python blender_handlib.py -- rig.glb|rig.fbx lib.json out_dir      (lib.json: {pose: entry}); writes out_dir/<pose>_side.png and <pose>_top.png"""
import bpy, sys, os, json
from mathutils import Vector
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import blender_handpose as H

glb, lib_p, out = sys.argv[sys.argv.index("--") + 1:][:3]; lib = json.load(open(lib_p)); os.makedirs(out, exist_ok=True)
bpy.ops.wm.read_factory_settings(use_empty=True)
if glb.lower().endswith(".fbx"): bpy.ops.import_scene.fbx(filepath=glb)
else: bpy.ops.import_scene.gltf(filepath=glb)
arm = next(o for o in bpy.data.objects if o.type == "ARMATURE"); arm.animation_data_clear()                       # a Mixamo FBX carries an animation that would overwrite the poses on every update
for a in list(bpy.data.actions): bpy.data.actions.remove(a)
F = H.Fingers(arm, lib); sc = bpy.context.scene
sc.render.engine = "BLENDER_WORKBENCH"; sc.display.shading.light = "STUDIO"; sc.display.shading.color_type = "TEXTURE"; sc.render.resolution_x = sc.render.resolution_y = 320
w = bpy.data.worlds.new("w"); w.color = (0.62, 0.62, 0.65); sc.world = w
cam = bpy.data.objects.new("c", bpy.data.cameras.new("c")); sc.collection.objects.link(cam); sc.camera = cam; cam.data.lens = 70
hand = next(b for b in arm.pose.bones if b.name.endswith("LeftHand")); tip = next(b for b in arm.pose.bones if b.name.endswith("LeftHandMiddle3"))
mw = arm.matrix_world; rest_head = mw @ hand.head; rest_tip = mw @ tip.tail; axis = (rest_tip - rest_head); hl = axis.length; axis.normalize()     # rest pose: the hand points along the arm
i1 = next(b for b in arm.pose.bones if b.name.endswith("LeftHandIndex1")); p1 = next(b for b in arm.pose.bones if b.name.endswith("LeftHandPinky1"))
knuckles = (mw @ i1.head + mw @ p1.head) / 2 - rest_head; across = knuckles - axis * knuckles.dot(axis)                      # the middle of the hand's width, as an offset from the wrist line
centre = rest_head + axis * (hl * 0.46) + across; side = axis.cross(Vector((0, 0, 1))).normalized()
if side.y > 0: side = -side                                                                  # the camera in front of the character (it faces -Y)
cam.data.clip_start = hl * 0.1; cam.data.clip_end = hl * 100
for name in lib:
    F.set_static(name, name); bpy.context.view_layer.update()
    for view, off in (("side", side * hl * 2.5), ("top", Vector((0, 0, 1)) * hl * 2.5)):
        cam.location = centre + off; cam.rotation_euler = (centre - cam.location).to_track_quat("-Z", "Y").to_euler()
        sc.render.filepath = os.path.join(out, f"{name}_{view}.png"); bpy.ops.render.render(write_still=True)
print(f"[handlib] {len(lib)} poses")
