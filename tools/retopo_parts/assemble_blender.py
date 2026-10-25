"""The Blender half of the retopo-parts skill. Run it inside the live Blender through the MCP:
    exec(open("/home/shubhankar/homunculus/tools/retopo_parts/assemble_blender.py").read()); build("/path/to/work_dir", "/path/to/config.json")
(work_dir holds full.ply, R.ply, L.ply and hands.json from run_parts.py; config is only {"name": "Ren"}: everything else is read from hands.json, the procedural hand analysis). Every step prints what it did, so the result can be checked from the MCP's output, and the scene
shows each step as it happens.  The functions:
  build(work, config)                          import the parts, smooth the arms, cut at the wrists, join, bridge, label  ->  the object "<name>_joined"
  finger_test(obj, work, side, curl)           pose a hand (curl the listed fingers about the knuckle, the others stay) on a copy "<name>_pose_test"; report the mesh edges that join two fingers
  rig_pose_test(rig, mesh, side, out_finger)   the same test on the RIGGED model, with its real skin weights: curl every finger but one about the knuckle line; report overlaps and skin folds
  add_knuckles(obj, work, amp)                 raise the four knuckles on the back of each hand (a bump at each finger base, on the back-facing surface)
  add_creases(obj, work)                       press the palm's three main lines and the finger-joint creases into the palm-facing surface (placed by proportions of the palm and finger lengths)
  export(obj, path)                            GLB for the pipeline (triangulated by the format) + <path>.parts.json (the part labels)
Labels: every vertex is in the vertex group part_body / part_hand_R / part_hand_L (what part it came from); the sidecar lists the counts.
No measured distances: lengths are fractions of the body height H or of the hand length, from hands.json. A 0.0004 H gap per side is opened before bridging; smoothing = 12 Taubin passes."""
import bpy, bmesh, json, numpy as np
from mathutils import Vector, Matrix

SIDE = {"R": 1, "L": -1}


def _hands(work):
    """hands.json -> per side: (wrist point, axis, tube radius, the analysis dict)."""
    A = json.load(open(work + "/hands.json")); return A, {s: (Vector(A[s]["wrist_point"]), Vector(A[s]["axis"]), A[s]["tube_radius"]) for s in SIDE}


def _in_tube(co, hand, back=0.0, front=1e9):
    """Is the point in the tube round the arm axis, between `back` behind the wrist plane and `front` in front of it?"""
    P, N, R = hand; d = co - P; t = d.dot(N)
    return -back <= t <= front and (d - N * t).length < R


def _sel(*objs):
    for o in bpy.data.objects: o.select_set(False)
    for o in objs: o.select_set(True)
    if objs: bpy.context.view_layer.objects.active = objs[-1]


def _loops(bm):
    seen = set(); out = []
    for e in [e for e in bm.edges if e.is_boundary]:
        if e.index in seen: continue
        st = [e]; seen.add(e.index); g = []
        while st:
            a = st.pop(); g.append(a)
            for v in a.verts:
                for b in v.link_edges:
                    if b.is_boundary and b.index not in seen: seen.add(b.index); st.append(b)
        vs = {v for x in g for v in x.verts}; c = sum((v.co for v in vs), Vector()) / len(vs)
        out.append((g, c, max((v.co - c).length for v in vs)))
    return out


def _import(path, name):
    before = set(bpy.data.objects); bpy.ops.wm.ply_import(filepath=path)
    o = [x for x in bpy.data.objects if x not in before][0]; o.name = name; return o


def _group(o, name):
    g = o.vertex_groups.new(name=name); g.add(list(range(len(o.data.vertices))), 1.0, "REPLACE")


