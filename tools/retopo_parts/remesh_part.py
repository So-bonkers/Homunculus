"""One part of a character, remeshed to quads:  RETOPO_SRC=model.glb blender -b --python remesh_part.py -- <R|L|full> <voxel_as_fraction_of_height> <target_quads> <out.ply>
R / L: a hand, cut out of the source mesh at the wrist (kept 0.022 H longer up the forearm so the wrist can be cut cleanly afterwards), capped, voxel-remeshed, slotted between the fingers, quadriflowed.
full: the whole body, no cuts. Writes a PLY at real size and hands.json next to it (hand_analysis.py's result: wrist planes, finger ranges, slot positions).
Nothing here is a measured distance: the hands, wrists, fingers and slots come from hand_analysis.py (ratios of the body height H and of the hand length), the voxel sizes are fractions of H.
Why scale: Quadriflow in Blender 5.2 refuses ("needs to be manifold") a perfectly manifold mesh whose edges are short, so the mesh is scaled to a 180 m figure for it and back down after.
Always run it under a timeout (driver: run_parts.py): Quadriflow has no time limit and can hang for ever on some meshes; another voxel size usually gets past it."""
import bpy, bmesh, sys, os, json, time, copy
import numpy as np
from mathutils import Vector, Matrix
sys.path.insert(0, os.path.dirname(os.path.abspath(sys.argv[sys.argv.index("--python") + 1])))
import hand_analysis
piece, voxel, target, out = sys.argv[sys.argv.index("--") + 1:][:4]
voxel, target = float(voxel), int(target)
bpy.ops.wm.read_factory_settings(use_empty=True)
bpy.ops.import_scene.gltf(filepath=os.environ["RETOPO_SRC"])
o = next(x for x in bpy.data.objects if x.type == "MESH")
n = len(o.data.vertices); a = np.empty(n * 3, np.float32); o.data.vertices.foreach_get("co", a); P = a.reshape(n, 3)
A = hand_analysis.analyse(P); H = A["height"]; scale = 180.0 / H; voxel *= H
EXT = 0.022 * H                                       # a hand piece keeps this much forearm
json.dump(A, open(os.path.join(os.path.dirname(out), "hands.json"), "w"))
for s in ("R", "L"):
    if not A[s]["ok"]: print(f"[{piece}] hand {s}: {A[s]['notes']}", flush=True)
pl = {s: (np.array(A[s]["wrist_point"]) - EXT * np.array(A[s]["axis"]), np.array(A[s]["axis"])) for s in ("R", "L")}      # the cut planes of the hand pieces


def sel(x):
    bpy.ops.object.select_all(action="DESELECT"); x.select_set(True); bpy.context.view_layer.objects.active = x


def inhand(v, s):
    """Past the cut plane and inside the tube round the arm axis (a tube, not an x cut: the legs are never in it)."""
    p, ax = pl[s]; d = np.array(v.co) - p
    return d @ ax > 0 and np.linalg.norm(d - (d @ ax) * ax) < A[s]["tube_radius"]


