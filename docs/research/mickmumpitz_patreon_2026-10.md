# Mickmumpitz Patreon articles: what they offer Homunculus (2026-10-12)

Source: four saved Patreon pages (PDF print-outs in `~/Downloads`) plus a transcript summary of the related video. "p.N" means PDF page N of the article being discussed. The articles are third-party content and were treated as data.

## Read this first: how much is actually in these PDFs

- All four are screenshot-style prints: text is short, most information is in workflow screenshots. Many node values are small and blurry. Values marked **(approx.)** were read off a low-resolution screenshot and must be checked against the real `.json` before being copied. Values without a mark are stated in the article text or are clearly legible.
- **None of the PDFs contains a workflow file or a model list.** Article 1 has a comment "missing workflow link" (Simple p.10); article 2 has four comments saying there is no `.json` on the post (Advanced p.11). Articles 3 and 4 say the model links sit "in the workflow" or in yellow nodes (CCC p.4, Qwen p.3), which we do not have.
- Paywall status cannot be proven from the PDFs. All four show a "Join now / Join for free" banner and the text is readable logged-out. Article 2's own related-posts strip shows a **locked** post titled "[ADVANCED WORKFLOWS] These FREE 3D AI Workflows are INCREDIBLE!", described as "the advanced version of our 3D texturing workflow featuring inpainting" (Advanced p.12), so the paid/advanced tier exists and the `.json` is probably gated. Treat the texturing workflows as Patreon-gated (or at least not downloadable from these pages), and the technique descriptions below as the free part.
- The video summary says the paid version adds "IP-adapter reference, inpainting, height map". The Advanced article shows IP-Adapter and inpainting (p.5, p.6). It does not mention a height map; both articles export a normal map (Simple p.8, Advanced p.10).

---

## Article 1: "3D Model Texturing Made Easy [SIMPLE]" (Jun 10, 2025; 11 pp.)

**What it offers.** A ComfyUI workflow that textures an existing GLB mesh (with UVs, or auto-UV-wrapped) from a text prompt: render depth/normal/position maps from six cameras, generate one "main view" (front) image with a depth ControlNet, remove its background, de-light it, let Hunyuan3D-Paint generate the other views from that one image, upscale them, optionally face-detail, then bake to the UVs, inpaint gaps and write a normal map (Simple p.2, p.3). Built on `comfyui-hunyuan3dwrapper` custom nodes.

