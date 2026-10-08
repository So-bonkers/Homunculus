"""blender -b --python tools/trial_render.py -- model.glb out_dir tag : textured front/left/back/right views and a close-up of each hand (the outermost points of the T-pose)."""
import bpy, sys, math, numpy as np
from mathutils import Vector
glb, out, tag = sys.argv[sys.argv.index("--") + 1:][:3]
bpy.ops.wm.read_factory_settings(use_empty=True); bpy.ops.import_scene.gltf(filepath=glb)
ob = [o for o in bpy.data.objects if o.type == "MESH"][0]; me = ob.data
V = np.empty(len(me.vertices) * 3, np.float32); me.vertices.foreach_get("co", V); V = V.reshape(-1, 3)
M = np.array(ob.matrix_world); W = V @ M[:3, :3].T + M[:3, 3]
zmin, zmax = W[:, 2].min(), W[:, 2].max(); H = zmax - zmin
sc = bpy.context.scene; sc.render.engine = "BLENDER_WORKBENCH"; sc.display.shading.light = "FLAT"; sc.display.shading.color_type = "TEXTURE"
sc.world = bpy.data.worlds.new("w"); sc.world.color = (0.82, 0.82, 0.84)
cam = bpy.data.objects.new("c", bpy.data.cameras.new("c")); sc.collection.objects.link(cam); sc.camera = cam; cam.data.type = "ORTHO"
def shoot(name, center, scale, d, res=900):
    d = Vector(d).normalized(); cam.data.ortho_scale = scale; sc.render.resolution_x = sc.render.resolution_y = res
    cam.location = Vector(center) - d * 8; cam.rotation_euler = (0, 0, 0) if abs(d.z) > 0.9 else (math.pi / 2, 0, math.atan2(-d.x, d.y)); cam.data.clip_start, cam.data.clip_end = 0.1, 40
    sc.render.filepath = f"{out}/{tag}_{name}.png"; bpy.ops.render.render(write_still=True)
c = ((W[:, 0].min() + W[:, 0].max()) / 2, (W[:, 1].min() + W[:, 1].max()) / 2, zmin + H / 2)
for n, d in (("front", (0, 1, 0)), ("left", (-1, 0, 0)), ("back", (0, -1, 0)), ("right", (1, 0, 0))): shoot(n, c, H * 1.08, d)
# hands: the outermost 3% of points on each side along x (the model faces -y, T-pose along x)
band = W[(W[:, 2] > zmin + 0.5 * H) & (W[:, 2] < zmin + 0.95 * H)]
for n, sel in (("handA", band[:, 0] > np.percentile(band[:, 0], 98.5)), ("handB", band[:, 0] < np.percentile(band[:, 0], 1.5))):
    p = band[sel]; hc = p.mean(0); shoot(n + "_front", hc, 0.22 * H, (0, 1, 0)); shoot(n + "_top", hc, 0.22 * H, (0, 0, -1))
