"""Project the sharp front image onto the head of a Pixal3D mesh and bake it into the base-colour texture.

blender -b --python blender_face_project.py -- in.glb image.png out.glb [preview_dir]

Pixal3D output is pixel-aligned with its input image, so a front orthographic mapping registered on the silhouette
(height + horizontal centre) lands the image on the mesh. Only the head is replaced, only where it faces the camera and is
visible (coarse z-buffer), with soft blends at the neck, at grazing angles and at occlusion edges.
"""
import bpy, sys, os, math, json, numpy as np

argv = sys.argv[sys.argv.index("--") + 1:]
glb_in, img_path, glb_out = argv[:3]
prev_dir = argv[3] if len(argv) > 3 and argv[3] != "-" else None
dist_path = argv[4] if len(argv) > 4 and argv[4] != "-" else None
mode = argv[5] if len(argv) > 5 else "project"          # "render": write the mesh front view in image pixels; "project": bake
affine_path = argv[6] if len(argv) > 6 and argv[6] != "-" else None   # 2x3 image<-render correction from the alignment
mask_path = argv[7] if len(argv) > 7 and argv[7] != "-" else None          # person cut-out (rembg), precomputed outside Blender
face_mask_path = argv[8] if len(argv) > 8 and argv[8] != "-" else None   # feathered inner-face mask in image pixels (landmark fit)

bpy.ops.wm.read_factory_settings(use_empty=True)
bpy.ops.import_scene.gltf(filepath=glb_in)
ob = [o for o in bpy.data.objects if o.type == "MESH"][0]
for o in list(bpy.data.objects):
    if o.type != "MESH": bpy.data.objects.remove(o, do_unlink=True)
bpy.context.view_layer.objects.active = ob; ob.select_set(True)
bpy.ops.object.transform_apply(location=True, rotation=True, scale=True)
me = ob.data
# multi-view: FACEPROJ_ANGLE turns the model about its vertical axis so another side faces the (front) camera;
# FACEPROJ_PREV lists the angles already projected (a view only takes over where it sees the surface better);
# FACEPROJ_REGION = head (default) | full (whole body)
ANGLE = float(os.environ.get("FACEPROJ_ANGLE", "0") or 0)
PREV = [float(a) for a in os.environ.get("FACEPROJ_PREV", "").split(",") if a.strip()]
REGION = os.environ.get("FACEPROJ_REGION", "head")     # head | headview (head band, agreement mask) | body | full
_n0 = len(me.vertices); N0 = np.empty(_n0 * 3, np.float32); me.vertices.foreach_get("normal", N0); N0 = N0.reshape(-1, 3)
def facing_at(a):
    t = math.radians(a); return -(N0[:, 0] * math.sin(t) + N0[:, 1] * math.cos(t))
if ANGLE:      # glTF imports use quaternions: switch to Euler so the turn is applied
    ob.rotation_mode = "XYZ"; ob.rotation_euler = (0, 0, math.radians(ANGLE)); bpy.ops.object.transform_apply(location=False, rotation=True, scale=False)