def smooth_arms(bm, hands, H, passes=12):
    """Taubin smoothing (no shrinking) of biceps and forearms, faded out toward the wrist (so the seam rims stay where they are) and toward the shoulder."""
    def sstep(t): t = max(0.0, min(1.0, t)); return t * t * (3 - 2 * t)
    bm.verts.ensure_lookup_table(); w = [0.0] * len(bm.verts)
    for v in bm.verts:
        best = 0.0
        for s_, hd in hands.items():
            if not _in_tube(v.co, hd, back=0.30 * H): continue
            back = (hd[0] - v.co).dot(hd[1])
            best = max(best, sstep(back / (0.033 * H)) * sstep((0.30 * H - back) / (0.03 * H)))
        w[v.index] = best
    def lap(lam):
        new = {}
        for v in bm.verts:
            if w[v.index] == 0.0: continue
            nb = [e.other_vert(v).co for e in v.link_edges]; new[v.index] = v.co + (sum(nb, Vector()) / len(nb) - v.co) * lam * w[v.index]
        for i, c in new.items(): bm.verts[i].co = c
    for _ in range(passes): lap(0.5); lap(-0.53)
    return sum(1 for x in w if x > 0)


def build(work, config):
    cfg = json.load(open(config)); name = cfg["name"]; A, hands_ = _hands(work); H = A["height"]; gap = 0.0004 * H
    for n in (f"{name}_joined", f"{name}_body", f"{name}_hand_R", f"{name}_hand_L"):
        if n in bpy.data.objects: bpy.data.objects.remove(bpy.data.objects[n], do_unlink=True)
    body = _import(work + "/full.ply", f"{name}_body"); hands = {s: _import(f"{work}/{s}.ply", f"{name}_hand_{s}") for s in ("R", "L")}
    bm = bmesh.new(); bm.from_mesh(body.data)
    print("smoothed arm vertices:", smooth_arms(bm, hands_, H))
    for s, sg in SIDE.items():           # the body, cut at each wrist plane (only inside the tube round the arm: the legs also lie "past" the plane)
        P, N, R_ = hands_[s]
        fs = [f for f in bm.faces if all(_in_tube(v.co, hands_[s], back=0.03 * H) for v in f.verts)]; es = list({e for f in fs for e in f.edges}); vs = list({v for f in fs for v in f.verts})
        bmesh.ops.bisect_plane(bm, geom=vs + es + fs, plane_co=P, plane_no=N, dist=1e-6)
        bmesh.ops.delete(bm, geom=[v for v in bm.verts if _in_tube(v.co, hands_[s], back=-1e-6) ], context="VERTS")
    bmesh.ops.delete(bm, geom=[v for v in bm.verts if not v.link_faces], context="VERTS")
    body_rings = {}
    for g, c, r in _loops(bm):
        for s in SIDE:
            if abs((c - hands_[s][0]).dot(hands_[s][1])) < 1e-3 and _in_tube(c, hands_[s], back=1e-3, front=1e-3): body_rings[s] = (len(g), r)
    for s in SIDE:                       # a hollow arm (a ring inside the ring, the signature of a voxelised hole) would give a third ring: keep the biggest loop at each wrist, cap the others
        P_, N_, R2 = hands_[s]; at = [t_ for t_ in _loops(bm) if abs((t_[1] - P_).dot(N_)) < 1e-3 and _in_tube(t_[1], hands_[s], back=1e-3, front=1e-3) and len(t_[0]) > 8]
        for g, c, r in sorted(at, key=lambda t_: -t_[2])[1:]: bmesh.ops.holes_fill(bm, edges=g, sides=400); print(f"body {s} wrist: capped a stray inner ring of {len(g)} edges (radius {r:.4f} m)")
    bm.to_mesh(body.data); bm.free()
    for s, h in hands.items():           # each hand, cut at the same plane; the doubled wall (a ring inside the ring) is capped, keeping the ring that matches the body's
        P, N, R_ = hands_[s]; bm = bmesh.new(); bm.from_mesh(h.data)
        bmesh.ops.bisect_plane(bm, geom=bm.verts[:] + bm.edges[:] + bm.faces[:], plane_co=P, plane_no=N, dist=1e-6)
        bmesh.ops.delete(bm, geom=[v for v in bm.verts if (v.co - P).dot(N) < -1e-6], context="VERTS")
        bmesh.ops.delete(bm, geom=[v for v in bm.verts if not v.link_faces], context="VERTS")
        Ls = _loops(bm); wrist = [t for t in Ls if abs((t[1] - P).dot(N)) < 1e-3 and len(t[0]) > 10]
        keep = min(wrist, key=lambda t: abs(t[2] - body_rings[s][1]))
        for g, c, r in Ls:
            if g is not keep[0]: bmesh.ops.holes_fill(bm, edges=g, sides=200)
        bmesh.ops.recalc_face_normals(bm, faces=bm.faces[:])
        print(f"hand {s}: wrist ring {len(keep[0])} edges, radius {keep[2]:.3f} m (body ring {body_rings[s][0]} edges, {body_rings[s][1]:.3f} m)")
        bm.to_mesh(h.data); bm.free()
    for o, nm in ((body, "part_body"), (hands["R"], "part_hand_R"), (hands["L"], "part_hand_L")): _group(o, nm)
    _sel(body, *hands.values()); bpy.ops.object.join(); j = bpy.context.view_layer.objects.active; j.name = f"{name}_joined"
    for s in SIDE:                       # open a 1.5 mm gap (two rims on one plane have nothing to bridge), then bridge the two rings
        bpy.ops.object.mode_set(mode="EDIT"); bm = bmesh.from_edit_mesh(j.data); P, N, R_ = hands_[s]
        es = [e for e in bm.edges if e.is_boundary and all(abs((v.co - P).dot(N)) < 2e-4 and _in_tube(v.co, hands_[s], back=2e-4, front=2e-4) for v in e.verts)]
        seen = set(); comps = []
        for e in es:
            if e.index in seen: continue
            st = [e]; seen.add(e.index); g = []
            while st:
                a = st.pop(); g.append(a)
                for v in a.verts:
                    for b in v.link_edges:
                        if b in es and b.index not in seen: seen.add(b.index); st.append(b)
            comps.append(g)
        comps.sort(key=len); assert len(comps) == 2, f"{s} wrist: {[len(g) for g in comps]} rings"
        body_first = comps[0] if len(comps[0]) == body_rings[s][0] else comps[1]
        for g in comps:
            for v in {v for e in g for v in e.verts}: v.co += N * gap * (-1 if g is body_first else 1)
        bpy.ops.mesh.select_mode(type="EDGE"); bpy.ops.mesh.select_all(action="DESELECT")
        for g in comps:
            for e in g: e.select_set(True)
        bm.select_flush_mode(); bmesh.update_edit_mesh(j.data)
        r = bpy.ops.mesh.bridge_edge_loops(type="SINGLE", use_merge=False, number_cuts=0, interpolation="SURFACE"); bpy.ops.object.mode_set(mode="OBJECT")
        print(f"wrist {s}: bridged rings of {[len(g) for g in comps]} edges -> {r}")
    bm = bmesh.new(); bm.from_mesh(j.data)
    be = [e for e in bm.edges if e.is_boundary]          # small holes left by Quadriflow (a few edges each), then merge near-duplicate vertices, then the holes that merging opened
    if be: bmesh.ops.holes_fill(bm, edges=be, sides=64)
    bmesh.ops.remove_doubles(bm, verts=bm.verts[:], dist=2e-4)
    be = [e for e in bm.edges if e.is_boundary]
    if be: bmesh.ops.holes_fill(bm, edges=be, sides=8)
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces[:])
    print(f"{name}_joined: {len(bm.faces)} faces = {sum(1 for f in bm.faces if len(f.verts)==4)} quads + {sum(1 for f in bm.faces if len(f.verts)==3)} tris + {sum(1 for f in bm.faces if len(f.verts)>4)} n-gons; "
          f"open edges {sum(1 for e in bm.edges if e.is_boundary)}, non-manifold {sum(1 for e in bm.edges if not e.is_manifold)}")
    bm.to_mesh(j.data); bm.free(); j.data.polygons.foreach_set("use_smooth", [True] * len(j.data.polygons)); j.data.update()
    _sel(j); return j


