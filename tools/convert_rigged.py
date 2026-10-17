"""blender -b --python tools/convert_rigged.py -- <model.glb|fbx> <out.glb> <out.fbx> [textures_dir] [thumbnail.png] [valorant]: a rigged character to a GLB and an FBX the app can use, with missing pictures attached from a folder; a front render as thumbnail.
With "valorant": the game rig (Pelvis, Spine1-4, L_/R_ limbs and fingers, twist, cloth and face bones) is rebuilt as Make-It-Animatable's 52-bone Mixamo skeleton (mixamorig:Hips ... fingers, three joints each): the bones sit at the same joints, the weights of every other bone go to its
nearest ancestor among the 52, the model is turned to face -Y and moved so its hips are at the origin, as the app's own rigs are.  Every tool that expects Mixamo names (the hand layer, the retargeting, the library pictures) then works on it unchanged."""
import bpy, sys, os, math
from mathutils import Vector
src, out_glb, out_fbx, tex_dir, thumb, skel = (sys.argv[sys.argv.index("--") + 1:] + ["", "", ""])[:6]
bpy.ops.wm.read_factory_settings(use_empty=True)
if src.lower().endswith(".blend"): bpy.ops.wm.open_mainfile(filepath=src)
else: (bpy.ops.import_scene.gltf if src.lower().endswith((".glb", ".gltf")) else bpy.ops.import_scene.fbx)(filepath=src)
for o in [o for o in bpy.data.objects if o.type == "MESH" and o.name == "Icosphere"]: bpy.data.objects.remove(o, do_unlink=True)
if tex_dir:
    tex_dir, _, explicit = tex_dir.partition("|"); files = {f.lower(): os.path.join(tex_dir, f) for f in os.listdir(tex_dir)}; byname = {f: os.path.join(tex_dir, f) for f in os.listdir(tex_dir)}
    for m in bpy.data.materials:                                                    # pictures a material points to but the file does not carry (a .blend or FBX with paths from the author's machine)
        for n in (m.node_tree.nodes if m.node_tree else []):
            if n.type == "TEX_IMAGE" and (n.image is None or not n.image.has_data):
                nm = (n.image.name if n.image else "").lower().split(".tga")[0].split(".png")[0]; hit = next((p for f, p in files.items() if f.startswith(nm) and nm), None)
                if hit: n.image = bpy.data.images.load(hit); n.image.pack(); print("texture attached", n.image.name)
    def body_file():
        c = [f for f in byname if f.lower().endswith(("_df.png", "_df.tga.png")) and not any(k in f.lower() for k in ("hair", "eye", "ability", "rocket", "prop", "weapon"))]; return byname[sorted(c)[0]] if c else None
    def hair_file():
        c = [f for f in byname if "hair" in f.lower() and "_df" in f.lower()]; return byname[sorted(c)[0]] if c else None
    chosen = {}                                                                     # explicit: "m0=file,m1=file": a mesh (by its order) gets that picture on all its materials
    for it in [x for x in explicit.split(",") if x]: k_, f_ = it.split("="); chosen[int(k_[1:])] = os.path.join(tex_dir, f_)
    meshes_ = [o for o in bpy.data.objects if o.type == "MESH" and o.data.materials]
    for mi, o in enumerate(meshes_):
        for m in o.data.materials:
            if m is None or not m.node_tree: continue
            bsdf = next((n for n in m.node_tree.nodes if n.type == "BSDF_PRINCIPLED"), None)
            if bsdf is None: continue
            lk = bsdf.inputs["Base Color"].links
            if mi not in chosen and lk and lk[0].from_node.type == "TEX_IMAGE" and lk[0].from_node.image is not None and lk[0].from_node.image.has_data: continue          # already has its colour picture (a material that goes through a node group does not count: the exporter cannot follow it)
            low = m.name.lower(); path = chosen.get(mi) or (hair_file() if "hair" in low else None if "eye" in low else body_file())
            if path and bsdf:
                t = m.node_tree.nodes.new("ShaderNodeTexImage"); t.image = bpy.data.images.load(path); t.image.pack(); m.node_tree.links.new(t.outputs["Color"], bsdf.inputs["Base Color"]); print("texture set", m.name, "<-", os.path.basename(path))
