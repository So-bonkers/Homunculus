"""Blender: one 3/4-view frame from the middle of an animated GLB (for the run page).  blender -b --python blender_clip_thumb.py -- clip.glb out.png"""
import bpy, sys, math
from mathutils import Vector
glb, out = sys.argv[sys.argv.index("--") + 1:][:2]
bpy.ops.wm.read_factory_settings(use_empty=True); bpy.ops.import_scene.gltf(filepath=glb)
sc = bpy.context.scene; sc.render.engine = "BLENDER_WORKBENCH"; sc.display.shading.light = "STUDIO"; sc.display.shading.color_type = "TEXTURE"
w = bpy.data.worlds.new("w"); sc.world = w; w.color = (0.82, 0.82, 0.85)
ms = [o for o in bpy.data.objects if o.type == "MESH"]; acts = list(bpy.data.actions)
f0, f1 = (int(acts[0].frame_range[0]), int(acts[0].frame_range[1])) if acts else (0, 1); sc.frame_set((f0 + f1) // 2)
dg = bpy.context.evaluated_depsgraph_get(); pts = [m.matrix_world @ v.co for m in ms for v in list(m.evaluated_get(dg).data.vertices)[::40]]
lo = Vector([min(p[i] for p in pts) for i in range(3)]); hi = Vector([max(p[i] for p in pts) for i in range(3)]); c = (lo + hi) / 2; H = hi.z - lo.z
cam = bpy.data.objects.new("c", bpy.data.cameras.new("c")); sc.collection.objects.link(cam); sc.camera = cam; cam.data.type = "ORTHO"; cam.data.clip_end = 1000; cam.data.ortho_scale = H * 1.2
r = math.radians(25); cam.location = c + Vector((math.sin(r), -math.cos(r), 0)) * 10; cam.rotation_euler = (math.pi / 2, 0, r)
sc.render.resolution_x, sc.render.resolution_y = 400, 500; sc.render.filepath = out; bpy.ops.render.render(write_still=True)
