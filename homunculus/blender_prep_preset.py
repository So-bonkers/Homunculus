"""Clean a downloaded rigged character for UniMate: keep the armature + skinned meshes only, apply the scene scale, export an FBX.
blender -b --python blender_prep_preset.py -- in.glb out.fbx"""
import bpy, sys
src, out = sys.argv[sys.argv.index("--") + 1:][:2]
bpy.ops.wm.read_factory_settings(use_empty=True); bpy.ops.import_scene.gltf(filepath=src)
arm = next(o for o in bpy.data.objects if o.type == "ARMATURE")
keep = {arm.name} | {o.name for o in bpy.data.objects if o.type == "MESH" and any(m.type == "ARMATURE" for m in o.modifiers)}
for o in list(bpy.data.objects):
    if o.name not in keep: bpy.data.objects.remove(o, do_unlink=True)
for o in bpy.data.objects: o.parent = None if o.type == "ARMATURE" else o.parent
bpy.ops.object.select_all(action="SELECT"); bpy.ops.object.transform_apply(location=False, rotation=True, scale=True)
for a in list(bpy.data.actions): bpy.data.actions.remove(a)
print("[prep] kept", sorted(keep))
bpy.ops.export_scene.fbx(filepath=out, use_selection=True, add_leaf_bones=False, bake_anim=False)
