"""Region repair, Blender side.  Two modes:

blender -b --python blender_repair.py -- analyse base.glb strokes.json out_dir [view]
    view: front (default) | back | left | right | top | auto. The model is turned so that this side faces the camera before the close-up is rendered (and turned back after
    the merge): a helmet crown is repaired from above, a back from behind. auto picks the side most of the painted surface faces. "left" = the character's left side.
    strokes.json: {"strokes": [[x, y, z, r], ...]} in glTF coordinates (Y up), as picked in the web viewer.
    Writes out_dir/regionN.json + maskN.npy (vertex indices, one region per connected blob), regionN_crop.png (front close-up of the region,
    orthographic, 1024 px) and prints [repair] lines. The crop is what the image model redraws.

blender -b --python blender_repair.py -- bake repaired.glb out.glb [size]
    repaired.glb (the merge result: the original mesh with its texture plus the flat-coloured donors) becomes ONE mesh with a fresh UV atlas and a baked base-colour
    texture (Cycles "selected to active", 1 sample, CPU), so the rest of the pipeline (colour projection, rig, texture) can use it like any Pixal3D mesh.

blender -b --python blender_repair.py -- merge base.glb regions.json out.glb out_dir
    regions.json: [{"region": "region0.json", "donor": "donor0.glb", "silhouette": [u0, v0, u1, v1, W, H]}, ...]  (silhouette = bounding box of the
    redrawn crop's subject in pixels). Each donor (an image-to-3D mesh of the redrawn crop) is mapped back into the region with the same
    pixel -> metre mapping as the crop render, snapped to the wrist ring, clipped to the hand side and joined; the original vertices of the region
    are deleted. Writes out.glb and out_dir/after_regionN_crop.png (same camera as the crop, for a before/after view).
blender -b --python blender_repair.py -- preset base.glb out.json name      (strokes for a named region: hands, head, crown, feet; "hands" is also kept as its own mode)
Front is -Y after import (Pixal3D meshes face the picture camera), Z is up.
"""
import bpy, bmesh, sys, os, json, math
import numpy as np
from mathutils import Vector

argv = sys.argv[sys.argv.index("--") + 1:]
mode = argv[0]
CROP = 1024


def load(path):
    bpy.ops.wm.read_factory_settings(use_empty=True); bpy.ops.import_scene.gltf(filepath=path)
    ms = [o for o in bpy.data.objects if o.type == "MESH" and len(o.data.vertices) > 500]
    for o in bpy.data.objects:
        if o.type == "MESH" and o not in ms: bpy.data.objects.remove(o, do_unlink=True)
    bpy.ops.object.select_all(action="DESELECT")
    for o in ms: o.select_set(True)
    bpy.context.view_layer.objects.active = ms[0]
    if len(ms) > 1: bpy.ops.object.join()
    ob = bpy.context.view_layer.objects.active
    bpy.ops.object.transform_apply(location=True, rotation=True, scale=True)
    return ob


def verts(ob):
    n = len(ob.data.vertices); V = np.empty(n * 3, np.float32); ob.data.vertices.foreach_get("co", V); return V.reshape(-1, 3)


def edges(ob):
    n = len(ob.data.edges); E = np.empty(n * 2, np.int32); ob.data.edges.foreach_get("vertices", E); return E.reshape(-1, 2)


def render_crop(path, box, light="STUDIO", clay=False):
    """Front orthographic render of the square (cx, cz, half) around the region, textured, on a plain grey background."""
    sc = bpy.context.scene; cx, cz, half = box
    for o in [o for o in bpy.data.objects if o.type == "CAMERA"]: bpy.data.objects.remove(o, do_unlink=True)
    cam = bpy.data.objects.new("cam", bpy.data.cameras.new("cam")); sc.collection.objects.link(cam); cam.data.type = "ORTHO"; cam.data.ortho_scale = 2 * half
    cam.location = (cx, -10, cz); cam.rotation_euler = (math.pi / 2, 0, 0); sc.camera = cam
    sc.world = bpy.data.worlds.new("w"); sc.world.color = (0.8, 0.8, 0.8)
    r = sc.render; r.engine = "BLENDER_WORKBENCH"; r.resolution_x = r.resolution_y = CROP; r.film_transparent = False; r.filepath = path
    s = sc.display.shading; s.light = light; s.color_type = "SINGLE" if clay else "TEXTURE"; s.single_color = (0.72, 0.72, 0.74); s.show_shadows = False; s.show_cavity = False; s.background_type = "WORLD"
    bpy.ops.render.render(write_still=True)


def region_color(ob, idx):
    """Median (linear) colour of the base-colour texture under the given vertices (the glove / skin / cloth the new part must keep)."""
    try:
        mat = next(m for m in ob.data.materials if m and m.use_nodes)
        tex = next(n for n in mat.node_tree.nodes if n.type == "TEX_IMAGE" and n.image)
        img = tex.image; w, h = img.size; buf = np.empty(w * h * 4, np.float32); img.pixels.foreach_get(buf); buf = buf.reshape(h, w, 4)
        me = ob.data; uv = me.uv_layers.active.data; nl = len(me.loops); UV = np.empty(nl * 2, np.float32); uv.foreach_get("uv", UV); UV = UV.reshape(-1, 2)
        LV = np.empty(nl, np.int32); me.loops.foreach_get("vertex_index", LV); sel = np.isin(LV, idx)
        u = np.clip((UV[sel, 0] % 1.0) * (w - 1), 0, w - 1).astype(int); v = np.clip((UV[sel, 1] % 1.0) * (h - 1), 0, h - 1).astype(int)
        c = np.median(buf[v, u, :3], axis=0)
        if not img.is_float and img.colorspace_settings.name.lower().startswith("srgb"):      # a byte image's pixels come back as stored (sRGB-encoded /255), not as linear light; a material's Base Color takes linear
            c = np.where(c <= 0.04045, c / 12.92, ((c + 0.055) / 1.055) ** 2.4)
        return [float(x) for x in np.clip(c, 0, 1)]
    except Exception as e:
        print(f"[repair] region colour not found ({type(e).__name__}); using grey"); return [0.35, 0.35, 0.36]