def finger_test(obj, work, side="R", curl=("pinky", "ring", "index"), degrees=95.0):
    """Quick check before there is a rig. Pass = (1) past the end of the web (hands.json: where the fingers start, plus a twentieth of the hand) the mesh falls into exactly four separate pieces, one per finger
    (thumb ends below that line), and (2) curling the listed fingers (each piece rigidly about the knuckle, a smooth blend over a tenth of the hand; the skin between knuckle and web follows the nearest finger)
    stretches no edge of a finger more than 3x. Webbing shows as fewer than four pieces (two fingers joined) and as edges stretched between a curled finger and its neighbour."""
    A = json.load(open(work + "/hands.json")); h = A[side]; j = bpy.data.objects[obj]
    if "finger_lines" not in h: print(f"{side} hand: the analysis found no five fingers (a relaxed hand kept as generated): webbing test skipped"); return 0
    P = np.array(h["wrist_point"]); ax = np.array(h["axis"]); lat = np.array(h["lat"]); pn = np.array(h["palm_normal"]); L = h["hand_len"]; names = [f["name"] for f in h["finger_lines"]]
    knuckle = h["knuckle_s"]; blend = 0.045 * L; web_end = h["slit_start"] + 0.05 * L
    nm = f"{obj}_pose_test"
    if nm in bpy.data.objects: bpy.data.objects.remove(bpy.data.objects[nm], do_unlink=True)
    p = j.copy(); p.data = j.data.copy(); p.name = nm; bpy.context.collection.objects.link(p); j.hide_set(True)
    k = len(p.data.vertices); co = np.empty(k * 3, np.float32); p.data.vertices.foreach_get("co", co); co = co.reshape(-1, 3)
    d = co - P; t = d @ ax; l = d @ lat; tube = np.linalg.norm(d - np.outer(t, ax), axis=1) < h["tube_radius"]
    hand = (t > knuckle - blend) & (t < 1.5 * L) & tube; past = (t > web_end) & (t < 1.5 * L) & tube
    parent = list(range(k))
    def find(x):
        while parent[x] != x: parent[x] = parent[parent[x]]; x = parent[x]
        return x
    for e in j.data.edges:
        a_, b_ = e.vertices
        if past[a_] and past[b_]: parent[find(a_)] = find(b_)
    comps = {}
    for v in np.where(past)[0]: comps.setdefault(find(v), []).append(v)
    comps = {r: vs for r, vs in comps.items() if len(vs) > 40}; sizes = sorted((len(v) for v in comps.values()), reverse=True)
    if len(comps) != 4:
        print(f"{side} hand: past the web (s > {web_end:.3f} m, {web_end / A['height']:.3f} H) the mesh is {len(comps)} pieces {sizes}, not 4 -> WEBBING (or a broken finger)"); p.hide_set(True); j.hide_set(False); return 1
    order = sorted(comps, key=lambda r: l[comps[r]].mean()); lab = np.full(k, -1)                 # finger index 0..3 by lateral position, named as hands.json names them
    for q_, r in enumerate(order): lab[comps[r]] = q_
    idx_hand = np.where(hand & (lab < 0))[0]; known = np.where(lab >= 0)[0]
    for i in idx_hand:                                                                            # the skin between knuckle and web follows the nearest finger
        lab[i] = lab[known[np.argmin(np.linalg.norm(co[known] - co[i], axis=1))]]
    new = co.copy(); sm = lambda x: np.clip(x, 0, 1) ** 2 * (3 - 2 * np.clip(x, 0, 1))
    for f in dict.fromkeys(curl):
        q_ = names.index(f); sel = hand & (lab == q_); lc = l[sel].mean(); depth = ((co[sel] - P) @ pn).mean()
        K = P + ax * knuckle + lat * lc + pn * depth; tip = Vector(co[sel][np.argmax(t[sel])].tolist()); Kv = Vector(K.tolist())
        sign = next((s_ for s_ in (1, -1) if (Matrix.Rotation(s_ * np.radians(degrees), 4, Vector(lat.tolist())) @ (tip - Kv) + Kv).y < tip.y), -1)      # the fingertip goes toward the palm (-y)
        for i, wi in zip(np.where(sel)[0], sm((t[sel] - (knuckle - blend)) / (2 * blend))):
            new[i] = np.array(Matrix.Rotation(sign * np.radians(degrees) * wi, 4, Vector(lat.tolist())) @ (Vector(co[i].tolist()) - Kv) + Kv)
        print(f"curled {f}: {int(sel.sum())} vertices")
    p.data.vertices.foreach_set("co", new.ravel()); p.data.update()
    stretch = 0; worst = 0.0
    for e in p.data.edges:
        a_, b_ = e.vertices
        if past[a_] and past[b_]:
            e0 = np.linalg.norm(co[a_] - co[b_]); e1 = np.linalg.norm(new[a_] - new[b_])
            if e0 > 1e-6: worst = max(worst, e1 / e0); stretch += e1 / e0 > 3.0
    ok = stretch == 0
    print(f"{side} hand: past the web (s > {web_end:.3f} m, {web_end / A['height']:.3f} H) exactly 4 separate fingers {sizes}; edges of the fingers stretched > 3x by the curl: {stretch} (worst {worst:.1f}x) -> " + ("NO WEBBING" if ok else "STRETCH"))
    p.data.polygons.foreach_set("use_smooth", [True] * len(p.data.polygons)); p.data.update(); _sel(p); return 0 if ok else 1


