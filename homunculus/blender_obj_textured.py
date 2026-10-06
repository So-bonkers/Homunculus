"""OBJ without its .mtl -> textured GLB: materials 'body' and 'hairs' get <name>_albedo / _normal from the textures folder, Y-up like every glTF.
blender -b --python blender_obj_textured.py -- model.obj textures_dir out.glb"""
import bpy, sys, os
src, tex, out = sys.argv[sys.argv.index("--") + 1:][:3]
bpy.ops.wm.read_factory_settings(use_empty=True); bpy.ops.wm.obj_import(filepath=src)
for o in bpy.data.objects:
    if o.type != "MESH": continue
    for slot in o.material_slots:
        m = slot.material
        if m is None: continue
        m.use_nodes = True; nt = m.node_tree; bsdf = next(n for n in nt.nodes if n.type == "BSDF_PRINCIPLED")
        base = next((f for f in (m.name.split(".")[0] + "_albedo.jpg", m.name.split(".")[0] + "_albedo.jpeg") if os.path.exists(os.path.join(tex, f))), None)
        if base:
            t = nt.nodes.new("ShaderNodeTexImage"); t.image = bpy.data.images.load(os.path.join(tex, base)); nt.links.new(t.outputs["Color"], bsdf.inputs["Base Color"])
        print("[mat]", m.name, base)
bpy.ops.export_scene.gltf(filepath=out, export_format="GLB")
