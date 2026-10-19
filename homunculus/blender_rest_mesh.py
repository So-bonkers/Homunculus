"""Blender: the mesh of a rigged GLB in the rest pose of its rig, alone (no armature, no skin), written as a GLB.
blender -b --python blender_rest_mesh.py -- rigged.glb out_mesh.glb
UltraTex paints six views of a mesh: it must see the surfaces that will be seen once the rig moves, so it is given the mesh as the rig holds it at rest (Make-It-Animatable's rest pose has the arms away from the body)
and not the A-posed mesh the rig was built from (whose armpits and sides are hidden by the arms).  UVs are the rig's own."""
import bpy, sys
src, out = sys.argv[sys.argv.index("--") + 1:][:2]
bpy.ops.wm.read_factory_settings(use_empty=True); bpy.ops.import_scene.gltf(filepath=src)
for o in [o for o in bpy.data.objects if o.type == "MESH" and o.name == "Icosphere"]: bpy.data.objects.remove(o, do_unlink=True)
ms = [o for o in bpy.data.objects if o.type == "MESH"]
for arm in [o for o in bpy.data.objects if o.type == "ARMATURE"]:
    if arm.animation_data: arm.animation_data.action = None
    for pb in arm.pose.bones: pb.matrix_basis.identity()
bpy.context.view_layer.update()
bpy.ops.object.select_all(action="DESELECT")
for o in ms:
    o.select_set(True)
    for m in [m for m in o.modifiers if m.type == "ARMATURE"]:
        bpy.context.view_layer.objects.active = o; bpy.ops.object.modifier_apply(modifier=m.name)       # bake the (rest) deformation into the vertices
    o.parent = None; o.matrix_world = o.matrix_world.copy()
for o in [o for o in bpy.data.objects if o.type != "MESH"]: bpy.data.objects.remove(o, do_unlink=True)
bpy.ops.export_scene.gltf(filepath=out, export_format="GLB", use_selection=False, export_skins=False, export_animations=False)
print("[rest] wrote", out)
