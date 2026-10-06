"""Transparent frames of a GLB for the demo video (Blender, CPU workbench).
blender -b --python render_frames.py -- model.glb out_dir width height [clip|turn] [turn_frames]
clip: every frame of the animation, camera framed once on the whole motion.  turn: a 360 degree turntable of the static pose."""
import bpy, sys, math, os
from mathutils import Vector
a = sys.argv[sys.argv.index("--") + 1:]; src, out, W, H = a[0], a[1], int(a[2]), int(a[3]); mode = a[4] if len(a) > 4 else "clip"; nturn = int(a[5]) if len(a) > 5 else 90
bpy.ops.wm.read_factory_settings(use_empty=True); bpy.ops.import_scene.gltf(filepath=src)
sc = bpy.context.scene; acts = list(bpy.data.actions)
f0, f1 = (int(min(x.frame_range[0] for x in acts)), int(max(x.frame_range[1] for x in acts))) if acts and mode == "clip" else (1, 1)
meshes = [o for o in bpy.data.objects if o.type == "MESH" and len(o.data.vertices) > 500]      # skip tiny helper objects (markers, icospheres) that some exports carry
for o in bpy.data.objects:
    if o.type == "MESH" and o not in meshes: o.hide_render = True
def pts(f):
    sc.frame_set(f); dg = bpy.context.evaluated_depsgraph_get(); p = []
    for o in meshes:
        e = o.evaluated_get(dg); p += [e.matrix_world @ Vector(c) for c in e.bound_box]
    return p
per = {f: pts(f) for f in range(f0, f1 + 1, 3)}
allp = [q for v in per.values() for q in v]
zlo, zhi = min(p.z for p in allp), max(p.z for p in allp)
fw = max(max(p.x for p in v) - min(p.x for p in v) for v in per.values()); fd = max(max(p.y for p in v) - min(p.y for p in v) for v in per.values())
lo = Vector((min(p.x for p in allp), min(p.y for p in allp), zlo)); hi = Vector((max(p.x for p in allp), max(p.y for p in allp), zhi))
c = (lo + hi) / 2; height = zhi - zlo; width = max(fw, fd)      # framed on the character itself, not on how far the motion travels
def centre(f):
    v = pts(f); return Vector(((max(p.x for p in v) + min(p.x for p in v)) / 2, (max(p.y for p in v) + min(p.y for p in v)) / 2, c.z))
pivot = bpy.data.objects.new("pivot", None); sc.collection.objects.link(pivot); pivot.location = c
cam = bpy.data.objects.new("c", bpy.data.cameras.new("c")); sc.collection.objects.link(cam); cam.data.type = "ORTHO"
cam.data.ortho_scale = max(height * 1.08, width * 1.08 * H / W); cam.parent = pivot
d = Vector((0.45, -1, 0.12)).normalized() if mode == "clip" else Vector((0, -1, 0.08)).normalized()
cam.location = d * 20; cam.rotation_euler = (-d).to_track_quat("-Z", "Y").to_euler(); sc.camera = cam
r = sc.render; r.resolution_x, r.resolution_y = W, H; r.engine = "BLENDER_WORKBENCH"; r.film_transparent = True; r.image_settings.color_mode = "RGBA"
s = sc.display.shading; s.light = "STUDIO"; s.color_type = "TEXTURE"; s.show_shadows = False; s.show_cavity = False; s.studio_light = "studio.sl"
os.makedirs(out, exist_ok=True)
if mode == "clip":
    for i, f in enumerate(range(f0, f1 + 1)):
        sc.frame_set(f); pivot.location = centre(f); r.filepath = os.path.join(out, f"f{i:03d}.png"); bpy.ops.render.render(write_still=True)
else:
    sc.frame_set(1)
    for i in range(nturn):
        pivot.rotation_euler = (0, 0, 2 * math.pi * i / nturn); r.filepath = os.path.join(out, f"f{i:03d}.png"); bpy.ops.render.render(write_still=True)