def add_knuckles(obj, work, amp=0.30, out_name=None):
    """The knuckles: a rounded bump on the back of the hand at each finger base. Positions from hands.json (finger bases at the knuckle line); the back of the hand is the side facing away from the palm (the character
    faces -y and its palms face forward, so the back is +y); a bump is a Gaussian in (across the hand, along the hand), as wide as 0.38 of the finger spacing and as long as 0.1 of the hand, as high as `amp` of the
    finger spacing, moving only the vertices on the back-facing surface, along the back direction. Applied to a copy named out_name (default <obj>_kn)."""
    A = json.load(open(work + "/hands.json")); src = bpy.data.objects[obj]; nm = out_name or obj + "_kn"
    if nm in bpy.data.objects: bpy.data.objects.remove(bpy.data.objects[nm], do_unlink=True)
    o = src.copy(); o.data = src.data.copy(); o.name = nm; bpy.context.collection.objects.link(o); src.hide_set(True)
    bm = bmesh.new(); bm.from_mesh(o.data); bm.verts.ensure_lookup_table(); bmesh.ops.recalc_face_normals(bm, faces=bm.faces[:]); bm.normal_update()
    co = np.array([v.co[:] for v in bm.verts]); nr = np.array([v.normal[:] for v in bm.verts]); moved = 0
    for side in SIDE:
        h = A[side]
        if "finger_lines" not in h: continue                                          # a hand kept as generated gets neither
        Pw = np.array(h["wrist_point"]); ax = np.array(h["axis"]); lat = np.array(h["lat"]); pn = np.array(h["palm_normal"]); L = h["hand_len"]; sk = h["knuckle_s"]
        back = pn if pn[1] > 0 else -pn                                               # +y: away from the palm
        d = co - Pw; s_ = d @ ax; l_ = d @ lat; z_ = d @ back; tube = np.linalg.norm(d - np.outer(s_, ax), axis=1) < h["tube_radius"]
        sp = h["finger_lines"][0]["spacing"]; zc = np.median(z_[tube & (np.abs(s_ - sk) < 0.05 * L)]); facing = (nr @ back) > 0.3
        for f in h["finger_lines"]:
            sk_f = sk - f.get("root_offset", 0.0); lb = f["m0"] + f["m1"] * sk_f; w = np.exp(-((l_ - lb) / (0.38 * sp)) ** 2 - ((s_ - sk_f) / (0.10 * L)) ** 2); w[~(tube & facing & (z_ > zc))] = 0
            co += np.outer(w * amp * sp, back); moved += int((w > 0.05).sum())
    for v, c in zip(bm.verts, co): v.co = c
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces[:]); bm.to_mesh(o.data); bm.free(); o.data.polygons.foreach_set("use_smooth", [True] * len(o.data.polygons)); o.data.update()
    print(f"knuckles: {moved} vertices raised on {nm}"); _sel(o); return o


