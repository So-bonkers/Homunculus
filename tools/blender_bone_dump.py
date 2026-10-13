"""Blender: world position of the main bones of a rigged character for every frame of its action (input of tools/align_camera.py).

    blender -b --python tools/blender_bone_dump.py -- <character.fbx> <out.npz>"""
import bpy, sys, numpy as np
f, out = sys.argv[sys.argv.index("--")+1:][:2]
bpy.ops.wm.read_factory_settings(use_empty=True); bpy.ops.import_scene.fbx(filepath=f)
A = next(o for o in bpy.data.objects if o.type=="ARMATURE"); sc=bpy.context.scene; P=A.pose.bones
names=["Hips","Spine2","Head","LeftUpLeg","RightUpLeg","LeftLeg","RightLeg","LeftFoot","RightFoot","LeftArm","RightArm","LeftForeArm","RightForeArm","LeftHand","RightHand"]
f0,f1=[int(round(v)) for v in A.animation_data.action.frame_range]; res=[]
for fr in range(f0,f1+1):
    sc.frame_set(fr); bpy.context.view_layer.update(); M=A.matrix_world
    res.append([tuple(M@P["mixamorig:"+n].head) for n in names])
np.savez(out, J=np.array(res), names=names); print("BONES done", len(res))
