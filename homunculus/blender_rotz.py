"""Turn a GLB about the vertical axis. The multiview Pixal3D model does NOT always come out facing the same way (the ChatGPT sheets gave +y, a generated sheet gave -y), so a fixed half turn is
wrong half the time; "auto" measures where the toes point and turns half a turn only when they point +y (the pipeline's front is -y: Pixal3D single-image meshes face -y).

blender -b --python blender_rotz.py -- in.glb out.glb [degrees|auto]
"""
import bpy, sys, math
argv = sys.argv[sys.argv.index("--") + 1:]
glb_in, glb_out = argv[:2]; mode = argv[2] if len(argv) > 2 else "180"
bpy.ops.wm.read_factory_settings(use_empty=True); bpy.ops.import_scene.gltf(filepath=glb_in)
for o in list(bpy.data.objects):
    if o.type != "MESH": bpy.data.objects.remove(o, do_unlink=True)
bpy.ops.object.select_all(action="DESELECT")
for o in bpy.data.objects: o.select_set(True)
bpy.context.view_layer.objects.active = bpy.data.objects[0]
bpy.ops.object.transform_apply(location=True, rotation=True, scale=True)
def toes_ahead():
    """+1 when the toes point +y, -1 when they point -y, 0 when it cannot tell (the foot barely sticks out)."""
    import numpy as np
    P = []
    for o in bpy.data.objects:
        V = np.empty(len(o.data.vertices) * 3, np.float32); o.data.vertices.foreach_get("co", V); P.append(V.reshape(-1, 3))
    W = np.concatenate(P); zmin, zmax = W[:, 2].min(), W[:, 2].max(); H = zmax - zmin
    foot = W[W[:, 2] < zmin + 0.04 * H]; shin = W[(W[:, 2] > zmin + 0.12 * H) & (W[:, 2] < zmin + 0.25 * H)]
    if len(foot) < 20 or len(shin) < 20: return 0, 0.0, 0.0
    c = shin[:, 1].mean(); fwd, bwd = foot[:, 1].max() - c, c - foot[:, 1].min()
    return (0 if max(fwd, bwd) < 1.3 * min(fwd, bwd) else (1 if fwd > bwd else -1)), fwd, bwd


if mode == "auto":
    d, fwd, bwd = toes_ahead(); deg = 180.0 if d == 1 else 0.0
    print(f"[rotz] toes ahead {fwd:.3f} m, behind {bwd:.3f} m -> " + ("pointing +y: turned half a turn" if d == 1 else "pointing -y: left as it is" if d == -1 else "cannot tell: left as it is"))
else: deg = float(mode)
for o in bpy.data.objects:
    o.rotation_mode = "XYZ"          # glTF imports use quaternions: the Euler angle below only counts in this mode
    o.rotation_euler = (0.0, 0.0, math.radians(deg))
bpy.ops.object.transform_apply(location=True, rotation=True, scale=True)
bpy.ops.export_scene.gltf(filepath=glb_out, export_format="GLB", export_yup=True)
print(f"[rotz] turned {glb_in} by {deg} degrees")
