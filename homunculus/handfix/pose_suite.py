"""Blender: render a rig-test suite for a rigged FBX.
poses: rest | walk (stride, arm swing, head turn) | wave (arm up beside the head, open hand) | fist (both hands closed)
views: full-body front + three-quarter, hand close-ups from back-of-hand and side."""
import bpy, sys, math, os
from mathutils import Vector
fbx, out = sys.argv[sys.argv.index("--") + 1:][:2]
bpy.ops.wm.read_factory_settings(use_empty=True); bpy.ops.import_scene.fbx(filepath=fbx)
arm = [o for o in bpy.data.objects if o.type == "ARMATURE"][0]; meshes = [o for o in bpy.data.objects if o.type == "MESH"]
if arm.animation_data: arm.animation_data_clear()      # imported animations (e.g. from Mixamo) would override the test poses
sc = bpy.context.scene; sc.render.engine = "BLENDER_WORKBENCH"; sc.display.shading.light = "STUDIO"; sc.display.shading.color_type = "TEXTURE"
wd = bpy.data.worlds.new("w"); sc.world = wd; wd.color = (0.82, 0.82, 0.84)
cam = bpy.data.objects.new("c", bpy.data.cameras.new("c")); sc.collection.objects.link(cam); sc.camera = cam; cam.data.type = "ORTHO"; cam.data.clip_end = 1000
def pb(n): return arm.pose.bones.get("mixamorig:" + n) or arm.pose.bones.get(n)
def reset():
    for p in arm.pose.bones: p.rotation_mode = "XYZ"; p.rotation_euler = (0, 0, 0); p.rotation_quaternion = (1, 0, 0, 0)
def rot(n, x=0, y=0, z=0):
    p = pb(n)
    if p: p.rotation_mode = "XYZ"; p.rotation_euler = (math.radians(x), math.radians(y), math.radians(z))
def bbox():
    bpy.context.view_layer.update(); dg = bpy.context.evaluated_depsgraph_get(); pts = []
    for m in meshes:
        ev = m.evaluated_get(dg); mw = m.matrix_world
        pts += [mw @ v.co for v in list(ev.data.vertices)[::40]]
    lo = Vector((min(p.x for p in pts), min(p.y for p in pts), min(p.z for p in pts))); hi = Vector((max(p.x for p in pts), max(p.y for p in pts), max(p.z for p in pts)))
    return lo, hi
def shoot(name, center, scale, az_deg, w=700, h=900):
    sc.render.resolution_x, sc.render.resolution_y = w, h; cam.data.ortho_scale = scale
    a = math.radians(az_deg); d = Vector((math.sin(a), -math.cos(a), 0))
    dist = max(10.0, 4 * scale); cam.data.clip_end = dist * 4
    cam.location = Vector(center) + d * dist; cam.rotation_euler = (math.pi / 2, 0, a)
    sc.render.filepath = os.path.join(out, name + ".png"); bpy.ops.render.render(write_still=True)
def hand_world(side): bpy.context.view_layer.update(); return arm.matrix_world @ pb(side + "Hand").head
FING = ["Index", "Middle", "Ring", "Pinky"]
from mathutils import Quaternion
def _palm_normal(side):
    """Normal pointing out of the palm, from the rest positions of wrist, index and pinky knuckles."""
    A = arm.matrix_world; w = A @ arm.data.bones["mixamorig:" + side + "Hand"].head_local
    i = A @ arm.data.bones["mixamorig:" + side + "HandIndex1"].head_local; p = A @ arm.data.bones["mixamorig:" + side + "HandPinky1"].head_local
    n = (i - w).cross(p - w).normalized(); th = A @ arm.data.bones["mixamorig:" + side + "HandThumb2"].head_local
    mid = (i + p) / 2
    return n if n.dot(th - mid) > 0 else -n        # thumb sits on the palm side of the knuckle line in a relaxed hand
def _bend(name, axis_world, ang):
    """Rotate pose bone `name` by `ang` degrees about a world-space axis (rest-pose frame)."""
    p = pb(name)
    if p is None: return
    rest = (arm.matrix_world @ p.bone.matrix_local).to_3x3().normalized()
    ax_local = rest.inverted() @ axis_world
    p.rotation_mode = "QUATERNION"; p.rotation_quaternion = Quaternion(ax_local.normalized(), math.radians(ang))
def curl(side, amt):
    n = _palm_normal(side); A = arm.matrix_world
    for f in FING + ["Thumb"]:
        for k in (1, 2, 3):
            b = arm.data.bones.get(f"mixamorig:{side}Hand{f}{k}")
            if b is None: continue
            d = ((A @ b.tail_local) - (A @ b.head_local)).normalized()
            axis = d.cross(n).normalized()          # rotating about d x n swings the tip toward the palm side
            _bend(f"{side}Hand{f}{k}", axis, (amt * (0.5 if f == "Thumb" else 1.0)) * (1 if k > 1 or f != "Thumb" else 0.6))
def spread(side, amt):
    for i, f in enumerate(FING): rot(f"{side}Hand{f}1", z=(i - 1.5) * amt)
os.makedirs(out, exist_ok=True)
reset(); lo, hi = bbox(); c = (lo + hi) / 2; H = hi.z - lo.z
shoot("rest_front", c, H * 1.15, 0); shoot("rest_34", c, H * 1.15, 35)
# walk: stride + arm swing + head turn
reset(); rot("LeftUpLeg", x=-30); rot("LeftLeg", x=35); rot("RightUpLeg", x=20); rot("LeftArm", z=-55, x=25); rot("RightArm", z=55, x=-25)
rot("LeftForeArm", x=-25); rot("RightForeArm", x=-25); rot("Spine1", y=8); rot("Head", y=-15); curl("Left", 25); curl("Right", 25)
lo, hi = bbox(); c = (lo + hi) / 2; H = hi.z - lo.z; shoot("walk_front", c, H * 1.15, 0); shoot("walk_34", c, H * 1.15, 35); shoot("walk_side", c, H * 1.15, 90)
# wave: left arm up beside the head, open spread hand
reset(); rot("LeftArm", z=40, x=-20); rot("LeftForeArm", x=-70); spread("Left", 8)
lo, hi = bbox(); c = (lo + hi) / 2; H = hi.z - lo.z; shoot("wave_front", c, H * 1.15, 0)
import os
HANDS = not os.environ.get("HOMUNCULUS_NO_HANDS")      # the hand close-ups are skipped unless HAND_VIEWS is on
if HANDS: hw = hand_world("Left"); shoot("wave_hand", hw + Vector((0, 0, 0.08)), H * 0.18, 0, 700, 700)
# fist: both hands closed, arms forward
reset(); rot("LeftArm", z=-70); rot("RightArm", z=70); rot("LeftForeArm", x=-60); rot("RightForeArm", x=-60); curl("Left", 80); curl("Right", 80)
for side in (("Left", "Right") if HANDS else ()):
    hw = hand_world(side); lo, hi = bbox(); H = hi.z - lo.z
    shoot(f"fist_{side}_a", hw + Vector((0, 0, -0.05)), H * 0.16, 0, 700, 700); shoot(f"fist_{side}_b", hw + Vector((0, 0, -0.05)), H * 0.16, 90 if side == "Left" else -90, 700, 700)
print("[pose_suite] done")
