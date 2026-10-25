"""Run inside Blender (MCP: PARTS = "path/parts.json"; exec(open(this).read())): Ren's separate parts as clean, light meshes, placed from measure_parts.py (body TRELLIS frame = Blender frame of the fused GLB).
headphones (one object: two cups with cushions and a band behind the neck), drawstring_L/R (one object each: cord + aglet), glasses_frame (rims, double bridge, top bar, temples) and glasses_lenses (glass material)."""
import bpy, bmesh, json, math, numpy as np
from mathutils import Vector, Matrix
J = json.load(open(PARTS)); ax = Vector((J["neck_axis"][0], J["neck_axis"][1], 0))
def mat(name, rgb, rough=0.5, metal=0.0, glass=False):
    m = bpy.data.materials.get(name) or bpy.data.materials.new(name); m.use_nodes = True; p = next(n for n in m.node_tree.nodes if n.type == "BSDF_PRINCIPLED")
    p.inputs["Base Color"].default_value = (*rgb, 1); p.inputs["Roughness"].default_value = rough; p.inputs["Metallic"].default_value = metal
    if glass:
        for k in ("Transmission Weight", "Transmission"):
            if k in p.inputs: p.inputs[k].default_value = 1.0
        p.inputs["IOR"].default_value = 1.5
    m.diffuse_color = (*rgb, 0.35 if glass else 1); return m
def new_obj(name, bm, material):
    old = bpy.data.objects.get(name)
    if old: bpy.data.objects.remove(old, do_unlink=True)
    me = bpy.data.meshes.new(name); bm.to_mesh(me); bm.free(); o = bpy.data.objects.new(name, me); bpy.context.scene.collection.objects.link(o); o.data.materials.append(material)
    for p in me.polygons: p.use_smooth = True
    return o
def tube(bm, pts, radius, seg=10, cap=True, radii=None):
    pts = [Vector(p) for p in pts]; rings = []
    for i, p in enumerate(pts):
        t = (pts[min(i + 1, len(pts) - 1)] - pts[max(i - 1, 0)]).normalized(); n = t.orthogonal().normalized(); b = t.cross(n); r = radii[i] if radii else radius
        rings.append([bm.verts.new(p + r * (math.cos(2 * math.pi * k / seg) * n + math.sin(2 * math.pi * k / seg) * b)) for k in range(seg)])
    for a, b in zip(rings[:-1], rings[1:]):
        for k in range(seg): bm.faces.new([a[k], a[(k + 1) % seg], b[(k + 1) % seg], b[k]])
    if cap: bm.faces.new(rings[0][::-1]); bm.faces.new(rings[-1])
# --- headphones: cups at the measured places, facing away from the neck; a band behind the neck
bm = bmesh.new(); cups = {c["side"]: c for c in J["cups"]}; tops = {}
for side, c in cups.items():
    ctr = Vector(c["centre"]); ext = Vector(c["hi"]) - Vector(c["lo"]); r = max(ext.x, ext.z) * 0.42; depth = r * 0.75
    out = Vector((ctr.x - ax.x, ctr.y - ax.y, 0)).normalized()
    shell = [ctr - out * depth * 0.5 + out * depth * t for t in (0.0, 0.15, 0.85, 1.0)]
    tube(bm, shell, r, seg=24, radii=[r * 0.92, r, r, r * 0.9])                                    # the cup shell
    tube(bm, [ctr - out * depth * 0.62, ctr - out * depth * 0.48], r * 0.95, seg=24, radii=[r * 0.85, r * 0.95])   # the cushion facing the neck
    tops[side] = ctr + Vector((0, 0, r * 0.9))
