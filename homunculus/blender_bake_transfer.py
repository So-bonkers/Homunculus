"""Blender: carry the base-colour texture of one mesh onto another mesh with its own UV layout, by baking (selected to active).
blender -b --python blender_bake_transfer.py -- source.glb target.glb out_basecolor.png [size] [--ray 0.05]
source: the mesh with the texture (UltraTex's result, its own UV unwrap); target: the mesh whose UVs the rig was built on (the picture goes in that layout).  The two are the same surface (same shape, possibly another
vertex order and another unwrap); the ray distance (metres) only has to bridge small differences.  Writes the picture; prints the share of covered texels."""
import bpy, sys, os
from mathutils import Vector
a = [x for x in sys.argv[sys.argv.index("--") + 1:] if not x.startswith("--")]; src, tgt, out = a[:3]; size = int(a[3]) if len(a) > 3 else 4096
ray = float(sys.argv[sys.argv.index("--ray") + 1]) if "--ray" in sys.argv else 0.05
bpy.ops.wm.read_factory_settings(use_empty=True)
def load(p):
    before = set(bpy.data.objects); bpy.ops.import_scene.gltf(filepath=p); return [o for o in bpy.data.objects if o not in before and o.type == "MESH" and o.name != "Icosphere"]
S = load(src); T = load(tgt)
for o in bpy.data.objects:
    if o.type == "MESH" and o.name == "Icosphere": bpy.data.objects.remove(o, do_unlink=True)
def box(objs):
    pts = [o.matrix_world @ Vector(c) for o in objs for c in o.bound_box]; lo = Vector((min(p.x for p in pts), min(p.y for p in pts), min(p.z for p in pts))); hi = Vector((max(p.x for p in pts), max(p.y for p in pts), max(p.z for p in pts))); return lo, hi
(slo, shi), (tlo, thi) = box(S), box(T); d = (tlo + thi) / 2 - (slo + shi) / 2
print(f"[bake] source extents {[round(v, 3) for v in (shi - slo)]}, target {[round(v, 3) for v in (thi - tlo)]}, centre offset {[round(v, 4) for v in d]}")
if d.length > 1e-4:
    for o in S: o.location = o.location + d
bpy.context.view_layer.update()
img = bpy.data.images.new("baked", size, size, alpha=False); img.colorspace_settings.name = "sRGB"
for o in T:
    o.data.materials.clear(); m = bpy.data.materials.new("bake"); m.use_nodes = True; o.data.materials.append(m)
    n = m.node_tree.nodes.new("ShaderNodeTexImage"); n.image = img; m.node_tree.nodes.active = n
sc = bpy.context.scene; sc.render.engine = "CYCLES"; sc.cycles.device = "CPU"; sc.cycles.samples = 1; sc.cycles.use_denoising = False
bpy.ops.object.select_all(action="DESELECT")
for o in S: o.select_set(True)
for o in T: o.select_set(True)
bpy.context.view_layer.objects.active = T[0]
bpy.ops.object.bake(type="DIFFUSE", pass_filter={"COLOR"}, use_selected_to_active=True, max_ray_distance=ray, cage_extrusion=ray * 0.5, margin=24, margin_type="EXTEND", use_clear=True)
img.filepath_raw = out; img.file_format = "PNG"; img.save()
import numpy as np
px = np.array(img.pixels[:], dtype=np.float32).reshape(size, size, 4); cov = float((px[..., :3].sum(-1) > 0.003).mean()); print(f"[bake] wrote {out} ({size} px), non-black texels {cov * 100:.0f} %")
