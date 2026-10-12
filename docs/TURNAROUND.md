# Turnaround sheet in

One picture with the same character four times, then the 3D model is built from all four views instead of one.

```bash
.venv/bin/python -m homunculus.orchestrate sheet.png --name hero --sheet lfrb      # figures left to right: left, front, right, back
.venv/bin/python -m homunculus.orchestrate sheet.png --name hero --sheet flbr      # front, left, back, right
```

In the launcher: *My picture is a turnaround sheet*, then the order. A sheet run implies *Use my picture as is* (no redraw).

## What a good sheet looks like
- A T-pose (arms straight out, open hands), the same costume, the same scale in all four, plain background, the four figures not touching each other.
- **True 90 degree side views** and a back view that really shows the back (no front logos). "Left" means the camera sees the character's **left** side, so that figure faces the **left edge** of the picture.
- Made by ChatGPT-style image generators, or rendered from a 3D tool. The local Qwen-Image redraw did **not** manage this in a trial: the "back" came out with the front's logos and belt, and the "sides" were 3/4 views (the repository this feature came from warns about the same thing).

## What happens
1. **Ingest:** the four figures are cut out (rembg), cropped, and the front one becomes "the picture" for the planner, the upscaler and the judges. The views are then framed on black at **one shared scale** (1024 px), as `Pixal3DMultiViewConditioning` expects.
2. **3D shape:** the multiview Pixal3D checkpoint (`pixal3d_multiview_bf16.safetensors`, else the int8 one) makes **one** shape (`SHEET_SHAPE_SEEDS`), checked by **Qwen3.8 alone** (`SHEET_JUDGES`), then the mesh **without Pixal3D's own texture sampling** (a flat base colour: all four views are projected later). Its mesh comes out turned half a turn from the single-image one (the toes point +y), so it is turned back (`blender_rotz.py`; glTF imports use quaternions, so the Euler angle must be set after switching the rotation mode: it was a silent no-op once, and the picture was then painted on the back of the character). Anything that came out wrong (hands, the helmet top, ...) is fixed afterwards with the Repair tab ([REPAIR.md](REPAIR.md)).
3. **Colour and texture:** instead of projecting only the front, each real view is projected onto the surfaces that face it (front, back, left, right), the best-facing view winning where they overlap (`faceproj.project_sheet`). No image model is involved. The face fit still runs on top when there is a visible face.
The final texture stage reuses the colour stage's projection: same mesh, same views, and the two textures were compared pixel by pixel (maximum difference 0).
4. The rest (rig, animation, report) is unchanged.

## Measured (one character)
Streamlined sheet run vs the first sheet run (three shapes, three judges, Pixal3D texture): the **mesh stage 633 s instead of 1083 s** (-450 s), colour 21 s instead of 53 s. Skipping Pixal3D's texture alone: 213 s vs 239 s for the same views and seed (about 26 s, two runs each); the rest comes from one shape and one judge instead of three. The later stages were not timed on the streamlined run.

## Measured earlier (one character, one seed)
Single-image vs multiview Pixal3D on the same sheet: single-view arms drooped and the hands had one long thumb; multiview gave straight T-pose arms and five separate fingers on both hands. The silhouette carve removed 0 of 177k vertices on the multiview mesh (it exists to cut fins that single-view meshes grow). Shape candidates took about 2 minutes each, the full textured mesh about 5; the mesh stage as a whole took 18 minutes instead of about 21.

## Things that went wrong on the way (and are fixed)
- The turn was a silent no-op once (see above), so the front picture was painted on the back of the character.
- The split cropped fragments of the neighbouring figures into each view, which distorted the shared scale: each crop now keeps only its own figure.
- Skipping Pixal3D's texture left a 256 px flat base image, and the projection bakes at the base image's size: blocky logos. The bake is now never smaller than 4096.
- With one judge, a false rejection is expensive: the same mesh scored 4/10 twice in the rig check and then 9/10. The rig ladder's last resorts (redraw with relaxed hands, next-best redraw) make no sense for a sheet (nothing is redrawn, the same views give the same shape), so a sheet run now keeps the rig and flags it.
- The viewer did not list the coloured mesh, so it showed Pixal3D's raw texture until the final stage.