GRAFT = os.environ.get("REPAIR_GRAFT", "1") != "0"      # planar cut + blend + bridge + colour transfer (0: the old overlapping shells with one flat colour)


def srgb_to_linear(c):
    c = np.asarray(c, np.float64); return np.where(c <= 0.04045, c / 12.92, ((c + 0.055) / 1.055) ** 2.4)


def texture_colours(ob, idx=None):
    """Linear base-colour of the given vertices (all of them when idx is None) sampled from the base-colour texture at each vertex's first loop UV; None when the mesh has no texture."""
    try:
        mat = next(m for m in ob.data.materials if m and m.use_nodes); tex = next(n for n in mat.node_tree.nodes if n.type == "TEX_IMAGE" and n.image)
        img = tex.image; w, h = img.size; buf = np.empty(w * h * 4, np.float32); img.pixels.foreach_get(buf); buf = buf.reshape(h, w, 4)
        me = ob.data; nl = len(me.loops); UV = np.empty(nl * 2, np.float32); me.uv_layers.active.data.foreach_get("uv", UV); UV = UV.reshape(-1, 2)
        LV = np.empty(nl, np.int32); me.loops.foreach_get("vertex_index", LV)
        first = np.full(len(me.vertices), -1, np.int64); first[LV[::-1]] = np.arange(nl)[::-1]             # the first loop of every vertex
        sel = np.arange(len(me.vertices)) if idx is None else np.asarray(idx); ok = first[sel] >= 0
        out = np.full((len(sel), 3), 0.35)
        u = np.clip((UV[first[sel[ok]], 0] % 1.0) * (w - 1), 0, w - 1).astype(int); v = np.clip((UV[first[sel[ok]], 1] % 1.0) * (h - 1), 0, h - 1).astype(int)
        c = buf[v, u, :3].astype(np.float64)
        out[ok] = srgb_to_linear(c) if (not img.is_float and img.colorspace_settings.name.lower().startswith("srgb")) else c
        return out
    except Exception as e:
        print(f"[repair] no texture colours ({type(e).__name__})"); return None


def bake_colours_to_texture(ob, cols, size=1024):
    """Give the object a material whose base colour is an IMAGE: the per-vertex colours baked onto the object's own UV layout (Cycles, emission, CPU). Vertex colours do not survive the glTF round trip
    to the later bake; an image does. Returns False (and leaves the object alone) when it has no UVs."""
    me = ob.data
    if not me.uv_layers: return False
    set_vertex_colours(ob, cols)
    m = me.materials[0]; nt = m.node_tree; out = next(n for n in nt.nodes if n.type == "OUTPUT_MATERIAL"); b = next(n for n in nt.nodes if n.type == "BSDF_PRINCIPLED"); an = next(n for n in nt.nodes if n.type == "VERTEX_COLOR")
    em = nt.nodes.new("ShaderNodeEmission"); nt.links.new(an.outputs["Color"], em.inputs["Color"]); nt.links.new(em.outputs["Emission"], out.inputs["Surface"])
    img = bpy.data.images.new("repair_part_basecolor", size, size, alpha=False); img.colorspace_settings.name = "sRGB"
    tn = nt.nodes.new("ShaderNodeTexImage"); tn.image = img; nt.nodes.active = tn
    sc = bpy.context.scene; sc.render.engine = "CYCLES"; sc.cycles.samples = 1; sc.cycles.device = "CPU"
    bpy.ops.object.select_all(action="DESELECT"); ob.select_set(True); bpy.context.view_layer.objects.active = ob
    bpy.ops.object.bake(type="EMIT", margin=6, use_clear=True)
    nt.links.new(tn.outputs["Color"], b.inputs["Base Color"]); nt.links.new(b.outputs["BSDF"], out.inputs["Surface"])      # the image is now the colour; the emission was only the bake's carrier
    img.pack(); me.color_attributes.remove(me.color_attributes["Col"]); return True


def set_vertex_colours(ob, cols, name="Col"):
    """A point-domain colour attribute (linear RGBA) on the object's mesh, and a material whose base colour is that attribute."""
    me = ob.data
    if name in me.color_attributes: me.color_attributes.remove(me.color_attributes[name])
    at = me.color_attributes.new(name=name, type="FLOAT_COLOR", domain="POINT"); a = np.ones((len(me.vertices), 4), np.float32); a[:, :3] = np.asarray(cols, np.float32); at.data.foreach_set("color", a.ravel())
    m = bpy.data.materials.new("repair_part"); m.use_nodes = True; nt = m.node_tree; b = next(n for n in nt.nodes if n.type == "BSDF_PRINCIPLED")
    an = nt.nodes.new("ShaderNodeVertexColor"); an.layer_name = name; nt.links.new(an.outputs["Color"], b.inputs["Base Color"]); b.inputs["Roughness"].default_value = 0.5
    me.materials.clear(); me.materials.append(m); return m


VIEWS = {"front": (0, -1, 0), "back": (0, 1, 0), "left": (1, 0, 0), "right": (-1, 0, 0), "top": (0, 0, 1)}      # direction from the model towards the camera ("left" = the character's left side, +x)


