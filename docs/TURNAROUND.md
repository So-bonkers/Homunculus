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

## Limits
- You must supply the sheet; there is no local generator for it yet.
- Four views at most: no top or bottom view.
- Some garbled texture remains where no view faces the surface well (the front of the lower legs, hands, helmet visor).
- The hands and the top of the helmet come out poorly with one shape and no top view: the sheet cannot show the top of the head. Use the Repair tab (crown, hands).
- Needs `comfy/dl.sh` to have fetched the multiview checkpoint (`doctor` checks it).
- The front and back of the model are swapped if the sheet order is wrong: try the other order.