def _seg_dist(P, A_, B_):
    """Distance from each of the points P (n x 2) to the segment A_B_."""
    AB = B_ - A_; t = np.clip(((P - A_) @ AB) / max(AB @ AB, 1e-12), 0, 1); return np.linalg.norm(P - (A_ + np.outer(t, AB)), axis=1)


def add_creases(obj, work, depth_palm=0.07, sigma_palm=0.20, depth_finger=0.045, sigma_finger=0.20, out_name=None):
    """The creases of a hand, pressed in as shallow grooves on the palm-facing surface (the character's palms face forward, -y). Placed in the hand's own coordinates: u across the palm (+1 toward the thumb, as wide as 4 finger
    spacings) and t along it (0 at the wrist, 1 at the knuckle line). Palm: the heart line (from the little-finger edge, curving up to between the index and middle fingers), the head line (from the thumb edge, across and slightly
    down) and the life line (the arc round the thumb's mound toward the middle of the wrist). Fingers: a crease at the base, two at the middle joint (the proximal interphalangeal joint, 46 % along the finger) and one at the outer joint (76 %),
    across the finger's width (a groove at the base or a double one made bead-like collars, and a groove thinner than about two vertex spacings aliases into diamonds: sigma is at least 0.2 of the finger spacing). A groove is `depth_*` of the finger spacing deep and `sigma_*` of it wide (Gaussian); vertices move inward along their normals. Applied to a copy named out_name (default <obj>_cr)."""
    A = json.load(open(work + "/hands.json")); src = bpy.data.objects[obj]; nm = out_name or obj + "_cr"
    if nm in bpy.data.objects: bpy.data.objects.remove(bpy.data.objects[nm], do_unlink=True)
    o = src.copy(); o.data = src.data.copy(); o.name = nm; bpy.context.collection.objects.link(o); src.hide_set(True)
    bm = bmesh.new(); bm.from_mesh(o.data); bm.verts.ensure_lookup_table(); bmesh.ops.recalc_face_normals(bm, faces=bm.faces[:]); bm.normal_update()
    co = np.array([v.co[:] for v in bm.verts]); nr = np.array([v.normal[:] for v in bm.verts]); moved = 0
    for side in SIDE:
        h = A[side]
        if "finger_lines" not in h: continue
        Pw = np.array(h["wrist_point"]); ax = np.array(h["axis"]); lat = np.array(h["lat"]); pn = np.array(h["palm_normal"]); L = h["hand_len"]; sk = h["knuckle_s"]; fl = h["finger_lines"]; sp = fl[0]["spacing"]
        palm_dir = -pn if pn[1] > 0 else pn                                              # the palm faces -y
        d = co - Pw; s_ = d @ ax; l_ = d @ lat; tube = np.linalg.norm(d - np.outer(s_, ax), axis=1) < h["tube_radius"]; facing = (nr @ palm_dir) > 0.25
        bl = [f["m0"] + f["m1"] * sk for f in fl]; lc = float(np.mean(bl)); half = 2.0 * sp; ts = 1.0 if h.get("thumb_side") == "high" else -1.0     # +u toward the thumb
        U = lambda u, t: np.array([lc + ts * u * half, t * sk])                           # (lat, s) of a point in the palm's (u, t)
        lines = [[(-0.90, 0.74), (-0.55, 0.86), (-0.10, 0.92), (0.35, 0.91), (0.62, 0.84)],      # heart line: from the little-finger edge, curving up to between the index and middle fingers
                 [(0.88, 0.62), (0.45, 0.62), (0.00, 0.56), (-0.45, 0.48), (-0.88, 0.38)],       # head line: from the thumb edge, across and down
                 [(0.60, 0.76), (0.72, 0.56), (0.66, 0.36), (0.46, 0.20), (0.20, 0.08)]]         # life line, round the thumb's mound
        palm_segs = [(U(*a), U(*b)) for ln in lines for a, b in zip(ln[:-1], ln[1:])]
        fing_segs = []
        for f in fl:                                                                     # finger creases across the finger at the middle joint (46 %) and the outer joint (76 %), shorter than the finger is wide
            for x, k in ((0.46, 0.70), (0.76, 0.55)):
                sk_f = sk - f.get("root_offset", 0.0); sc = sk_f + x * (f["reach"] - sk_f); lcn = f["m0"] + f["m1"] * sc; wid = 0.5 * sp * 0.9 * k
                fing_segs.append((np.array([lcn - wid, sc]), np.array([lcn + wid, sc])))
        P2 = np.stack([l_, s_], axis=1); ok = tube & facing & (s_ > 0.04 * L) & (s_ < sk + 0.95 * (max(f["reach"] for f in fl) - sk)); amount = np.zeros(len(co))
        for segs, dep_, sig_ in ((palm_segs, depth_palm, sigma_palm), (fing_segs, depth_finger, sigma_finger)):
            dist = np.full(len(co), 1e9)
            for A_, B_ in segs: dist = np.minimum(dist, _seg_dist(P2, A_, B_))
            w = np.exp(-(dist / (sig_ * sp)) ** 2); w[~ok] = 0; amount += w * dep_ * sp; moved += int((w > 0.1).sum())
        co -= nr * amount[:, None]
    for v, c in zip(bm.verts, co): v.co = c
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces[:]); bm.to_mesh(o.data); bm.free(); o.data.polygons.foreach_set("use_smooth", [True] * len(o.data.polygons)); o.data.update()
    print(f"creases: {moved} vertices pressed in on {nm}"); _sel(o); return o