def view_rotation(d):
    """3x3 matrix that turns direction d to the front camera direction (0, -1, 0): a turn about the vertical axis for the four sides, a quarter turn about x for the top."""
    d = np.array(d, float); d /= np.linalg.norm(d)
    if abs(d[2]) > 0.9:
        t = math.radians(90 if d[2] > 0 else -90); return np.array([[1, 0, 0], [0, math.cos(t), -math.sin(t)], [0, math.sin(t), math.cos(t)]])
    t = math.radians(-90) - math.atan2(d[1], d[0]); return np.array([[math.cos(t), -math.sin(t), 0], [math.sin(t), math.cos(t), 0], [0, 0, 1]])


def turn(ob, M):
    """Apply the 3x3 matrix M to every vertex of the object (the object's own transform is already applied)."""
    V = verts(ob) @ np.asarray(M, np.float32).T; ob.data.vertices.foreach_set("co", V.ravel()); ob.data.update()


def ring_normal(Rg, cen):
    """Normal of the plane through the boundary ring (smallest-variance axis), pointing from the ring to the region: the direction the part sticks out. Falls back to the centre line."""
    rc = Rg.mean(0); _, sv, vt = np.linalg.svd(Rg - rc, full_matrices=False); n = vt[2]
    if sv[2] > 0.6 * sv[1] or np.linalg.norm(cen - rc) < 1e-6: n = cen - rc
    n = n / (np.linalg.norm(n) + 1e-9)
    return (-n if (cen - rc) @ n < 0 else n), rc


# ---------------------------------------------------------------------------------------------------------------- bake
if mode == "bake":
    src_p, out_glb = argv[1:3]; size = int(argv[3]) if len(argv) > 3 else 4096
    bpy.ops.wm.read_factory_settings(use_empty=True); bpy.ops.import_scene.gltf(filepath=src_p)
    srcs = [o for o in bpy.data.objects if o.type == "MESH" and len(o.data.vertices) > 100]
    for o in [o for o in bpy.data.objects if o.type != "MESH"]: bpy.data.objects.remove(o, do_unlink=True)
    for o in srcs: o.hide_render = False
    bpy.ops.object.select_all(action="DESELECT")
    copies = []
    for o in srcs:
        c = o.copy(); c.data = o.data.copy(); bpy.context.scene.collection.objects.link(c); c.name = "target_part"; copies.append(c)
    for c in copies: c.select_set(True)
    bpy.context.view_layer.objects.active = copies[0]
    if len(copies) > 1: bpy.ops.object.join()
    tgt = bpy.context.view_layer.objects.active; tgt.name = "repaired"; tgt.data.name = "repaired"
    me = tgt.data; me.materials.clear()
    while me.uv_layers: me.uv_layers.remove(me.uv_layers[0])
    bpy.ops.object.mode_set(mode="EDIT"); bpy.ops.mesh.select_all(action="SELECT")
    bpy.ops.uv.smart_project(angle_limit=math.radians(66), island_margin=0.002); bpy.ops.object.mode_set(mode="OBJECT")
    img = bpy.data.images.new("repaired_basecolor", size, size, alpha=False); img.colorspace_settings.name = "sRGB"
    mat = bpy.data.materials.new("repaired"); mat.use_nodes = True; nt = mat.node_tree; bsdf = next(n for n in nt.nodes if n.type == "BSDF_PRINCIPLED")
    tn = nt.nodes.new("ShaderNodeTexImage"); tn.image = img; nt.links.new(tn.outputs["Color"], bsdf.inputs["Base Color"]); bsdf.inputs["Roughness"].default_value = 0.6
    me.materials.append(mat); nt.nodes.active = tn
    sc = bpy.context.scene; sc.render.engine = "CYCLES"; sc.cycles.samples = 1; sc.cycles.device = "CPU"
    bpy.ops.object.select_all(action="DESELECT")
    for o in srcs: o.select_set(True)
    tgt.select_set(True); bpy.context.view_layer.objects.active = tgt
    ext = 0.02 * (max(tgt.dimensions) if max(tgt.dimensions) > 0 else 1)
    bpy.ops.object.bake(type="DIFFUSE", pass_filter={"COLOR"}, use_selected_to_active=True, cage_extrusion=ext, max_ray_distance=ext * 3, margin=8, use_clear=True)
    print(f"[repair] baked {size}x{size} onto a fresh atlas ({len(me.polygons)} faces)")
    for o in srcs: bpy.data.objects.remove(o, do_unlink=True)
    bpy.ops.object.select_all(action="DESELECT"); tgt.select_set(True); bpy.context.view_layer.objects.active = tgt
    img.pack(); bpy.ops.export_scene.gltf(filepath=out_glb, export_format="GLB", use_selection=True); print("[repair] wrote", out_glb)

# ---------------------------------------------------------------------------------------------------------------- hands
elif mode in ("hands", "preset"):
    """blender -b --python blender_repair.py -- preset base.glb strokes.json name : brush strokes covering a named region of a T/A-posed figure, the same rules as the web viewer's
    buttons. hands: the outer ~10.5 % of the height at each side; head: the top 13.5 %; crown: the top 7 % (a helmet's dome); feet: the lowest 5 %. Used for tests and from the command line."""
    base, out_p = argv[1:3]; name = argv[3] if mode == "preset" and len(argv) > 3 else "hands"; ob = load(base); V = verts(ob); lo, hi = V.min(0), V.max(0); cx = (lo[0] + hi[0]) / 2; height = hi[2] - lo[2]
    if name == "hands": sel = V[np.abs(V[:, 0] - cx) > (hi[0] - lo[0]) / 2 - 0.105 * height]
    elif name == "head": sel = V[V[:, 2] > hi[2] - 0.135 * height]
    elif name == "crown": sel = V[V[:, 2] > hi[2] - 0.07 * height]
    elif name == "feet": sel = V[V[:, 2] < lo[2] + 0.05 * height]
    else: print(f"[repair] unknown region preset {name}"); sys.exit(2)
    cell = 0.02; keys = {tuple(k) for k in np.floor(sel / cell).astype(int)}; strokes = []
    for k in keys:
        c = (np.array(k) + 0.5) * cell; strokes.append([float(c[0]), float(c[2]), float(-c[1]), cell * 0.8])      # Blender -> glTF (x, z, -y)
    json.dump({"strokes": strokes}, open(out_p, "w")); print(f"[repair] {name}: {len(sel)} vertices -> {len(strokes)} strokes")

