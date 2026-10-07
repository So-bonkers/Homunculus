"""Convert a GLB to another format, on demand.  blender -b --python blender_export.py -- in.glb out_dir stem fmt
fmt: fbx (rigged character or clip, animation baked, textures copied next to the file and shared), usd (same, animated), obj (static mesh + mtl + texture), stl (static mesh, no colour)."""
import bpy, sys, os
a = sys.argv[sys.argv.index("--") + 1:]; src, out_dir, stem, fmt = a[:4]
os.makedirs(out_dir, exist_ok=True); path = os.path.join(out_dir, stem + "." + fmt)
bpy.ops.wm.read_factory_settings(use_empty=True); bpy.ops.import_scene.gltf(filepath=src)
for o in [o for o in bpy.data.objects if o.type == "MESH" and len(o.data.vertices) < 500]: bpy.data.objects.remove(o, do_unlink=True)
animated = bool(bpy.data.actions)
for im in bpy.data.images:      # textures from a GLB live in memory: write them next to the export (shared by every file of the same character), then reference them
    if im.type == "IMAGE" and im.size[0] > 0 and im.users:
        im.filepath_raw = os.path.join(out_dir, (im.name if im.name.lower().endswith(".png") else im.name + ".png").replace("/", "_")); im.file_format = "PNG"
        if not os.path.exists(im.filepath_raw): im.save()
if fmt == "fbx":
    bpy.ops.export_scene.fbx(filepath=path, add_leaf_bones=False, bake_anim=animated, path_mode="RELATIVE", embed_textures=False)
elif fmt == "usd":
    bpy.ops.wm.usd_export(filepath=path, export_animation=animated, export_materials=True, export_textures_mode="NEW")
elif fmt in ("obj", "stl"):
    ms = [o for o in bpy.data.objects if o.type == "MESH"]; bpy.ops.object.select_all(action="DESELECT")
    for o in ms: o.select_set(True)
    bpy.context.view_layer.objects.active = ms[0]
    if len(ms) > 1: bpy.ops.object.join()
    ob = bpy.context.view_layer.objects.active
    for m in list(ob.modifiers): ob.modifiers.remove(m)            # a rigged mesh exports in its rest pose
    bpy.ops.object.select_all(action="DESELECT"); ob.select_set(True)
    if fmt == "obj": bpy.ops.wm.obj_export(filepath=path, export_selected_objects=True, export_materials=True, path_mode="RELATIVE")
    else: bpy.ops.wm.stl_export(filepath=path, export_selected_objects=True)
else: print("[export] unknown format", fmt); sys.exit(2)
print("[export] wrote", path)
