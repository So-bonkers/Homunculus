# Group dance from one fixed-camera video

Six dancers in one shot (We Dem Boyz, 0:13–2:03, 110 s, 4K, steady camera) become six characters in one scene, rendered from the camera of the video. Everything is in `tools/`; the data stays in `gvhmr/work/<name>/` (not in git).

## Steps
1. `track_raw.py`: track everyone in the 1080p, 30 fps cut (`tracks_raw.json`).
2. `group_tracks.py`: stitch tracker ids into N dancers by outfit (DINOv2-small + HSV histograms, average linkage, a cannot-link between ids that overlap in time).
3. `group_segments.py`: per frame, check that the box is still that dancer (similarity against the dancer's own mean appearance, sigma 6), bridge gaps up to 20 frames, drop stretches under 45 frames. Coverage 73–96 % per dancer.
4. `gvhmr_segments.py`: GVHMR (static camera) on every stretch; `video_to_smpl.py` also writes `smpl_incam.npz`, the body in the camera's frame.
5. `group_scene.py`: all dancers into one gravity-aligned frame. The floor is fitted to the feet (camera 1.48 m high, tilt 0.8°, 7.7 cm rms); the camera intrinsics are the ones GVHMR assumes (focal = image diagonal).
6. `register_group.py`: SMPL to BVH, retarget onto the rig with a recoloured texture per dancer (`retarget_bvh.py --texture`), clips registered in the Animate tab with `valid_ranges` (seconds where the dancer is really in the picture).
7. `render_group.py`: Blender Workbench, one scene, the video's camera, a dancer hidden outside its verified ranges (`--lift 0.9919` puts the hips-origin clip on the floor).
8. `group_crops.py`: a 4K crop video per dancer at the original fps, used as the reference for annotation.
9. `annotate_clips.py`: runs the LLM hand annotation (Qwen3.8, thinking on, 3 s chunks, original fps) over the clips, only inside `valid_ranges`.

## What to expect
- The side-by-side video (original left, six characters right) lines up by eye at every time checked; positions are relative to the first verified frame of each dancer.
- Feet are not locked to the floor; floor work and fast spins are weaker (GVHMR).
- LLM annotation costs about 35 s of wall time per second of video, per dancer (about 4 h for the six).
- Neighbouring dancers in a crop can confuse the hand labels; masking them is not built.

## Corrections made after the first render (what to know)
- **The pelvis offset.** GVHMR's `transl` is the SMPL-X model's origin, not the pelvis: the pelvis is 0.39 m above it, in the body's own frame. Fitted to the ViTPose keypoints of all six dancers (2855 frames) the reprojection error fell from 0.243 m to 0.043 m. `tools/group_scene.py` applies it (`PELVIS`); before that every character stood 0.39 m too low.
- **Gaps.** A frame outside a dancer's verified stretches used to keep the zero pose (a T-pose): the fill took a rounded interpolated index, which maps such a frame to itself. Poses are now held at the ends of the shot and blended (rotations by slerp, the root linearly) across the gaps.
- **Nobody is hidden.** The render's camera is not the video's camera (which whip-pans, drops to the floor, and is blocked by other dancers), so `tools/render_group.py` draws every dancer in every frame (`--hide-gaps-over S` hides only gaps longer than S seconds). Blended frames are interpolated, not observed.
- **Camera tilt.** `--pitch` (default 1.0 degree) turns the camera further down than the floor fit says: measured against the video's keypoints the render stood 21 px (waist) to 68 px (ankles) too low at 1080p, 1.0 degree is 38 px.
- **Forcing a stretch.** `tools/group_segments.py --only K --accept "K:first-last"` takes frames the appearance check rejected although the dancer is clearly there (checked by eye). The check often rejects look-alikes' frames wrongly and, in the other direction, `tools/group_audit.py` (which compares every detected person with each dancer) picks look-alikes too: its candidates must be looked at.
- **Neon stage.** `--neon` renders with EEVEE: a dark glossy floor, neon tubes on the back wall, coloured rim lights (about 0.85 s a frame at 1280x720).