# ---------------------------------------------------------------------------------------------------------------- analyse
elif mode == "analyse":
    base, strokes_p, out_dir = argv[1:4]; view = argv[4] if len(argv) > 4 else "front"; os.makedirs(out_dir, exist_ok=True)
    ob = load(base); V = verts(ob); E = edges(ob)
    S = np.array(json.load(open(strokes_p))["strokes"], np.float32).reshape(-1, 4)
    S[:, :3] = np.stack([S[:, 0], -S[:, 2], S[:, 1]], 1)                    # glTF (x, y, z) -> Blender (x, -z, y)
    mask = np.zeros(len(V), bool)
    for i in range(0, len(S), 64):
        c = S[i:i + 64]; d = np.linalg.norm(V[:, None, :] - c[None, :, :3], axis=2); mask |= (d <= c[None, :, 3]).any(1)
    print(f"[repair] {int(mask.sum())} of {len(V)} vertices inside {len(S)} brush strokes")
    if view == "auto" and mask.any():      # the side that most of the painted surface faces (front wins a near tie: it is the best tested one)
        Nv = np.empty(len(V) * 3, np.float32); ob.data.vertices.foreach_get("normal", Nv); Nv = Nv.reshape(-1, 3)[mask]
        score = {k: int((Nv @ np.array(d) > 0.3).sum()) for k, d in VIEWS.items()}; view = max(score, key=score.get)
        if score["front"] >= 0.85 * score[view]: view = "front"
        print(f"[repair] view chosen from the painted surface: {view} {score}")
    VIEW_R = view_rotation(VIEWS.get(view, VIEWS["front"]))
    if view != "front": turn(ob, VIEW_R); V = verts(ob)                       # from here on everything is in the camera's frame: the close-up is always rendered from the front
    json.dump({"view": view, "R": VIEW_R.tolist()}, open(os.path.join(out_dir, "view.json"), "w"))
    # connected blobs. The glTF importer splits vertices along UV seams, so connectivity is computed on welded positions
    uq, canon = np.unique(np.round(V * 1e5).astype(np.int64), axis=0, return_inverse=True); canon = canon.ravel(); nc = len(uq)
    Vc = np.zeros((nc, 3), np.float32); Vc[canon] = V; Ec = canon[E]; Ec = Ec[Ec[:, 0] != Ec[:, 1]]
    maskc = np.zeros(nc, bool); maskc[canon[mask]] = True
    me = Ec[maskc[Ec[:, 0]] & maskc[Ec[:, 1]]]; parent = {int(i): int(i) for i in np.nonzero(maskc)[0]}
    def find(a):
        while parent[a] != a: parent[a] = parent[parent[a]]; a = parent[a]
        return a
    for a, b in me: parent[find(int(a))] = find(int(b))
    comps = {}
    for i in parent: comps.setdefault(find(i), []).append(i)
    comps = [np.array(c) for c in comps.values() if len(c) > 60]
    height = float(V[:, 2].max() - V[:, 2].min()); gap = 0.04 * height
    def bb(c): return Vc[c].min(0), Vc[c].max(0)
    merged = True
    while merged and len(comps) > 1:         # pieces that nearly touch are one region (a hand whose thumb is a separate island is still one hand)
        merged = False
        for i in range(len(comps)):
            for j in range(i + 1, len(comps)):
                (a0, a1), (b0, b1) = bb(comps[i]), bb(comps[j])
                if np.all(np.maximum(a0, b0) - np.minimum(a1, b1) < gap): comps[i] = np.concatenate([comps[i], comps[j]]); del comps[j]; merged = True; break
            if merged: break
    comps = sorted([c for c in comps if len(c) > 150], key=len, reverse=True)[:4]
    regions = []
    for k, idc in enumerate(comps):
        mc = np.zeros(nc, bool); mc[idc] = True; idx = np.nonzero(mc[canon])[0]            # every (split) vertex of the blob
        P = V[idx]; lo, hi = P.min(0), P.max(0); cen = P.mean(0)
        bd = Ec[mc[Ec[:, 0]] != mc[Ec[:, 1]]]; ring_idx = np.unique(np.where(mc[bd[:, 0]], bd[:, 0], bd[:, 1]))     # masked vertices next to unmasked ones
        if len(ring_idx) < 8: print(f"[repair] blob {k}: no boundary (the selection covers a whole part); skipped"); continue
        R = Vc[ring_idx]; n, rc = ring_normal(R, cen); rr = float(np.linalg.norm(R - rc - np.outer((R - rc) @ n, n), axis=1).mean())
        half = float(max(hi[0] - lo[0], hi[2] - lo[2]) / 2 * 1.35 + 0.02); box = [float((lo[0] + hi[0]) / 2), float((lo[2] + hi[2]) / 2), half]
        info = {"index": k, "n_verts": int(len(idx)), "bbox": [lo.tolist(), hi.tolist()], "centroid": cen.tolist(), "ring": {"center": rc.tolist(), "normal": n.tolist(), "radius": rr},
                "box": box, "mask": f"mask{k}.npy", "crop": f"region{k}_crop.png", "view": view, "R": VIEW_R.tolist()}
        np.save(os.path.join(out_dir, f"mask{k}.npy"), idx); json.dump(info, open(os.path.join(out_dir, f"region{k}.json"), "w"), indent=1)
        info["color"] = region_color(ob, idx); json.dump(info, open(os.path.join(out_dir, f"region{k}.json"), "w"), indent=1)
        render_crop(os.path.join(out_dir, f"region{k}_crop.png"), box); render_crop(os.path.join(out_dir, f"region{k}_clay.png"), box, clay=True)
        print(f"[repair] region {k}: {len(idx)} vertices, ring radius {rr * 100:.1f} cm, crop {2 * half * 100:.0f} cm wide")
        regions.append(k)
    json.dump({"regions": regions}, open(os.path.join(out_dir, "regions_index.json"), "w"))
    if not regions: print("[repair] nothing to repair: no usable region"); sys.exit(2)