def torn_tip_domes(bm, tips, H):
    """Torn fingertips: the source's fingers can end in ragged open tubes (jagged shreds). A flat hole fill leaves chopped stumps (and the shreds voxelise into a crust). So: find every open boundary loop of finger size near a hand's
    fingertip, cut the ragged fringe off with a clean plane 0.7 radii behind the loop (only the geometry within 1.6 radii of it), and close the clean cut with a dome (three rings and an apex, a hemisphere of 0.95 radii).
    Returns how many tips were domed."""
    def loops():
        seen = set(); out = []
        for e in [e for e in bm.edges if e.is_boundary]:
            if e.index in seen: continue
            st = [e]; seen.add(e.index); g = []
            while st:
                a = st.pop(); g.append(a)
                for v in a.verts:
                    for b in v.link_edges:
                        if b.is_boundary and b.index not in seen: seen.add(b.index); st.append(b)
            out.append(g)
        return out
    def ordered(g):
        adj = {}
        for e in g:
            a, b = e.verts; adj.setdefault(a, []).append(b); adj.setdefault(b, []).append(a)
        if any(len(v) != 2 for v in adj.values()): return None
        start = next(iter(adj)); ring = [start]; prev = None; cur = start
        while True:
            nxt = [v for v in adj[cur] if v is not prev]; nxt = nxt[0] if nxt else None
            if nxt is None or nxt is start: break
            ring.append(nxt); prev, cur = cur, nxt
            if len(ring) > len(adj): return None
        return ring if len(ring) == len(adj) else None
    done = 0; handled = []; bm.verts.ensure_lookup_table()
    while True:                                                                      # one tip at a time; the loops are looked up again after each, as cutting and capping change the mesh
        pick = None
        for g in loops():
            vs = list({v for e in g for v in e.verts})
            if len(vs) < 6: continue
            c = sum((v.co for v in vs), Vector()) / len(vs); r = sum((v.co - c).length for v in vs) / len(vs)
            if not (0.0015 * H < r < 0.012 * H) or min((c - Vector(t)).length for t in tips) > 0.12 * H: continue
            if any((c - h_).length < 1.5 * r for h_ in handled): continue
            pick = (vs, c, r); break
        if pick is None: break
        vs, c, r = pick; handled.append(c.copy()); vset = set(vs)
        inside = [v for v in bm.verts if (v.co - c).length < 3 * r and v not in vset]
        if len(inside) < 4: continue
        d = (c - sum((v.co for v in inside), Vector()) / len(inside)).normalized()                 # out of the finger, along its axis
        pco = c - d * 0.7 * r; near = [v for v in bm.verts if (v.co - c).length < 2.3 * r]; nset = set(near)
        ne = list({e for v in near for e in v.link_edges if e.verts[0] in nset and e.verts[1] in nset}); nf = list({f for v in near for f in v.link_faces if all(w in nset for w in f.verts)})
        bmesh.ops.bisect_plane(bm, geom=near + ne + nf, plane_co=pco, plane_no=d, dist=1e-7, clear_outer=True)
        bmesh.ops.delete(bm, geom=[v for v in bm.verts if not v.link_faces], context="VERTS")
        bm.verts.ensure_lookup_table(); bm.edges.ensure_lookup_table()
        for g2 in loops():
            ring = ordered(g2)
            if ring is None or len(ring) < 6: continue
            c2 = sum((v.co for v in ring), Vector()) / len(ring)
            if abs((c2 - pco).dot(d)) > 0.15 * r or (c2 - pco).length > 0.6 * r: continue
            r2 = sum((v.co - c2).length for v in ring) / len(ring); prev_ring = ring
            for th in (30, 58, 80):
                sc_, hh = np.cos(np.radians(th)), r2 * 0.95 * np.sin(np.radians(th))
                new = [bm.verts.new(c2 + (v.co - c2) * sc_ + d * hh) for v in ring]
                for i in range(len(ring)):
                    bm.faces.new((prev_ring[i], prev_ring[(i + 1) % len(ring)], new[(i + 1) % len(ring)], new[i]))
                prev_ring = new
            ap = bm.verts.new(c2 + d * r2 * 0.95)
            for i in range(len(ring)): bm.faces.new((prev_ring[i], prev_ring[(i + 1) % len(ring)], ap))
            done += 1; break
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces[:]); return done


t0 = time.time()
while o.data.uv_layers: o.data.uv_layers.remove(o.data.uv_layers[0])
bm = bmesh.new(); bm.from_mesh(o.data)
bmesh.ops.remove_doubles(bm, verts=bm.verts[:], dist=1e-5)
print(f"[{piece}] torn fingertips closed with a dome: {torn_tip_domes(bm, [A[s_]['tip'] for s_ in ('R', 'L')], H)}", flush=True)
if piece != "full":
    for s in ("R", "L"):
        bmesh.ops.bisect_plane(bm, geom=bm.verts[:] + bm.edges[:] + bm.faces[:], plane_co=Vector(pl[s][0]), plane_no=Vector(pl[s][1]), dist=1e-6)
    bmesh.ops.delete(bm, geom=[v for v in bm.verts if not inhand(v, piece)], context="VERTS")
