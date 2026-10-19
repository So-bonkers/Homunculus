"""Blender: put a base-colour picture on a mesh that already has UVs and a material, and write a GLB.
blender -b --python blender_set_texture.py -- mesh.glb basecolor.png out.glb
The mesh's material keeps its other settings; its base colour is the picture (a new one is made when the mesh has none)."""
import bpy, sys
glb, png, out = sys.argv[sys.argv.index("--") + 1:][:3]
bpy.ops.wm.read_factory_settings(use_empty=True); bpy.ops.import_scene.gltf(filepath=glb)
for o in [o for o in bpy.data.objects if o.type == "MESH" and o.name == "Icosphere"]: bpy.data.objects.remove(o, do_unlink=True)
img = bpy.data.images.load(png); img.pack(); n = 0
for o in bpy.data.objects:
    if o.type != "MESH": continue
    if not o.data.materials: o.data.materials.append(bpy.data.materials.new("m"))
    for m in o.data.materials:
        m.use_nodes = True; bsdf = next((x for x in m.node_tree.nodes if x.type == "BSDF_PRINCIPLED"), None)
        if bsdf is None: continue
        lk = bsdf.inputs["Base Color"].links
        node = lk[0].from_node if lk and lk[0].from_node.type == "TEX_IMAGE" else m.node_tree.nodes.new("ShaderNodeTexImage")
        node.image = img; m.node_tree.links.new(node.outputs["Color"], bsdf.inputs["Base Color"]); n += 1
bpy.ops.export_scene.gltf(filepath=out, export_format="GLB"); print("[settex] base colour set on", n, "material(s) ->", out)
