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
HIDE_OVER = opt("--hide-gaps-over", 1e9, float)      # seconds: a dancer is hidden only in gaps (frames outside his verified stretches) longer than this; the poses across a gap are blended (tools/group_scene.py).  Default: never hidden, the camera of the video is not the render's camera
PITCH = opt("--pitch", 1.0, float)                      # degrees the camera is turned further DOWN than the floor fit says (measured against the video's keypoints on 380 samples: the render stood 21 px (waist) to 68 px (ankles) too low at 1080p; 1.0 degree is 38 px)
OVER = "--over-plate" in argv                          # characters only, on a transparent background (RGBA), lit with coloured lights like the room of the plate: composite them over tools/clean_plate.py's video (ffmpeg overlay)
if OVER: argv.remove("--over-plate")
LIGHTS = opt("--lights", "", str)                       # --over-plate: "r,g,b" of the key light (default a cool teal) and the ambient colour
NEON = "--neon" in argv                                # the stage as in the Miles renders: a dark room, a glossy floor, neon tubes on the back wall, coloured rim lights, EEVEE (slower than the plain Workbench render)
if NEON: argv.remove("--neon")
LIFT = opt("--lift", 0.9919, float); FRAMES = opt("--frames", None); F0 = opt("--from", 0, int); F1 = opt("--to", None, int); STEP = opt("--step", 1, int); SIZE = opt("--size", "1280x720"); RW, RH = (int(x) for x in SIZE.split("x"))
scene_p, out_dir = argv[:2]; clips = []; os.makedirs(out_dir, exist_ok=True)
for c in argv[2:]:                                  # path:scale or path:scale:lift (the height of the clip's origin above the floor; default --lift: the Mixamo clips have it at the hips, a game rig on the floor)
    f_ = c.split(":"); clips.append((f_[0], float(f_[1]), float(f_[2]) if len(f_) > 2 else LIFT))
SC = json.load(open(scene_p)); W, H, N = SC["width"], SC["height"], SC["frames"]; F1 = N - 1 if F1 is None else F1
bpy.ops.wm.read_factory_settings(use_empty=True); sc = bpy.context.scene; sc.render.fps = 30; sc.render.fps_base = 1.0
M = Matrix(((1, 0, 0), (0, 0, -1), (0, 1, 0)))                           # glTF (y up, z back) -> Blender (z up, y back): (x, y, z) -> (x, -z, y)
placed = []
for d, (glb, scale, lift) in zip(SC["dancers"], clips):
    before = set(bpy.data.objects); bpy.ops.import_scene.gltf(filepath=glb)
    for o in [o for o in bpy.data.objects if o not in before and o.type == "MESH" and o.name.startswith("Icosphere")]: bpy.data.objects.remove(o, do_unlink=True)      # the glTF importer's bone-shape helper
    new = [o for o in bpy.data.objects if o not in before]; arm = next(o for o in new if o.type == "ARMATURE"); meshes = [o for o in new if o.type == "MESH"]; x0, z0 = d["start_xz"]
    arm.location = Vector((x0 * scale, -z0 * scale, lift)); arm.name = f"D{d['k']}"; placed.append((d, arm, meshes))
    print(f"[render_group] D{d['k']}: {os.path.basename(glb)}, {len(meshes)} mesh(es), first position ({x0 * scale:.2f}, {z0 * scale:.2f}) m, scale {scale:.3f}")
FIRST = int(min((a.frame_range[0] for a in bpy.data.actions), default=1))              # the Blender frame of the shot's frame 0
for d, arm, meshes in placed:                                                          # hidden outside the verified ranges (a boolean property: it switches, it does not fade)
    for o in meshes:
        o.hide_render = True; o.keyframe_insert("hide_render", frame=min(0, FIRST - 1))
        rg = []                                                                                        # the verified stretches, joined across the gaps that are not longer than HIDE_OVER (the ends of the shot count as gaps too)
        for s_, e_ in d["valid_ranges"]:
            if rg and s_ - rg[-1][1] <= HIDE_OVER * 30: rg[-1][1] = e_
            else: rg.append([s_, e_])
        if rg and rg[0][0] <= HIDE_OVER * 30: rg[0][0] = 0
        if rg and N - rg[-1][1] <= HIDE_OVER * 30: rg[-1][1] = N + 1
        for s_, e_ in rg:
            o.hide_render = False; o.keyframe_insert("hide_render", frame=s_ + FIRST); o.hide_render = True; o.keyframe_insert("hide_render", frame=e_ + FIRST)
