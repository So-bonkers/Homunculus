"""Depth maps of a coarse mesh seen from the four sides (and optionally above and below): the guide for generating consistent turnaround views.

blender -b --python blender_depth_views.py -- mesh.glb out_dir [size] [views]
  views: comma list of front,left,back,right,top,bottom (default the first four). The mesh faces -y (the pipeline's front); "left" = the camera sees the character's LEFT side (+x).
Writes <view>_depth.png (near = white, far = black, background black, orthographic, one shared scale so the four are views of one object), <view>_normal.png (camera-space normals as RGB: red = towards the
picture's right, green = up, blue = towards the viewer; background the flat "straight at the viewer" colour) and <view>_mask.png. A ControlNet reads the depth or the normal picture.
"""
import bpy, sys, math, os, numpy as np
from mathutils import Vector
argv = sys.argv[sys.argv.index("--") + 1:]; glb, out = argv[:2]; size = int(argv[2]) if len(argv) > 2 else 768
views = (argv[3] if len(argv) > 3 else "front,left,back,right").split(","); os.makedirs(out, exist_ok=True)
bpy.ops.wm.read_factory_settings(use_empty=True); bpy.ops.import_scene.gltf(filepath=glb)
obs = [o for o in bpy.data.objects if o.type == "MESH"]; P = []
for ob in obs:
    me = ob.data; V = np.empty(len(me.vertices) * 3, np.float32); me.vertices.foreach_get("co", V); V = V.reshape(-1, 3); M = np.array(ob.matrix_world); P.append(V @ M[:3, :3].T + M[:3, 3])
W = np.concatenate(P); lo, hi = W.min(0), W.max(0); c = (lo + hi) / 2; H = hi[2] - lo[2]; span = max(H, hi[0] - lo[0], hi[1] - lo[1]) * 1.1
DIRS = {"front": (0, -1, 0), "back": (0, 1, 0), "left": (1, 0, 0), "right": (-1, 0, 0), "top": (0, 0, 1), "bottom": (0, 0, -1)}      # direction from the model towards the camera
DIST = 10.0; near, far = DIST - span / 2, DIST + span / 2
from mathutils.bvhtree import BVHTree
import bmesh, struct, zlib
bm = bmesh.new()
for ob in obs:
    bm.from_mesh(ob.data); 
    for v in bm.verts[-len(ob.data.vertices):]: v.co = ob.matrix_world @ v.co
bmesh.ops.triangulate(bm, faces=bm.faces[:]); tree = BVHTree.FromBMesh(bm)
def png(path, arr, w, h):
    arr = (np.clip(arr, 0, 1) * 255).astype(np.uint8); rgb = arr.ndim == 3; raw = b"".join(b"\x00" + arr[i].tobytes() for i in range(h))
    chunk = lambda t, d: struct.pack(">I", len(d)) + t + d + struct.pack(">I", zlib.crc32(t + d) & 0xffffffff)
    open(path, "wb").write(b"\x89PNG\r\n\x1a\n" + chunk(b"IHDR", struct.pack(">IIBBBBB", w, h, 8, 2 if rgb else 0, 0, 0, 0)) + chunk(b"IDAT", zlib.compress(raw)) + chunk(b"IEND", b""))
for name in views:
    d = Vector(DIRS[name]); up = Vector((0, 0, 1)) if abs(d.z) < 0.9 else Vector((0, 1, 0)) * (1 if d.z > 0 else -1)           # picture up; from above the character's front (-y) is the picture bottom
    right = (up.cross(d)).normalized() if abs(d.z) < 0.9 else (Vector((1, 0, 0)) if d.z > 0 else Vector((1, 0, 0)))
    if abs(d.z) < 0.9: right = up.cross(d).normalized() * -1 if False else d.cross(up).normalized() * -1 if False else (-d).cross(up).normalized()      # picture right as seen by the camera looking along -d
    z = np.zeros((size, size), np.float32); mask = np.zeros((size, size), bool); nrm = np.zeros((size, size, 3), np.float32); origin = Vector(c.tolist()) + d * DIST
    for j in range(size):
        for i in range(size):
            pos = origin + right * ((i + 0.5) / size - 0.5) * span + up * (0.5 - (j + 0.5) / size) * span
            hit = tree.ray_cast(pos, -d, 100.0)
            if hit[0] is not None:
                mask[j, i] = True; z[j, i] = hit[3]; n_ = hit[1]
                if n_.dot(d) < 0: n_ = -n_                                     # face the camera whatever the triangle's winding
                nrm[j, i] = (n_.dot(right), n_.dot(up), n_.dot(d))
    nz = np.clip((far - z) / (far - near), 0, 1) * mask
    if mask.any():      # a depth ControlNet expects the object to use the full range: stretch each view over the object's own depth, near = 1.0, far = 0.15 (the background stays 0)
        zn, zf = float(z[mask].min()), float(z[mask].max()); nz = np.where(mask, 1.0 - 0.85 * (z - zn) / max(zf - zn, 1e-6), 0.0)
    nimg = np.where(mask[..., None], nrm * 0.5 + 0.5, np.array([0.5, 0.5, 1.0], np.float32)[None, None, :])
    png(os.path.join(out, f"{name}_normal.png"), nimg, size, size); png(os.path.join(out, f"{name}_depth.png"), nz, size, size); png(os.path.join(out, f"{name}_mask.png"), mask.astype(np.float32), size, size)
    print(f"[depth] {name}: {int(mask.sum())} px, distance {float(z[mask].min()):.2f}-{float(z[mask].max()):.2f}")
