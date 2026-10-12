# Dance from a video

Video of one dancer -> SMPL motion (GVHMR) -> BVH (`tools/smpl_to_bvh.py`) -> your rigged character (`tools/retarget_bvh.py --map smpl`) -> preview (`tools/make_mp4.py --fixed`).

## One-time setup (everything lives in `gvhmr/`, which git ignores)
1. `git clone --depth 1 https://github.com/zju3dv/GVHMR gvhmr/repo`
2. `uv venv --python 3.12 gvhmr/.venv`, then PyTorch for ROCm (`uv pip install torch torchvision --index-url https://download.pytorch.org/whl/rocm7.2`) and the packages GVHMR imports (timm, lightning, pytorch-lightning, hydra-core, hydra-zen, hydra_colorlog, rich, numpy<2, scipy, einops, imageio, av, opencv-python, scikit-image, trimesh, smplx, ultralytics, cython_bbox, lapx, yacs, ...). The pinned CUDA 12.1 build in GVHMR's requirements is not used.
3. Body models need a free, non-commercial registration: SMPL (smpl.is.tue.mpg.de, version 1.1.0 with the neutral model) and SMPL-X (smpl-x.is.tue.mpg.de). Put `SMPLX_NEUTRAL.npz` in `gvhmr/repo/inputs/checkpoints/body_models/smplx/`. The SMPL `.pkl` was pickled with chumpy: strip it to plain numpy with a restricted unpickler and save it as `body_models/smpl/SMPL_NEUTRAL.pkl`.
4. Checkpoints (dpvo, gvhmr, hmr2, vitpose, yolo) from GVHMR's Google Drive folder; the ViTPose file hit Drive's quota, the mirror `camenduru/GVHMR` on HuggingFace has identical files.
5. `gvhmr/shim/pytorch3d`: the pure-torch rotation code copied from pytorch3d plus a small `knn`, and stubs for the renderer (not available on ROCm; rendering is done in Blender).

## Per video
```
ffmpeg -ss 30 -t 20 -i video.mp4 -vf fps=30 -an -c:v libx264 -crf 14 gvhmr/work/clip.mp4       # the model expects 30 fps; cut where the camera does not cut
gvhmr/.venv/bin/python tools/video_to_smpl.py --video gvhmr/work/clip.mp4 --output_root gvhmr/work/out -s      # -s = fixed camera
python3 -I tools/smpl_to_bvh.py gvhmr/work/out/clip/smpl_global.npz gvhmr/work/clip.bvh
blender -b --python tools/retarget_bvh.py -- <character.fbx> gvhmr/work/clip.bvh gvhmr/work/rt clip --map smpl --fps 30
.venv/bin/python tools/make_mp4.py gvhmr/work/rt/clip.fbx gvhmr/work/rt/clip.mp4 --fixed
```
A 20 s clip took about two and a half minutes on the Radeon (YOLO tracking, ViTPose, HMR2 features, then the model itself: under 2 s).

## What to expect
Body only (no fingers), depth is guessed from one camera, feet slide (0.6-0.7 body heights per second while low in the first test), fast spins and floor work are weaker. Tested on one 20 s freestyle slice (dark clothes, coloured light, steady camera): the arm and leg poses matched the footage at five checked moments.