def to_mixamo():
    import mathutils
    from mathutils import Matrix
    A = next(o for o in bpy.data.objects if o.type == "ARMATURE"); H = {b.name.replace(" ", "_"): b.head_local.copy() for b in A.data.bones}; P = {b.name.replace(" ", "_"): (b.parent.name.replace(" ", "_") if b.parent else None) for b in A.data.bones}; meshes = [o for o in bpy.data.objects if o.type == "MESH"]
    SIDES = (("Left", "L"), ("Right", "R")); parent = {"Spine": "Hips", "Spine1": "Spine", "Spine2": "Spine1", "Neck": "Spine2", "Head": "Neck"}
    src = {"Hips": "Pelvis", "Spine": "Spine1", "Spine1": "Spine2", "Spine2": "Spine3", "Neck": "Neck", "Head": "Head"}
    for S, s_ in SIDES:
        for n, v, par in (("Shoulder", "Clavicle", "Spine2"), ("Arm", "Shoulder", f"{S}Shoulder"), ("ForeArm", "Elbow", f"{S}Arm"), ("Hand", "Hand", f"{S}ForeArm"), ("UpLeg", "Hip", "Hips"), ("Leg", "Knee", f"{S}UpLeg"), ("Foot", "Foot", f"{S}Leg"), ("ToeBase", "Toe", f"{S}Foot")):
            src[S + n] = f"{s_}_{v}"; parent[S + n] = par
        for f in ("Thumb", "Index", "Middle", "Ring", "Pinky"):
            for j in (1, 2, 3): src[f"{S}Hand{f}{j}"] = f"{s_}_{f}{j}"; parent[f"{S}Hand{f}{j}"] = f"{S}Hand" if j == 1 else f"{S}Hand{f}{j - 1}"
    miss = [v for v in src.values() if v not in H]
    if miss: raise SystemExit(f"to_mixamo: the rig lacks {miss}")
    back = {v: k for k, v in src.items()}
    W = A.matrix_world.copy(); lh, rh = W @ H["L_Hip"], W @ H["R_Hip"]; fwd = (lh - rh).cross(Vector((0, 0, 1))); yaw = -math.pi / 2 - math.atan2(fwd.y, fwd.x)                  # the way the model faces (left hip - right hip) x up, turned to -Y
    print(f"to_mixamo: faces {math.degrees(math.atan2(fwd.y, fwd.x)):.0f} degrees, turned by {math.degrees(yaw):.0f}")
    Rz = Matrix.Rotation(yaw, 4, "Z"); hips = Rz @ (W @ H["Pelvis"]); T = Matrix.Translation(-hips); unit = 0.01 if abs((W @ H["Pelvis"]).z) > 20 else 1.0; X = Matrix.Scale(unit, 4) @ T @ Rz          # the model's world -> new: faces -Y, hips at the origin, in metres (a model made in centimetres, Tejo: 214 tall, is scaled by 0.01)
    head = {k: X @ (W @ H[v]) for k, v in src.items()}
    def child_head(k):
        kids = [c for c, p in parent.items() if p == k and not (k == "Hips" and c != "Spine") and not (k == "Spine2" and c != "Neck")]
        return head[kids[0]] if kids else None
    tail = {}
    for k in src:
        c = child_head(k)
        if k == "Hand": c = (head[k.replace("Hand", "HandMiddle1")])
        if c is None:
            p = head[parent[k]]; d = head[k] - p
            if k == "Head": d = Vector((0, 0, 1)) * max(d.length, 0.1) * 1.0
            elif k == "ToeBase": d = Vector((0, -1, 0)) * max(d.length, 0.04) * 0.8
            c = head[k] + d * 0.8
        tail[k] = c
    # the new armature
    for o in meshes:                                                         # the mesh in the new world, no parent, no armature modifier
        mw = o.matrix_world.copy(); o.parent = None; o.data.transform(X @ mw); o.matrix_world = Matrix.Identity(4)
        for m in [m for m in o.modifiers if m.type == "ARMATURE"]: o.modifiers.remove(m)
    ad = bpy.data.armatures.new("Armature"); N = bpy.data.objects.new("Armature", ad); bpy.context.scene.collection.objects.link(N); bpy.context.view_layer.objects.active = N; bpy.ops.object.mode_set(mode="EDIT")
    PFX = "mixamorig:"
    for k in src:
        e = ad.edit_bones.new(PFX + k); e.head = head[k]; e.tail = tail[k]
        if (e.tail - e.head).length < 1e-4: e.tail = e.head + Vector((0, 0, 0.01))
    for k, p in parent.items(): ad.edit_bones[PFX + k].parent = ad.edit_bones[PFX + p]; ad.edit_bones[PFX + k].use_connect = False
    bpy.ops.object.mode_set(mode="OBJECT")
    def target(nm):                                                          # the nearest ancestor (or itself) that is one of the 52
        while nm is not None:
            if nm in back: return back[nm]
            nm = P.get(nm)
        return "Hips"
    for o in meshes:
        old = {g.index: g.name for g in o.vertex_groups}; new = {}; acc = [dict() for _ in o.data.vertices]
        for v in o.data.vertices:
            for g in v.groups:
                nm = (old.get(g.group) or "").replace(" ", "_")
                if nm in P: t = target(nm); acc[v.index][t] = acc[v.index].get(t, 0.0) + g.weight
        for g in list(o.vertex_groups): o.vertex_groups.remove(g)
        for k in src: new[k] = o.vertex_groups.new(name=PFX + k)
        for i, d in enumerate(acc):
            tot = sum(d.values())
            for t, w in d.items(): new[t].add([i], w / tot if tot > 0 else 0.0, "REPLACE")
        o.parent = N; m = o.modifiers.new("Armature", "ARMATURE"); m.object = N
    bpy.data.objects.remove(A, do_unlink=True)
    print(f"to_mixamo: {len(src)} bones, hips at the origin, faces -Y")
