"""Blender: put a base-colour texture on an animated character (same UVs) and export GLB + FBX with the animation kept.
blender -b --python anim_tex_swap.py -- clip.glb basecolor.png out.glb out.fbx|-   ("-": no FBX)"""
import bpy, sys
glb, png, out_glb, out_fbx = sys.argv[sys.argv.index("--") + 1:][:4]
bpy.ops.wm.read_factory_settings(use_empty=True); bpy.ops.import_scene.gltf(filepath=glb)
img = bpy.data.images.load(png); n = 0
for o in bpy.data.objects:
    if o.type != "MESH": continue
    for m in o.data.materials:
        if not m or not m.use_nodes: continue
        bsdf = [x for x in m.node_tree.nodes if x.type == "BSDF_PRINCIPLED"]
        if not bsdf or not bsdf[0].inputs["Base Color"].links: continue
        node = bsdf[0].inputs["Base Color"].links[0].from_node
        while node.type != "TEX_IMAGE" and node.inputs and node.inputs[0].links: node = node.inputs[0].links[0].from_node
        if node.type == "TEX_IMAGE": node.image = img; n += 1
bpy.ops.export_scene.gltf(filepath=out_glb, export_format="GLB", export_animations=True)
if out_fbx != "-": bpy.ops.export_scene.fbx(filepath=out_fbx, add_leaf_bones=False, bake_anim=True, path_mode="COPY", embed_textures=True)
print("[animtex] replaced", n, "->", out_glb)