# close the cut and every hole in the source, for every piece (the whole body too): an open mesh is voxelised as a hollow, thin-walled tube (a 1-voxel double wall) around the hole
bnd = [e for e in bm.edges if e.is_boundary]
if bnd: bmesh.ops.holes_fill(bm, edges=bnd, sides=4000)
left = [e for e in bm.edges if e.is_boundary]
print(f"[{piece}] boundary edges before: {len(bnd)}, after fill: {len(left)}", flush=True)
if left: bmesh.ops.triangle_fill(bm, edges=left, use_beauty=False)
bmesh.ops.delete(bm, geom=[v for v in bm.verts if not v.link_faces], context="VERTS")
bm.to_mesh(o.data); bm.free()


def largest_shell(bm):
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces[:])
    seen = set(); comps = []
    for f in bm.faces:
        if f.index in seen: continue
        st = [f]; seen.add(f.index); g = []
        while st:
            a_ = st.pop(); g.append(a_)
            for e in a_.edges:
                for h in e.link_faces:
                    if h.index not in seen: seen.add(h.index); st.append(h)
        comps.append(g)
    comps.sort(key=len, reverse=True)
    bmesh.ops.delete(bm, geom=[f for g in comps[1:] for f in g], context="FACES")
    bmesh.ops.delete(bm, geom=[v for v in bm.verts if not v.link_faces], context="VERTS")
    return len(comps)


sel(o); o.data.remesh_voxel_size = voxel; o.data.remesh_voxel_adaptivity = 0.0
bpy.ops.object.voxel_remesh()
bm = bmesh.new(); bm.from_mesh(o.data); shells = largest_shell(bm)
idx = {v.index: i for i, v in enumerate(bm.verts)}
verts = [tuple(c * scale for c in v.co) for v in bm.verts]; faces = [tuple(idx[v.index] for v in f.verts) for f in bm.faces]
print(f"[{piece}] voxel {voxel*1000:.2f} mm: {len(faces)} faces, shells {shells} ({time.time()-t0:.1f}s)", flush=True)
bm.free()
nm = bpy.data.meshes.new("p"); nm.from_pydata(verts, [], faces); nm.update()
q = bpy.data.objects.new("p", nm); bpy.context.collection.objects.link(q); sel(q)
def smooth_band(nm, h, scale, passes=14):
    """Round the crease where the palm's flat cut meets the finger roots: Taubin smoothing (no shrinking) of the vertices in a band along the hand, from a bit behind the knuckle line to a third of the way along the
    fingers, fading out at both ends. The band is a fraction of the hand length."""
    Pw = np.array(h["wrist_point"]) * scale; ax = np.array(h["axis"]); L = h["hand_len"] * scale; sk = h["knuckle_s"] * scale
    n = len(nm.vertices); co = np.empty(n * 3, np.float64); nm.vertices.foreach_get("co", co); co = co.reshape(-1, 3)
    ed = np.empty(len(nm.edges) * 2, np.int64); nm.edges.foreach_get("vertices", ed); ed = ed.reshape(-1, 2)
    sm = lambda t: np.clip(t, 0, 1) ** 2 * (3 - 2 * np.clip(t, 0, 1)); sv = (co - Pw) @ ax
    w = sm((sv - (sk - 0.08 * L)) / (0.06 * L)) * (1 - sm((sv - (sk + 0.12 * L)) / (0.08 * L)))
    cnt = np.zeros(n); np.add.at(cnt, ed[:, 0], 1); np.add.at(cnt, ed[:, 1], 1); cnt = np.maximum(cnt, 1)
    def lap(lam):
        acc = np.zeros_like(co); np.add.at(acc, ed[:, 0], co[ed[:, 1]]); np.add.at(acc, ed[:, 1], co[ed[:, 0]])
        co[:] = co + (acc / cnt[:, None] - co) * (lam * w)[:, None]
    for _ in range(passes): lap(0.5); lap(-0.53)
    nm.vertices.foreach_set("co", co.ravel()); nm.update(); return int((w > 0).sum())


