# Repair: regenerate a broken region of the 3D model

Pixal3D sometimes returns fused, melted or cut-off fingers. The **Repair** tab of a run page lets you paint over the broken part of the model (or press *Select hands*) and regenerates just that part.

## How it works

1. **Select.** The browser sends brush strokes (spheres in the model's own coordinates), not vertex numbers, so nothing has to match between three.js and Blender. *Select hands* uses the T/A-pose: the outer ~10.5 % of the height on each side.
2. **Region** (`blender_repair.py analyse`, CPU). Strokes become a vertex mask on the pre-rig mesh (`mesh_glb`). Blobs that nearly touch are one region (a hand with a separate thumb island is still one hand). The wrist ring is where the mask meets the rest of the model. Two close-ups are rendered from the front: textured (shown in the UI) and a grey clay one (what the image model sees). The median colour of the base-colour texture under the region is recorded (the glove, skin or cloth the new part must keep).
3. **Redraw** (Qwen-Image, GPU). The clay close-up is redrawn with complete anatomy. Clay on purpose: given a coloured render the image model turns a black glove into bare skin and even redraws the sleeve, and no instruction in the prompt stopped that. Three candidates per round, up to two rounds. A silhouette finger counter (`digits.py`) rejects any redraw without five digits; the VLM picks the most natural of the rest.
4. **Shape** (Pixal3D, GPU). The chosen redraw becomes a small mesh (90k faces).
5. **Merge** (`blender_repair.py merge`, CPU). The donor is mapped back with the same pixel-to-metre mapping as the close-up render and scaled to the arm; then **contact is enforced**: the point where the remaining arm really ends along the arm axis is measured and the donor's stub is slid over it by about one wrist radius, centred on the arm and given the arm's size (the picture alone only fixes the hand roughly; before this step a hand could float a few centimetres off the arm). The region's original vertices are deleted.
6. **Bake** (`blender_repair.py bake`, CPU, ~30 s). The merged parts (original mesh with its texture, flat-coloured donors) become **one mesh with a fresh UV atlas**; the original texture is carried over with a Cycles "selected to active" bake (1 sample, 4096²). Output: `repaired_textured.glb`.
7. **Use for this run** (button on the finished job, or `POST /api/repair_use`). The textured mesh replaces the run's 3D model (the old path is kept as `mesh_before_repair`) and the run restarts from the **Colour** stage: colour projection, rig, rig check, animation, texture. *New run* keeps the original untouched; *Replace in this run* restarts it in place. The run must be stopped or finished.

The job waits for the GPU lock like every other GPU job, runs as the unit `homunculus-repair-<run>`, and keeps the VRAM peak under the limit (768 px redraw with a 512 reference: 19.4 GB; at 1024 it reached 23.2 GB).

## What was tested

On the failed hands of a Max Verstappen run (cut-off glove fingers on both hands): both regions found, five-finger redraws chosen (the counter rejected one candidate with a single digit), two Pixal3D hands built, merged and counted as five fingers each. **12 minutes** end to end on the RX 7900 XTX. The result is a complete hand in the right place with a black glove colour.

## Known limits (Phase 1)

- The new hand's colour is **one flat colour** sampled from the original (no stitching, logos or wrist band on the new part). After *Use for this run* the colour and texture stages project the reference picture onto the whole mesh again, which adds the detail where the picture shows it. The bake re-unwraps the whole mesh (Smart UV Project), so the UV layout differs from the original Pixal3D mesh and the texture is resampled once.
- Not yet tested end to end: a full run (colour, rig, animation, texture) on a repaired mesh. The endpoint, the state change and the restart arguments were checked with a stand-in launcher.
- The seam at the wrist is an overlap of two shells (the new hand's cuff slides over the arm's cut end), not a welded surface; in a flat-coloured preview the overlap shows as a slightly different shade until the texture stage recolours it.
- Repairing an already repaired mesh stacks the uncertainty; repair the **original** mesh when you can. `python -m homunculus.repair <run> --remerge <job> [--base mesh.glb]` joins an earlier job's hands again (CPU only, no GPU) after a merge fix; the old result is kept as `repaired_old.glb`.
- Only T/A-posed figures have a meaningful *Select hands*; for anything else paint the region by hand.
- A region that covers a whole separate part (no boundary to the rest of the mesh) is skipped.
- The finger counter and the VLM are the only checks; a hand can have five fingers and still be odd.

## Research notes (October 2026; read from project pages and abstracts, nothing here was run except what is described above)

- No released tool does mask-based local regeneration on TRELLIS.2 / Pixal3D. VoxHammer, Easy3E and Nano3D build on the first TRELLIS and need NVIDIA-only code; newer TRELLIS.2 editing papers (EditFlow3D, EditVerse3D, InpaintSLat) had no released code when checked. Masked re-sampling inside Pixal3D's own latents is feasible in principle but nobody has published it, and fingers may be smaller than its coarse first-stage grid.
- Click-to-part segmentation: SegviGen (MIT, TRELLIS.2-based, CUDA extensions to port) is the best candidate; P3-SAM's Tencent licence is not GPL-compatible. HoloPart (MIT) completes missing geometry but does not invent a good hand.
- A parametric hand (MANO) would guarantee five fingers but is non-commercial (not verified here) and hard to pose on stylised characters.
