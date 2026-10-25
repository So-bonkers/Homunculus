"""Headless preview renders of an assembled kit (workbench, texture colours, orthographic): front, back, side and a face close-up -> OUT_PREFIX_{front,back,side,face}.png.
    blender -b --python tools/ren_graft/render_kit.py -- ASSEMBLED_DIR OUT_PREFIX [extra.glb ...]"""
import bpy, sys, os, math
from mathutils import Vector
argv = sys.argv[sys.argv.index("--") + 1:]; D, OUT = argv[:2]; extra = argv[2:]
bpy.ops.wm.read_factory_settings(use_empty=True); sc = bpy.context.scene
for f in [os.path.join(D, x) for x in sorted(os.listdir(D)) if x.endswith(".glb")] + extra: bpy.ops.import_scene.gltf(filepath=f)
for o in [o for o in bpy.data.objects if o.type != "MESH"]: bpy.data.objects.remove(o, do_unlink=True)
sc.render.engine = "BLENDER_WORKBENCH"; sh = sc.display.shading; sh.light = "STUDIO"; sh.color_type = "TEXTURE"; sh.show_backface_culling = False
sc.render.resolution_x, sc.render.resolution_y = 700, 1000; sc.world = bpy.data.worlds.new("w"); sc.world.color = (0.25, 0.25, 0.27)
cam = bpy.data.objects.new("cam", bpy.data.cameras.new("cam")); sc.collection.objects.link(cam); sc.camera = cam; cam.data.type = "ORTHO"
def shot(name, loc, rot, scale):
    cam.location = loc; cam.rotation_euler = rot; cam.data.ortho_scale = scale; sc.render.filepath = f"{OUT}_{name}.png"; bpy.ops.render.render(write_still=True)
shot("front", (0, -3, 0.0), (math.radians(90), 0, 0), 1.08); shot("back", (0, 3, 0.0), (math.radians(90), 0, math.radians(180)), 1.15)
shot("side", (3, 0, 0.0), (math.radians(90), 0, math.radians(90)), 1.15); sc.render.resolution_x, sc.render.resolution_y = 800, 800
shot("face", (0, -3, 0.40), (math.radians(90), 0, 0), 0.32); print("rendered", OUT)