def export(obj, path):
    j = bpy.data.objects[obj]; _sel(j)
    bpy.ops.export_scene.gltf(filepath=path, use_selection=True, export_format="GLB")
    parts = {g.name: sum(1 for v in j.data.vertices if any(vg.group == g.index for vg in v.groups)) for g in j.vertex_groups}
    json.dump({"object": obj, "faces": len(j.data.polygons), "parts": parts}, open(path + ".parts.json", "w"), indent=1); print("exported", path, parts)


FINGERS = ("Thumb", "Index", "Middle", "Ring", "Pinky")


def _chain(arm, side, f): return [arm.pose.bones[f"mixamorig:{side}Hand{f}{i}"] for i in (1, 2, 3)]


def _rest_hand(arm, mesh, side):
    """The hand's vertices (those with any weight on this hand's finger bones), their finger (dominant chain) and the weights, from the rest pose."""
    names = {g.index: g.name for g in mesh.vertex_groups}
    fin = {f: {g.index for g in mesh.vertex_groups if g.name.startswith(f"mixamorig:{side}Hand{f}")} for f in FINGERS}
    n = len(mesh.data.vertices); W = np.zeros((n, len(FINGERS)), np.float32)
    for v in mesh.data.vertices:
        for g in v.groups:
            for k, f in enumerate(FINGERS):
                if g.group in fin[f]: W[v.index, k] += g.weight
    return W