# ---------------------------------------------------------------- image + silhouette registration
img = bpy.data.images.load(img_path); W, H = img.size
px = np.array(img.pixels[:], dtype=np.float32).reshape(H, W, 4)[::-1, :, :3]      # row 0 = top
bg = np.median(np.concatenate([px[:20].reshape(-1, 3), px[-20:].reshape(-1, 3), px[:, :20].reshape(-1, 3), px[:, -20:].reshape(-1, 3)]), 0)
fg = np.load(mask_path) if mask_path else (np.abs(px - bg).sum(2) > 0.10)
rows = np.nonzero(fg.any(1))[0]; cols = np.nonzero(fg.any(0))[0]
top_i, bot_i = rows.min(), rows.max()
n = len(me.vertices); V = np.empty(n * 3, np.float32); me.vertices.foreach_get("co", V); V = V.reshape(-1, 3)
Nrm = np.empty(n * 3, np.float32); me.vertices.foreach_get("normal", Nrm); Nrm = Nrm.reshape(-1, 3)
zmin, zmax = V[:, 2].min(), V[:, 2].max()
s = (bot_i - top_i) / (zmax - zmin)                                       # pixels per metre
# horizontal centre from the torso band (robust against arms/hair)
band = (V[:, 2] > zmin + 0.55 * (zmax - zmin)) & (V[:, 2] < zmin + 0.70 * (zmax - zmin))
xc_m = np.median(V[band, 0])
r0, r1 = int(top_i + 0.30 * (bot_i - top_i)), int(top_i + 0.45 * (bot_i - top_i))
xs = [np.mean(np.nonzero(fg[r])[0]) for r in range(r0, r1) if fg[r].any()]
xc_i = float(np.median(xs))
if os.environ.get("FACEPROJ_FRAME"):      # mesh-first runs: the exact camera of the grey front render (no estimate from the silhouette)
    _f = json.load(open(os.environ["FACEPROJ_FRAME"])); _k = W / _f["canvas"]
    s, top_i, xc_i, xc_m = _f["s"] * _k, _f["top"] * _k, _f["xc_i"] * _k, _f["xc_m"]
    top_i += (_f["zmax"] - zmax) * s          # same mapping even if this copy of the mesh sits slightly differently
u_px = (V[:, 0] - xc_m) * s + xc_i
v_px = (zmax - V[:, 2]) * s + top_i

H_m0 = zmax - zmin
if mode == "render":
    sc = bpy.context.scene; sc.render.engine = "BLENDER_WORKBENCH"; sc.display.shading.light = "FLAT"; sc.display.shading.color_type = "TEXTURE"
    wd = bpy.data.worlds.new("w"); sc.world = wd; wd.color = tuple(float(c) for c in bg)
    cam = bpy.data.objects.new("c", bpy.data.cameras.new("c")); sc.collection.objects.link(cam); sc.camera = cam
    cam.data.type = "ORTHO"; cam.data.ortho_scale = max(W, H) / s; cam.data.clip_end = 100
    cx = (W / 2 - xc_i) / s + xc_m; cz = zmax - (H / 2 - top_i) / s
    cam.location = (cx, V[:, 1].min() - 5, cz); cam.rotation_euler = (math.pi / 2, 0, 0)
    sc.render.resolution_x, sc.render.resolution_y = W, H; sc.view_settings.view_transform = "Standard"
    sc.render.filepath = glb_out; bpy.ops.render.render(write_still=True)
    print("[faceproj] rendered", glb_out); sys.exit(0)
if affine_path and os.path.exists(affine_path):
    import json
    M = np.array(json.load(open(affine_path))["image_from_render"], dtype=np.float64)   # 2x3
    uu = M[0, 0] * u_px + M[0, 1] * v_px + M[0, 2]; vv = M[1, 0] * u_px + M[1, 1] * v_px + M[1, 2]
    hb = np.clip((V[:, 2] - (zmax - 0.22 * H_m0)) / (0.05 * H_m0), 0, 1)          # head only, fade out at the neck
    u_px = u_px + hb * (uu - u_px); v_px = v_px + hb * (vv - v_px)
    print(f"[faceproj] feature alignment applied: {np.round(M, 3).tolist()}")

# ---------------------------------------------------------------- weights: head region x facing x visibility
H_m = zmax - zmin
head_lo = zmax - 0.135 * H_m; neck_blend = 0.025 * H_m
w_head = np.clip((V[:, 2] - head_lo) / neck_blend, 0, 1)
facing = -Nrm[:, 1]                                                        # camera looks along +Y at a model facing -Y
w_face = np.clip((facing + 0.10) / 0.30, 0, 1)            # include near-sideways walls (visibility is checked by the z-buffer)
# coarse z-buffer in image space: visible if within 6 mm of the front-most surface in that cell
cell = 3.0
gx = (u_px / cell).astype(int); gy = (v_px / cell).astype(int)
key = gy * 100000 + gx
order = np.argsort(V[:, 1])                                                # smaller y = closer to camera
front = {}
for i in order:
    k = key[i]
    if k not in front: front[k] = V[i, 1]
