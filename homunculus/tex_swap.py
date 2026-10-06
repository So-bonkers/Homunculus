"""Blender: replace the base-colour image of a rigged FBX with a new one (same UVs) and export FBX + GLB.
blender -b --python tex_swap.py -- rigged.fbx basecolor.png out.fbx"""
import bpy, sys
fbx, png, out = sys.argv[sys.argv.index("--") + 1:][:3]
bpy.ops.wm.read_factory_settings(use_empty=True); bpy.ops.import_scene.fbx(filepath=fbx)
img = bpy.data.images.load(png); n = 0
for o in bpy.data.objects:
    if o.type != "MESH": continue
    for m in o.data.materials:
        bsdf = [x for x in m.node_tree.nodes if x.type == "BSDF_PRINCIPLED"]
        if not bsdf or not bsdf[0].inputs["Base Color"].links: continue
        node = bsdf[0].inputs["Base Color"].links[0].from_node
        if node.type == "TEX_IMAGE": node.image = img; n += 1
bpy.ops.export_scene.fbx(filepath=out, add_leaf_bones=False, bake_anim=False, path_mode="COPY", embed_textures=True)
bpy.ops.export_scene.gltf(filepath=out[:-4] + ".glb", export_format="GLB")
print("[texswap] replaced", n, "->", out)
