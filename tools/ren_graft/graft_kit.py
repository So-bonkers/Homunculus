"""Graft parts from better TRELLIS.2 models onto the kit's base body, all in the reference glTF frame (y up, faces +z): the approved head (bust, placed by GRAFT.json) and the hands of the
full-body model. The base body loses its hands below the cuffs and its head above the neck's narrowest point; the bust keeps face, hair, ears and neck (down inside the collar), not its hood or
headphones; the hands are the full-body model's skin-coloured faces below the cuffs. Colours come from each GLB's own texture. -> OUT_DIR/{body,head,hands}.glb
    trellis venv python tools/ren_graft/graft_kit.py ASSEMBLED_BODY.glb BUST.glb GRAFT.json FULLBODY.glb OUT_DIR [--neck 0.34] [--collar 0.30] [--chin 0.345] [--cuff 0.02] [--hand-x 0.09]"""
import sys, os, json, argparse, numpy as np, trimesh
ap = argparse.ArgumentParser(); ap.add_argument("body"); ap.add_argument("bust"); ap.add_argument("graft"); ap.add_argument("full"); ap.add_argument("out"); ap.add_argument("--hoodie", required=True, help="the placed hoodie (its cuffs receive the hands)"); ap.add_argument("--base-full", default=None, help="the placed base body BEFORE hiding (to fit the hands on its own hands)")
for k, v in (("wrist", -0.005), ("forearm_top", 0.16), ("neck", 0.34), ("collar", 0.30), ("chin", 0.345), ("cuff", 0.02), ("hand_x", 0.09), ("hand_low", -0.16)): ap.add_argument("--" + k.replace("_", "-"), type=float, default=v)
a = ap.parse_args(); os.makedirs(a.out, exist_ok=True)
def face_colours(m):
    tex = np.asarray(m.visual.material.baseColorTexture.convert("RGB")).astype(float) / 255; H, W = tex.shape[:2]; uv = np.asarray(m.visual.uv)[m.faces].mean(1)
    return tex[np.clip(((1 - uv[:, 1]) * H).astype(int), 0, H - 1), np.clip((uv[:, 0] * W).astype(int), 0, W - 1)]
def classes(c):
    r, g, b = c[:, 0], c[:, 1], c[:, 2]; lum = c @ np.array([0.2126, 0.7152, 0.0722]); skin = (r > 0.15) & (g < 0.75 * r) & (b < 0.6 * r) & (r - b > 0.12)
    return skin, lum
def keep(m, sel): m = m.copy(); m.update_faces(sel); m.remove_unreferenced_vertices(); return m
body = trimesh.load(a.body, force="mesh", process=False); ctr = body.triangles_center
hand_zone = (ctr[:, 1] < a.forearm_top) & (ctr[:, 1] > a.hand_low) & (np.abs(ctr[:, 0]) > a.hand_x)          # the base body's hands AND forearms: the sleeves cover the arms, the new hands sit in the cuffs
keep(body, ~hand_zone & (ctr[:, 1] < a.neck)).export(os.path.join(a.out, "body.glb")); print("body: dropped", int((hand_zone | (ctr[:, 1] >= a.neck)).sum()), "faces (hands, head)")
bust = trimesh.load(a.bust, force="mesh", process=False); bust.apply_transform(np.array(json.load(open(a.graft))["matrix"])); bc = bust.triangles_center; sk, lum = classes(face_colours(bust))
neck_axis = np.median(bc[sk & (bc[:, 1] > a.collar) & (bc[:, 1] < a.chin)][:, [0, 2]], axis=0); rad = np.linalg.norm(bc[:, [0, 2]] - neck_axis, axis=1)
head_sel = ((bc[:, 1] >= a.chin) & ((rad < 0.082) | sk)) | (sk & (bc[:, 1] >= a.collar - 0.03) & (rad < 0.06))
head_sel &= ~((bc[:, 1] < a.chin + 0.05) & (rad > 0.068) & ~sk)                     # the bust's own hood rim around the collar (it showed as two dark wings)
keep(bust, head_sel).export(os.path.join(a.out, "head.glb")); print("head: kept", int(head_sel.sum()), "of", len(head_sel), "faces; neck axis", neck_axis.round(4))
full = trimesh.load(a.full, force="mesh", process=False); fc = full.triangles_center; fsk, _ = classes(face_colours(full))
# each hand of the full-body model is fitted (trimmed similarity ICP) onto the base body's own hand, which hangs on its forearm inside the sleeve; the base keeps its forearm and wrist
from scipy.spatial import cKDTree
base0 = trimesh.load(a.base_full, force="mesh", process=False) if a.base_full else body; b0c = base0.triangles_center
def icp(S, T, it=60, frac=0.8):
    tree = cKDTree(T); s, R, t = 1.0, np.eye(3), T.mean(0) - S.mean(0)
    for _ in range(it):
        X = s * S @ R.T + t; d, i = tree.query(X); k = d <= np.quantile(d, frac); A, Bp = S[k], T[i[k]]; ma, mb = A.mean(0), Bp.mean(0); Ac, Bc = A - ma, Bp - mb
        U, D, Vt = np.linalg.svd(Bc.T @ Ac / len(A)); Sg = np.eye(3); Sg[2, 2] = -1 if np.linalg.det(U) * np.linalg.det(Vt) < 0 else 1; R = U @ Sg @ Vt; s = np.trace(np.diag(D) @ Sg) / Ac.var(0).sum(); t = mb - s * R @ ma
    d, _ = tree.query(s * S @ R.T + t); return s, R, t, float(np.median(d))
