import bpy, sys, os, math, numpy as np
from mathutils import Vector
glb,out,tag=sys.argv[sys.argv.index("--")+1:][:3]
bpy.ops.wm.read_factory_settings(use_empty=True)
bpy.ops.import_scene.gltf(filepath=glb)
ob=[o for o in bpy.data.objects if o.type=="MESH"][0]
me=ob.data; V=np.empty(len(me.vertices)*3,np.float32); me.vertices.foreach_get("co",V); V=V.reshape(-1,3)
M=np.array(ob.matrix_world); W=V@M[:3,:3].T+M[:3,3]
zmin,zmax=W[:,2].min(),W[:,2].max(); H=zmax-zmin
ob.data.materials.clear(); m=bpy.data.materials.new("m"); m.diffuse_color=(0.85,0.7,0.62,1); ob.data.materials.append(m)
sc=bpy.context.scene; sc.render.engine="BLENDER_WORKBENCH"; sc.display.shading.light="STUDIO"; sc.display.shading.color_type="MATERIAL"
wd=bpy.data.worlds.new("w"); sc.world=wd; wd.color=(0.82,0.82,0.84)
cam=bpy.data.objects.new("c",bpy.data.cameras.new("c")); sc.collection.objects.link(cam); sc.camera=cam; cam.data.type="ORTHO"; cam.data.clip_end=1000
def shoot(name,c,scale,dx,dy,w=800,h=800):
    sc.render.resolution_x,sc.render.resolution_y=w,h; cam.data.ortho_scale=scale
    cam.location=Vector(c)+Vector((dx*5,dy*5,0)); cam.rotation_euler=(math.pi/2,0,math.atan2(dx,-dy))
    sc.render.filepath=f"{out}/{tag}_{name}.png"; bpy.ops.render.render(write_still=True)
cx=(W[:,0].min()+W[:,0].max())/2; cy=(W[:,1].min()+W[:,1].max())/2
shoot("front",(cx,cy,zmin+H/2),H*1.05,0,-1,700,1000); shoot("side",(cx,cy,zmin+H/2),H*1.05,1,0,700,1000)
# hands: vertices in z band 0.44-0.60 with |x-cx| > 0.17*H*...: take outermost per side
band=W[(W[:,2]>zmin+0.30*H)&(W[:,2]<zmin+0.92*H)]   # hands are the outermost points in A-pose and T-pose alike
def shoot_dir(name, center, scale, d, res=800):
    """orthographic shot looking along direction d (camera placed at center - 5*d)"""
    d = Vector(d).normalized(); cam.data.ortho_scale = scale; sc.render.resolution_x = sc.render.resolution_y = res
    cam.location = Vector(center) - d * 5; cam.rotation_euler = d.to_track_quat("-Z", "Z" if abs(d.z) < 0.9 else "Y").to_euler()
    cam.data.clip_start, cam.data.clip_end = 5 - 0.6 * scale, 5 + 0.6 * scale     # only the hand's own depth slab (no torso behind it)
    sc.render.filepath = f"{out}/{tag}_{name}.png"; bpy.ops.render.render(write_still=True)
    cam.data.clip_start, cam.data.clip_end = 0.1, 1000
for s,nm in (() if os.environ.get("HOMUNCULUS_NO_HANDS") else ((-1,"handR"),(1,"handL"))):
    side=band[(band[:,0]-cx)*s>0]; k=np.argsort(-(side[:,0]-cx)*s)[:2000]; c=side[k].mean(0)
    hc = Vector((c[0] - s * 0.03 * H, c[1], c[2])); sz = 0.17 * H
    tpose = c[2] > zmin + 0.70 * H
    if not tpose: hc = Vector((c[0], c[1], c[2] - 0.02 * H))
    # four views of every hand: back of hand, palm, front, outer side
    views = ({"top": (0, 0, -1), "palm": (0, 0, 1), "front": (0, 1, 0), "side": (-s, 0, 0)} if tpose else
             {"front": (0, 1, 0), "back": (0, -1, 0), "side": (-s, 0, 0), "inner": (s, 0, 0)})
    for vn, d in views.items(): shoot_dir(f"{nm}_{vn}", hc, sz, d)
    first = list(views)[0]
    import shutil; shutil.copy(f"{out}/{tag}_{nm}_{first}.png", f"{out}/{tag}_{nm}.png")
    open(f"{out}/{tag}_{nm}_views.txt", "w").write(",".join(views))
shoot("face",(cx,cy,zmin+0.915*H),0.17*H,0,-1,800,800); shoot("feet",(cx,cy,zmin+0.04*H),0.22*H,0,-1,1000,500)
