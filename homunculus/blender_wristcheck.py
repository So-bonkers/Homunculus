"""Wrist-bend check on a rigged model: does each hand stay attached to its forearm?  (CPU, a few seconds)
blender -b --python blender_wristcheck.py -- rigged.fbx out.json [--simulate-gap]
Vertices are assigned to the hand (hand + finger bones) or the forearm by their strongest skin weight. If the hand and the forearm are parts of ONE continuous mesh (shared, welded
edges) they cannot come apart. If they are separate pieces (a repaired hand that overlaps the arm, or a floating one), the distance between the two pieces around the wrist is measured at rest
and with the wrist bent 55 degrees about its two bending axes (the worst case counts): overlapping pieces touch (about 0 cm), a floating hand shows a gap.
Result per side: separate (bool), gap_rest_cm, gap_bent_cm, ok (gap <= 0.8 cm)."""
import bpy, sys, re, json, math
import numpy as np
from mathutils import Quaternion, Vector

argv = sys.argv[sys.argv.index("--") + 1:]; src, out = argv[:2]; simulate = "--simulate-gap" in argv
bpy.ops.wm.read_factory_settings(use_empty=True); bpy.ops.import_scene.fbx(filepath=src)
arm = next((o for o in bpy.data.objects if o.type == "ARMATURE"), None); meshes = [o for o in bpy.data.objects if o.type == "MESH" and len(o.data.vertices) > 500]
if arm is None or not meshes: print("[wrist] no armature or mesh"); json.dump({"error": "no armature or mesh"}, open(out, "w")); sys.exit(2)
short = lambda n: n.split(":")[-1]
FINGER = re.compile(r"Hand(Thumb|Index|Middle|Ring|Pinky)\d"); res = {}
dg = lambda: bpy.context.evaluated_depsgraph_get()


def positions():
    """World positions of every vertex of every skinned mesh (posed), concatenated, plus the strongest bone of each vertex."""
    P, G = [], []
    for o in meshes:
        e = o.evaluated_get(dg()); me = e.to_mesh(); n = len(me.vertices); a = np.empty(n * 3, np.float32); me.vertices.foreach_get("co", a)
        M = np.array(o.matrix_world); P.append(a.reshape(-1, 3) @ M[:3, :3].T + M[:3, 3]); e.to_mesh_clear()
    return np.concatenate(P)


gname = []; edges = []; off = 0
for o in meshes:
    names = {g.index: short(g.name) for g in o.vertex_groups}
    for v in o.data.vertices:
        best = max(v.groups, key=lambda g: g.weight) if v.groups else None; gname.append(names.get(best.group, "") if best else "")
    E = np.empty(len(o.data.edges) * 2, np.int32); o.data.edges.foreach_get("vertices", E); edges.append(E.reshape(-1, 2) + off); off += len(o.data.vertices)
gname = np.array(gname); edges = np.concatenate(edges)
P_rest = positions()
_, canon = np.unique(np.round(P_rest * 1e5).astype(np.int64), axis=0, return_inverse=True); canon = canon.ravel()            # the importer splits vertices at UV seams: weld by position
ca = canon[edges[:, 0]]; cb = canon[edges[:, 1]]; label = np.arange(canon.max() + 1)
for _ in range(400):                                                                                                       # connected components by label propagation
    m = np.minimum(label[ca], label[cb]); new = label.copy(); np.minimum.at(new, ca, m); np.minimum.at(new, cb, m)
    if (new == label).all(): break
    label = new
comp = label[canon]
bpy.context.view_layer.objects.active = arm
for side in ("Left", "Right"):
    hand = next((b for b in arm.pose.bones if short(b.name) == side + "Hand"), None)
    if hand is None: continue
    is_hand = np.array([g.startswith(side + "Hand") for g in gname]); is_fore = np.array([g == side + "ForeArm" for g in gname])
    if not is_hand.any() or not is_fore.any(): continue
    hc = np.bincount(comp[is_hand]).argmax(); fc = np.bincount(comp[is_fore]).argmax(); hmask = comp == hc; fmask = comp == fc
    if simulate: hmask = is_hand; fmask = ~is_hand & (comp == fc)           # a test: pretend the hand is its own piece
    separate = bool(hc != fc) or simulate
    def gap():
        P = positions()
        if simulate: P = P.copy(); P[is_hand] += (P[is_hand].mean(0) - P[is_fore].mean(0)) / max(np.linalg.norm(P[is_hand].mean(0) - P[is_fore].mean(0)), 1e-6) * 0.05
        head = np.array(arm.matrix_world @ hand.head); H = P[hmask]; F = P[fmask]; near = H[np.linalg.norm(H - head, axis=1) < 0.08]
        if len(near) == 0: return 0.0
        near = near[::max(1, len(near) // 600)]; return float(min(np.linalg.norm(F - h, axis=1).min() for h in near))
    if not separate:
        res[side.lower()] = {"separate": False, "gap_rest_cm": 0.0, "gap_bent_cm": 0.0, "ok": True}
    else:
        g0 = gap(); worst = g0; hand.rotation_mode = "QUATERNION"; base = hand.rotation_quaternion.copy()
        for axis in (Vector((1, 0, 0)), Vector((0, 0, 1))):
            for sgn in (1, -1):
                hand.rotation_quaternion = Quaternion(axis, math.radians(55 * sgn)); bpy.context.view_layer.update(); worst = max(worst, gap())
        hand.rotation_quaternion = base; bpy.context.view_layer.update()
        res[side.lower()] = {"separate": True, "gap_rest_cm": round(g0 * 100, 2), "gap_bent_cm": round(worst * 100, 2), "ok": bool(worst * 100 <= 0.8)}
    r = res[side.lower()]
    print(f"[wrist] {side}: " + ("one continuous mesh with the forearm: cannot detach" if not r["separate"] else f"separate piece, gap {r['gap_rest_cm']} cm at rest, {r['gap_bent_cm']} cm worst when bent") + f" -> {'ok' if r['ok'] else 'DETACHED'}")
json.dump(res, open(out, "w"))