def round_edges(nm, h, scale, passes=10, lo_deg=14.0, span_deg=26.0):
    """Round the sharp lip along the knuckle row (where the palm's cut edge meets the finger roots) and any flap there, without touching the smooth parts: Taubin smoothing weighted by SHARPNESS (the largest angle between a vertex's
    normal and its neighbours') inside the band where the knuckle arch lies, from a bit behind the farthest-back root to a seventh of the hand beyond the knuckle line. (Smoothing a whole band regardless of sharpness left ring-shaped
    shading bands across the finger roots.)"""
    Pw = np.array(h["wrist_point"]) * scale; ax = np.array(h["axis"]); L = h["hand_len"] * scale; sk = h["knuckle_s"] * scale; off = max(f["root_offset"] for f in h["finger_lines"]) * scale
    bm = bmesh.new(); bm.from_mesh(nm); bm.normal_update(); n = len(bm.verts)
    co = np.array([v.co[:] for v in bm.verts]); nr = np.array([v.normal[:] for v in bm.verts]); ed = np.array([[e.verts[0].index, e.verts[1].index] for e in bm.edges])
    ang = np.degrees(np.arccos(np.clip((nr[ed[:, 0]] * nr[ed[:, 1]]).sum(1), -1, 1))); sharp = np.zeros(n); np.maximum.at(sharp, ed[:, 0], ang); np.maximum.at(sharp, ed[:, 1], ang)
    sm = lambda t: np.clip(t, 0, 1) ** 2 * (3 - 2 * np.clip(t, 0, 1)); sv = (co - Pw) @ ax
    band = sm((sv - (sk - off - 0.10 * L)) / (0.05 * L)) * (1 - sm((sv - (sk + 0.14 * L)) / (0.05 * L))); w = band * sm((sharp - lo_deg) / span_deg)
    cnt = np.zeros(n); np.add.at(cnt, ed[:, 0], 1); np.add.at(cnt, ed[:, 1], 1); cnt = np.maximum(cnt, 1)
    def lap(lam):
        acc = np.zeros_like(co); np.add.at(acc, ed[:, 0], co[ed[:, 1]]); np.add.at(acc, ed[:, 1], co[ed[:, 0]]); co[:] = co + (acc / cnt[:, None] - co) * (lam * w)[:, None]
    for _ in range(passes): lap(0.5); lap(-0.53)
    for v, c in zip(bm.verts, co): v.co = c
    bm.to_mesh(nm); bm.free(); nm.update(); return int((w > 0.05).sum())


