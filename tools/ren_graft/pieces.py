"""Connected pieces of a TRELLIS.2 GLB (vertices welded by position first: the GLB splits them at UV seams), with size, bounds and mean texture colour each.
    trellis venv python tools/ren_graft/pieces.py MESH.glb [--top 12]"""
import sys, numpy as np, trimesh
m = trimesh.load(sys.argv[1], force="mesh"); uv = np.asarray(m.visual.uv); tex = np.asarray(m.visual.material.baseColorTexture.convert("RGB")).astype(float) / 255; H, W = tex.shape[:2]
col = tex[np.clip(((1 - uv[:, 1]) * H).astype(int), 0, H - 1), np.clip((uv[:, 0] * W).astype(int), 0, W - 1)]
m2 = m.copy(); m2.visual = trimesh.visual.ColorVisuals(m2, vertex_colors=(np.c_[col, np.ones(len(col))] * 255).astype(np.uint8)); m2.merge_vertices(merge_tex=True, merge_norm=True)
parts = m2.split(only_watertight=False); parts = sorted(parts, key=lambda p: -len(p.faces))
print(len(parts), "pieces; faces", len(m2.faces))
for p in parts[: int(sys.argv[3]) if len(sys.argv) > 3 else 12]:
    c = np.asarray(p.visual.vertex_colors)[:, :3].mean(0) / 255; b = p.bounds
    print(f"  {len(p.faces):8d} faces  x {b[0,0]:+.3f}..{b[1,0]:+.3f}  y {b[0,1]:+.3f}..{b[1,1]:+.3f}  z {b[0,2]:+.3f}..{b[1,2]:+.3f}  colour {np.round(c, 2)}")