# the camera of the video
sc.render.resolution_x, sc.render.resolution_y = RW, RH; sc.render.resolution_percentage = 100
cam = bpy.data.objects.new("cam", bpy.data.cameras.new("cam")); sc.collection.objects.link(cam); sc.camera = cam; cam.data.sensor_fit = "HORIZONTAL"; cam.data.sensor_width = 36.0; cam.data.lens = SC["fx"] / W * 36.0
cam.data.clip_start = 0.05; cam.data.clip_end = 400
sk = sum(c[1] for c in clips) / len(clips)                                             # the characters' common scale: the camera's height scales with it
def cam_mat(upv, height):
    up = Vector(upv); axis = up.cross(Vector((0, 1, 0))); ang = math.acos(max(-1.0, min(1.0, up.y)))
    Rg = Matrix.Rotation(ang, 3, axis.normalized()) if axis.length > 1e-9 else Matrix.Identity(3)                     # camera frame -> gravity frame, as in group_scene.py
    return Matrix.Translation(Vector((0.0, 0.0, height * sk))) @ ((M @ Rg) @ Matrix.Rotation(-math.radians(PITCH), 3, "X")).to_4x4()
SHOTS = SC.get("shots") or [{"start": 0, "end": N, "camera_height": SC["camera_height"], "up_in_camera_frame": SC["up_in_camera_frame"]}]                        # a video with cuts: every shot has its own floor plane, so its own camera height and tilt
CAMS = [cam_mat(sh["up_in_camera_frame"], sh["camera_height"]) for sh in SHOTS]
def cam_for_frame(f):
    for i, sh in enumerate(SHOTS):
        if sh["start"] <= f < sh["end"]: return CAMS[i]
    return CAMS[-1]
cam.matrix_world = CAMS[0]
# floor, light, world
if OVER:
    sc.render.engine = "BLENDER_EEVEE"; sc.eevee.taa_render_samples = 16; sc.render.film_transparent = True
    for attr, val in (("use_shadows", True), ("use_gtao", True)):
        if hasattr(sc.eevee, attr): setattr(sc.eevee, attr, val)
    w = bpy.data.worlds.new("w"); w.use_nodes = True; sc.world = w; w.node_tree.nodes["Background"].inputs["Color"].default_value = (0.05, 0.07, 0.08, 1); w.node_tree.nodes["Background"].inputs["Strength"].default_value = 1.0
    for nm_, pos_, col_, pw_, sz_ in (("key", (1.5, 1.5, 4.5), (0.9, 0.78, 0.65), 900, 6.0), ("teal", (-5.0, 4.0, 2.5), (0.2, 0.9, 0.75), 900, 3.0), ("warm", (4.0, 12.0, 3.0), (1.0, 0.55, 0.3), 1200, 4.0), ("violet", (0.0, 12.0, 4.0), (0.5, 0.25, 1.0), 700, 4.0)):
        L_ = bpy.data.lights.new(nm_, "AREA"); L_.energy = pw_; L_.color = col_; L_.size = sz_; lo_ = bpy.data.objects.new(nm_, L_); sc.collection.objects.link(lo_); lo_.location = pos_; lo_.rotation_euler = (Vector((0, 6.0, 1.0)) - Vector(pos_)).to_track_quat("-Z", "Y").to_euler()
    sc.view_settings.view_transform = "Standard"; sc.view_settings.look = "None"
elif not NEON:
    bpy.ops.mesh.primitive_plane_add(size=200, location=(0, 0, -0.002)); fl = bpy.context.active_object; mat = bpy.data.materials.new("floor"); mat.diffuse_color = (0.36, 0.37, 0.40, 1.0); fl.data.materials.append(mat)
    w = bpy.data.worlds.new("w"); w.color = (0.17, 0.18, 0.20); sc.world = w
    sc.render.engine = "BLENDER_WORKBENCH"; sh = sc.display.shading; sh.light = "STUDIO"; sh.color_type = "TEXTURE"; sh.show_shadows = True; sh.shadow_intensity = 0.55; sh.show_cavity = False
    sc.display.light_direction = Vector((0.35, -0.4, -0.85)); sc.view_settings.view_transform = "Standard"
