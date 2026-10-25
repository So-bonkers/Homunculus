"""Kit assembly without Blender loops: place every item (align_item.py transforms), cut the garments' lids at their openings, tuck the base body GAP inside the garments, write one GLB per item
(placed, in the reference glTF frame) for Blender to load. GPU nearest-point queries (CuMesh cuBVH): a body vertex near a garment whose closest garment point is not at least GAP out along the
BODY's normal moves inward along that normal (garment normals are not reliable).
    trellis venv python tools/ren_graft/tuck_kit.py KIT_DIR OUT_DIR [--gap 0.004] [--reach 0.05]"""
import sys, os, json, argparse, numpy as np, torch, trimesh, cumesh
ap = argparse.ArgumentParser(); ap.add_argument("kit"); ap.add_argument("out"); ap.add_argument("--gap", type=float, default=0.004); ap.add_argument("--reach", type=float, default=0.05); ap.add_argument("--mode", default="hide", help="hide: delete body faces covered by a garment (robust; the default) | tuck: push the body in along its normals (needs consistent outward normals)"); ap.add_argument("--cover", type=float, default=0.03, help="hide: a body vertex this close to a garment counts as covered"); a = ap.parse_args(); os.makedirs(a.out, exist_ok=True)
GARMENTS = {"hoodie": ("bottom",), "joggers": ("bottom", "top"), "shoe_left": (), "shoe_right": ()}      # covering items (lids cut at the given openings)
items = {}
for f in sorted(os.listdir(a.kit)):
    if f.startswith("place_") and f.endswith(".json"):
        it = f[6:-5]; glb = os.path.join(a.kit, "shoes", "s42", f"{it}.glb") if it.startswith("shoe_") else os.path.join(a.kit, it, "s42", "textured.glb")
        if os.path.exists(glb):
            m = trimesh.load(glb, force="mesh", process=False); M = np.array(json.load(open(os.path.join(a.kit, f)))["matrix"]); m.apply_transform(M); items[it] = m; print("placed", it, len(m.faces), flush=True)
for g, where in GARMENTS.items():                         # glTF frame: y is up
    if g not in items: continue
    m = items[g]; fn = m.face_normals; fy = m.triangles_center[:, 1]; lo, hi = fy.min(), fy.max(); dead = np.zeros(len(fy), bool)
    if "bottom" in where: dead |= (fn[:, 1] < -0.85) & (fy < lo + 0.012)
    if "top" in where: dead |= (fn[:, 1] > 0.85) & (fy > hi - 0.012)
    m.update_faces(~dead); m.remove_unreferenced_vertices(); print(g, "lid faces removed", int(dead.sum()), flush=True)
body = items["body"]; V = torch.tensor(body.vertices, dtype=torch.float32, device="cuda")
w = trimesh.Trimesh(body.vertices.copy(), body.faces.copy(), process=False); w.merge_vertices(); trimesh.repair.fix_normals(w)          # TRELLIS's remesh leaves the winding inconsistent (half the normals point in)
from scipy.spatial import cKDTree
_, j = cKDTree(w.vertices).query(body.vertices); wn = w.vertex_normals[j]; c = body.vertices.mean(0)
if np.mean(((body.vertices - c) * wn).sum(1) > 0) < 0.5: wn = -wn                                   # outward overall
Nb = torch.tensor(wn.copy(), dtype=torch.float32, device="cuda"); print("outward normals:", round(float(np.mean(((body.vertices - c) * wn).sum(1) > 0)), 3), flush=True)
moved = torch.zeros(len(V), dtype=torch.bool, device="cuda"); covered = torch.zeros(len(V), dtype=torch.bool, device="cuda"); opening_keep = torch.zeros(len(V), dtype=torch.bool, device="cuda")
for g in GARMENTS:
    if g not in items: continue
    gm = items[g]; bvh = cumesh.cuBVH(torch.tensor(gm.vertices, dtype=torch.float32, device="cuda"), torch.tensor(gm.faces, dtype=torch.int32, device="cuda"))
    ylo, yhi = gm.vertices[:, 1].min() - 0.005, gm.vertices[:, 1].max() + 0.005; sel = (V[:, 1] > ylo) & (V[:, 1] < yhi); idx = torch.nonzero(sel)[:, 0]
    d, fid, uvw = bvh.unsigned_distance(V[idx], return_uvw=True); G = torch.tensor(gm.vertices, dtype=torch.float32, device="cuda")[torch.tensor(gm.faces, device="cuda")[fid.long()]]
    covered[idx[d < a.cover]] = True
    gw = trimesh.Trimesh(gm.vertices.copy(), gm.faces.copy(), process=False); gw.merge_vertices(); from trimesh.grouping import group_rows
    edges = gw.edges_sorted; bnd = gw.vertices[np.unique(edges[group_rows(edges, require_count=1)])]          # the garment's open edges: cuffs, hem, collar, waist, ankles
    if len(bnd):
        from scipy.spatial import cKDTree as _K; dd, _ = _K(bnd).query(V[idx].cpu().numpy()); near_edge = torch.as_tensor(dd < 0.03, device="cuda")
        opening_keep[idx[near_edge]] = True; print(g, "open-edge points", len(bnd), flush=True)
    if a.mode == "hide": continue
    P = (G * uvw[..., None]).sum(1); n = Nb[idx]; along = ((P - V[idx]) * n).sum(1)            # how far the garment lies out along the body normal
    need = (d < a.reach) & (along < a.gap); shift = (a.gap - along).clamp(min=0)
    V[idx[need]] -= n[need] * shift[need, None]; moved[idx[need]] = True; print(g, "body vertices tucked", int(need.sum()), flush=True)
body.vertices = V.cpu().numpy().astype(np.float64)
if a.mode == "hide":
    cov = (covered & ~opening_keep).cpu().numpy(); keep = ~cov[body.faces].all(1); body.update_faces(keep); body.remove_unreferenced_vertices(); print("body faces hidden under garments:", int((~keep).sum()), "kept", int(keep.sum()), flush=True)
for it, m in items.items(): m.export(os.path.join(a.out, f"{it}.glb"))
print("wrote", len(items), "items to", a.out, "| body vertices moved:", int(moved.sum()), "of", len(V))