fy = np.array([front[k] for k in key])
w_vis = np.clip(1 - (V[:, 1] - fy - 0.006) / 0.010, 0, 1)
if REGION != "head":
    # occlusion edges: a surface just behind an edge where something closer covers the neighbouring pixels (a coat edge over the
    # shirt, hair over the face) would get the covering colour -> no paint there from this view
    gxs, gys = np.array([k % 100000 for k in front]), np.array([k // 100000 for k in front]); dep = np.array(list(front.values()))
    ox, oy = gxs.min(), gys.min(); grid = np.full((gys.max() - oy + 1, gxs.max() - ox + 1), np.inf, np.float32); grid[gys - oy, gxs - ox] = dep
    near = grid.copy(); r = 4
    for dy in range(-r, r + 1):
        for dx in range(-r, r + 1):
            sh = np.full_like(grid, np.inf)
            ys0, ys1 = max(0, dy), grid.shape[0] + min(0, dy); xs0, xs1 = max(0, dx), grid.shape[1] + min(0, dx)
            sh[ys0:ys1, xs0:xs1] = grid[ys0 - dy:ys1 - dy, xs0 - dx:xs1 - dx]; near = np.minimum(near, sh)
    cy_, cx_ = np.clip(gy - oy, 0, grid.shape[0] - 1), np.clip(gx - ox, 0, grid.shape[1] - 1)
    w_vis = w_vis * np.clip(1 - ((V[:, 1] - near[cy_, cx_]) - 0.015) / 0.015, 0, 1)
if REGION in ("full", "body"):     # whole-body passes: only surfaces that really face this view (no stretched pixels on side walls)
    w_face = np.clip((facing - 0.35) / 0.25, 0, 1)
if REGION == "full": w_head = np.ones_like(w_head)
elif REGION == "body":      # everything below the chin (clothes, arms, legs); the head and chin have their own passes
    w_head = np.clip(((head_lo - 0.03 * H_m) - V[:, 2]) / neck_blend, 0, 1)
w = (w_head * w_face * w_vis).astype(np.float32)
inside = (u_px >= 0) & (u_px < W) & (v_px >= 0) & (v_px < H)
w[~inside] = 0
if PREV:      # take over only where this view sees the surface clearly better than the views already projected
    f_prev = np.max([facing_at(a) for a in PREV], 0)
    w *= np.clip((facing - f_prev - 0.05) / 0.20, 0, 1).astype(np.float32)

if mode == "smooth":      # even out the geometry inside a mask (e.g. squinting eye slits) so an open-eyed texture sits on a smooth surface
    fm = np.load(face_mask_path); iters = int(argv[9]) if len(argv) > 9 else 12
    ui_ = np.clip(u_px.astype(int), 0, W - 1); vi_ = np.clip(v_px.astype(int), 0, H - 1)
    wf = (np.clip((facing - 0.1) / 0.3, 0, 1) * w_vis * fm[vi_, ui_] * inside).astype(np.float32)
    E = np.empty(len(me.edges) * 2, np.int32); me.edges.foreach_get("vertices", E); E = E.reshape(-1, 2)
    deg = np.bincount(E.ravel(), minlength=n).astype(np.float32); deg[deg == 0] = 1
    P = V.copy()
    for _ in range(iters):
        acc = np.zeros_like(P); np.add.at(acc, E[:, 0], P[E[:, 1]]); np.add.at(acc, E[:, 1], P[E[:, 0]])
        P = P + (wf * 0.6)[:, None] * (acc / deg[:, None] - P)
    me.vertices.foreach_set("co", P.ravel()); me.update()
    print(f"[faceproj] smoothed {int((wf > 0.05).sum())} vertices, max move {float(np.linalg.norm(P - V, axis=1).max() * 1000):.1f} mm")
    bpy.ops.export_scene.gltf(filepath=glb_out, export_format="GLB", export_yup=True)
    print("[faceproj] wrote", glb_out); sys.exit(0)

if mode == "reshape":     # move front-facing face vertices so the mesh's features land where the reference has them
    disp = np.load(argv[9]); fm = np.load(face_mask_path)
    ui_ = np.clip(u_px.astype(int), 0, W - 1); vi_ = np.clip(v_px.astype(int), 0, H - 1)
    wf = np.clip((facing - 0.15) / 0.30, 0, 1) * w_vis * fm[vi_, ui_] * inside
    d = disp[vi_, ui_]
    V[:, 0] += wf * d[:, 0] / s; V[:, 2] -= wf * d[:, 1] / s
    me.vertices.foreach_set("co", V.ravel()); me.update()
    moved = wf > 0.05
    print(f"[faceproj] reshaped {int(moved.sum())} face vertices, max shift {float((np.abs(d[moved]).max() if moved.any() else 0) / s * 1000):.1f} mm")
    bpy.ops.export_scene.gltf(filepath=glb_out, export_format="GLB", export_yup=True)
    print("[faceproj] wrote", glb_out); sys.exit(0)
# only sample pixels that belong to the character, well inside its silhouette (no background bleeding onto hair edges);
# the distance map (px from the eroded silhouette edge) is precomputed outside Blender, which has no scipy
dist = np.load(dist_path) if dist_path else np.full((H, W), 1e6, np.float32)
ui = np.clip(u_px.astype(int), 0, W - 1); vi = np.clip(v_px.astype(int), 0, H - 1)
w *= np.clip(dist[vi, ui] / (0.006 * H), 0, 1)
if face_mask_path and REGION != "head":      # whole-body passes: agreement mask (only where the new pixels roughly match the mesh)
    w *= np.load(face_mask_path)[vi, ui]
elif face_mask_path:      # landmark fit: only the inner face, the mesh keeps its own hair, ears and hairline
    fm = np.load(face_mask_path)[vi, ui]
    # inside the face the mask already decides; let concave parts (eye sockets, nostrils) that face slightly away take the image too
    w_face2 = np.clip((facing + 0.45) / 0.30, 0, 1)
    w = (w_head * np.maximum(w_face, w_face2 * fm) * w_vis).astype(np.float32); w[~inside] = 0
    w *= np.clip(dist[vi, ui] / (0.006 * H), 0, 1) * fm
print(f"[faceproj] scale {s:.1f}px/m, head verts weighted {int((w > 0.5).sum())}")

# ---------------------------------------------------------------- per-loop projection UVs + weight attribute
uv_proj = me.uv_layers.new(name="proj")
li = np.empty(len(me.loops), np.int32); me.loops.foreach_get("vertex_index", li)
uvs = np.stack([u_px[li] / W, 1 - v_px[li] / H], 1).astype(np.float32)
uv_proj.data.foreach_set("uv", uvs.ravel())
attr = me.color_attributes.new(name="projw", type="FLOAT_COLOR", domain="POINT")
cols = np.repeat(w[:, None], 4, 1); cols[:, 3] = 1; attr.data.foreach_set("color", cols.ravel())
orig_uv = [u for u in me.uv_layers if u.name != "proj"][0]; me.uv_layers.active = orig_uv
orig_uv.active_render = True

# ---------------------------------------------------------------- material: mix(original base colour, projected image) -> bake
mat = me.materials[0]; nt = mat.node_tree
bsdf = [n_ for n_ in nt.nodes if n_.type == "BSDF_PRINCIPLED"][0]
link = bsdf.inputs["Base Color"].links[0]; base_tex = link.from_node
while base_tex.type != "TEX_IMAGE":
    base_tex = [l.from_node for l in base_tex.inputs[0].links][0] if base_tex.inputs and base_tex.inputs[0].links else base_tex
    if base_tex.type != "TEX_IMAGE" and not base_tex.inputs: break
base_img = base_tex.image; BW, BH = base_img.size
uvn = nt.nodes.new("ShaderNodeUVMap"); uvn.uv_map = "proj"
ptex = nt.nodes.new("ShaderNodeTexImage"); ptex.image = img; ptex.extension = "EXTEND"
nt.links.new(uvn.outputs[0], ptex.inputs[0])
attrn = nt.nodes.new("ShaderNodeVertexColor"); attrn.layer_name = "projw"
mix = nt.nodes.new("ShaderNodeMix"); mix.data_type = "RGBA"
nt.links.new(attrn.outputs["Color"], mix.inputs["Factor"])
nt.links.new(base_tex.outputs["Color"], mix.inputs["A"]); nt.links.new(ptex.outputs["Color"], mix.inputs["B"])
emit = nt.nodes.new("ShaderNodeEmission"); nt.links.new(mix.outputs["Result"], emit.inputs[0])
out = [n_ for n_ in nt.nodes if n_.type == "OUTPUT_MATERIAL"][0]
old_surface = out.inputs["Surface"].links[0].from_socket
nt.links.new(emit.outputs[0], out.inputs["Surface"])
target = bpy.data.images.new("basecolor_faceproj", BW, BH, alpha=False)
tnode = nt.nodes.new("ShaderNodeTexImage"); tnode.image = target; nt.nodes.active = tnode

sc = bpy.context.scene; sc.render.engine = "CYCLES"; sc.cycles.samples = 1; sc.cycles.device = "CPU"
sc.render.bake.margin = 8
bpy.ops.object.bake(type="EMIT", use_clear=True, margin=8)
print("[faceproj] baked", BW, BH)
png_out = glb_out[:-4] + "_basecolor.png"; target.filepath_raw = png_out; target.file_format = "PNG"; target.save()
print("[faceproj] basecolor", png_out)

# ---------------------------------------------------------------- restore material with the new base colour, export
nt.links.new(old_surface, out.inputs["Surface"])
base_tex.image = target
for n_ in (uvn, ptex, attrn, mix, emit, tnode): nt.nodes.remove(n_)
if ANGLE:      # back to the original orientation before export
    ob.rotation_mode = "XYZ"; ob.rotation_euler = (0, 0, math.radians(-ANGLE)); bpy.ops.object.transform_apply(location=False, rotation=True, scale=False)
me.uv_layers.remove(me.uv_layers["proj"]); me.color_attributes.remove(me.color_attributes["projw"])
target.file_format = "PNG"
bpy.ops.export_scene.gltf(filepath=glb_out, export_format="GLB", export_yup=True)
print("[faceproj] wrote", glb_out)

if prev_dir:   # before/after face close-ups for the progress page
    os.makedirs(prev_dir, exist_ok=True)
    sc.render.engine = "BLENDER_WORKBENCH"; sc.display.shading.light = "FLAT"; sc.display.shading.color_type = "TEXTURE"
    wd = bpy.data.worlds.new("w"); sc.world = wd; wd.color = (0.82, 0.82, 0.84)
    cam = bpy.data.objects.new("c", bpy.data.cameras.new("c")); sc.collection.objects.link(cam); sc.camera = cam
    cam.data.type = "ORTHO"; cam.data.ortho_scale = 0.17 * H_m; sc.render.resolution_x = sc.render.resolution_y = 800
    hc = V[V[:, 2] > head_lo]; c = hc.mean(0)
    cam.location = (c[0], c[1] - 5, zmax - 0.075 * H_m); cam.rotation_euler = (math.pi / 2, 0, 0)
    sc.render.filepath = os.path.join(prev_dir, "face_after.png"); bpy.ops.render.render(write_still=True)
    base_tex.image = base_img
    sc.render.filepath = os.path.join(prev_dir, "face_before.png"); bpy.ops.render.render(write_still=True)
