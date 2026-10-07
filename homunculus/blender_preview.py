"""A light copy of a heavy model for the browser: blender -b --python blender_preview.py -- in.glb out.glb [target_triangles]
Pixal3D's raw shapes have millions of triangles (hundreds of MB) which a browser cannot open; the viewer gets a decimated copy (about 150k triangles) instead."""
import bpy, sys
a = sys.argv[sys.argv.index("--") + 1:]; src, out = a[0], a[1]; target = int(a[2]) if len(a) > 2 else 150000
bpy.ops.wm.read_factory_settings(use_empty=True); bpy.ops.import_scene.gltf(filepath=src)
ms = [o for o in bpy.data.objects if o.type == "MESH"]
bpy.ops.object.select_all(action="DESELECT")
for o in ms: o.select_set(True)
bpy.context.view_layer.objects.active = ms[0]
if len(ms) > 1: bpy.ops.object.join()
ob = bpy.context.view_layer.objects.active; tris = sum(len(p.vertices) - 2 for p in ob.data.polygons)
if tris > target:
    m = ob.modifiers.new("d", "DECIMATE"); m.decimate_type = "COLLAPSE"; m.ratio = target / tris; bpy.ops.object.modifier_apply(modifier="d")
bpy.ops.object.select_all(action="SELECT"); bpy.ops.export_scene.gltf(filepath=out, export_format="GLB")
print(f"[preview] {tris} -> {sum(len(p.vertices) - 2 for p in ob.data.polygons)} triangles")
