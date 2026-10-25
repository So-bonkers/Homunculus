# TRELLIS.2 on the RX 7900 XTX (ROCm): copies of the working scripts

These are **copies** of the scripts in `~/trellis2_test` (made 2026-10-25), kept here so the port is not lost. The pipeline (`homunculus/charkit/jobs.py`, `CHARKIT_TRELLIS` to override)
still runs the originals in `~/trellis2_test`, because they need that patched venv. If you change one, change both, or point the pipeline here once the venv moves.

| file | what |
|---|---|
| `run_trellis.py` | image (RGBA, background already cut) -> `OUT/s<seed>/{state.pt, raw_shape.glb, textured.glb}`; `--batch FILE` (lines `IMAGE OUT_DIR`) and `--seeds 42,7` load the models once for many jobs |
| `export_trellis.py` | re-export a result from its `state.pt` (textured GLB, and a `vertex_colours.glb` straight from the colour voxels, to tell bake errors from generation errors) |
| `shims/flash_attn/__init__.py` | stand-in for flash-attn's varlen functions using torch SDPA (exact, not approximate); installed as `venv/lib/python3.12/site-packages/flash_attn/` |
| `shims/nvdiffrast/{__init__,torch}.py` | stand-in for nvdiffrast: a torch UV rasteriser (only the texture bake uses it); installed as `venv/lib/python3.12/site-packages/nvdiffrast/` |
| `patches/cumesh.diff` | CuMesh for HIP: C++20, `hipcub::Sum`, `rocprim::tuple`, host-device `Vec3f` constructors, no `--extended-lambda` under HIP, a bounds-checked `set_flag` kernel |
| `patches/flexgemm.diff`, `patches/o-voxel.diff` | FlexGEMM and O-Voxel: C++20 only (the `.hip` files next to the sources are hipify output, made by the build) |

Typical use (as the pipeline runs it, in a memory-capped unit: TRELLIS keeps ~30 GB in RAM during the export):

    systemd-run --user --quiet --wait --collect -p MemoryMax=38G --working-directory=$HOME/trellis2_test \
        $HOME/trellis2_test/venv/bin/python run_trellis.py FIRST.png OUT --batch batch.txt --seeds 42,7 --type 1024_cascade --texture 4096

One 1024_cascade job: ~80 s model load (once per batch), 40-100 s generation, 1-3 min for the 4K GLB export; peak ~3-9 GB allocated (15 GB for 1536).

## How the venv is set up

- `~/trellis2_test/venv` (Python 3.12, made with uv) borrows ROCm torch 2.14.1+rocm7.2 from `homunculus/comfy/.venv` through a `.pth` file listing that venv's site-packages.
- TRELLIS.2: `microsoft/TRELLIS.2` at commit 75fbf01 in `~/trellis2_test/TRELLIS.2`. Weights: `microsoft/TRELLIS.2-4B`, `microsoft/TRELLIS-image-large` (only `ckpts/ss_dec_conv3d_16l8_fp16*`),
  `timm/vit_large_patch16_dinov3.lvd1689m` (see `~/trellis2_test/dl.py`).
- **FlexGEMM** (commit 6dd94a8), **CuMesh** (commit 12289e1) and **O-Voxel** (TRELLIS.2's copy) are built from `~/trellis2_test/ext/*` for gfx1100 with the patches above: C++20 is needed for
  the new torch headers. They were installed into the venv with uv (`uv pip install --no-build-isolation ./ext/<name>`, `PYTORCH_ROCM_ARCH=gfx1100`; this exact command was not recorded, only its uv output in `ext/*_build.log`).
- **flash_attn** and **nvdiffrast** are not installed packages: the shims above are dropped into site-packages. `run_trellis.py` sets `ATTN_BACKEND=sdpa` (dense) and `SPARSE_ATTN_BACKEND=flash_attn` (the shim).
- **DINOv3**: the facebook repo is gated, so `run_trellis.py` swaps the feature extractor for timm's ungated copy `vit_large_patch16_dinov3.lvd1689m`, created with `dynamic_img_size=True`,
  because the pipeline asks for features at 512 AND 1024 pixels. It returns [cls, 4 registers, patches] before the final norm, then a plain layer norm, as the transformers version does.
- **RMBG-2.0** is gated too: it is replaced by a stub that refuses, so give a picture whose background is already transparent (charkit cuts it with rembg `birefnet-general`).

## Pitfalls (do not undo these)

- **Never set `PYTORCH_HIP_ALLOC_CONF` / `PYTORCH_CUDA_ALLOC_CONF` `expandable_segments`**: on ROCm 7.2 it gave illegal memory accesses (the run died in plain torch ops).
- **CuMesh `fill_holes` is skipped** (`TRELLIS_FILL_HOLES=1` turns it back on): its boundary-loop tracing gives out-of-range edge ids on real meshes on gfx1100. The mesh before the step is
  saved as `before_fill_holes.npz` for an offline repro. The GLB export's remesh closes small holes.
- All models get `requires_grad_(False)`: FlexGEMM's training-path kernel (neighbour map with backward prep) faults on gfx1100.
- GPU errors are reported late. To find the real place, run with `AMD_SERIALIZE_KERNEL=3 HIP_LAUNCH_BLOCKING=1`.
- TRELLIS's raw output is z-up facing -y. The GLBs it exports are glTF y-up facing +z.
- 1536_cascade: 6-8 min a job; the 32M-face remesh in the export runs out of RAM.
- Never `pkill -f` / `pgrep -f` with the script's name: it matches the calling shell too. Kill by PID.
