"""Mesh-first runs (STL/OBJ/PLY/GLB/FBX without a picture): prepare the model, re-orient it, and render grey reference views.

blender -b --python blender_mesh_prep.py -- prep   in_mesh out.glb views_dir info.json      (clean, scale, UV, blank texture, 4 grey views)
blender -b --python blender_mesh_prep.py -- orient in.glb out.glb rot_x_deg rot_z_deg views_dir   (turn upright / to the front, re-render views)
blender -b --python blender_mesh_prep.py -- front  in.glb out.png frame.json canvas             (exact orthographic front render + its pixel mapping)

The front render's mapping (pixel = (x * s + canvas/2, (zmax - z) * s + top)) is written to frame.json, so the texture projection can
use it instead of estimating the camera from the silhouette: the painted reference lines up with the mesh exactly.
"""
import bpy, bmesh, sys, os, json, math
import numpy as np
from mathutils import Vector

argv = [os.path.abspath(a) if ("/" in a or "." in os.path.basename(a)) and not a.lstrip("-").replace(".", "").isdigit() else a
        for a in sys.argv[sys.argv.index("--") + 1:]]      # Blender (snap) resolves relative output paths elsewhere
mode = argv[0]
TARGET_FACES = 300_000
HEIGHT = 1.8


def reset():
    bpy.ops.wm.read_factory_settings(use_empty=True)


def import_any(path):
    ext = os.path.splitext(path)[1].lower()
    if ext == ".stl": bpy.ops.wm.stl_import(filepath=path)
    elif ext == ".obj": bpy.ops.wm.obj_import(filepath=path)
    elif ext == ".ply": bpy.ops.wm.ply_import(filepath=path)
    elif ext in (".glb", ".gltf"): bpy.ops.import_scene.gltf(filepath=path)
    elif ext == ".fbx": bpy.ops.import_scene.fbx(filepath=path)
    else: raise SystemExit(f"unsupported mesh type {ext}")
    for o in list(bpy.data.objects):
        if o.type != "MESH": bpy.data.objects.remove(o, do_unlink=True)
    ms = [o for o in bpy.data.objects if o.type == "MESH"]
    if not ms: raise SystemExit("no mesh in the file")
    bpy.ops.object.select_all(action="DESELECT")
    for o in ms: o.select_set(True)
    bpy.context.view_layer.objects.active = ms[0]
    if len(ms) > 1: bpy.ops.object.join()
    ob = bpy.context.view_layer.objects.active
    bpy.ops.object.transform_apply(location=True, rotation=True, scale=True)
    return ob


def verts(ob):
    n = len(ob.data.vertices); V = np.empty(n * 3, np.float32); ob.data.vertices.foreach_get("co", V); return V.reshape(-1, 3)


def components(me):
    """Connected parts by union-find over the edges (fast even for millions of vertices)."""
    n = len(me.vertices); E = np.empty(len(me.edges) * 2, np.int64); me.edges.foreach_get("vertices", E); E = E.reshape(-1, 2)
    parent = np.arange(n)
    def find(a):
        while parent[a] != a: parent[a] = parent[parent[a]]; a = parent[a]
        return a
    # vectorised pointer jumping until stable
    for _ in range(64):
        pa, pb = parent[E[:, 0]], parent[E[:, 1]]; lo = np.minimum(pa, pb)
        np.minimum.at(parent, pa, lo); np.minimum.at(parent, pb, lo)
        parent = parent[parent]
        if np.array_equal(parent[E[:, 0]], parent[E[:, 1]]): break
    return parent


def normalize(ob):
    """Feet on the floor, centred on the vertical axis, 1.8 m tall."""
    V = verts(ob); lo, hi = V.min(0), V.max(0); h = hi[2] - lo[2]
    k = HEIGHT / h if h > 0 else 1.0
    c = np.array([(lo[0] + hi[0]) / 2, (lo[1] + hi[1]) / 2, lo[2]])
    V = (V - c) * k; ob.data.vertices.foreach_set("co", V.ravel()); ob.data.update()


