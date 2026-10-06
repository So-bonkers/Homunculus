import bpy, sys, math
from mathutils import Vector
fbx=sys.argv[sys.argv.index("--")+1]; out=sys.argv[sys.argv.index("--")+2]
bpy.ops.wm.read_factory_settings(use_empty=True)
bpy.ops.import_scene.fbx(filepath=fbx)
arm=[o for o in bpy.data.objects if o.type=="ARMATURE"][0]; meshes=[o for o in bpy.data.objects if o.type=="MESH"]
print("OBJ",[(o.name,o.type) for o in bpy.data.objects]); print("BONES",len(arm.data.bones)); print("BONENAMES",[b.name for b in arm.data.bones][:80])
for m in meshes: print("MESH",m.name,len(m.data.polygons),"mods",[x.type for x in m.modifiers],"mats",[mt.name for mt in m.data.materials],"vgroups",len(m.vertex_groups))
sc=bpy.context.scene; sc.render.engine="BLENDER_WORKBENCH"; sc.display.shading.light="FLAT"; sc.display.shading.color_type="TEXTURE"
wd=bpy.data.worlds.new("w"); sc.world=wd; wd.color=(0.82,0.82,0.84)
cam=bpy.data.objects.new("c",bpy.data.cameras.new("c")); sc.collection.objects.link(cam); sc.camera=cam; cam.data.type="ORTHO"; cam.data.clip_end=1000
import numpy as np
V=np.array([ (m.matrix_world@v.co)[:] for m in meshes for v in list(m.data.vertices)[::50]]); lo,hi=V.min(0),V.max(0); c=(lo+hi)/2; H=hi[2]-lo[2]
print("BBOX",lo.round(2),hi.round(2))
def shoot(name,dx,dy,center=None,scale=None,w=700,h=900):
    sc.render.resolution_x,sc.render.resolution_y=w,h; cam.data.ortho_scale=scale or H*1.15; cc=Vector(center if center is not None else c)
    cam.location=cc+Vector((dx*10,dy*10,0)); cam.rotation_euler=(math.pi/2,0,math.atan2(dx,-dy)); sc.render.filepath=f"{out}_{name}.png"; bpy.ops.render.render(write_still=True)
bpy.context.view_layer.objects.active=arm
def rot(bn,x=0,y=0,z=0):
    pb=arm.pose.bones.get("mixamorig:"+bn) or arm.pose.bones.get(bn)
    if pb is None: print("MISSING",bn); return
    pb.rotation_mode="XYZ"; pb.rotation_euler=(math.radians(x),math.radians(y),math.radians(z))
shoot("rest_f",0,-1); 
for b in ("LeftHandIndex1","LeftHandIndex2","LeftHandMiddle1","LeftHandMiddle2","LeftHandRing1","LeftHandRing2","LeftHandPinky1","LeftHandPinky2","LeftHandThumb1","LeftHandThumb2"): rot(b,x=-60 if "Thumb" not in b else -30)
rot("LeftArm",z=-50); rot("LeftForeArm",x=-60); rot("RightUpLeg",x=-70); rot("RightLeg",x=80); rot("Head",x=15); rot("Spine1",x=-10)
bpy.context.view_layer.update(); shoot("pose_f",0,-1); shoot("pose_s",-1,0)
# hand closeup
hb=arm.pose.bones.get("mixamorig:LeftHand"); hp=(arm.matrix_world@hb.head)
shoot("hand_pose",0,-1,center=hp+Vector((0,0,-0.05)),scale=0.35,w=700,h=700)
