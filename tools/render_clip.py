"""Render an animated GLB to PNG frames (Blender, CPU workbench): blender -b --python render_clip.py -- clip.glb out_dir [size] [step]
Camera is fixed on the first frame's bounds so the character moves through the shot instead of being re-centred."""
import bpy, sys, math, os
from mathutils import Vector
a = sys.argv[sys.argv.index("--") + 1:]; src, out = a[0], a[1]; size = int(a[2]) if len(a) > 2 else 420; step = int(a[3]) if len(a) > 3 else 1
bpy.ops.wm.read_factory_settings(use_empty=True); bpy.ops.import_scene.gltf(filepath=src)
sc = bpy.context.scene; acts = list(bpy.data.actions); f0, f1 = (int(min(x.frame_range[0] for x in acts)), int(max(x.frame_range[1] for x in acts))) if acts else (1, 1)
meshes = [o for o in bpy.data.objects if o.type == "MESH"]
def bounds(f):
    sc.frame_set(f); dg = bpy.context.evaluated_depsgraph_get(); pts = []
    for o in meshes:
        e = o.evaluated_get(dg); pts += [e.matrix_world @ Vector(c) for c in e.bound_box]
    return pts
allp = [p for f in range(f0, f1 + 1, 4) for p in bounds(f)]
lo = Vector((min(p.x for p in allp), min(p.y for p in allp), min(p.z for p in allp))); hi = Vector((max(p.x for p in allp), max(p.y for p in allp), max(p.z for p in allp)))
c = (lo + hi) / 2; span = max(hi.z - lo.z, hi.x - lo.x, hi.y - lo.y) * 1.0
cam = bpy.data.objects.new("c", bpy.data.cameras.new("c")); sc.collection.objects.link(cam); cam.data.type = "ORTHO"; cam.data.ortho_scale = span
d = Vector((0.55, -1, 0.15)).normalized(); cam.location = c + d * 20; cam.rotation_euler = (-d).to_track_quat("-Z", "Y").to_euler(); sc.camera = cam
sc.world = bpy.data.worlds.new("w"); sc.world.color = (0.93, 0.93, 0.95)
r = sc.render; r.resolution_x = int(size * 0.8); r.resolution_y = size; r.engine = "BLENDER_WORKBENCH"; r.film_transparent = False
s = sc.display.shading; s.light = "STUDIO"; s.color_type = "TEXTURE"; s.show_shadows = False; s.background_type = "WORLD"
os.makedirs(out, exist_ok=True)
for i, f in enumerate(range(f0, f1 + 1, step)):
    sc.frame_set(f); r.filepath = os.path.join(out, f"f{i:03d}.png"); bpy.ops.render.render(write_still=True)
print("[render] frames", i + 1)