def rebuild_fingers(q, nm, h, A, H, scale):
    """The four fingers made from scratch, so they cannot be fused: the source hand is cut at the knuckle line (the palm and the thumb, which ends below it, stay as generated) and each finger is a tapered
    capsule with an elliptical cross-section from its base to its tip (hand_analysis.finger_lines), as wide as the room its neighbours leave less a gap of a few voxels. All in real units, then scaled."""
    Pw = np.array(h["wrist_point"]); ax = np.array(h["axis"]); lat = np.array(h["lat"]); pn = np.array(h["palm_normal"]); L = h["hand_len"]; sk = h["knuckle_s"]
    bm = bmesh.new(); bm.from_mesh(nm)
    # the palm's distal edge follows the arch of the knuckles (the middle finger's root is the farthest out, the little finger's the furthest back): warp the palm along the hand by the arch, cut it flat, warp it back
    fls = h["finger_lines"]; bls = np.array([f["m0"] + f["m1"] * sk for f in fls]); ofs = np.array([f["root_offset"] for f in fls]); order_ = np.argsort(bls)
    def arch(lv): return np.interp(lv, bls[order_], ofs[order_])                  # beyond the outer fingers the offset of the nearest one is kept
    for v in bm.verts:
        c_ = np.array(v.co[:]) / scale; v.co = Vector((c_ + ax * arch((c_ - Pw) @ lat)) * scale)
    bmesh.ops.bisect_plane(bm, geom=bm.verts[:] + bm.edges[:] + bm.faces[:], plane_co=Vector((Pw + ax * sk) * scale), plane_no=Vector(ax), dist=1e-6 * scale, clear_outer=True)
    bmesh.ops.delete(bm, geom=[v for v in bm.verts if not v.link_faces], context="VERTS")
    bnd = [e for e in bm.edges if e.is_boundary]
    if bnd: bmesh.ops.holes_fill(bm, edges=bnd, sides=4000)
    left = [e for e in bm.edges if e.is_boundary]
    if left: bmesh.ops.triangle_fill(bm, edges=left, use_beauty=False)
    for v in bm.verts:
        c_ = np.array(v.co[:]) / scale; v.co = Vector((c_ - ax * arch((c_ - Pw) @ lat)) * scale)
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces[:]); bm.to_mesh(nm); bm.free(); nm.update()
    gap = 0.0016 * H; NR, NS, NT = 24, 10, 6; th = np.linspace(0, 2 * np.pi, NR, endpoint=False)
    d_ = P - Pw; s_ = d_ @ ax; l_ = d_ @ lat; z_ = d_ @ pn; fl_ = h["finger_lines"]; sp0 = fl_[0]["spacing"]; bl = [f["m0"] + f["m1"] * sk for f in fl_]
    mk = (np.abs(s_ - sk) < 0.04 * L) & (np.linalg.norm(d_ - np.outer(s_, ax), axis=1) < h["tube_radius"]) & (l_ > min(bl) - sp0) & (l_ < max(bl) + sp0)
    Tk = min(float(np.ptp(np.percentile(z_[mk], [5, 95]))), 1.5 * 0.9 * sp0); zc_palm = None
    rs = []                                                                          # the source's own finger shape: depth / width in the outer half of each finger (where the webs do not touch the reading)
    for f_ in fl_:
        if f_["reach"] <= sk: continue
        for x_ in (0.5, 0.62, 0.74, 0.86):
            sc_ = sk + x_ * (f_["reach"] - sk); lc_ = f_["m0"] + f_["m1"] * sc_
            m_ = (np.abs(s_ - sc_) < 0.012 * L) & (np.abs(l_ - lc_) < 0.5 * sp0) & (np.linalg.norm(d_ - np.outer(s_, ax), axis=1) < h["tube_radius"])
            if m_.sum() > 20 and np.ptp(l_[m_]) > 0: rs.append(float(np.ptp(z_[m_]) / np.ptp(l_[m_])))
    ratio_src = float(np.clip(np.median(rs), 0.8, 1.2)) if rs else 0.85                  # a finger of this character is as round as this; the textbook 0.85 made them flat
    print(f"[{piece}] finger depth/width measured on the source: {ratio_src:.2f} (from {len(rs)} cross-sections)", flush=True)       # the palm's thickness across the four finger bases, bounded by 1.5 finger widths. (Tried and dropped: the whole thickness (1-99 %) centred on the palm: it made the roots stick out past the palm as rim-like bulges.)
    band_all = (np.abs(s_ - sk) < 0.04 * L) & (np.linalg.norm(d_ - np.outer(s_, ax), axis=1) < h["tube_radius"])
    pinky_high = h.get("thumb_side") == "low"                                        # the little finger is on the side away from the thumb
    palm_edge = float(np.percentile(l_[band_all], 99 if pinky_high else 1))
    thumb_edge = float(np.percentile(l_[band_all], 1 if pinky_high else 99))               # and on the thumb's side            # the outline of the palm on that side: the pinky's root must run into it       # the palm's thickness across the four finger bases, bounded by 1.5 finger widths (the rough source surface would make it more)
    for k_, f in enumerate(h["finger_lines"]):
        c_ = bl[k_]; lo_ = (c_ + bl[k_ - 1]) / 2 if k_ > 0 else c_ - sp0 / 2; hi_ = (c_ + bl[k_ + 1]) / 2 if k_ < 3 else c_ + sp0 / 2
        if f["name"] == "pinky":
            if pinky_high: hi_ = max(hi_, palm_edge)
            else: lo_ = min(lo_, palm_edge)
        if f["name"] == "index":                                                         # the index finger's outer side runs into the web toward the thumb: cover the palm's edge there too (by at most 0.8 of a finger spacing)
            if pinky_high: lo_ = min(lo_, max(thumb_edge, lo_ - 0.8 * sp0))
            else: hi_ = max(hi_, min(thumb_edge, hi_ + 0.8 * sp0))
        root_c, root_hw = (lo_ + hi_) / 2 - c_, (hi_ - lo_) / 2 * 1.02                   # the root: from halfway to one neighbour to halfway to the other (or to the palm's edge)
        sb = sk - f["root_offset"] - 0.03 * L; m0, m1, dep = f["m0"], f["m1"], f["depth"]
        # the palm is arched (thinner and shifted toward its edges), so each root takes the depth range of the palm's cut face right under THIS finger, not one thickness and the finger's own depth for all
        mz_ = band_all & (np.abs(s_ - (sk - f["root_offset"] - 0.02 * L)) < 0.03 * L) & (l_ >= lo_ - 0.05 * sp0) & (l_ <= hi_ + 0.05 * sp0)
        if mz_.sum() > 20: zr_ = np.percentile(z_[mz_], [3, 97]); root_hd, zk_ = float(zr_[1] - zr_[0]) / 2, float(zr_[0] + zr_[1]) / 2
        else: root_hd, zk_ = 0.5 * Tk, dep
        base = Pw + lat * (m0 + m1 * sb) + ax * sb + pn * dep; tip = Pw + lat * (m0 + m1 * f["reach"]) + ax * f["reach"] + pn * dep
        d = tip - base; length = np.linalg.norm(d); d /= length; w = np.cross(pn, d); w /= np.linalg.norm(w); n = np.cross(d, w)
        sp, sc = f["spacing"], (0.9 if f["name"] == "pinky" else 1.0)
        # a finger starts as wide as the room it has (touching its neighbours: the skin between them arches into a web) and as deep as the palm it comes out of, and narrows to a finger over its first part:
        # the palm's cut face is then hidden, with no ledge across the knuckles. Width: 1.02 of the spacing at the root, 0.90 from a quarter of the way on, then the finger's taper; depth: the palm's, to 0.85 of the width by a third.
        smt = lambda t: min(1.0, max(0.0, t)) ** 2 * (3 - 2 * min(1.0, max(0.0, t)))
        TR = float(os.environ.get("RETOPO_ROOT_BLEND", "0.55"))                # how far along the finger (as a fraction of its length) the root's shape (the palm's cut face) blends into the finger's own: the back of the hand slopes into the finger, not a step
        # the source's fingers are not flat along the hand: they flex gently toward the palm (the middle of a finger lies ~10 mm further back at its root than at its tip). A rebuilt finger at one constant depth sat shifted
        # against the hand, so each finger follows the source's own depth curve (the median depth at six places along it), blended from the palm's cut-face depth at the root.
        sk_f = sk - f["root_offset"]; xs_, zs_ = [], []
        for x_ in (0.25, 0.40, 0.55, 0.70, 0.85, 0.95):
            sc_ = sk_f + x_ * (f["reach"] - sk_f); lc_ = m0 + m1 * sc_
            mm_ = (np.abs(s_ - sc_) < 0.012 * L) & (np.abs(l_ - lc_) < 0.5 * sp0) & (np.linalg.norm(d_ - np.outer(s_, ax), axis=1) < h["tube_radius"])
            if mm_.sum() > 15: xs_.append(x_); zs_.append(float(np.median(z_[mm_])))
        if len(xs_) >= 4:                                                          # a finger flexes in a smooth arc: a quadratic through the samples, kept within their range (the raw medians wobble by several mm and made the fingers lumpy)
            cf_ = np.polyfit(xs_, zs_, 2); lo_z, hi_z = min(zs_), max(zs_)
            zcurve = lambda x, cf_=cf_, lo_z=lo_z, hi_z=hi_z: float(np.clip(np.polyval(cf_, x), lo_z, hi_z))
        else: zcurve = lambda x: dep
        dcen = lambda x: zk_ * (1 - smt(x / TR)) + zcurve(x) * smt(x / TR)
        hw_line = lambda x: 0.5 * sp * sc * (0.96 + 0.06 * (1 - smt(x / 0.25))) * (1 - 0.22 * x)
        hw = lambda x: root_hw * (1 - smt(x / TR)) + hw_line(x) * smt(x / TR)
        coff = lambda x: root_c * (1 - smt(x / TR)); doff = lambda x: dcen(x) - dep
        hd = lambda x: root_hd * (1 - smt(x / TR)) + ratio_src * hw(x) * smt(x / TR)
        rtw, rtd = hw(1.0), hd(1.0); Ls = length - rtw
        rings = [(Ls * j / (NS - 1), hw(Ls * j / (NS - 1) / length), hd(Ls * j / (NS - 1) / length), coff(Ls * j / (NS - 1) / length), doff(Ls * j / (NS - 1) / length)) for j in range(NS)]
        rings += [(Ls + rtw * np.sin(np.pi / 2 * (j + 1) / (NT + 1)), rtw * np.cos(np.pi / 2 * (j + 1) / (NT + 1)), rtd * np.cos(np.pi / 2 * (j + 1) / (NT + 1)), 0.0, doff(1.0)) for j in range(NT)]
        # the root is squarer than a finger (a superellipse of power 5 against 2 for an ellipse), blending to a round finger over the first third, so it fills the corners of the palm's rectangular cut face (an ellipse left them as a thin ledge)
        def sq(c, pw): return np.sign(c) * np.abs(c) ** (2.0 / pw)
        V_ = []
        for u, rw, rd, co_, do_ in rings:
            pw_ = 2.0 + 3.0 * (1 - smt(u / length / TR)) if u < length * (TR + 0.1) else 2.0
            V_ += [base + d * u + lat * co_ + pn * do_ + w * rw * sq(np.cos(t), pw_) + n * rd * sq(np.sin(t), pw_) for t in th]; apex = len(V_); V_.append(base + d * length); ctr = len(V_); V_.append(base)
        F_ = [(j * NR + i, j * NR + (i + 1) % NR, (j + 1) * NR + (i + 1) % NR, (j + 1) * NR + i) for j in range(len(rings) - 1) for i in range(NR)]
        F_ += [((len(rings) - 1) * NR + (i + 1) % NR, (len(rings) - 1) * NR + i, apex) for i in range(NR)] + [(i, (i + 1) % NR, ctr) for i in range(NR)]
        me = bpy.data.meshes.new("finger"); me.from_pydata([tuple(c * scale for c in v) for v in V_], [], F_); me.update()
        fo = bpy.data.objects.new("finger", me); bpy.context.collection.objects.link(fo)
        bm_ = bmesh.new(); bm_.from_mesh(me); bmesh.ops.recalc_face_normals(bm_, faces=bm_.faces[:]); bm_.to_mesh(me); bm_.free()
        sel(q); md = q.modifiers.new("add", "BOOLEAN"); md.operation = "UNION"; md.object = fo; md.solver = "MANIFOLD"
        bpy.ops.object.modifier_apply(modifier="add"); bpy.data.objects.remove(fo, do_unlink=True)
        print(f"  finger {f['name']}: {1000 * length:.0f} mm long, {2000 * hw(0):.1f} x {2000 * hd(0):.1f} mm at the root, {2000 * rtw:.1f} x {2000 * rtd:.1f} mm at the tip", flush=True)
    bmx = bmesh.new(); bmx.from_mesh(nm); Pk = Vector((Pw + ax * sk) * scale); axv = Vector(ax); ex = 0.0
    for fc in bmx.faces:
        if abs((fc.calc_center_median() - Pk).dot(axv)) < 0.3 * 0.0005 * H * scale and fc.normal.dot(axv) > 0.9: ex += fc.calc_area()
    print(f"[exposed] flat cut face still showing at the knuckle line, after the fingers are added: {ex / scale ** 2 * 1e6:.1f} mm2", flush=True); bmx.free()


