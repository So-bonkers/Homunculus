"""Targeted re-texturing, Blender side (CPU only).  Two modes:

blender -b --python blender_retex.py -- project base.glb camera.json strokes.json ref.png refmask.png|- out_basecolor.png out_preview.glb
    Projects a reference image onto the model from the camera the user lined up in the web viewer and bakes the result into the model's own UV atlas.
    camera.json: {"elements": 16 floats (three.js Matrix4 of the camera in the model's own glTF coordinates), "fov": vertical degrees, "aspect": w/h of the reference,
                  "min_cos": 0.15 (grazing-angle cut-off), "feather": 0.35 (soft edge of the brush, fraction of its radius)}
    strokes.json: {"strokes": [[x, y, z, r], ...]} brush spheres on the model in glTF coordinates; empty = every visible surface.
    refmask: white = the reference pixels that may be used (black / absent = all of them).
    Weight per vertex = brush(soft) x visible (ray cast from the camera) x facing the camera x inside the picture; the baked texture is
    mix(old texture, reference, weight x mask) (Cycles EMIT bake, 1 sample).

blender -b --python blender_retex.py -- render base.glb camera.json out.png [long_side]
    The model, textured, seen from that camera on a plain grey background (what the image model is asked to redraw, and the before/after previews).
Front is -Y, Z up after import (glTF Y-up is converted); the camera looks along its own -Z like in three.js.
"""
import bpy, sys, os, json, math
import numpy as np
from mathutils import Vector, Matrix
from mathutils.bvhtree import BVHTree

argv = sys.argv[sys.argv.index("--") + 1:]
mode = argv[0]
C4 = np.array([[1, 0, 0, 0], [0, 0, -1, 0], [0, 1, 0, 0], [0, 0, 0, 1]], float)          # glTF (x, y, z) -> Blender (x, -z, y)


def load(path):
    bpy.ops.wm.read_factory_settings(use_empty=True); bpy.ops.import_scene.gltf(filepath=path)
    ms = [o for o in bpy.data.objects if o.type == "MESH" and len(o.data.vertices) > 500]
    for o in [o for o in bpy.data.objects if o.type == "MESH" and o not in ms]: bpy.data.objects.remove(o, do_unlink=True)
    bpy.ops.object.select_all(action="DESELECT")
    for o in ms: o.select_set(True)
    bpy.context.view_layer.objects.active = ms[0]
    if len(ms) > 1: bpy.ops.object.join()
    ob = bpy.context.view_layer.objects.active; bpy.ops.object.transform_apply(location=True, rotation=True, scale=True); return ob


def cam_pose(cj):
    """Camera position and orthonormal axes in Blender coordinates from the three.js matrix (column-major, model-local, maybe scaled)."""
    M = np.array(cj["elements"], float).reshape(4, 4).T; M = C4 @ M                  # world conversion only: the camera's own axes (right, up, back) stay as they are
    pos = M[:3, 3]; R = M[:3, :3]; R = R / np.linalg.norm(R, axis=0, keepdims=True)
    u, _, vt = np.linalg.svd(R); R = u @ vt                                                    # exactly orthonormal
    if np.linalg.det(R) < 0: R[:, 2] *= -1
    return pos, R


def project_np(P, pos, R, fov, aspect):
    """Pixel position in the picture (u right, v up, 0..1) and depth in front of the camera, for points P (n, 3)."""
    X = (P - pos) @ R; z = -X[:, 2]; t = math.tan(math.radians(fov) / 2)
    z_safe = np.where(z > 1e-6, z, 1e-6)
    return (X[:, 0] / z_safe / (t * aspect) + 1) / 2, (X[:, 1] / z_safe / t + 1) / 2, z