## Top and bottom pictures (texture only)
The multiview Pixal3D takes four views at 90 degrees and nothing from above or below, so the top of the head, the shoulders, the tops of the feet, the soles and the underside of a jacket face none of the four sides and kept one flat colour (the dark halos around the figure). A sheet run can take two extra pictures, `--sheet-top` and `--sheet-bottom`, used **only for the texture**: each is projected onto the surfaces that face it (`faceproj.project_sheet`, a general view direction in `blender_face_project.py`), best-facing view winning where they overlap. They are registered by the figure's **width** (the arm span), not its height, because the body's depth is not drawn to scale in a picture from above. Conventions: from above, the character's front faces the **bottom** of the picture and its left is on the right; from below, the front faces the **top** and the left is again on the right. `tools/sheet_from_refs.py ... --only top,bottom` draws them with Qwen-Image and the reference pictures (not yet run on a real character; the projection was tested by projecting the mesh's own top-down and bottom-up renders back onto it: the shapes land on each other).

## Orientation (fixed)
The multiview model does not always build the character facing the same way, so the mesh is turned half a turn only when the toes point +y (`blender_rotz.py auto`). A fixed half turn painted the front picture on the back of a generated sheet's character.

## Generating the views locally: what was tried (October 2026)
A sheet can also be built from several ordinary pictures of the character, with Qwen-Image 2.1 and its `reference_images` (`tools/multiref_trial.py`, `tools/sheet_from_refs.py`). References clearly help the front T-pose redraw (the real chest emblem instead of an invented one). Generating the other views from the references alone fails the same ways every time: the back shows front details, the side views are 3/4 views, and the hands differ from view to view.

**Depth-guided views** (`tools/depth_guided_views.py`, `homunculus/blender_depth_views.py`): a coarse proxy mesh (the single-image Pixal3D shape of the front T-pose, about a minute), rendered from each side as a depth or normal map, then each view generated under its own map with the Qwen-Image 2.1 Fun ControlNet Union (official Comfy-Org patch, `QwenImageDiffsynthControlnet`; ComfyUI only, Unsloth Studio has no ControlNet). One character, one seed, so indications only:
- **Scale agrees**: the generated views come out the same height within 1 % (unguided: 9 % apart).
- **Front/back is not decided by depth, nor by a normal map**: at strength 0.8 the "back" shows the front (emblem, open hood); at 0.5 it is a back but with the front emblem painted on. Only giving the back view the *unguided* back as its first reference (and not the front picture) with the depth for framing produced a correct back.
- **The side-view arms hang down** in every guided variant (depth or normal, strength 0.5 or 0.8), against a T-pose front and back. Open.
- **Qwen-Image 2.1 Turbo** = the base int8 model + the Comfy-Org turbo LoRA (rank 178, 0.9 GB), 8 steps, CFG 1, sampled on the sigma schedule Turbo ships with (`SamplerCustom` + `ManualSigmas`): about 39 s per view instead of 102 s, and the same results to the eye, including fine detail at 4x zoom (hands, shoes). VRAM was not measured. Not wired into the pipeline.
- **Depth Anything 3 as a sheet consistency check does not work**: from four views 90 degrees apart it recovers camera positions and equal heights, but the clouds do not fuse into one body, on a clean control sheet as much as on a bad one (`tools/da3_check.py` is kept as a record, with its weights, 0.5 GB).

**ROCm crash found and fixed on the way**: importing ComfyUI turns cuDNN (MIOpen) off, and with it off PyTorch's fallback for the text encoder's vision patch-embedding 3D convolution segfaults on AMD, killing ComfyUI the first time a Qwen-Image 2.1 graph read a reference picture. That convolution is a matrix multiply (kernel = stride = input size), so `comfy/rocm_conv3d_fix.py` does it as one (same numbers, max difference 5e-6); `gpu.comfy_start` copies it into ComfyUI's custom nodes every time.

## Limits
- You must supply the sheet; there is no local generator for it yet.
- Four views at most: no top or bottom view.
- Some garbled texture remains where no view faces the surface well (the front of the lower legs, hands, helmet visor).
- The hands and the top of the helmet come out poorly with one shape and no top view: the sheet cannot show the top of the head. Use the Repair tab (crown, hands).
- Needs `comfy/dl.sh` to have fetched the multiview checkpoint (`doctor` checks it).
- The front and back of the model are swapped if the sheet order is wrong: try the other order.