else:
    sc.render.engine = "BLENDER_EEVEE"; sc.eevee.taa_render_samples = 16
    for attr, val in (("use_shadows", True), ("use_raytracing", True), ("use_gtao", True)):
        if hasattr(sc.eevee, attr): setattr(sc.eevee, attr, val)
    def matl(name, col, rough, spec=0.5):
        m_ = bpy.data.materials.new(name); m_.use_nodes = True; b_ = m_.node_tree.nodes["Principled BSDF"]; b_.inputs["Base Color"].default_value = (*col, 1); b_.inputs["Roughness"].default_value = rough
        if "Specular IOR Level" in b_.inputs: b_.inputs["Specular IOR Level"].default_value = spec
        return m_
    w = bpy.data.worlds.new("w"); w.use_nodes = True; sc.world = w; w.node_tree.nodes["Background"].inputs["Color"].default_value = (0.003, 0.008, 0.012, 1); w.node_tree.nodes["Background"].inputs["Strength"].default_value = 1.0
    bpy.ops.mesh.primitive_plane_add(size=120, location=(0, 0, -0.002)); fl = bpy.context.active_object; fl.data.materials.append(matl("floor", (0.03, 0.045, 0.05), 0.18, 0.9))
    DEEP = max((-d["start_xz"][1] * c[1] for d, c in zip(SC["dancers"], clips)), default=12) + 4.5                     # the back wall: a few metres behind the farthest dancer (the dancers stand at positive Blender y, the camera looks along +y)
    DEEP = max(DEEP, 17.0); bpy.ops.mesh.primitive_plane_add(size=1, location=(0, DEEP, 5.0)); bw = bpy.context.active_object; bw.scale = (60, 10, 1); bw.rotation_euler = (math.radians(90), 0, 0); bw.data.materials.append(matl("wall", (0.01, 0.022, 0.025), 0.9, 0.2))
    def tube(a, b, col, power, radius=0.03):
        a, b = Vector(a), Vector(b); mid = (a + b) / 2; dv = b - a; L = dv.length
        bpy.ops.mesh.primitive_cylinder_add(radius=radius, depth=L, location=mid); cy = bpy.context.active_object; cy.rotation_euler = dv.to_track_quat("Z", "Y").to_euler()
        em = bpy.data.materials.new("tube"); em.use_nodes = True; nt_ = em.node_tree; nt_.nodes.remove(nt_.nodes["Principled BSDF"]); eo = nt_.nodes.new("ShaderNodeEmission"); eo.inputs["Color"].default_value = (*col, 1); eo.inputs["Strength"].default_value = 6.0
        nt_.links.new(eo.outputs[0], nt_.nodes["Material Output"].inputs["Surface"]); cy.data.materials.append(em)
        for j in range(4):
            Lt = bpy.data.lights.new("tube", "POINT"); Lt.energy = power / 4; Lt.color = col; Lt.shadow_soft_size = max(0.05, L / 8); lo_ = bpy.data.objects.new("tube", Lt); sc.collection.objects.link(lo_); lo_.location = a + dv * ((j + 0.5) / 4)
    CY, MG, VI = (0.1, 0.7, 1.0), (1.0, 0.15, 0.6), (0.55, 0.25, 1.0)
    y0 = DEEP - 0.2                                                                               # tubes on the wall: slanted bars at the sides, a long one across, floor-level strips
    tube((-9.0, y0, 0.3), (-6.0, y0, 6.5), CY, 2600); tube((9.0, y0, 0.3), (6.0, y0, 6.5), CY, 2600); tube((-7.0, y0, 3.4), (7.0, y0, 3.4), MG, 3600); tube((-4.5, y0, 6.8), (4.5, y0, 6.8), VI, 2200)
    tube((-12.0, DEEP - 3.0, 0.15), (-3.0, DEEP - 3.0, 0.15), MG, 500, 0.05); tube((3.0, DEEP - 3.0, 0.15), (12.0, DEEP - 3.0, 0.15), CY, 500, 0.05)
    for nm_, pos_, col_, pw_, sz_ in (("key", (0, -2.0, 6.0), (0.85, 0.92, 1.0), 4200, 9.0), ("rimL", (-8.0, DEEP - 3, 3.5), CY, 3800, 3.0), ("rimR", (8.0, DEEP - 3, 3.5), MG, 3800, 3.0)):
        L_ = bpy.data.lights.new(nm_, "AREA"); L_.energy = pw_; L_.color = col_; L_.size = sz_; lo_ = bpy.data.objects.new(nm_, L_); sc.collection.objects.link(lo_); lo_.location = pos_
        lo_.rotation_euler = (Vector((0, 8.0, 1.0)) - Vector(pos_)).to_track_quat("-Z", "Y").to_euler()
    sc.view_settings.view_transform = "Standard"; sc.view_settings.look = "None"; sc.view_settings.exposure = 0.0
sc.render.image_settings.file_format = "PNG"; sc.render.image_settings.color_mode = "RGBA" if OVER else "RGB"
for f in ([int(x) for x in FRAMES.split(",")] if FRAMES else range(F0, F1 + 1, STEP)):
    cam.matrix_world = cam_for_frame(f); sc.frame_set(f + FIRST); sc.render.filepath = os.path.join(out_dir, f"f{f:05d}.png"); bpy.ops.render.render(write_still=True)
    if ((f - F0) // STEP) % 50 == 0: print(f"[render_group] frame {f}/{F1}", flush=True)
print(f"[render_group] done: {out_dir}")