# ---------------------------------------------------------------------------------------------------------------- merge
elif mode == "merge":
    base, regs_p, out_glb, out_dir = argv[1:5]; os.makedirs(out_dir, exist_ok=True)
    jobs = json.load(open(regs_p)); ob = load(base)
    _R0 = np.array(json.load(open(jobs[0]["region"])).get("R") or np.eye(3))      # all regions of a job share one view: work in the camera's frame, turn back before writing
    if not np.allclose(_R0, np.eye(3)): turn(ob, _R0)
    V = verts(ob)
    # 1) every region's donor, mapped, snapped to the wrist, clipped; collected before anything is deleted
    donors = []; delete = np.zeros(len(V), bool); boxes = []; grafts = []; base_cols = texture_colours(ob) if GRAFT else None
    if GRAFT:      # welded connectivity (the importer splits vertices along texture seams) for the flood fill that removes what the old part leaves behind
        _uq, _canon = np.unique(np.round(V * 1e5).astype(np.int64), axis=0, return_inverse=True); _canon = _canon.ravel(); _nc = len(_uq)
        _Vc = np.zeros((_nc, 3), np.float32); _Vc[_canon] = V; _E = _canon[edges(ob)]; _E = _E[_E[:, 0] != _E[:, 1]]; _E = np.vstack([_E, _E[:, ::-1]])
    def flood(mark_w, allowed_w):
        """Grow mark_w along mesh edges into allowed vertices until nothing new is reached."""
        while True:
            new = np.zeros(_nc, bool); sel = mark_w[_E[:, 0]] & allowed_w[_E[:, 1]] & ~mark_w[_E[:, 1]]
            if not sel.any(): return mark_w
            new[_E[sel, 1]] = True; mark_w = mark_w | new
    for j in jobs:
        _i = json.load(open(j["region"])); delete[np.load(os.path.join(os.path.dirname(j["region"]), _i["mask"]))] = True
    Vk = V[~delete]                                                          # what stays of the original mesh: the donors must meet it
    for j in jobs:
        info = json.load(open(j["region"])); idx = np.load(os.path.join(os.path.dirname(j["region"]), info["mask"])); delete[idx] = True
        cx, cz, half = info["box"]; ppm = CROP / (2 * half); u0, v0, u1, v1, W, H = j["silhouette"]
        bpy.ops.object.select_all(action="DESELECT"); before = set(bpy.data.objects)
        bpy.ops.import_scene.gltf(filepath=j["donor"]); new = [o for o in bpy.data.objects if o not in before and o.type == "MESH"]
        for o in [o for o in bpy.data.objects if o not in before and o.type != "MESH"]: bpy.data.objects.remove(o, do_unlink=True)
        bpy.ops.object.select_all(action="DESELECT")
        for o in new: o.select_set(True)
        bpy.context.view_layer.objects.active = new[0]
        if len(new) > 1: bpy.ops.object.join()
        do = bpy.context.view_layer.objects.active; bpy.ops.object.transform_apply(location=True, rotation=True, scale=True)
        col = info.get("color")
        if col:      # the donor was built from a grey clay redraw: it gets the original region's colour as a flat material
            m = bpy.data.materials.new(f"repair_{info['index']}"); m.use_nodes = True; b = next(n for n in m.node_tree.nodes if n.type == "BSDF_PRINCIPLED")
            b.inputs["Base Color"].default_value = (*col, 1.0); b.inputs["Roughness"].default_value = 0.5; m.diffuse_color = (*col, 1.0); do.data.materials.clear(); do.data.materials.append(m)
        D = verts(do); dlo, dhi = D.min(0), D.max(0)
        s_px = (v1 - v0) / max(dhi[2] - dlo[2], 1e-6); f = s_px / ppm; xc_m = (dlo[0] + dhi[0]) / 2; xc_i = (u0 + u1) / 2
        # same pixel -> metre mapping as the crop render: the redraw's subject (picture box) <-> the donor's bounding box
        Xo = cx + (xc_i - W / 2) / ppm - f * xc_m; Zo = cz - (v0 - H / 2) / ppm - f * dhi[2]
        ymean = (dlo[1] + dhi[1]) / 2; Yo = ((np.array(info["bbox"][0][1]) + np.array(info["bbox"][1][1])) / 2) - f * ymean
        D2 = np.stack([f * D[:, 0] + Xo, f * D[:, 1] + Yo, f * D[:, 2] + Zo], 1)
        rc = np.array(info["ring"]["center"]); n = np.array(info["ring"]["normal"]); rr = info["ring"]["radius"]
        # size: the redraw fixes the shape, but its size is whatever the image model drew and its depth is a guess (a picture has no thickness). The region being replaced is the size reference:
        # the new part may be redrawn, never smaller than what it replaces (length along the part and spread across it, thickness along the camera axis)
        P0 = V[idx]; ctr = D2.mean(0)
        ext = lambda P, ax: float(np.ptp(P @ ax))
        k = max(ext(P0, n) / max(ext(D2, n), 1e-6), ext(P0, np.array([0.0, 0.0, 1.0])) / max(ext(D2, np.array([0.0, 0.0, 1.0])), 1e-6)); k = min(max(k, 1.0), 1.4)
        D2 = ctr + (D2 - ctr) * k
        ky = min(max(float(np.ptp(P0[:, 1])) / max(float(np.ptp(D2[:, 1])), 1e-6), 1.0), 1.8); D2[:, 1] = D2[:, 1].mean() + (D2[:, 1] - D2[:, 1].mean()) * ky
        print(f"[repair] region {info['index']}: size matched to the original (x{k:.2f} overall, x{ky:.2f} in depth)")
        # contact: the picture fixes the hand's size and position only roughly, so measure where the remaining arm REALLY ends along the arm axis and slide the donor's
        # stub over that end (an overlap of about one wrist radius), centred on the arm and with the arm's size. Nothing is left floating.
        ax = lambda P: P - rc - np.outer((P - rc) @ n, n)                    # offsets from the arm axis (the line through the wrist ring along n)
        tb = (Vk - rc) @ n; lb = np.linalg.norm(ax(Vk), axis=1); arm = (lb < 2.5 * rr) & (tb < 3 * rr) & (tb > -6 * rr)
        td = (D2 - rc) @ n; ld = np.linalg.norm(ax(D2), axis=1); tube = ld < 2.5 * rr
        if arm.sum() > 30 and tube.sum() > 30:
            t_end = float(np.percentile(tb[arm], 98)); t_start = float(np.percentile(td[tube], 2)); stub = max(0.0, 2.0 * rr)
            overlap = min(1.0 * rr, 0.6 * max(float(np.percentile(td[tube], 50)) - t_start, 0.01))
            D2 = D2 + n * ((t_end - overlap) - t_start)                       # along the arm: the stub starts one overlap inside the arm
            td = (D2 - rc) @ n
            za = arm & (tb > t_end - 0.6 * rr); zd = (td < td[tube].min() + 0.6 * rr) & (np.linalg.norm(ax(D2), axis=1) < 2.5 * rr)
            if za.sum() > 10 and zd.sum() > 10:
                cb, cd = Vk[za].mean(0), D2[zd].mean(0); cb = cb - ((cb - rc) @ n) * n; cd = cd - ((cd - rc) @ n) * n
                D2 = D2 + (cb - cd)                                           # across the arm: centred on it
                perp = lambda P, c: np.linalg.norm(P - c - np.outer((P - c) @ n, n), axis=1).mean()
                g = min(1.3, max(0.95, perp(Vk[za], cb) / max(perp(D2[zd], cb), 1e-6))); D2 = cb + (D2 - cb) * g
                print(f"[repair] region {info['index']}: donor scale x{f:.3f}; arm ends {abs(t_end) * 100:.1f} cm from the wrist ring, stub slid {overlap * 100:.1f} cm over it, "
                      f"centred ({np.linalg.norm(cb - cd) * 100:.1f} cm shift, x{g:.2f} size)")
        t = (D2 - rc) @ n; keep = np.ones(len(D2), bool)                      # the donor starts inside the arm by construction: nothing to clip
        grafted = False
        if GRAFT and arm.sum() > 30 and tube.sum() > 30:
            # --- a real graft instead of two shells: cut both parts at one plane just inside the retained end, blend the donor's cross-section into the retained ring, bridge the two rings, carry the colours over
            tV = (V - rc) @ n; lV = np.linalg.norm(ax(V), axis=1)
            _m0 = np.zeros(_nc, bool); _m0[_canon[delete]] = True; _touch = np.zeros(_nc, bool); _sel0 = _m0[_E[:, 0]] & ~_m0[_E[:, 1]]; _touch[_E[_sel0, 1]] = True      # retained vertices that touch the old region = its ragged end
            _tw0 = (_Vc - rc) @ n; _near = _touch & (np.linalg.norm(_Vc - rc - np.outer(_tw0, n), axis=1) < 2.2 * rr)
            t_cut = (float(np.percentile(_tw0[_near], 4)) - 0.25 * rr) if _near.sum() > 20 else t_end - 0.4 * overlap      # inside the most inward ragged tip: below it everything goes, so the cut is clean
            D2 = D2 + n * (((t_cut - 0.35 * rr) - float(np.percentile(((D2 - rc) @ n)[tube], 2))))                   # the donor's stub starts below the plane (it is cut there)
            delete |= (tV > t_cut) & (lV < 1.8 * rr)                                    # the retained end is cut clean at the plane (the sphere selection left it ragged, with bits of the old part)
            _mark = np.zeros(_nc, bool); _mark[_canon[delete]] = True; _tW = (_Vc - rc) @ n
            _mark = flood(_mark, _tW > t_cut); _before = int(delete.sum()); delete |= _mark[_canon]               # whatever of the old part is still attached beyond the plane goes too (shoe collars, laces)
            print(f"[repair] region {info['index']}: {int(delete.sum()) - _before} more vertices of the old part removed beyond the plane (what the selection left attached)")
            td = (D2 - rc) @ n; ld = np.linalg.norm(ax(D2), axis=1); keep = td >= t_cut      # the donor's stub inside the retained part is dropped
            ring_r = (~delete) & (np.abs(tV - t_cut) < 0.4 * rr) & (lV < 2.2 * rr); ring_d = keep & (td < t_cut + 0.4 * rr) & (ld < 2.2 * rr)
            if ring_r.sum() > 12 and ring_d.sum() > 12:
                perp = lambda P: P - rc - np.outer((P - rc) @ n, n)
                c_r, c_d = perp(V[ring_r]).mean(0), perp(D2[ring_d]).mean(0); r_r = np.linalg.norm(perp(V[ring_r]) - c_r, axis=1).mean(); r_d = np.linalg.norm(perp(D2[ring_d]) - c_d, axis=1).mean()
                L = 1.6 * rr; fb = np.clip(1.0 - (td - t_cut) / L, 0, 1)                   # 1 at the plane, fading to 0 a little beyond: the donor flows into the retained ring's size and centre
                Pp = perp(D2); scale = 1 + fb * (r_r / max(r_d, 1e-6) - 1)
                D2 = np.where((fb > 0)[:, None], D2 - Pp + c_r + (Pp - c_d) * scale[:, None], D2)          # the perpendicular part is re-expressed about the retained ring's centre, with the ring's size, fading out along the part
                grafted = True; print(f"[repair] region {info['index']}: graft plane {t_cut * 100:+.1f} cm from the ring; ring radius retained {r_r * 100:.1f} cm, donor {r_d * 100:.1f} cm blended over {L * 100:.1f} cm")
                grafts.append({"rc": rc, "n": n, "rr": rr, "t_cut": t_cut, "index": info["index"]})
            else: print(f"[repair] region {info['index']}: no clean ring to graft onto (retained {int(ring_r.sum())} / donor {int(ring_d.sum())} vertices near the plane); using the overlapping shells")
        for i, v in enumerate(do.data.vertices): v.co = Vector(D2[i].tolist())
        if grafted:   # colours: each donor vertex takes the colour of the nearest vertex of the region it replaces (its texture there); where nothing is near, the region's median colour
            src = texture_colours(ob, idx)
            if src is not None:
                from mathutils import kdtree
                kd = kdtree.KDTree(len(idx)); [kd.insert(Vector(V[i].tolist()), q) for q, i in enumerate(idx)]; kd.balance()
                Nb = np.empty(len(V) * 3, np.float32); ob.data.vertices.foreach_get("normal", Nb); Nb = Nb.reshape(-1, 3)[idx]        # the old part's surface normals
                do.data.update(); Nd = np.empty(len(D2) * 3, np.float32); do.data.vertices.foreach_get("normal", Nd); Nd = Nd.reshape(-1, 3)
                dmax = 1.6 * rr; flat = np.array(info.get("color") or [0.35, 0.35, 0.36]); dc = np.tile(flat, (len(D2), 1)); near = 0
                for i in range(len(D2)):
                    # the donor surface lies inside or outside the old one by a few mm: among the nearest old vertices take the closest that FACES the same way (not the old part's inside lining)
                    cand = kd.find_n(Vector(D2[i].tolist()), 12)
                    pick = next((c for c in cand if c[2] < dmax and float(Nb[c[1]] @ Nd[i]) > 0.2), None) or next((c for c in cand if c[2] < dmax), None)
                    if pick is not None: dc[i] = src[pick[1]]; near += 1
                ok_tex = bake_colours_to_texture(do, dc); print(f"[repair] region {info['index']}: colours carried over for {near} of {len(D2)} donor vertices" + (" (baked into the donor's texture)" if ok_tex else " (the donor has no UVs: one flat colour)"))
        bm = bmesh.new(); bm.from_mesh(do.data); bm.verts.ensure_lookup_table()
        bmesh.ops.delete(bm, geom=[bm.verts[i] for i in np.nonzero(~keep)[0]], context="VERTS"); bm.to_mesh(do.data); bm.free(); do.name = f"repair_donor_{info['index']}"
        donors.append(do); boxes.append(info)
        print(f"[repair] region {info['index']}: donor kept {int(keep.sum())} of {len(D2)} vertices")
    # 2) delete the original hand region (the selected vertices) from the base, then join everything
    bpy.context.view_layer.objects.active = ob
    bm = bmesh.new(); bm.from_mesh(ob.data); bm.verts.ensure_lookup_table()
    bmesh.ops.delete(bm, geom=[bm.verts[i] for i in np.nonzero(delete)[0]], context="VERTS"); bm.to_mesh(ob.data); bm.free()
    if grafts:
        base_mat = [m for m in ob.data.materials][:]; 
        bpy.ops.object.select_all(action="DESELECT"); ob.select_set(True)
        for d_ in donors: d_.select_set(True)
        bpy.context.view_layer.objects.active = ob; bpy.ops.object.join(); ob = bpy.context.view_layer.objects.active
        bm = bmesh.new(); bm.from_mesh(ob.data)
        bmesh.ops.remove_doubles(bm, verts=bm.verts[:], dist=1e-6)           # the glTF importer splits vertices along texture seams: weld them (the UVs live on the face corners and stay), or every seam looks like a boundary
        bm.verts.ensure_lookup_table(); bm.edges.ensure_lookup_table(); part_slot = max(len(ob.data.materials) - 1, 0)
        for g in grafts:
            rc_, n_, rr_, tc = g["rc"], g["n"], g["rr"], g["t_cut"]
            def on_ring(v):
                p_ = np.array(v.co); t_ = (p_ - rc_) @ n_; return abs(t_ - tc) < 0.5 * rr_ and np.linalg.norm(p_ - rc_ - t_ * n_) < 2.4 * rr_
            es = [e for e in bm.edges if e.is_boundary and all(on_ring(v) for v in e.verts)]
            # the boundary edges there should form exactly two loops (the retained ring and the donor's): count the connected pieces
            seen, loops = set(), 0
            adj = {}
            for e in es:
                for v in e.verts: adj.setdefault(v.index, []).append(e)
            for e in es:
                if e.index in seen: continue
                loops += 1; stack = [e]
                while stack:
                    c = stack.pop()
                    if c.index in seen: continue
                    seen.add(c.index)
                    for v in c.verts: stack += [x for x in adj[v.index] if x.index not in seen]
            if os.environ.get("REPAIR_DEBUG"):      # what are the loops? edges, mean distance from the axis, which material (base or new part) the neighbouring face has
                comp, seen2 = [], set()
                for e in es:
                    if e.index in seen2: continue
                    stack, grp = [e], []
                    while stack:
                        c = stack.pop()
                        if c.index in seen2: continue
                        seen2.add(c.index); grp.append(c); [stack.extend(x for x in adj[v.index] if x.index not in seen2) for v in c.verts]
                    comp.append(grp)
                for grp in comp:
                    pts = np.array([np.array(v.co) for e in grp for v in e.verts]); t_ = (pts - rc_) @ n_; rad = np.linalg.norm(pts - rc_ - np.outer(t_, n_), axis=1)
                    mats = {f.material_index for e in grp for f in e.link_faces}
                    print(f"[repair]   loop: {len(grp)} edges, mean radius {rad.mean() * 100:.1f} cm (max {rad.max() * 100:.1f}), t {t_.mean() * 100:+.1f} cm, centre offset {np.linalg.norm((pts - rc_ - np.outer(t_, n_)).mean(0)) * 100:.1f} cm, material index {mats}")
            comp, seen2 = [], set()
            for e in es:
                if e.index in seen2: continue
                stack, grp = [e], []
                while stack:
                    c = stack.pop()
                    if c.index in seen2: continue
                    seen2.add(c.index); grp.append(c); [stack.extend(x for x in adj[v.index] if x.index not in seen2) for v in c.verts]
                comp.append(grp)
            def stat(grp):
                pts = np.array([np.array(v.co) for e in grp for v in e.verts]); t_ = (pts - rc_) @ n_; q = pts - rc_ - np.outer(t_, n_); return np.linalg.norm(q - q.mean(0), axis=1).mean(), {f.material_index for e in grp for f in e.link_faces}
            info_l = [(grp, *stat(grp)) for grp in comp]
            ret = [x for x in info_l if x[2] and min(x[2]) < part_slot - (len(donors) - 1)]          # loops whose faces use the base material
            new_ = [x for x in info_l if x[2] and min(x[2]) >= part_slot - (len(donors) - 1)]
            if not ret or not new_: print(f"[repair] graft {g['index']}: no retained loop or no donor loop at the plane ({len(ret)} / {len(new_)}): not bridged"); continue
            r_loop = max(ret, key=lambda x: len(x[0])); n_loop = max(new_, key=lambda x: x[1])         # the biggest retained loop; the donor's OUTER loop (a hollow donor has an inner one too)
            if len(comp) != 2: print(f"[repair] graft {g['index']}: {len(comp)} loops at the plane; bridging the largest retained one ({len(r_loop[0])} edges) to the donor's outer one ({len(n_loop[0])} edges)")
            es = r_loop[0] + n_loop[0]
            ring_ids = sorted({v.index for e in r_loop[0] for v in e.verts}); strip_col = None
            if base_cols is not None:      # the strip takes the colour of the retained ring (its vertices still carry their index in the original numbering only before the weld: use the nearest original vertex by position)
                from mathutils import kdtree
                kd0 = kdtree.KDTree(len(V)); [kd0.insert(Vector(V[i].tolist()), i) for i in range(0, len(V), 3)]; kd0.balance()
                strip_col = np.mean([base_cols[kd0.find(v.co)[1]] for v in (bm.verts[i] for i in ring_ids)], axis=0)
            res = bmesh.ops.bridge_loops(bm, edges=es, use_pairs=False, use_cyclic=False, use_merge=False, merge_factor=0.5, twist_offset=0)
            strip_slot = part_slot
            if strip_col is not None:      # a flat material for the strip (a thin band, ~2 cm): the mean colour of the retained ring
                sm = bpy.data.materials.new("repair_strip"); sm.use_nodes = True; sb = next(n for n in sm.node_tree.nodes if n.type == "BSDF_PRINCIPLED"); sb.inputs["Base Color"].default_value = (*[float(x) for x in strip_col], 1.0); sb.inputs["Roughness"].default_value = 0.6
                ob.data.materials.append(sm); strip_slot = len(ob.data.materials) - 1
            for f_ in res.get("faces", []): f_.material_index = strip_slot; f_.smooth = True
            print(f"[repair] graft {g['index']}: the two rings bridged with {len(res.get('faces', []))} faces")
        bm.normal_update(); bm.to_mesh(ob.data); bm.free()
    for info in boxes: render_crop(os.path.join(out_dir, f"after_region{info['index']}_crop.png"), info["box"])
    if not np.allclose(_R0, np.eye(3)):
        for o in [o for o in bpy.data.objects if o.type == "MESH"]: turn(o, _R0.T)                    # back to the model's own frame
    bpy.ops.object.select_all(action="SELECT"); bpy.ops.export_scene.gltf(filepath=out_glb, export_format="GLB")
    print("[repair] wrote", out_glb)
