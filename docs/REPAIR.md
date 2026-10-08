# Repair: regenerate a broken region of the 3D model

Pixal3D sometimes returns fused, melted or cut-off fingers, a crumpled helmet top, a melted foot. The **Repair** tab of a run page lets you paint over **any** broken part of the model (or press a region button: *Hands*, *Head*, *Crown*, *Feet*) and regenerates just that part: the part is redrawn, Pixal3D builds its shape again, and it replaces the broken one.

What you give it besides the paint: **What is it?** (a few words, e.g. "the top of the helmet"; it goes into the redraw prompt) and **Redraw from** (automatic, front, back, left, right, above). From the command line: `python -m homunculus.repair <run> --region crown --view top` (regions: hands, head, crown, feet) or `--job <id>` for painted strokes.

What is general and what is specific to hands:
- General: the region (any painted blob with a boundary to the rest of the surface), the camera (the model is turned so the side the region faces looks at the camera, then turned back after the merge), the redraw prompt (built from the label), the merge (the new part is slid over the boundary along the boundary's own plane normal).
- Hands only (the label mentions hand, finger, glove, palm or thumb): the five-digit finger counter filters the redraws and the after-picture is counted. Every other region is checked by silhouette instead: a redraw must keep the region's rough shape (overlap 0.5 to 0.985 with the close-up) but really change it (1.0 means the image model handed the broken part back), then the VLM picks the most natural.
- Regions with no boundary to the rest (a whole separate part) are skipped. A broken *flat patch* of a surface (a dent in a torso) is not a part that sticks out: the donor approach suits parts that have a boundary ring, such as hands, head tops, feet, tails, horns.

## How it works

1. **Select.** The browser sends brush strokes (spheres in the model's own coordinates), not vertex numbers, so nothing has to match between three.js and Blender. The region buttons use the T/A-pose: hands = the outer ~10.5 % of the height on each side, head = the top 13.5 %, crown = the top 7 %, feet = the lowest 5 %.
2. **Region** (`blender_repair.py analyse`, CPU). Strokes become a vertex mask on the pre-rig mesh (`mesh_glb`). Blobs that nearly touch are one region (a hand with a separate thumb island is still one hand). The wrist ring is where the mask meets the rest of the model. Two close-ups are rendered from the front: textured (shown in the UI) and a grey clay one (what the image model sees). The median colour of the base-colour texture under the region is recorded (the glove, skin or cloth the new part must keep).
3. **Redraw** (Qwen-Image, GPU). The clay close-up is redrawn with complete anatomy. Clay on purpose: given a coloured render the image model turns a black glove into bare skin and even redraws the sleeve, and no instruction in the prompt stopped that. Three candidates per round, up to two rounds. A silhouette finger counter (`digits.py`) rejects any redraw without five digits; the VLM picks the most natural of the rest.
4. **Shape** (Pixal3D, GPU). The chosen redraw becomes a small mesh (90k faces), without Pixal3D's own texture (the part gets the original region's flat colour anyway). Voxel resolution 1536 for hands, 1024 for other parts: a part that fills its whole picture (a helmet top seen from above) peaked at 23.3 GB at 1536 and the VRAM watchdog stopped ComfyUI.
5. **Merge** (`blender_repair.py merge`, CPU). The donor is mapped back with the same pixel-to-metre mapping as the close-up render and scaled to the arm; then **contact is enforced**: the point where the remaining arm really ends along the arm axis is measured and the donor's stub is slid over it by about one wrist radius, centred on the arm and given the arm's size (the picture alone only fixes the hand roughly; before this step a hand could float a few centimetres off the arm). The region's original vertices are deleted.
6. **Bake** (`blender_repair.py bake`, CPU, ~30 s). The merged parts (original mesh with its texture, flat-coloured donors) become **one mesh with a fresh UV atlas**; the original texture is carried over with a Cycles "selected to active" bake (1 sample, 4096²). Output: `repaired_textured.glb`.
7. **Use for this run** (button on the finished job, or `POST /api/repair_use`). The textured mesh replaces the run's 3D model (the old path is kept as `mesh_before_repair`) and the run restarts from the **Colour** stage: colour projection, rig, rig check, animation, texture. *New run* keeps the original untouched; *Replace in this run* restarts it in place. The run must be stopped or finished.

The job waits for the GPU lock like every other GPU job, runs as the unit `homunculus-repair-<run>`, and keeps the VRAM peak under the limit (768 px redraw with a 512 reference: 19.4 GB; at 1024 it reached 23.2 GB).

## Several parts, size and colour

- **Several parts in one job.** A job holds *groups* (hands, feet, a crown, ...): each has its own label, view, prompt and checks. They are repaired one after the other on the running result and the texture is baked once at the end (`--region hands --region feet`, or *Add this part, select another* in the viewer). Parts that are far apart are different regions; parts that nearly touch (4 % of the height) are one region.
- **Size.** The redraw fixes the shape, but its size is whatever the image model drew, and a picture has no thickness. The region being replaced is the size reference: the new part is scaled up to its length and spread (at most x1.4) and its depth to the original's (at most x1.8), and the wrist match may not shrink it by more than 5 %. Measured on one pair of hands: tip distance 38.7 cm before this, 42.5 after (original 41.3); finger span 4.8 cm, 6.8 cm (original 7.1); thickness 4.3 cm, 5.3 cm (original 7.0: still thin).
- **Colour.** The new part is one flat colour taken from the base-colour texture under the region. A byte image's pixels come back sRGB-encoded, so they are converted to linear light first (a dark navy used to come out light grey-blue). On a turnaround-sheet run the repair works on the *coloured* mesh, because the raw mesh has one flat colour.
- **Re-basing.** `python -m homunculus.repair <run> --remerge <job> --base <other mesh>` finds the job's regions again on another mesh (its vertex numbers differ) and matches each to the old one by centroid, so a left donor cannot land on the right hand. Single-group jobs only.
- **Redraw choice.** A region that is not a hand is checked by silhouette overlap with the close-up (0.5 to 0.985: 1.0 means the image model handed the broken part back), then the VLM picks.

## What was tested

On the failed hands of a Max Verstappen run (cut-off glove fingers on both hands): both regions found, five-finger redraws chosen (the counter rejected one candidate with a single digit), two Pixal3D hands built, merged and counted as five fingers each. **12 minutes** end to end on the RX 7900 XTX. The result is a complete hand in the right place with a black glove colour.

## Tested on a turnaround-sheet run (October 2026)

Hands and feet in one job: 24 minutes, five fingers counted on both hands. The hands came out about 30 % too small and light grey-blue (both fixed above, then continued as a run: right size, five fingers, glove colour). The **feet came out worse than the originals** (blocky boots, no toe-cap or sole detail, ragged remnants of the old leg at the ankles): repairing parts that were already fine is not worth it. Part of the colour problem is not the repair's: the palm, the back of the hand and the top and sole of a boot face none of the four horizontal views, so nothing paints them and they keep the flat colour.

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