def make_camera(cj, long_side):
    pos, R = cam_pose(cj); sc = bpy.context.scene
    for o in [o for o in bpy.data.objects if o.type == "CAMERA"]: bpy.data.objects.remove(o, do_unlink=True)
    cam = bpy.data.objects.new("cam", bpy.data.cameras.new("cam")); sc.collection.objects.link(cam)
    m = Matrix.Identity(4)
    for i in range(3):
        for j in range(3): m[i][j] = R[i, j]
    for i in range(3): m[i][3] = pos[i]
    cam.matrix_world = m; cam.data.sensor_fit = "VERTICAL"; cam.data.angle = math.radians(cj["fov"]); cam.data.clip_start = 0.01; cam.data.clip_end = 100
    a = cj["aspect"]; W, H = (long_side, int(round(long_side / a))) if a >= 1 else (int(round(long_side * a)), long_side)
    sc.render.resolution_x, sc.render.resolution_y = W, H; sc.camera = cam
    return pos, R, W, H


if mode == "render":
    base, cam_p, out = argv[1:4]; long_side = int(argv[4]) if len(argv) > 4 else 1024
    ob = load(base); cj = json.load(open(cam_p)); make_camera(cj, long_side); sc = bpy.context.scene
    sc.world = bpy.data.worlds.new("w"); sc.world.color = (0.8, 0.8, 0.8)
    r = sc.render; r.engine = "BLENDER_WORKBENCH"; r.film_transparent = False; r.filepath = out
    s = sc.display.shading; s.light = "FLAT"; s.color_type = "TEXTURE"; s.show_shadows = False; s.show_cavity = False; s.background_type = "WORLD"
    bpy.ops.render.render(write_still=True); print("[retex] rendered", out)

