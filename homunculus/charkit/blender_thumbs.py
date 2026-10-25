"""Headless thumbnails of GLB models for the judges: orthographic views (front, side, back, and from below for garments: a lid over the hem shows there), one PNG per view.
    blender -b --factory-startup --python homunculus/charkit/blender_thumbs.py -- JOBS.json [--engine workbench|cycles] [--size 384]
JOBS.json: [{"glb": path, "out": prefix, "views": ["front", "side", "back", "below"]}, ...] -> <prefix>_<view>.png (the caller joins them into one strip).
workbench uses OpenGL (a little of the GPU through EGL); cycles renders on the CPU only (slower, no GPU at all). Also imported by blender_pokes.py for its render."""
import bpy, json, math, os, sys
from mathutils import Vector

VIEWS = {"front": (Vector((0, -1, 0)), 0), "side": (Vector((1, 0, 0)), 0), "back": (Vector((0, 1, 0)), 0), "below": (Vector((0, 0, -1)), 0), "three_q": (Vector((0.7, -0.7, 0.15)).normalized(), 0)}   # direction from the model to the camera (Blender z up)

def setup(engine="workbench", size=384):
    sc = bpy.context.scene; r = sc.render; r.resolution_x = r.resolution_y = size; r.resolution_percentage = 100; r.film_transparent = False
    r.image_settings.file_format = "PNG"
    if engine == "cycles":
        r.engine = "CYCLES"; sc.cycles.device = "CPU"; sc.cycles.samples = 12; sc.cycles.use_denoising = False
        w = bpy.data.worlds.get("World") or bpy.data.worlds.new("World"); sc.world = w; w.use_nodes = True
        bg = next(n for n in w.node_tree.nodes if n.type == "BACKGROUND"); bg.inputs[0].default_value = (0.8, 0.8, 0.8, 1); bg.inputs[1].default_value = 1.4
    else:
        try: r.engine = "BLENDER_WORKBENCH"
        except TypeError as e: print("workbench engine name not accepted:", e); raise
        sh = sc.display.shading; sh.light = "STUDIO"; sh.color_type = "TEXTURE"; sh.show_cavity = True; sh.background_type = "VIEWPORT"; sh.background_color = (0.82, 0.82, 0.82)
    return sc

def bounds(objs):
    lo, hi = Vector((1e9,) * 3), Vector((-1e9,) * 3)
    for o in objs:
        for c in o.bound_box:
            w = o.matrix_world @ Vector(c); lo = Vector(map(min, lo, w)); hi = Vector(map(max, hi, w))
    return lo, hi

def render_views(objs, prefix, views):
    sc = bpy.context.scene; lo, hi = bounds(objs); ctr = (lo + hi) / 2; ext = hi - lo; outs = []
    cam = bpy.data.objects.get("thumb_cam")
    if cam is None: cam = bpy.data.objects.new("thumb_cam", bpy.data.cameras.new("thumb_cam")); sc.collection.objects.link(cam)
    cam.data.type = "ORTHO"; sc.camera = cam; cam.data.clip_end = 100
    for v in views:
        d, _ = VIEWS[v]; cam.location = ctr + d * (ext.length * 2 + 1)          # d: from the model towards the camera (glTF +z front = Blender -y)
        cam.rotation_euler = (math.pi, 0, 0) if v == "below" else (-d).to_track_quat("-Z", "Y").to_euler()     # the camera looks down its -Z with its Y up
        span = {"front": max(ext.x, ext.z), "back": max(ext.x, ext.z), "side": max(ext.y, ext.z), "below": max(ext.x, ext.y), "three_q": max(ext.x, ext.y, ext.z) * 1.2}[v]
        cam.data.ortho_scale = span * 1.12
        sc.render.filepath = f"{prefix}_{v}.png"; bpy.ops.render.render(write_still=True); outs.append(sc.render.filepath)
    return outs

def clear():
    for o in list(bpy.data.objects):
        if o.name != "thumb_cam": bpy.data.objects.remove(o, do_unlink=True)
    for m in list(bpy.data.meshes):
        if m.users == 0: bpy.data.meshes.remove(m)
    for im in list(bpy.data.images):
        if im.users == 0: bpy.data.images.remove(im)

if __name__ == "__main__" and "--" in sys.argv:
    argv = sys.argv[sys.argv.index("--") + 1:]; jobs = json.load(open(argv[0]))
    engine = argv[argv.index("--engine") + 1] if "--engine" in argv else "workbench"; size = int(argv[argv.index("--size") + 1]) if "--size" in argv else 384
    bpy.ops.wm.read_factory_settings(use_empty=True); setup(engine, size)
    if engine == "cycles":       # a sun so the CPU render has form, not only the grey sky
        sun = bpy.data.objects.new("sun", bpy.data.lights.new("sun", "SUN")); sun.data.energy = 3; sun.rotation_euler = (math.radians(50), 0, math.radians(30)); bpy.context.scene.collection.objects.link(sun)
    for j in jobs:
        clear(); before = set(bpy.data.objects); bpy.ops.import_scene.gltf(filepath=j["glb"]); objs = [o for o in bpy.data.objects if o not in before and o.type == "MESH"]
        print("rendered", render_views(objs, j["out"], j.get("views", ["front", "side", "back"])), flush=True)
