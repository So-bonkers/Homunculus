# Repair: regenerate a broken region of the 3D model

Pixal3D sometimes returns fused, melted or cut-off fingers. The **Repair** tab of a run page lets you paint over the broken part of the model (or press *Select hands*) and regenerates just that part.

## How it works

1. **Select.** The browser sends brush strokes (spheres in the model's own coordinates), not vertex numbers, so nothing has to match between three.js and Blender. *Select hands* uses the T/A-pose: the outer ~10.5 % of the height on each side.
2. **Region** (`blender_repair.py analyse`, CPU). Strokes become a vertex mask on the pre-rig mesh (`mesh_glb`). Blobs that nearly touch are one region (a hand with a separate thumb island is still one hand). The wrist ring is where the mask meets the rest of the model. Two close-ups are rendered from the front: textured (shown in the UI) and a grey clay one (what the image model sees). The median colour of the base-colour texture under the region is recorded (the glove, skin or cloth the new part must keep).
3. **Redraw** (Qwen-Image, GPU). The clay close-up is redrawn with complete anatomy. Clay on purpose: given a coloured render the image model turns a black glove into bare skin and even redraws the sleeve, and no instruction in the prompt stopped that. Three candidates per round, up to two rounds. A silhouette finger counter (`digits.py`) rejects any redraw without five digits; the VLM picks the most natural of the rest.
4. **Shape** (Pixal3D, GPU). The chosen redraw becomes a small mesh (90k faces).
5. **Merge** (`blender_repair.py merge`, CPU). The donor is mapped back with the same pixel-to-metre mapping as the close-up render, snapped to the wrist (lateral shift and size, measured the same way on both meshes), clipped to the hand side of the wrist plane plus a one-radius overlap into the forearm, and given a flat material of the original colour. The region's original vertices are deleted. The result is `10_repair/<job>/repaired.glb` plus before/after close-ups and a finger count of the "after" render.

The job waits for the GPU lock like every other GPU job, runs as the unit `homunculus-repair-<run>`, and keeps the VRAM peak under the limit (768 px redraw with a 512 reference: 19.4 GB; at 1024 it reached 23.2 GB).

## What was tested

On the failed hands of a Max Verstappen run (cut-off glove fingers on both hands): both regions found, five-finger redraws chosen (the counter rejected one candidate with a single digit), two Pixal3D hands built, merged and counted as five fingers each. **12 minutes** end to end on the RX 7900 XTX. The result is a complete hand in the right place with a black glove colour.

## Known limits (Phase 1)

- The repaired model is **geometry plus a flat colour**: the new hand has no texture detail (stitching, logos, a white wrist band) and the result is several parts (the original mesh, one donor per region), not one textured mesh. **It is not yet fed back into the run**: using it means rigging and texturing it yourself or re-running from the 3D stage with it. Next step: UV-unwrap and bake the original texture onto the joined mesh, then offer *Use for this run* (re-colour, rig, texture).
- The seam at the wrist is an overlap of two shells, not a welded surface; a tilted wrist plane can show it.
- Only T/A-posed figures have a meaningful *Select hands*; for anything else paint the region by hand.
- A region that covers a whole separate part (no boundary to the rest of the mesh) is skipped.
- The finger counter and the VLM are the only checks; a hand can have five fingers and still be odd.

## Research notes (October 2026; read from project pages and abstracts, nothing here was run except what is described above)

- No released tool does mask-based local regeneration on TRELLIS.2 / Pixal3D. VoxHammer, Easy3E and Nano3D build on the first TRELLIS and need NVIDIA-only code; newer TRELLIS.2 editing papers (EditFlow3D, EditVerse3D, InpaintSLat) had no released code when checked. Masked re-sampling inside Pixal3D's own latents is feasible in principle but nobody has published it, and fingers may be smaller than its coarse first-stage grid.
- Click-to-part segmentation: SegviGen (MIT, TRELLIS.2-based, CUDA extensions to port) is the best candidate; P3-SAM's Tencent licence is not GPL-compatible. HoloPart (MIT) completes missing geometry but does not invent a good hand.
- A parametric hand (MANO) would guarantee five fingers but is non-commercial (not verified here) and hard to pose on stylised characters.
