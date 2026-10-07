"""Region repair, Blender side.  Two modes:

blender -b --python blender_repair.py -- analyse base.glb strokes.json out_dir
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
        c = np.median(buf[v, u, :3], axis=0)                                              # Image.pixels are already scene-linear, which is what a material's Base Color takes
        return [float(x) for x in np.clip(c, 0, 1)]
    except Exception as e:
        print(f"[repair] region colour not found ({type(e).__name__}); using grey"); return [0.35, 0.35, 0.36]


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
elif mode == "hands":
    """blender -b --python blender_repair.py -- hands base.glb strokes.json : brush strokes covering both hands of a T/A-posed figure (the outer ~10.5 % of the
    height at each side). The same rule as the web viewer's 'Select hands' button; used for tests and as the server-side fallback."""
    base, out_p = argv[1:3]; ob = load(base); V = verts(ob); lo, hi = V.min(0), V.max(0); cx = (lo[0] + hi[0]) / 2; height = hi[2] - lo[2]
    lim = (hi[0] - lo[0]) / 2 - 0.105 * height; sel = V[np.abs(V[:, 0] - cx) > lim]; cell = 0.02
    keys = {tuple(k) for k in np.floor(sel / cell).astype(int)}; strokes = []
    for k in keys:
        c = (np.array(k) + 0.5) * cell; strokes.append([float(c[0]), float(c[2]), float(-c[1]), cell * 0.8])      # Blender -> glTF (x, z, -y)
    json.dump({"strokes": strokes}, open(out_p, "w")); print(f"[repair] {len(sel)} hand vertices -> {len(strokes)} strokes")

# ---------------------------------------------------------------------------------------------------------------- analyse
elif mode == "analyse":
    base, strokes_p, out_dir = argv[1:4]; os.makedirs(out_dir, exist_ok=True)
    ob = load(base); V = verts(ob); E = edges(ob)
    S = np.array(json.load(open(strokes_p))["strokes"], np.float32).reshape(-1, 4)
    S[:, :3] = np.stack([S[:, 0], -S[:, 2], S[:, 1]], 1)                    # glTF (x, y, z) -> Blender (x, -z, y)
    mask = np.zeros(len(V), bool)
    for i in range(0, len(S), 64):
        c = S[i:i + 64]; d = np.linalg.norm(V[:, None, :] - c[None, :, :3], axis=2); mask |= (d <= c[None, :, 3]).any(1)
    print(f"[repair] {int(mask.sum())} of {len(V)} vertices inside {len(S)} brush strokes")
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
        R = Vc[ring_idx]; rc = R.mean(0); n = cen - rc
        n = n / (np.linalg.norm(n) + 1e-9); rr = float(np.linalg.norm(R - rc - np.outer((R - rc) @ n, n), axis=1).mean())
        half = float(max(hi[0] - lo[0], hi[2] - lo[2]) / 2 * 1.35 + 0.02); box = [float((lo[0] + hi[0]) / 2), float((lo[2] + hi[2]) / 2), half]
        info = {"index": k, "n_verts": int(len(idx)), "bbox": [lo.tolist(), hi.tolist()], "centroid": cen.tolist(), "ring": {"center": rc.tolist(), "normal": n.tolist(), "radius": rr},
                "box": box, "mask": f"mask{k}.npy", "crop": f"region{k}_crop.png"}
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
    jobs = json.load(open(regs_p)); ob = load(base); V = verts(ob)
    # 1) every region's donor, mapped, snapped to the wrist, clipped; collected before anything is deleted
    donors = []; delete = np.zeros(len(V), bool); boxes = []
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
                g = min(1.3, max(0.77, perp(Vk[za], cb) / max(perp(D2[zd], cb), 1e-6))); D2 = cb + (D2 - cb) * g
                print(f"[repair] region {info['index']}: donor scale x{f:.3f}; arm ends {abs(t_end) * 100:.1f} cm from the wrist ring, stub slid {overlap * 100:.1f} cm over it, "
                      f"centred ({np.linalg.norm(cb - cd) * 100:.1f} cm shift, x{g:.2f} size)")
        t = (D2 - rc) @ n; keep = np.ones(len(D2), bool)                      # the donor starts inside the arm by construction: nothing to clip
        for i, v in enumerate(do.data.vertices): v.co = Vector(D2[i].tolist())
        bm = bmesh.new(); bm.from_mesh(do.data); bm.verts.ensure_lookup_table()
        bmesh.ops.delete(bm, geom=[bm.verts[i] for i in np.nonzero(~keep)[0]], context="VERTS"); bm.to_mesh(do.data); bm.free(); do.name = f"repair_donor_{info['index']}"
        donors.append(do); boxes.append(info)
        print(f"[repair] region {info['index']}: donor kept {int(keep.sum())} of {len(D2)} vertices")
    # 2) delete the original hand region (the selected vertices) from the base, then join everything
    bpy.context.view_layer.objects.active = ob
    bm = bmesh.new(); bm.from_mesh(ob.data); bm.verts.ensure_lookup_table()
    bmesh.ops.delete(bm, geom=[bm.verts[i] for i in np.nonzero(delete)[0]], context="VERTS"); bm.to_mesh(ob.data); bm.free()
    bpy.ops.object.select_all(action="SELECT"); bpy.ops.export_scene.gltf(filepath=out_glb, export_format="GLB")
    for info in boxes: render_crop(os.path.join(out_dir, f"after_region{info['index']}_crop.png"), info["box"])
    print("[repair] wrote", out_glb)
