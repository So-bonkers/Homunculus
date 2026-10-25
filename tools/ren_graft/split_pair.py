"""Split a TRELLIS.2 GLB holding a PAIR (shoes) into its two largest connected pieces, light on memory (welded by rounded position, scipy connected components):
writes OUT_left.glb and OUT_right.glb (by x of the centroid in the glTF frame: +x = the character's left when it faces +z) with the original UVs and texture.
    trellis venv python tools/ren_graft/split_pair.py PAIR.glb OUT_PREFIX"""
import sys, numpy as np, trimesh, scipy.sparse as sp
from scipy.sparse.csgraph import connected_components
m = trimesh.load(sys.argv[1], force="mesh", process=False); out = sys.argv[2]
key = np.round(m.vertices / 1e-6).astype(np.int64); _, weld = np.unique(key, axis=0, return_inverse=True); weld = weld.ravel(); F = weld[m.faces]
n = weld.max() + 1; e = np.concatenate([F[:, [0, 1]], F[:, [1, 2]], F[:, [2, 0]]]); g = sp.coo_matrix((np.ones(len(e), np.int8), (e[:, 0], e[:, 1])), shape=(n, n))
k, lab = connected_components(g, directed=False); fl = lab[F[:, 0]]; sizes = np.bincount(fl); top = np.argsort(sizes)[::-1][:2]; print(k, "pieces; the two largest:", sizes[top].tolist())
pieces = []
for t in top:
    sub = m.submesh([np.nonzero(fl == t)[0]], append=True); pieces.append(sub)
pieces.sort(key=lambda p: p.vertices[:, 0].mean())
pieces[0].export(out + "_right.glb"); pieces[1].export(out + "_left.glb"); print("wrote", out + "_right.glb", out + "_left.glb", [len(p.faces) for p in pieces])