hand_meshes = []
# each hand goes into its sleeve's cuff: the cuff = the hoodie's open-edge loop at that sleeve's end (centre, radius), the sleeve's axis = from the sleeve 6 cm up to the cuff centre;
# the hand's wrist (its top slice) sits 1.2 cm inside the cuff, its long axis (PCA) along the sleeve axis, scaled so the wrist is ~0.8 of the cuff's width
from trimesh.grouping import group_rows
hood = trimesh.load(a.hoodie, force="mesh", process=False); hw = hood.copy(); hw.merge_vertices(); E = hw.edges_sorted; bE = E[group_rows(E, require_count=1)]
import scipy.sparse as sp_; from scipy.sparse.csgraph import connected_components as cc_
nV = len(hw.vertices); g = sp_.coo_matrix((np.ones(len(bE)), (bE[:, 0], bE[:, 1])), shape=(nV, nV)); _, lab = cc_(g, directed=False); bv = np.unique(bE); loops = {}
for l in np.unique(lab[bv]):
    P = hw.vertices[bv[lab[bv] == l]]
    if len(P) > 20: loops[l] = P
for sgn in (1, -1):
    cand = [(P.mean(0), P) for P in loops.values() if sgn * P.mean(0)[0] > 0.1 and P.mean(0)[1] < 0.15]
    c_, P = min(cand, key=lambda q: q[0][1]) if cand else (None, None)
    if c_ is None: print("no cuff found on side", sgn); continue
    r_cuff = np.median(np.linalg.norm(P - c_, axis=1)); up = hw.vertices[(np.linalg.norm(hw.vertices - c_, axis=1) < 0.09) & (hw.vertices[:, 1] > c_[1] + 0.04)]
    axis = c_ - up.mean(0); axis /= np.linalg.norm(axis)                                         # pointing out of the sleeve (down the arm)
    src = fsk & (fc[:, 1] < a.cuff + 0.01) & (fc[:, 1] > a.hand_low) & (sgn * fc[:, 0] > a.hand_x); hm = keep(full, src); V = hm.vertices
    hc = V.mean(0); U, S_, Vt = np.linalg.svd(V - hc, full_matrices=False); hax = Vt[0] if Vt[0][1] < 0 else -Vt[0]            # the hand's long axis, pointing to the fingertips (down)
    tproj = (V - hc) @ hax; wrist_pts = V[tproj < np.quantile(tproj, 0.06)]; wc = wrist_pts.mean(0); w_rad = np.median(np.linalg.norm(wrist_pts - wc - np.outer((wrist_pts - wc) @ hax, hax), axis=1))
    v1, v2 = hax, axis; cr = np.cross(v1, v2); co = float(v1 @ v2); K = np.array([[0, -cr[2], cr[1]], [cr[2], 0, -cr[0]], [-cr[1], cr[0], 0]]); Rm = np.eye(3) + K + K @ K / (1 + co)
    k = float(np.clip(0.8 * r_cuff / max(w_rad, 1e-4), 0.85, 1.2)); target = c_ - axis * 0.012
    M = np.eye(4); M[:3, :3] = k * Rm; M[:3, 3] = target - k * Rm @ wc; hm.apply_transform(M); hand_meshes.append(hm)
    print(f"hand {'left' if sgn > 0 else 'right'}: cuff radius {r_cuff:.4f}, wrist radius {w_rad:.4f}, scale {k:.3f}, sleeve axis {axis.round(2)}", flush=True)
trimesh.util.concatenate(hand_meshes).export(os.path.join(a.out, "hands.glb")); print("hands written")