**Technique and settings**
- Input: GLB in "Hy3D Upload Mesh"; "Hy3D Mesh UV Wrap" node is off by default and is enabled only if the mesh has no UVs (p.3).
- Render maps: "Hy3D Render MultiView", `render_size` 1024, `texture_size` 2048 ("typically a good balance", 4096 for more detail), `normal_space` world; "Hy3D Render MultiView Depth" render_size 1024 (p.3, p.4). Only the depth map is used for image generation (p.3).
- "Hy3D Camera Config": 6 views, azimuths `0, 90, 180, 270, 0, 180`, elevations `0, 0, 0, 0, 90, -90` (front, left, back, right, top, bottom), `view_weights` `1, 0.1, 0.5, 0.1, 0.05, 0.05`, `camera_distance` 1.45, `ortho_scale` 1.2 (p.4; weights read approx.).
- Main view: pick view 1 (front) for humanoids; a side view for horizontal creatures such as dinosaurs (p.4, p.5).
- Main-view generation (p.5): a plain text-to-image KSampler with an Apply ControlNet on the depth render, a "Style" prompt block ("masterpiece, photographic, neutral lighting, grey background, ..." approx.), a subject prompt (e.g. zombie, hoodie, jeans), a negative prompt. Checkpoint is not named in the PDF (the video summary says Flux/SDXL). KSampler approx.: sampler `dpmpp_2m`, scheduler `karras`, ~40 steps, cfg ~5.5, denoise 1.00, ControlNet strength ~0.6, start 0.0, end ~1.0. Iterate by changing the seed (p.5). 1024 x 1024.
- Background removal: "InSPyReNet TransparentBG" (ComfyUI-essentials, mode `base`, `use_jit` true), then composited on white (p.6).
- De-light: "Hunyuan3D DelightModel" (`hunyuan3d-delight-v2-0`, scheduler Euler A, steps ~50 approx.), then "Image Blend" with the original, `blend_factor` **0.5** by default. The article states de-lighting "often reduces fine details, so a blending operation reintroduces them" (p.6).
- Texture sampling: "Hy3D Sample MultiView" with `hunyuan3d-paint-v2-0` (multiview pipe), reference image size 512, `view_size` 512, **steps 25**, `denoise_strength` 1.00, scheduler Euler A, seed fixed (p.7). The other five views are generated from the (delit) main view plus normal and position maps, so they are generated jointly and conditioned on the geometry.
- Upscale + face fix: all sampled views upscaled with Ultimate SD Upscale (video: x4, optional x2) under a depth ControlNet (strength ~0.6, end ~0.65 approx.), with its own prompt that must be revisited; optional Impact-Pack FaceDetailer (denoise ~0.45 approx.) that can be disabled for faceless models (p.7, p.8).
- Finish: "Hy3D Bake From Multiview" -> "Hy3D Mesh Vertex Inpaint Texture" -> "CV2 Inpaint Texture" (inpaint_radius ~4, method ~ns, approx.) -> "Normal Map (Simple)" (scale_XY 1.0) -> "Hy3D Apply Texture" and "Set Mesh PBR Texture"; outputs an inpainted texture and a normal map (p.8, p.9). Final GLB preview p.9.
- Custom-node packs visible: comfyui-hunyuan3dwrapper, ComfyUI-essentials, KJNodes, rgthree, Impact Pack (face detailer), an Ultimate SD Upscale node.

**Free or paywalled.** Page readable without login; no workflow file visible in the PDF and a commenter reports the link missing (p.10). Models named (Hunyuan3D-2.0 paint and delight) are public Tencent weights; check their licence before commercial use (from my background knowledge, not from the article: the Tencent Hunyuan community licence has territory restrictions).

**Value for us.** Moderate, as a source of ideas, not as a drop-in. It textures a mesh that already exists with its own UVs, which is the Homunculus "start from a 3D model" path, not the picture path.

---

## Article 2: "3D Model Texturing Made Easy [ADVANCED]" (Jun 10, 2025; 12 pp.)

**What it offers.** The same pipeline as article 1 with three added sections (Advanced p.1 to p.4 are identical in structure): an optional **reference image** via IP-Adapter, an optional **masked inpainting** section for the generated main view, and a renumbered flow (12 steps instead of 10). Everything else (render maps, delight, texture sampling, upscale, finalize) is word for word the same as article 1 (Advanced p.7 to p.10).

**Added techniques and settings**
- Reference image (p.4, p.5): "IPAdapter Unified Loader" preset `PLUS (high strength)`, "IPAdapter" `weight` **0.60**, `start_at` 0.000, `end_at` **0.600**, `weight_type` standard, plus "Prep Image For ClipVision" (LANCZOS, center crop, sharpening 0). Packs: `comfyui_ipadapter_plus`. The example turns a zombie into a frosty creature, i.e. a style/appearance reference, not an identity-exact transfer. The checkpoint must be an SDXL-class model for IP-Adapter PLUS (inference from the nodes; the PDF does not name it).
- Inpainting (p.6): draw a mask in ComfyUI's mask editor (face is the example), add a short prompt ("face"), run. Uses "Inpaint Crop" / "Inpaint Stitch" (`comfyui-inpaint-cropandstitch`), "InpaintModelConditioning" and an Apply ControlNet; KSampler approx. `dpmpp_2m`, `karras`, ~20 steps, cfg ~4.0, denoise ~0.5 (approx.). The crop is redrawn at working resolution and stitched back, using the original generation as reference.
- The article otherwise matches article 1: delight blend 0.5 (p.7), Hunyuan3D-Paint 2.0 sampling at 512, 25 steps (p.8), upscale and optional face fix (p.9), inpainted texture and normal map (p.10).