if skel == "valorant": to_mixamo()
for m in bpy.data.materials:                                                          # the viewport (and the thumbnail) shows the ACTIVE picture node: make it the one that feeds the base colour (not a normal map or a placeholder)
    if m.node_tree:
        for n in m.node_tree.nodes:
            if n.type == "BSDF_PRINCIPLED" and n.inputs["Base Color"].links and n.inputs["Base Color"].links[0].from_node.type == "TEX_IMAGE": m.node_tree.nodes.active = n.inputs["Base Color"].links[0].from_node
bpy.ops.object.select_all(action="SELECT")
bpy.ops.export_scene.gltf(filepath=out_glb, export_format="GLB", use_selection=True)
bpy.ops.export_scene.fbx(filepath=out_fbx, use_selection=True, object_types={"ARMATURE", "MESH"}, add_leaf_bones=False, path_mode="COPY", embed_textures=True)
if thumb:                                                                    # a front render
    ms = [o for o in bpy.data.objects if o.type == "MESH"]; pts = [o.matrix_world @ Vector(c) for o in ms for c in o.bound_box]; lo = Vector(map(min, *[tuple(p) for p in pts])); hi = Vector(map(max, *[tuple(p) for p in pts])); mid = (lo + hi) / 2; h = hi.z - lo.z
    sc = bpy.context.scene; sc.render.engine = "BLENDER_WORKBENCH"; sc.render.resolution_x, sc.render.resolution_y = 768, 1024; sh = sc.display.shading; sh.light = "STUDIO"; sh.color_type = "TEXTURE"; sc.view_settings.view_transform = "Standard"
    w = bpy.data.worlds.new("w"); w.use_nodes = False; w.color = (0.2, 0.2, 0.22); sc.world = w
    cam = bpy.data.objects.new("c", bpy.data.cameras.new("c")); sc.collection.objects.link(cam); sc.camera = cam; cam.data.lens = 60; fy = -1; cam.location = Vector((mid.x, mid.y + fy * h * 2.1, mid.z)); cam.rotation_euler = (math.radians(90), 0, math.pi if fy > 0 else 0)
    sc.render.filepath = thumb; bpy.ops.render.render(write_still=True)
print("converted", out_glb)