if piece in ("R", "L") and A[piece]["ok"]:
    h = A[piece]; Pw = np.array(h["wrist_point"]); ax = np.array(h["axis"]); lat = np.array(h["lat"]); pn = np.array(h["palm_normal"]); cc = np.array(h["centre"])
    s0 = h["slit_start"]; length = 1.4 * h["hand_len"] - s0                      # from where a web ends to past the fingertips
    thick, height = 0.0013 * H * scale, 0.05 * H * scale                         # a slot ~2.5 voxels wide, as tall as the hand is thick, with margin
    MODE = os.environ.get("RETOPO_FINGERS", "rebuild")                           # rebuild: the fingers are made from scratch (default); slots: cut slots in the source's fingers; plain: the hand as generated, only remeshed (its fingers keep whatever webbing the source has)
    if MODE == "rebuild": rebuild_fingers(q, nm, h, A, H, scale)
    for m0, m1 in (h["slits"] if MODE == "slots" else []):                                                     # lat = m0 + m1 * s: the line along the groove between two fingers
        d = ax + lat * m1; d /= np.linalg.norm(d); w = np.cross(pn, d); w /= np.linalg.norm(w); sm = s0 + length / 2      # the slot runs along d, is thin along w, tall along the palm normal
        ctr = Pw + lat * (m0 + m1 * sm) + ax * sm + pn * ((cc - Pw) @ pn)
        bpy.ops.mesh.primitive_cube_add(size=1.0); bl = bpy.context.active_object; bl.name = "blade"
        M = Matrix([[w[0], d[0], pn[0], ctr[0] * scale], [w[1], d[1], pn[1], ctr[1] * scale], [w[2], d[2], pn[2], ctr[2] * scale], [0, 0, 0, 1]])
        bl.matrix_world = M @ Matrix.Diagonal((thick, length * scale, height, 1.0))
        sel(q); md = q.modifiers.new("cut", "BOOLEAN"); md.operation = "DIFFERENCE"; md.object = bl; md.solver = "MANIFOLD"
        bpy.ops.object.modifier_apply(modifier="cut"); bpy.data.objects.remove(bl, do_unlink=True)
    bm2 = bmesh.new(); bm2.from_mesh(nm)
    bmesh.ops.remove_doubles(bm2, verts=bm2.verts[:], dist=1e-4); bmesh.ops.dissolve_degenerate(bm2, dist=1e-5, edges=bm2.edges[:]); largest_shell(bm2)
    bm2.to_mesh(nm); bm2.free(); nm.update()
    sel(q); nm.remesh_voxel_size = voxel * scale; nm.remesh_voxel_adaptivity = 0.0; bpy.ops.object.voxel_remesh()      # a boolean leaves slivers and pinches that Quadriflow refuses: derive a clean surface from the cut shape again (the slots are wider than a voxel, they stay)
    bm3 = bmesh.new(); bm3.from_mesh(nm); largest_shell(bm3); bm3.to_mesh(nm); bm3.free(); nm.update()
    if MODE == "rebuild" and os.environ.get("RETOPO_SMOOTH") == "1": print(f"[{piece}] knuckle band smoothed: {smooth_band(nm, h, scale)} vertices", flush=True)      # off by default: it left ring-shaped shading bands across the finger roots
    if MODE == "rebuild" and os.environ.get("RETOPO_ROUND", "1") == "1": print(f"[{piece}] sharp edges rounded at the knuckle row: {round_edges(nm, h, scale)} vertices", flush=True)
    print(f"[{piece}] fingers {MODE}: faces now {len(nm.polygons)}", flush=True)
    sel(q)
t1 = time.time(); r = bpy.ops.object.quadriflow_remesh(target_faces=target, mode="FACES")
print(f"[{piece}] quadriflow {r} faces {len(nm.polygons)} ({time.time()-t1:.1f}s)", flush=True)
if "FINISHED" not in r: sys.exit(3)
for v in nm.vertices: v.co *= 1.0 / scale
nm.update(); sel(q)
bpy.ops.wm.ply_export(filepath=out, export_selected_objects=True, export_normals=False, export_uv=False, export_colors="NONE")
print(f"[{piece}] wrote {out}", flush=True)