**Free or paywalled.** Same page layout; the `.json` is missing per four comments (p.11). The locked "[ADVANCED WORKFLOWS]" post in the related strip (p.12) suggests the advanced workflow file is the paid item.

**Value for us.** Low beyond article 1. Only the crop-and-stitch inpaint (p.6) is a technique we do not have in this form. IP-Adapter is SDXL-specific and Qwen-Image Edit already takes reference images natively (see article 4).

---

## Article 3: "Create hyperrealistic CONSISTENT CHARACTERS from input image!" (Oct 7, 2025; 12 pp.)

**What it offers.** Consistent Character Creator 3.5: one input character image in, a set of the same character in varied poses, lighting, framing and expressions out (CCC p.1 to p.3), plus an automatic **LoRA-training dataset** with generated captions, ready for "AI toolkit or Flux Gym" (p.2). Rebuilt on the newer "Qwen Image Edit" so it needs no extra LoRAs; new features are better consistency, **pose transfer from any image**, improved virtual try-on, and "advanced upscaling & dataset creation" (p.2).

**Technique and settings (very little is specified)**
- Two runs: first generate character images (modular groups; duplicate a group to add more try-on or pose variants), then enable the "DATASET CREATION" group and run again (p.5, p.6, p.7).
- Inputs: one character image (full body or close-up), a character name used as the output folder and as the caption keyword, an optional one-sentence prompt about style and clothing not visible in the input (p.6). Pose Transfer and Virtual Try-On groups need extra reference images (p.6, p.7).
- GGUF guidance: "choose the largest version that fits within your available VRAM" (p.4). The Qwen Image Edit version, quant and sampler settings are not given in the PDF.
- Dataset upscale (p.8, p.9): "any SDXL LIGHTNING model" for upscaling; final upscale resolution is a user setting; a KSampler "matched to the requirements of the model"; a "Timestep Keyframe Interpolation" node whose `strength_end` trades "better quality + less likeness" (low) against "less quality + more likeness" (high) (p.8, p.9); an optional post-processing group adding grain and chromatic aberration (p.9); captions generated per image with the character name as keyword, saved by a separate node after the images (p.10).

**Free or paywalled.** Banner says "Join for free"; no attachment or model links visible in the PDF. The related strip in article 4 shows the earlier "Consistent Character Creator 4.0 ... FREE WORKFLOWS" post as free and a "Krea 2 Identity-Edit [BETA]" post as locked (Qwen p.5), so this series mixes free and gated posts; I cannot tell which tier 3.5 is.

