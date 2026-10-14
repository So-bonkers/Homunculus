# Dance from a video

**In the web app:** the Animate page (`/ui#/animate`): pick any rigged character, drop a video, drag the range (or play it and press Start here / End here), Copy the dance. The job is followed as stages (cut, body motion, camera, retarget, texture, preview, side by side), each with its time and a report, and the time left (the estimates in `homunculus/stages/video_progress.py`, scaled by how fast the finished stages went). When it is done the reference and the character play together on one clock; scrub, slow down, orbit the 3D view. The same is in a run's Animate tab. The job waits for the GPU like the other jobs and adds a clip to the run (with a preview render and the video next to it). It does everything below, plus the camera step (a moving camera is tracked from the background and taken out of the dancer's path; a steady one is left alone). The rest of this page is the same pipeline by hand.

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
The dance's heading is not recoverable from the clip: if the character faces away from the render camera, pass `--yaw 180` (any angle) to `smpl_to_bvh.py`. For the first test clip, where the dancer faces the camera at the start, 180 is right.

Body only (no fingers), depth is guessed from one camera, feet slide (0.6-0.7 body heights per second while low in the first test), fast spins and floor work are weaker. Tested on one 20 s freestyle slice (dark clothes, coloured light, steady camera): the arm and leg poses matched the footage at five checked moments.

## Fingers (work in progress, 2026-10-14)
GVHMR gives the body only, so a dance from a video leaves every finger at rest. The hand-pose layer (`homunculus/blender_handpose.py`) can now give each hand a **timeline of poses** (open, relaxed, fist, grip, point, thumbs up, pinch; eased between), not one pose for the whole clip:

```json
{"tracks": {"left": [[0, "open"], [2.0, "fist"], [5.0, "point"]], "right": [[0, "fist"], [3.0, "open"]]}, "ease": 0.13, "ramp": 6, "lib": "<handpose.LIB>"}
```
```bash
blender -b --python homunculus/blender_handpose.py -- clip.glb spec.json      # rewrites the GLB (and the FBX next to it)
```
Times are in seconds from the start of the clip. Tried on the Thriller rig with a hand-made track: open, fist, point, grip and thumbs-up all show on both hands at the set times.

**The timeline editor** (Animate tab, under the video and the character of a dance from a video): one lane per hand, a block per pose. Play the video and press **1-7** (open, relaxed, fist, grip, point, thumbs up, pinch) at the moment a hand changes; **L / R / B** choose the left, right or both hands; click a block to change or remove it, drag its left edge to move the change. **Apply to the model** saves the timeline (`runs/<run>/09_animate/hands/<clip>.json`: these are also the labels of a later classifier) and bakes it into a copy of the clip (`<clip>_hands.glb`, about 10 s on the CPU); the original clip is untouched, and an empty timeline takes the fingers off again. API: `GET /api/hands/<run>/<clip>`, `POST /api/hands`. Code: `homunculus/hands.py`, `web/src/features/animate/HandTimeline.tsx`.

**The label library** (`homunculus/handshapes.py`): 48 hand shapes in seven groups (neutral, curved, closed, pointing, signs, pinch and snap, finger wave), each defined the way sign-language handshapes are: a state per finger (straight, soft, curved, claw, hook, bent, half, fist, tight), a thumb position (side, out, up, across, oppose, tucked) and how far the fingers are spread. Every shape has a picture (side view and top view, `static/hands/`; redraw with `python -m homunculus.hand_library <rig.fbx|glb>`, on a Mixamo character: the project's own Make-It-Animatable rigs orient the finger bones differently and curl backwards, so they are not used). The editor shows nine pinned poses on keys 1-9 (star a pose in the picker to pin it), an **All poses** picker with search and categories, and **Gestures**: snap, flick, clench-release, burst, finger wave, jazz-hands shake and finger tap, dropped at the playhead as a timed run of poses (timings are animation estimates, editable afterwards). Each change has its own **transition**: smooth (minimum jerk, 0.13 s), quick (0.07 s), snap (0.05 s with a little overshoot), linear or cut, and an optional length in milliseconds; a change after a short pose is shortened so a quick accent still arrives. See [research/08](research/08_hand_label_vocabularies.md) for the vocabularies this is based on (no published vocabulary ships joint angles: the shared scheme is finger states + thumb + spread) and the timing facts (peak finger speed about 1,300 degrees a second, so a full curl takes at least ~70 ms).

Where the poses come from automatically is the open part. In a wide shot of a group the hands are about 40 px (1080p video), blurred and partly hidden, so a hand-pose estimator cannot read the fingers there; a close shot (a hand over ~150 px) may. Planned: a classifier (open / fist / point ...) trained on the editor's labels plus synthetic hands (the rig's hand rendered in a known pose, drawn realistic under a depth map, degraded to 40 px), and the hand boxes saved per frame so the labels come with their crops.
