# The depth phase (stage "Views")

For a run that starts from one picture, the shape model has to guess everything it cannot see. This stage draws the character's back first, so Pixal3D builds the shape from two views that agree instead of one. It runs between *Prepare* and *3D shape* and is on by default (`--depth-views off`, or `HOMUNCULUS_DEPTH_VIEWS=off`, turns it off). It is skipped for turnaround-sheet runs (the sheet already is the views) and mesh input.

## What it does (stages/depthviews.py)
1. **Proxy shape.** One quick Pixal3D pass from the upscaled front picture (about 90 s). Its back is a guess, but its pose and proportions are one consistent body.
2. **Depth map** of the proxy seen from behind (`blender_depth_views.py`, orthographic, shared scale).
3. **The back view.** First an unguided Turbo redraw of the front picture as "seen from behind" (so the front's logos cannot leak onto the back); that picture is the reference for the real one, drawn by Qwen-Image 2.1 Turbo with the Fun ControlNet Union under the depth map (8 steps, about 6 s each after the load).
4. **Outline check, no language model.** The view is kept only if its silhouette agrees with the proxy's for that side (IoU of the two cut-outs, at least 0.80; `HOMUNCULUS_DEPTH_VIEW_IOU`). A view that fails is dropped and the shape is built without it.
5. **Framing.** The front and the kept view are framed at one scale (equal figure height) and go to the multiview Pixal3D shape pass, exactly like the views of a turnaround sheet. They are used for the shape and Pixal3D's own texture; the colours still come from the front picture as before.

About 3 minutes in all on the Radeon. The stage page shows the views the shape model saw and the unguided back.

## What was tried (F1 driver, 2026-10-13)
- **Back:** lettering and logos on the back, the T-pose kept, IoU 0.88. Good.
- **Sides** (off by default, `HOMUNCULUS_DEPTH_VIEWS_SIDES=1`): the model draws the T-pose arms hanging down along the body (IoU 0.78 left, 0.91 right: the outline check misses it on one side, because the arm overlaps the torso), and with a prompt that says the arms point at the camera it draws them stretched forward. Not usable yet.
- **Top and bottom** (depth strength 0.8 and 1.2, normal-map guide): the model returns the front view again or a foreshortened full body. Not usable; they would only feed the texture anyway (the shape model takes four sides).
- On Miles the views agreed on scale within 1 %.

## Files it needs
Qwen-Image 2.1 int8, its text encoder and VAE, the turbo LoRA and the Fun ControlNet Union in ComfyUI's model folders (the Doctor lists any that are missing; without them the stage is skipped and redraws fall back to Unsloth Studio).