def give_texture(ob, size=4096):
    """UVs (smart projection) and a blank light-grey base-colour texture: the projection steps paint into it."""
    me = ob.data
    if not me.uv_layers:
        bpy.context.view_layer.objects.active = ob; bpy.ops.object.mode_set(mode="EDIT"); bpy.ops.mesh.select_all(action="SELECT")
        bpy.ops.uv.smart_project(angle_limit=math.radians(66), island_margin=0.002)
        bpy.ops.object.mode_set(mode="OBJECT")
    img = bpy.data.images.new("basecolor", size, size, alpha=False); img.generated_color = (0.62, 0.62, 0.64, 1)
    mat = bpy.data.materials.new("character"); mat.use_nodes = True; nt = mat.node_tree
    bsdf = [n for n in nt.nodes if n.type == "BSDF_PRINCIPLED"][0]; bsdf.inputs["Roughness"].default_value = 0.6
    tex = nt.nodes.new("ShaderNodeTexImage"); tex.image = img; nt.links.new(tex.outputs["Color"], bsdf.inputs["Base Color"])
    me.materials.clear(); me.materials.append(mat)
    img.pack()


def grey_views(ob, out_dir, angles=(0, 90, 180, 270), size=768):
    os.makedirs(out_dir, exist_ok=True)
    sc = bpy.context.scene; sc.render.engine = "BLENDER_WORKBENCH"; sc.display.shading.light = "STUDIO"; sc.display.shading.color_type = "SINGLE"
    sc.display.shading.single_color = (0.75, 0.75, 0.77); sc.display.shading.show_cavity = True
    w = bpy.data.worlds.new("w"); sc.world = w; w.color = (0.92, 0.92, 0.93)
    cam = bpy.data.objects.new("c", bpy.data.cameras.new("c")); sc.collection.objects.link(cam); sc.camera = cam; cam.data.type = "ORTHO"
    V = verts(ob); lo, hi = V.min(0), V.max(0); c = (lo + hi) / 2; span = max(hi[2] - lo[2], np.linalg.norm((hi - lo)[:2])) * 1.08
    cam.data.ortho_scale = span; sc.render.resolution_x = sc.render.resolution_y = size
    for i, a in enumerate(angles):
        r = math.radians(a); d = Vector((math.sin(r), -math.cos(r), 0))
        cam.location = Vector(c) + d * 10; cam.rotation_euler = (math.pi / 2, 0, r)
        sc.render.filepath = os.path.join(out_dir, f"view{i + 1}.png"); bpy.ops.render.render(write_still=True)


def export(path):
    bpy.ops.export_scene.gltf(filepath=path, export_format="GLB", export_yup=True)


if mode == "prep":
    src, out, vdir, info_p = argv[1:5]
    reset(); ob = import_any(src); me = ob.data
    info = {"faces_in": len(me.polygons), "verts_in": len(me.vertices)}
    # weld duplicate vertices (STL stores every triangle separately)
    bm = bmesh.new(); bm.from_mesh(me); bmesh.ops.remove_doubles(bm, verts=bm.verts, dist=1e-6 * max(ob.dimensions)); bm.to_mesh(me); bm.free()
    V = verts(ob); lab = components(me); ids, counts = np.unique(lab, return_counts=True); H = V[:, 2].max() - V[:, 2].min()
    info["parts"] = int(len(ids))
    drop = np.zeros(len(V), bool); base = False
    for cid, cnt in zip(ids, counts):
        sel = lab == cid; P = V[sel]; ext = P.max(0) - P.min(0)
        if cnt < max(30, 0.0002 * len(V)): drop |= sel; continue                         # loose debris
        if (P[:, 2].min() - V[:, 2].min() < 0.03 * H and ext[2] < 0.12 * H and max(ext[0], ext[1]) > 0.25 * H
                and cnt < 0.5 * len(V)):                                                       # a flat display base under the feet
            drop |= sel; base = True
    if drop.any():
        bm = bmesh.new(); bm.from_mesh(me); bm.verts.ensure_lookup_table()
        bmesh.ops.delete(bm, geom=[bm.verts[i] for i in np.nonzero(drop)[0]], context="VERTS"); bm.to_mesh(me); bm.free()
    info["base_removed"] = base; info["debris_removed_verts"] = int(drop.sum())
    if len(me.polygons) > TARGET_FACES:
        mod = ob.modifiers.new("dec", "DECIMATE"); mod.ratio = TARGET_FACES / len(me.polygons); bpy.ops.object.modifier_apply(modifier=mod.name)
    bpy.ops.object.shade_smooth()
    bm = bmesh.new(); bm.from_mesh(me); bmesh.ops.recalc_face_normals(bm, faces=bm.faces); bm.to_mesh(me); bm.free()
    normalize(ob); info["faces_out"] = len(me.polygons)
    give_texture(ob); grey_views(ob, vdir); export(out)
    json.dump(info, open(info_p, "w"), indent=1); print("[prep]", json.dumps(info))

