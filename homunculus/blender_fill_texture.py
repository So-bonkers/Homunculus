"""Helpers for stages/texfill.py (fill the texels no view painted).

blender -b --python blender_fill_texture.py -- prep  in.glb out_prefix [size]     writes <out_prefix>_pos.npy (size x size x 3, the 3D position of every texel), <out_prefix>_mask.npy (texels inside a UV island)
blender -b --python blender_fill_texture.py -- apply in.glb texture.png out.glb    puts texture.png in as the base colour image and exports the glb
"""
import bpy, sys, os, numpy as np

argv = sys.argv[sys.argv.index("--") + 1:]
mode, glb_in = argv[0], argv[1]
bpy.ops.wm.read_factory_settings(use_empty=True)
bpy.ops.import_scene.gltf(filepath=glb_in)
ob = [o for o in bpy.data.objects if o.type == "MESH" and o.data.materials][0]          # (the importer adds a bone-shape helper mesh without material to rigged files)
for o in list(bpy.data.objects):
    if o is not ob: bpy.data.objects.remove(o, do_unlink=True)
bpy.context.view_layer.objects.active = ob; ob.select_set(True)
bpy.ops.object.transform_apply(location=True, rotation=True, scale=True)
me = ob.data
mat = me.materials[0]; nt = mat.node_tree
bsdf = [n for n in nt.nodes if n.type == "BSDF_PRINCIPLED"][0]
base_tex = bsdf.inputs["Base Color"].links[0].from_node
while base_tex.type != "TEX_IMAGE": base_tex = [l.from_node for l in base_tex.inputs[0].links][0]


def to_np(img, ch=4):
    a = np.empty(len(img.pixels), np.float32); img.pixels.foreach_get(a); return a.reshape(img.size[1], img.size[0], 4)[::-1]       # top row first


if mode == "prep":
    out, size = argv[2], int(argv[3]) if len(argv) > 3 else 1024
    me.materials.clear()
    m2 = bpy.data.materials.new("posbake"); m2.use_nodes = True; n2 = m2.node_tree; n2.nodes.clear()
    geo = n2.nodes.new("ShaderNodeNewGeometry"); em = n2.nodes.new("ShaderNodeEmission"); outn = n2.nodes.new("ShaderNodeOutputMaterial")
    n2.links.new(geo.outputs["Position"], em.inputs[0]); n2.links.new(em.outputs[0], outn.inputs["Surface"]); me.materials.append(m2)
    img = bpy.data.images.new("pos", size, size, alpha=True, float_buffer=True); img.colorspace_settings.name = "Non-Color"
    tn = n2.nodes.new("ShaderNodeTexImage"); tn.image = img; n2.nodes.active = tn
    sc = bpy.context.scene; sc.render.engine = "CYCLES"; sc.cycles.samples = 1; sc.cycles.device = "CPU"; sc.render.bake.margin = max(2, size // 256)
    bpy.ops.object.bake(type="EMIT", use_clear=True, margin=sc.render.bake.margin)
    a = to_np(img)
    np.save(out + "_pos.npy", a[..., :3].astype(np.float32)); np.save(out + "_mask.npy", np.abs(a[..., :3]).sum(-1) > 0)       # texels the bake never touched stay exactly 0
    print(f"[texfill] baked positions {size}x{size}, {int((np.abs(a[..., :3]).sum(-1) > 0).sum())} texels in islands")
elif mode == "apply":
    png, out = argv[2], argv[3]
    img = bpy.data.images.load(png); img.colorspace_settings.name = "sRGB"; img.pack()
    base_tex.image = img
    bpy.ops.export_scene.gltf(filepath=out, export_format="GLB", export_yup=True)
    print("[texfill] wrote", out)