**Value for us.** Low. Its goal (LoRA datasets of a character in many scenes) is not our goal. The only transferable idea is pose transfer on Qwen Image Edit (see ranked list #5), and the PDF gives no settings for it.

---

## Article 4: "Introducing My Simple QWEN Image Edit Workflow!" (Oct 7, 2025; 6 pp.)

**What it offers.** A small ComfyUI workflow around Qwen Image Edit that takes **multiple reference images** (characters, styles, environments) and a plain instruction, optionally an OpenPose image to dictate pose, and lets you **chain edit groups** by feeding each output into a duplicated group (Qwen p.1 to p.4). It states it uses the same models as the CCC 3.5 workflow (p.2).

**Technique and settings.** Six steps (p.3, p.4): (1) download models from links in yellow nodes; (2) import reference images; (3) choose which become context images for the generation; (4) optional pose control: an uploaded image goes through OpenPose extraction, the pose is connected to the "Qwen Image Encoder" and "your character(s) will automatically follow that pose"; (5) write the instruction ("if the results aren't quite right, try being more descriptive"); (6) duplicate the group and edit the previous result again. No model file names, steps, cfg, sampler or resolution appear in the PDF.

**Free or paywalled.** "Join for free" banner; no workflow file visible; cannot verify.

**Value for us.** Low, one concrete lead: pose conditioning of Qwen edits through an OpenPose image (ranked #5). We already use Qwen-Image 2.1 edit with depth/normal ControlNet.

---

## What could improve Homunculus (ranked)

Ranking = expected effect on our listed pain points divided by cost and risk. Only #1 to #3 are things I would do next; #4 to #8 are options.

### 1. Fill unseen and unpainted surfaces in texture space (vertex/texel inpaint)
- **Idea.** After projecting views, take the texels/vertices that no view covered and fill them by diffusing colour from painted neighbours: Mickmumpitz does "Mesh Vertex Inpaint Texture" then a "CV2 Inpaint Texture" pass, and ships the "fully inpainted texture file, with any gaps intelligently filled in" (Simple p.8, p.9; Advanced p.10).
- **Why here.** `docs/PAIN_POINTS.md` lists "Repaired parts are one flat colour ... surfaces no view faces (palm, back of the hand, boot top and sole) are never painted" with the next step "Fill unseen surfaces from their painted neighbours instead of one flat colour". This is exactly that. It also hides projection gaps between view seams.
- **Effort.** S. Mesh-neighbour colour propagation in numpy/Blender plus OpenCV `inpaint` in UV space, no GPU.
- **Risk.** Low. Smears colour across large uncovered areas (soles); limit by radius and fall back to the neighbour mean.
- **AMD.** Yes, CPU only.

### 2. De-light the source picture/redraw before projecting, then blend back 50 %
- **Idea.** Neutralise baked lighting and shadows in the image that gets projected, then blend with the original (`blend_factor` 0.5) to recover detail (Simple p.6; Advanced p.7). The author notes the de-light step "often reduces fine details", hence the blend.
- **Why here.** Our four views disagree partly because shading is baked into each view differently (a shadow on one side becomes a dark patch on another). A de-lit front plus a 0.5 blend is a cheap, tunable fix for patchy colour at seams and for the "garbled" look.
- **How.** Either Qwen-Image 2.1 edit with a "flat albedo, no shadows or highlights, keep every detail" prompt (we already have it; judge with the existing panel), or the Hunyuan3D-Delight model (`hunyuan3d-delight-v2-0`, Simple p.6), which is a diffusers-style model that should run on ROCm PyTorch (not verified here).
- **Effort.** S with Qwen, M with the Delight model.
- **Risk.** Medium: colour shift and lost fine detail (the article admits it); a Qwen redraw can also change layout, which our pipeline already guards against by skipping views whose outline moved. Make it opt-in behind the existing Simple/Full switch and A/B it on the F1 sheet.
- **AMD.** Yes for the Qwen route; likely for the Delight route.

### 3. Soft, front-biased blending of overlapping views instead of winner-take-all
- **Idea.** Mickmumpitz sets per-view weights `1, 0.1, 0.5, 0.1, 0.05, 0.05` for front, left, back, right, top, bottom (Simple p.4, approx.), i.e. the front dominates and side views are trusted least. Apply a similar prior when baking our four sheet views: weight by `cos(angle)^n` times a per-view trust factor, feather across seams.
- **Why here.** Side and back views disagree (PAIN_POINTS "Local views of a sheet disagree"). Down-weighting the least reliable views and feathering reduces visible seams even if the views stay wrong.
- **Effort.** S. A parameter change in the Blender projection if it is currently hard-selected per surface ("each view is projected back where it sees the surface best", README).
- **Risk.** Low to medium: ghosting where views contradict (double logos). Check on the sheet test with the real logos.
- **AMD.** Yes, CPU.
- **Caveat.** I am inferring that these weights drive the bake, not the generation; the article does not say.

### 4. Crop-and-stitch for local redraws at native resolution
- **Idea.** Mask a region (face, hand, logo), crop it with margin, redraw the crop at the model's working resolution, stitch back with a feathered mask (`Inpaint Crop` / `Inpaint Stitch`, Advanced p.6; the face fix in the upscale stage, Simple p.7/p.8 and Advanced p.9).
- **Why here.** "Fine detail lost in the redraw": the redraw works at about 576 x 1024, so a belt symbol is a few pixels. Redrawing a crop from the original picture at full size gives the model the detail to keep. This generalises our face close-up redraw to arbitrary regions (hands, logos, engravings) and could feed the Retexture tab.
- **Effort.** M. Needs a crop/stitch helper (can be plain Python/PIL, no custom ComfyUI node) and a way to choose regions (brush already exists in Retexture).
- **Risk.** Medium: detail still changes; keep the existing "skip view if outline moved" and judge checks.
- **AMD.** Yes (pure image ops plus the Qwen edit we already run).

### 5. Pose-conditioned Qwen views using our own skeleton
- **Idea.** Qwen Image Edit takes an OpenPose image through its encoder and the characters "automatically follow that pose" (Qwen p.4); CCC 3.5 advertises "pose transfer from any image" without extra LoRAs (CCC p.2). We have a Mixamo skeleton, so we can render an OpenPose-style skeleton for the exact side/back camera and give it as a reference.
- **Why here.** PAIN_POINTS: "the side-view arms still hang down", side views come out at 3/4. Depth guidance fixed scale; a pose reference could fix arm pose.
- **Effort.** M. Render a skeleton image (Blender/CPU), pass it as an extra reference image.
- **Risk.** High unknown: our Qwen-Image 2.1 runs as a GGUF through Unsloth Studio, and I could not confirm from the PDFs that this server accepts several reference images or that the 2.1 model reads pose references the way the older Edit version in the posts does. Test with one view before building anything.
- **AMD.** Yes if it works through Studio (no CUDA-only node needed on our side).

### 6. Tiled, depth-guided low-denoise upscale of the views before projection
- **Idea.** Upscale each view with Ultimate SD Upscale under a depth ControlNet, with a per-stage prompt, then optional face detailer (Simple p.7/p.8; video summary: x4 then optional x2). CCC p.8, p.9 describes the same lever: lower ControlNet `strength_end` gives quality, higher gives likeness.
- **Why here.** Our upscale is RealESRGAN 4x, which cannot add detail. A tiled diffusion pass with a depth guide adds plausible texture detail (fabric, skin) per tile.
- **Effort.** M. ComfyUI graph using SDXL-class model plus tile/depth ControlNet; fits 24 GB.
- **Risk.** Medium to high: it hallucinates, and doing it per view makes the views drift apart, which is our existing pain. Safer to upscale one view and project, or to test on the front only. The 512 px that Hunyuan3D-Paint samples at (Simple p.7) is why Mickmumpitz needs this step; we start from larger views.
- **AMD.** Ultimate SD Upscale and Impact Pack are pure Python custom nodes and normally run on ROCm; not verified here.

### 7. Hunyuan3D-Paint 2.0 multiview texture generation (experimental alternative)
- **Idea.** Generate the other five views jointly from one reference view, conditioned on normal and position maps of the mesh (`hunyuan3d-paint-v2-0`, 25 steps, 512 views, Simple p.7), then bake. Joint generation is the one thing in these posts that attacks "views disagree" at the source.
- **Why here.** It is the only approach here that guarantees cross-view agreement by construction, for the shape-conditioned views we currently get from independent Qwen redraws.
- **Effort.** L. New model download, a `comfyui-hunyuan3dwrapper` setup, and integration with our Pixal3D meshes and rig.
- **Risk.** High. Output views are only 512 px (p.7), so detail depends on upscaling (#6). From my background knowledge, not the articles: the wrapper's rasteriser is a compiled CUDA extension and the Tencent licence has territory limits; neither is verified here.
- **AMD.** Doubtful until proven; do not start without a 1-hour ROCm build test.

### 8. Normal map from the finished colour texture
- **Idea.** "Normal Map (Simple)" (scale 1.0) turns the final texture into a normal map, set as PBR normal on the GLB (Simple p.9).
- **Why here.** PAIN_POINTS: "no PBR maps (normal, roughness) yet".
- **Effort.** S.
- **Risk.** Medium: a normal map derived from colour invents relief from paint (a dark crease becomes a groove). It looks "richer" but is not geometry. Only worth it as an optional export.
- **AMD.** Yes, CPU.

---

## What we already do or do better

- **Front-first, then the rest from references**: their main-view-then-generate-others flow (Simple p.4 to p.7) is the same idea as our turnaround/front projection with depth-guided generation and the unguided back as reference (PAIN_POINTS). Ours is built on the real mesh of a rigged character.
- **Depth-guided generation**: they use a depth ControlNet on the main view (Simple p.5); we already do depth/normal-guided generation and our views are within 1 % scale.
- **Real multi-view input**: our `--sheet` route builds the shape with multiview Pixal3D and projects four real views. They have no equivalent input; their texture is always generated.
- **Face fidelity**: face fit by landmarks from the original picture, face reshape, early close-up. They rely on a face detailer re-generating the face (Simple p.8), which cannot be faithful to a real photo.
- **Automatic quality control**: a 3-judge VLM panel, outline-moved checks, and manual review. Their method is "tweak the seed value ... repeat until you're satisfied" (Simple p.5).
- **Regional repair**: the Retexture tab and Repair tab (any region, new geometry) go beyond their masked inpaint (Advanced p.6), which only edits a 2D image.
- **Rig, animation, hands**: nothing in these posts touches rigging, animation or hands (they only note a face fix).
- **Texture safety defaults**: we found extra generated views make things worse and made Simple the default; the articles never discuss this failure.
- **Background removal, upscale of the input**: the README already covers both (RealESRGAN / 4x-UltraSharp; background removal of the input).

Honest caveat: they output a 2048 (or 4096) UV texture plus a normal map on a mesh with clean UVs (Simple p.3, p.8); we have not compared our texture resolution to that, and we have no PBR maps.

---

## Not applicable / skip

- **LoRA dataset generation and captioning (CCC p.2, p.8 to p.10).** We do not train per-character LoRAs; a training step per character would add far more time than the whole 53-minute run and needs a ROCm-compatible trainer (AI Toolkit / Flux Gym named, p.2) we have not verified. Skip unless we later decide a per-character LoRA is the way to fix side/back drift.
- **Virtual try-on, scene variations, "kiss" story chaining (CCC p.2, p.3; Qwen p.1).** Product features for image makers, not our texturing.
- **Grain and chromatic aberration group (CCC p.9).** Harms a texture; we want clean albedo.
- **IP-Adapter PLUS reference (Advanced p.5).** SDXL-specific; Qwen Image Edit takes references directly (Qwen p.2). Our Look/style handling already covers "restyle from a reference".
- **Hy3D Mesh UV Wrap (Simple p.3).** We already create UVs when preparing 3D-model inputs (README, "Starting from a 3D model").
- **Background removal with InSPyReNet (Simple p.6).** Our input already gets background removal; adding another remover gives nothing.
- **Their prompts and checkpoint choices (Flux/SDXL, SDXL Lightning).** Not named well enough in the PDFs, and we use Qwen-Image 2.1 for generation.
- **The workflows themselves.** No `.json` is in the PDFs (Simple p.10; Advanced p.11), and the advanced tier looks gated (Advanced p.12). Nothing here is a drop-in; everything above is a re-implementation from description.

## Suggested next step (smallest useful test)

Do #1 and #2 together on the existing F1-driver sheet run: fill uncovered texels, add a 50 % de-lit blend of the front view, compare contact sheets against the current Simple texture. Both are CPU or one Qwen call, no new downloads, and they target the two listed texture complaints (flat/unpainted regions, patchy seams). Defer #5 until one manual test shows Studio accepts a pose reference image.
