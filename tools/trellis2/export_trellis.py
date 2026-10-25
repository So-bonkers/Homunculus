"""Re-export a TRELLIS.2 result from its saved state (run_trellis.py writes OUT/state.pt): the textured GLB, and a reference mesh coloured per vertex straight from the colour voxels (no UVs, no bake), to tell bake errors from generation errors.
    venv/bin/python export_trellis.py OUT_DIR [--texture 4096] [--faces 1000000] [--only-vertex-colours]"""
import os, sys, argparse
HERE = os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0, os.path.join(HERE, "TRELLIS.2"))
ap = argparse.ArgumentParser(); ap.add_argument("out"); ap.add_argument("--texture", type=int, default=4096); ap.add_argument("--faces", type=int, default=1000000); ap.add_argument("--only-vertex-colours", action="store_true"); ap.add_argument("--state", default="state.pt"); ap.add_argument("--tag", default=""); a = ap.parse_args()
import torch, numpy as np, trimesh, cumesh
cumesh.CuMesh.fill_holes = lambda self, *k, **kw: None                      # see run_trellis.py
from flex_gemm.ops.grid_sample import grid_sample_3d
import o_voxel
S = torch.load(os.path.join(a.out, a.state), weights_only=False); v, f, attrs, coords = S["vertices"].cuda(), S["faces"].cuda(), S["attrs"].cuda(), S["coords"].cuda(); vs = S["voxel_size"]; L = S["layout"]
aabb = torch.tensor([[-0.5, -0.5, -0.5], [0.5, 0.5, 0.5]], device="cuda"); grid = ((aabb[1] - aabb[0]) / vs).round().int()
col = grid_sample_3d(attrs, torch.cat([torch.zeros_like(coords[:, :1]), coords], -1), shape=torch.Size([1, attrs.shape[1], *grid.tolist()]), grid=((v - aabb[0]) / vs).reshape(1, -1, 3), mode="trilinear")
col = col.reshape(-1, attrs.shape[1])[:, L["base_color"]].clamp(0, 1).cpu().numpy()
vv = v.cpu().numpy(); vv = np.stack([vv[:, 0], vv[:, 2], -vv[:, 1]], 1)                  # z-up -> glTF y-up
trimesh.Trimesh(vertices=vv, faces=f.cpu().numpy(), vertex_colors=(np.concatenate([col, np.ones_like(col[:, :1])], 1) * 255).astype(np.uint8), process=False).export(os.path.join(a.out, f"vertex_colours{a.tag}.glb"))
print("wrote vertex_colours.glb", flush=True)
if not a.only_vertex_colours:
    glb = o_voxel.postprocess.to_glb(vertices=v, faces=f, attr_volume=attrs, coords=coords, attr_layout=L, voxel_size=vs, aabb=[[-0.5, -0.5, -0.5], [0.5, 0.5, 0.5]], decimation_target=a.faces, texture_size=a.texture, remesh=True, remesh_band=1, remesh_project=0, verbose=True)
    glb.export(os.path.join(a.out, f"textured{a.tag}.glb")); print("wrote textured.glb")
