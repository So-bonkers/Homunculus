"""Export a textured GLB as OBJ + MTL + base-colour PNG for Mixamo (which rejects Blender's FBX 7.4).

blender -b --python blender_obj_export.py -- in.glb out_dir
Writes out_dir/character.obj, character.mtl (relative map_Kd) and out_dir/Image_0.png (the base-colour texture only).
"""
import bpy, sys, os, shutil
glb, out = sys.argv[sys.argv.index("--") + 1:][:2]
os.makedirs(out, exist_ok=True)
bpy.ops.wm.read_factory_settings(use_empty=True)
bpy.ops.import_scene.gltf(filepath=glb)
for o in list(bpy.data.objects):
    if o.type != "MESH": bpy.data.objects.remove(o, do_unlink=True)
meshes = [o for o in bpy.data.objects if o.type == "MESH"]
bpy.ops.object.select_all(action="DESELECT")
for o in meshes: o.select_set(True)
bpy.context.view_layer.objects.active = meshes[0]
bpy.ops.object.transform_apply(location=True, rotation=True, scale=True)
tex = None
for o in meshes:
    for m in o.data.materials:
        for n in (m.node_tree.nodes if m and m.use_nodes else []):
            if n.type == "BSDF_PRINCIPLED" and n.inputs["Base Color"].links:
                src = n.inputs["Base Color"].links[0].from_node
                if src.type == "TEX_IMAGE" and src.image: tex = src.image
if tex is None: raise SystemExit("no base-colour texture found on the mesh")
png = os.path.join(out, "Image_0.png"); tex.filepath_raw = png; tex.file_format = "PNG"; tex.save()
obj = os.path.join(out, "character.obj")
bpy.ops.wm.obj_export(filepath=obj, export_selected_objects=True, export_materials=False, export_uv=True, export_normals=True)
with open(os.path.join(out, "character.mtl"), "w") as f:       # hand-written MTL: one material, texture next to the OBJ
    f.write("newmtl character\nKa 1 1 1\nKd 1 1 1\nKs 0 0 0\nd 1\nillum 1\nmap_Kd Image_0.png\n")
txt = open(obj).read().split("\n")                              # point the OBJ at the MTL and its single material
head = ["mtllib character.mtl"]; body = []; used = False
for l in txt:
    if l.startswith(("mtllib", "usemtl")): continue
    if l.startswith("f ") and not used: body.append("usemtl character"); used = True
    body.append(l)
open(obj, "w").write("\n".join(head + body))
print("[objzip] wrote", obj)
