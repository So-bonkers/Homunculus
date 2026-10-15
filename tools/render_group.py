"""Render several retargeted dancers of one fixed-camera shot together, from the camera of the video:
    blender -b --python tools/render_group.py -- <scene.json> <out_dir> <clip1.glb:scale1> <clip2.glb:scale2> ... [--from N] [--to M] [--step S | --frames a,b,c] [--size 1280x720] [--lift 0.9919]

scene.json is the one of tools/group_scene.py: the camera (height above the floor, the way it is turned, the intrinsics GVHMR assumed) and per dancer the verified frame ranges and the first absolute position.  Each clip is a glb of
tools/retarget_bvh.py (the character with its animation, the root motion relative to its first frame, 30 fps) followed by the scale the retargeting printed (the ratio of the character's hip height to the SMPL body's): the
character is put at its first position times that scale and the camera height is scaled the same way, so the picture has the video's perspective.  A dancer is hidden in the frames outside its verified ranges.  The clips come in the
order of the dancers in scene.json.  Writes <out_dir>/f%05d.png for the shot's frames N..M (30 fps frame numbers from 0); Workbench engine (no GPU needed): a floor, a backdrop colour, studio light with soft shadows."""
import bpy, sys, os, json, math
from mathutils import Matrix, Vector
argv = sys.argv[sys.argv.index("--") + 1:]
def opt(flag, default=None, cast=str):
    if flag in argv: i = argv.index(flag); v = argv[i + 1]; del argv[i:i + 2]; return cast(v)
    return default
LIFT = opt("--lift", 0.9919, float); FRAMES = opt("--frames", None); F0 = opt("--from", 0, int); F1 = opt("--to", None, int); STEP = opt("--step", 1, int); SIZE = opt("--size", "1280x720"); RW, RH = (int(x) for x in SIZE.split("x"))
scene_p, out_dir = argv[:2]; clips = [(c.rsplit(":", 1)[0], float(c.rsplit(":", 1)[1])) for c in argv[2:]]; os.makedirs(out_dir, exist_ok=True)
SC = json.load(open(scene_p)); W, H, N = SC["width"], SC["height"], SC["frames"]; F1 = N - 1 if F1 is None else F1
bpy.ops.wm.read_factory_settings(use_empty=True); sc = bpy.context.scene; sc.render.fps = 30; sc.render.fps_base = 1.0
M = Matrix(((1, 0, 0), (0, 0, -1), (0, 1, 0)))                           # glTF (y up, z back) -> Blender (z up, y back): (x, y, z) -> (x, -z, y)
placed = []
for d, (glb, scale) in zip(SC["dancers"], clips):
    before = set(bpy.data.objects); bpy.ops.import_scene.gltf(filepath=glb)
    for o in [o for o in bpy.data.objects if o not in before and o.type == "MESH" and o.name.startswith("Icosphere")]: bpy.data.objects.remove(o, do_unlink=True)      # the glTF importer's bone-shape helper
    new = [o for o in bpy.data.objects if o not in before]; arm = next(o for o in new if o.type == "ARMATURE"); meshes = [o for o in new if o.type == "MESH"]; x0, z0 = d["start_xz"]
    arm.location = Vector((x0 * scale, -z0 * scale, LIFT)); arm.name = f"D{d['k']}"; placed.append((d, arm, meshes))
    print(f"[render_group] D{d['k']}: {os.path.basename(glb)}, {len(meshes)} mesh(es), first position ({x0 * scale:.2f}, {z0 * scale:.2f}) m, scale {scale:.3f}")
FIRST = int(min((a.frame_range[0] for a in bpy.data.actions), default=1))              # the Blender frame of the shot's frame 0
for d, arm, meshes in placed:                                                          # hidden outside the verified ranges (a boolean property: it switches, it does not fade)
    for o in meshes:
        o.hide_render = True; o.keyframe_insert("hide_render", frame=min(0, FIRST - 1))
        for s_, e_ in d["valid_ranges"]:
            o.hide_render = False; o.keyframe_insert("hide_render", frame=s_ + FIRST); o.hide_render = True; o.keyframe_insert("hide_render", frame=e_ + FIRST)
# the camera of the video
sc.render.resolution_x, sc.render.resolution_y = RW, RH; sc.render.resolution_percentage = 100
cam = bpy.data.objects.new("cam", bpy.data.cameras.new("cam")); sc.collection.objects.link(cam); sc.camera = cam; cam.data.sensor_fit = "HORIZONTAL"; cam.data.sensor_width = 36.0; cam.data.lens = SC["fx"] / W * 36.0
cam.data.clip_start = 0.05; cam.data.clip_end = 400
sk = sum(s for _, s in clips) / len(clips)                                             # the characters' common scale: the camera's height scales with it
up = Vector(SC["up_in_camera_frame"]); axis = up.cross(Vector((0, 1, 0))); ang = math.acos(max(-1.0, min(1.0, up.y)))
Rg = Matrix.Rotation(ang, 3, axis.normalized()) if axis.length > 1e-9 else Matrix.Identity(3)                     # camera frame -> gravity frame, as in group_scene.py
cam.matrix_world = Matrix.Translation(Vector((0.0, 0.0, SC["camera_height"] * sk))) @ (M @ Rg).to_4x4()
# floor, light, world
bpy.ops.mesh.primitive_plane_add(size=200, location=(0, 0, -0.002)); fl = bpy.context.active_object; mat = bpy.data.materials.new("floor"); mat.diffuse_color = (0.36, 0.37, 0.40, 1.0); fl.data.materials.append(mat)
w = bpy.data.worlds.new("w"); w.color = (0.17, 0.18, 0.20); sc.world = w
sc.render.engine = "BLENDER_WORKBENCH"; sh = sc.display.shading; sh.light = "STUDIO"; sh.color_type = "TEXTURE"; sh.show_shadows = True; sh.shadow_intensity = 0.55; sh.show_cavity = False
sc.display.light_direction = Vector((0.35, -0.4, -0.85)); sc.view_settings.view_transform = "Standard"; sc.render.image_settings.file_format = "PNG"; sc.render.image_settings.color_mode = "RGB"
for f in ([int(x) for x in FRAMES.split(",")] if FRAMES else range(F0, F1 + 1, STEP)):
    sc.frame_set(f + FIRST); sc.render.filepath = os.path.join(out_dir, f"f{f:05d}.png"); bpy.ops.render.render(write_still=True)
    if ((f - F0) // STEP) % 50 == 0: print(f"[render_group] frame {f}/{F1}", flush=True)
print(f"[render_group] done: {out_dir}")