L, R = tops["left"], tops["right"]; back = Vector((ax.x, ax.y + abs(L.x - R.x) * 0.55, (L.z + R.z) / 2 + 0.01))
arc = [(1 - t) ** 2 * R + 2 * (1 - t) * t * back + t * t * L for t in np.linspace(0, 1, 28)]
tube(bm, arc, 0.006, seg=8)
hp = new_obj("headphones", bm, mat("headphones_black", (0.02, 0.02, 0.022), rough=0.35))
# --- drawstrings: cord along the measured path, an aglet at its end, one object each
for c in J["cords"]:
    path = sorted([Vector(p) for p in c["path"]], key=lambda p: -p.z); r = max(0.0022, min(0.004, c["half_width"] * 0.6))
    bm = bmesh.new(); tip = path[-1]; d = (path[-1] - path[-2]).normalized() if len(path) > 1 else Vector((0, 0, -1))
    pts = path + [tip + d * 0.004, tip + d * 0.022]; radii = [r] * len(path) + [r * 1.35, r * 1.25]
    tube(bm, pts, r, seg=8, radii=radii); new_obj(f"drawstring_{c['side']}", bm, mat("cord_yellow", (0.85, 0.55, 0.10), rough=0.6))
# --- glasses: rectangular rims before the eyes, a double bridge (nose bridge + top bar), temples to the ears
E_ = {e["side"]: Vector(e["centre"]) for e in J["eyes"]}; eR, eL = E_["right"], E_["left"]; ipd = (eL - eR).length; front = min(eR.y, eL.y) - 0.012
w = ipd * 1.28; h = w * 0.66; t = 0.0024                    # Ren's reference: large rectangular lenses, together about as wide as the face
def rim(c):
    pts = []; cr = h * 0.22
    for (sx, sy) in ((1, 1), (-1, 1), (-1, -1), (1, -1)):
        cc = Vector((c.x + sx * (w / 2 - cr), front, c.z + sy * (h / 2 - cr))); a0 = {(1, 1): 0, (-1, 1): 90, (-1, -1): 180, (1, -1): 270}[(sx, sy)]
        pts += [cc + Vector((cr * math.cos(math.radians(a0 + 90 * k / 6)), 0, cr * math.sin(math.radians(a0 + 90 * k / 6)))) for k in range(7)]
    return pts + [pts[0]]
bm = bmesh.new(); cR = Vector((eR.x, front, eR.z)); cL = Vector((eL.x, front, eL.z))
for c in (cR, cL): tube(bm, rim(c), t, seg=6, cap=False)
tube(bm, [cR + Vector((w / 2, 0, h * 0.12)), Vector(((cR.x + cL.x) / 2, front - 0.002, cR.z + h * 0.16)), cL + Vector((-w / 2, 0, h * 0.12))], t * 0.9, seg=6)        # nose bridge
tube(bm, [cR + Vector((w * 0.15, 0, h / 2)), cL + Vector((-w * 0.15, 0, h / 2))], t * 0.8, seg=6)                                                   # the top bar (double bridge)
ear_y = J["ears"]["y_at"] if J["ears"]["y_at"] is not None else J["head"]["back"] - 0.04
for c, sgn in ((cR, -1), (cL, 1)):
    p0 = c + Vector((sgn * w / 2, 0, h * 0.3)); x_side = (J["ears"]["x_lo"] if sgn < 0 else J["ears"]["x_hi"]) + sgn * 0.002
    tube(bm, [p0, Vector((x_side, p0.y + 0.02, p0.z)), Vector((x_side, ear_y, p0.z - 0.004)), Vector((x_side - sgn * 0.004, ear_y + 0.012, p0.z - 0.02))], t, seg=6)
new_obj("glasses_frame", bm, mat("glasses_frame", (0.05, 0.055, 0.065), rough=0.3, metal=0.6))
bm = bmesh.new()
for c in (cR, cL):
    ring = rim(c)[:-1]; vs = [bm.verts.new(p + Vector((0, 0.0005, 0))) for p in ring]; bm.faces.new(vs)
new_obj("glasses_lenses", bm, mat("glasses_lens", (0.85, 0.9, 0.95), rough=0.05, glass=True))
print("built: headphones, drawstrings, glasses (ipd %.4f, lens %.4f x %.4f)" % (ipd, w, h))