elif mode == "project":
    base, cam_p, strokes_p, ref_p, mask_p, out_png, out_glb = argv[1:8]
    ob = load(base); me = ob.data; cj = json.load(open(cam_p)); pos, R = cam_pose(cj); aspect = cj["aspect"]
    V = np.empty(len(me.vertices) * 3, np.float32); me.vertices.foreach_get("co", V); V = V.reshape(-1, 3).astype(float)
    N = np.empty(len(me.vertices) * 3, np.float32); me.vertices.foreach_get("normal", N); N = N.reshape(-1, 3).astype(float)
    u, v, depth = project_np(V, pos, R, cj["fov"], aspect)
    to_cam = pos - V; dist = np.linalg.norm(to_cam, axis=1); cosv = (N * (to_cam / np.maximum(dist, 1e-9)[:, None])).sum(1)
    inside = (u >= 0) & (u <= 1) & (v >= 0) & (v <= 1) & (depth > 0.01)
    # brush weight: soft-edged spheres in the model's coordinates; none = the whole visible surface
    S = np.array(json.load(open(strokes_p)).get("strokes") or [], float).reshape(-1, 4)
    if len(S):
        S[:, :3] = np.stack([S[:, 0], -S[:, 2], S[:, 1]], 1); wm = np.zeros(len(V)); fe = float(cj.get("feather", 0.35))
        for i in range(0, len(S), 48):
            c = S[i:i + 48]; d = np.linalg.norm(V[:, None, :] - c[None, :, :3], axis=2); wm = np.maximum(wm, np.clip((c[None, :, 3] - d) / np.maximum(c[None, :, 3] * fe, 1e-9), 0, 1).max(1))
    else: wm = np.ones(len(V))
    min_cos = float(cj.get("min_cos", 0.15)); wf = np.clip((cosv - min_cos) / 0.45, 0, 1)
    cand = np.nonzero((wm > 0) & inside & (wf > 0))[0]; vis = np.zeros(len(V), bool)
    bvh = BVHTree.FromObject(ob, bpy.context.evaluated_depsgraph_get()); org = Vector(pos.tolist()); eps = 0.004 * max(float(np.ptp(V[:, 2])), 1e-3) / 0.9
    for i in cand:                                                                          # occlusion: the first surface the ray meets must be (about) this vertex
        d = Vector((V[i] - pos).tolist()); L = d.length; h = bvh.ray_cast(org, d / L, L + 1.0)
        vis[i] = h[0] is None or h[3] >= L - eps
    w = wm * wf * vis * inside
    print(f"[retex] {int((w > 0.02).sum())} of {len(V)} vertices get the reference ({int(vis.sum())} visible from the camera inside the picture, {len(S)} brush dabs)")
    if not (w > 0.02).any(): print("[retex] nothing visible in the selection from this camera"); sys.exit(2)
    for name, data in (("projuv", np.stack([u, v, np.zeros_like(u), np.ones_like(u)], 1)), ("retex_w", np.stack([w, w, w, np.ones_like(w)], 1))):
        a = me.color_attributes.new(name, "FLOAT_COLOR", "POINT"); a.data.foreach_set("color", data.astype(np.float32).ravel())
    mat0 = next(m for m in me.materials if m and m.use_nodes); tex0 = next(n for n in mat0.node_tree.nodes if n.type == "TEX_IMAGE" and n.image); old = tex0.image; size = old.size[0]
    mat = bpy.data.materials.new("retex"); mat.use_nodes = True; nt = mat.node_tree
    for n in list(nt.nodes): nt.nodes.remove(n)
    L = nt.links; N_ = nt.nodes.new
    tA = N_("ShaderNodeTexImage"); tA.image = old; tR = N_("ShaderNodeTexImage"); tR.image = bpy.data.images.load(os.path.abspath(ref_p)); tR.extension = "EXTEND"
    aUV = N_("ShaderNodeAttribute"); aUV.attribute_name = "projuv"; aW = N_("ShaderNodeAttribute"); aW.attribute_name = "retex_w"
    L.new(aUV.outputs["Color"], tR.inputs["Vector"]); fac = aW.outputs["Fac"]
    if mask_p != "-" and os.path.exists(mask_p):
        tM = N_("ShaderNodeTexImage"); tM.image = bpy.data.images.load(os.path.abspath(mask_p)); tM.image.colorspace_settings.name = "Non-Color"; tM.extension = "EXTEND"
        L.new(aUV.outputs["Color"], tM.inputs["Vector"]); mul = N_("ShaderNodeMath"); mul.operation = "MULTIPLY"; L.new(aW.outputs["Fac"], mul.inputs[0]); L.new(tM.outputs["Color"], mul.inputs[1]); fac = mul.outputs[0]
    mix = N_("ShaderNodeMixRGB"); L.new(fac, mix.inputs["Fac"]); L.new(tA.outputs["Color"], mix.inputs["Color1"]); L.new(tR.outputs["Color"], mix.inputs["Color2"])
    em = N_("ShaderNodeEmission"); L.new(mix.outputs["Color"], em.inputs["Color"]); outn = N_("ShaderNodeOutputMaterial"); L.new(em.outputs["Emission"], outn.inputs["Surface"])
    new = bpy.data.images.new("retex_basecolor", size, size, alpha=False); new.colorspace_settings.name = "sRGB"
    tB = N_("ShaderNodeTexImage"); tB.image = new; nt.nodes.active = tB
    me.materials.clear(); me.materials.append(mat)
    sc = bpy.context.scene; sc.render.engine = "CYCLES"; sc.cycles.samples = 1; sc.cycles.device = "CPU"
    bpy.context.view_layer.objects.active = ob; ob.select_set(True)
    bpy.ops.object.bake(type="EMIT", margin=8, use_clear=True)
    new.filepath_raw = os.path.abspath(out_png); new.file_format = "PNG"; new.save()
    # preview GLB: the original material with the new texture
    me.materials.clear(); m2 = bpy.data.materials.new("retex_preview"); m2.use_nodes = True; b = next(n for n in m2.node_tree.nodes if n.type == "BSDF_PRINCIPLED")
    t2 = m2.node_tree.nodes.new("ShaderNodeTexImage"); t2.image = new; m2.node_tree.links.new(t2.outputs["Color"], b.inputs["Base Color"]); b.inputs["Roughness"].default_value = 0.6; me.materials.append(m2)
    for name in ("projuv", "retex_w"): me.color_attributes.remove(me.color_attributes[name])
    new.pack(); bpy.ops.object.select_all(action="SELECT"); bpy.ops.export_scene.gltf(filepath=os.path.abspath(out_glb), export_format="GLB"); print("[retex] wrote", out_png)