elif mode == "orient":
    src, out, rx, rz, vdir = argv[1:6]
    reset(); bpy.ops.import_scene.gltf(filepath=src)
    ob = [o for o in bpy.data.objects if o.type == "MESH"][0]
    for o in list(bpy.data.objects):
        if o.type != "MESH": bpy.data.objects.remove(o, do_unlink=True)
    bpy.context.view_layer.objects.active = ob; ob.select_set(True)
    bpy.ops.object.transform_apply(location=True, rotation=True, scale=True)
    ob.rotation_mode = "XYZ"; ob.rotation_euler = (math.radians(float(rx)), 0, math.radians(float(rz)))
    bpy.ops.object.transform_apply(location=False, rotation=True, scale=False)
    normalize(ob); grey_views(ob, vdir); export(out); print("[orient] wrote", out)

elif mode == "front":
    src, out, frame_p, canvas = argv[1], argv[2], argv[3], int(argv[4])
    reset(); bpy.ops.import_scene.gltf(filepath=src)
    ob = [o for o in bpy.data.objects if o.type == "MESH"][0]
    bpy.context.view_layer.objects.active = ob; ob.select_set(True); bpy.ops.object.transform_apply(location=True, rotation=True, scale=True)
    V = verts(ob); zmax, zmin = float(V[:, 2].max()), float(V[:, 2].min()); xr = float(np.abs(V[:, 0]).max())
    s = 0.88 * canvas / max(zmax - zmin, 2 * xr)                   # pixels per metre
    top = (canvas - (zmax - zmin) * s) / 2
    sc = bpy.context.scene; sc.render.engine = "BLENDER_WORKBENCH"; sc.display.shading.light = "STUDIO"; sc.display.shading.color_type = "SINGLE"
    sc.display.shading.single_color = (0.75, 0.75, 0.77); sc.display.shading.show_cavity = True
    w = bpy.data.worlds.new("w"); sc.world = w; w.color = (0.82, 0.82, 0.84)
    cam = bpy.data.objects.new("c", bpy.data.cameras.new("c")); sc.collection.objects.link(cam); sc.camera = cam
    cam.data.type = "ORTHO"; cam.data.ortho_scale = canvas / s; cam.data.clip_end = 100
    cam.location = (0, float(V[:, 1].min()) - 5, zmax - (canvas / 2 - top) / s); cam.rotation_euler = (math.pi / 2, 0, 0)
    sc.render.resolution_x = sc.render.resolution_y = canvas; sc.view_settings.view_transform = "Standard"
    sc.render.filepath = out; bpy.ops.render.render(write_still=True)
    json.dump({"canvas": canvas, "s": s, "top": top, "xc_i": canvas / 2, "xc_m": 0.0, "zmax": zmax}, open(frame_p, "w"))
    print("[front] wrote", out)