def _evaluated(mesh):
    ev = mesh.evaluated_get(bpy.context.evaluated_depsgraph_get()); me = ev.to_mesh()
    co = np.array([(mesh.matrix_world @ v.co)[:] for v in me.vertices]); polys = [tuple(p.vertices) for p in me.polygons]; ev.to_mesh_clear(); return co, polys


def rig_pose_test(rig, mesh, side, out_finger, angles=(85.0, 100.0, 65.0), thumb_angles=(20.0, 30.0, 35.0), converge=3.0, dominant=0.5):
    """side: 'Left' or 'Right' (Mixamo's, the character's own: Left = +x). All fingers except `out_finger` curl about ONE axis, the knuckle line (index MCP to pinky MCP), so the curl planes are parallel, each
    finger turned `converge` degrees toward the middle finger per finger of distance (a fist's fan). Reports, against the rest pose: triangles of one finger overlapping another's, faces folded over
    (normal turned > 120 deg) and edges stretched past 3x, all in the hand's finger region. Linear blend skinning (what a game engine does): nothing is smoothed over."""
    from mathutils.bvhtree import BVHTree
    arm = bpy.data.objects[rig] if isinstance(rig, str) else rig; mesh = bpy.data.objects[mesh] if isinstance(mesh, str) else mesh
    bpy.context.view_layer.objects.active = arm; bpy.ops.object.mode_set(mode="POSE")
    for pb in arm.pose.bones: pb.matrix_basis = Matrix()
    bpy.context.view_layer.update()
    B = arm.data.bones; H = lambda f, i=1: Vector(B[f"mixamorig:{side}Hand{f}{i}"].head_local)
    axis = (H("Pinky") - H("Index")).normalized()                                   # the knuckle line
    mid_dir = (Vector(B[f"mixamorig:{side}HandMiddle3"].tail_local) - H("Middle")).normalized()
    palm_n = axis.cross(mid_dir).normalized()
    # curl direction: the middle fingertip must move toward -y (the character faces -y: the palm side when the arms hang)
    sgn = 1 if (Matrix.Rotation(np.radians(60), 3, axis) @ mid_dir).y < mid_dir.y else -1
    W = _rest_hand(arm, mesh, side); rest, polys = _evaluated(mesh)
    hand_v = np.where(W.sum(1) > 0.05)[0]
    order = {"Index": -2, "Middle": -1, "Ring": 0, "Pinky": 1}                      # position across the hand, for the fan
    mid_pos = order["Middle"]
    for f in FINGERS:
        if f == out_finger: continue
        ch = _chain(arm, side, f); angs = thumb_angles if f == "Thumb" else angles
        ax = axis.copy()
        if f != "Thumb": ax = Matrix.Rotation(np.radians(converge * (order[f] - mid_pos)) * sgn, 3, palm_n) @ axis
        tsg = sgn
        if f == "Thumb":                                  # the thumb opposes: it hinges about the axis that sweeps its tip toward the base of the little finger, over a limited range (no bending outward or back)
            t1 = Vector(B[f"mixamorig:{side}HandThumb1"].head_local); tdir = Vector(B[f"mixamorig:{side}HandThumb3"].tail_local) - t1; goal = H("Pinky") - t1
            ax = tdir.cross(goal).normalized()
            tsg = 1 if (Matrix.Rotation(np.radians(40), 3, ax) @ tdir - goal).length < (Matrix.Rotation(np.radians(-40), 3, ax) @ tdir - goal).length else -1
        head = Vector(ch[0].bone.head_local); cum = 0.0; prev = None
        for pb, a in zip(ch, angs):
            cum += a; R = Matrix.Rotation(np.radians(cum) * tsg, 3, ax)
            if prev is not None: head = head + prevR @ (Vector(pb.bone.head_local) - Vector(prev.bone.head_local))
            pb.matrix = Matrix.Translation(head) @ (R @ pb.bone.matrix_local.to_3x3()).to_4x4(); bpy.context.view_layer.update(); prev, prevR = pb, R
    bpy.context.view_layer.update(); pose, _ = _evaluated(mesh)
    # which finger does each triangle belong to: all three vertices dominated by that finger
    dom = np.where(W.max(1) > dominant, W.argmax(1), -1)
    def tree(k, co):
        fs = [p for p in polys if all(dom[v] == k for v in p)]
        return (BVHTree.FromPolygons([tuple(c) for c in co], fs, epsilon=0.0) if fs else None), len(fs)
    over = {}
    for k in range(len(FINGERS)):
        for j in range(k + 1, len(FINGERS)):
            ta, na = tree(k, pose); tb, nb = tree(j, pose); ra, _ = tree(k, rest); rb, _ = tree(j, rest)
            if ta and tb:
                n_pose = len(ta.overlap(tb)); n_rest = len(ra.overlap(rb)) if ra and rb else 0
                if n_pose - n_rest > 0: over[f"{FINGERS[k]}-{FINGERS[j]}"] = n_pose - n_rest
    # folded faces and stretched edges in the hand
    hv = set(hand_v.tolist()); folded = 0; stretched = 0; worst = 0.0
    for p in polys:
        if all(v in hv for v in p):
            a0 = np.cross(rest[p[1]] - rest[p[0]], rest[p[2]] - rest[p[0]]); a1 = np.cross(pose[p[1]] - pose[p[0]], pose[p[2]] - pose[p[0]])
            d = np.linalg.norm(a0) * np.linalg.norm(a1)
            if d > 1e-14 and (a0 @ a1) / d < -0.5: folded += 1
            for i in range(len(p)):
                e0 = np.linalg.norm(rest[p[i]] - rest[p[(i + 1) % len(p)]]); e1 = np.linalg.norm(pose[p[i]] - pose[p[(i + 1) % len(p)]])
                if e0 > 1e-6: r = e1 / e0; worst = max(worst, r); stretched += r > 3.0
    print(f"{side} hand, '{out_finger}' out: overlapping triangles {over or 'none'}; folded faces {folded}; edges stretched >3x: {stretched // 2} (worst {worst:.1f}x)")
    bpy.ops.object.mode_set(mode="OBJECT")
    return {"overlap": over, "folded": folded, "stretched": stretched // 2, "worst": worst}
