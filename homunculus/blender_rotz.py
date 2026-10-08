"""Turn a GLB half a turn about the vertical axis (the multiview Pixal3D model comes out facing the other way from the single-image one).

blender -b --python blender_rotz.py -- in.glb out.glb [degrees]
"""
import bpy, sys, math
argv = sys.argv[sys.argv.index("--") + 1:]
glb_in, glb_out = argv[:2]; deg = float(argv[2]) if len(argv) > 2 else 180.0
bpy.ops.wm.read_factory_settings(use_empty=True); bpy.ops.import_scene.gltf(filepath=glb_in)
for o in list(bpy.data.objects):
    if o.type != "MESH": bpy.data.objects.remove(o, do_unlink=True)
bpy.ops.object.select_all(action="DESELECT")
for o in bpy.data.objects: o.select_set(True)
bpy.context.view_layer.objects.active = bpy.data.objects[0]
bpy.ops.object.transform_apply(location=True, rotation=True, scale=True)
for o in bpy.data.objects:
    o.rotation_mode = "XYZ"          # glTF imports use quaternions: the Euler angle below only counts in this mode
    o.rotation_euler = (0.0, 0.0, math.radians(deg))
bpy.ops.object.transform_apply(location=True, rotation=True, scale=True)
bpy.ops.export_scene.gltf(filepath=glb_out, export_format="GLB", export_yup=True)
print(f"[rotz] turned {glb_in} by {deg} degrees")
