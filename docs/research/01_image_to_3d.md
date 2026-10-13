# Image(s) to 3D shape and texture: from foundations to October 2026

Research note for Homunculus, written 2026-10-13. Audience: a smart newcomer to 3D (an audio/speech engineer). Everything marked **verified** was checked this session against an arXiv abstract, a GitHub README or the vendor; **secondary** means it comes from a blog or aggregator only; **unverified** means I could not confirm it. Where I cite an arXiv number from memory without re-fetching it, I say so.

## 0. Vocabulary first (read this once)

- **Mesh**: the standard 3D model. A list of points (vertices) joined into triangles (faces). Games, Blender and rigging all want meshes.
- **Topology**: how the triangles are arranged. "Good" topology (what an artist makes) has clean rings of faces around elbows and knees so the mesh bends well. "Bad" topology (what marching cubes or a scanner makes) is millions of tiny random triangles that look fine still but deform badly.
- **Texture / PBR**: the picture painted on the mesh (via UV coordinates, an unwrapping of the surface onto a flat sheet). PBR adds extra sheets: roughness, metallic, normals, so lighting looks right.
- **NeRF**: a neural network that stores a scene as a glowing fog you can render from any angle. **3D Gaussian Splatting (3DGS)**: stores a scene as millions of soft coloured blobs; fast to render. Neither is a clean mesh.
- **SDF / implicit surface**: a function that says "how far am I from the surface"; the surface is where it equals 0. Marching cubes turns it into a mesh.
- **Diffusion model**: generates data by starting from noise and removing it step by step, guided by a condition (here an image). **Latent diffusion** does this in a compressed space (the latent) made by a VAE (an autoencoder). **Flow matching / rectified flow** is a newer, simpler cousin of diffusion.
- **Sparse voxels**: a 3D grid of tiny cubes where only the cubes near the surface are stored. This is what makes high resolution affordable.

## 1. Ten-line overview

1. Before 2020, 3D from images meant photogrammetry: you needed dozens of photos of a real object.
2. NeRF (2020) and 3D Gaussian Splatting (2023) made reconstruction from photos fast and beautiful, but still needed many photos.
3. DreamFusion (2022) invented "score distillation": use a 2D image generator as a judge and optimize a 3D object until every angle looks plausible to it. Magic, but about an hour per object, blobby, "Janus" faces (a face on every side).
4. Multi-view diffusion (Zero-1-to-3, MVDream, Wonder3D, Era3D, 2023-24) fine-tuned image models to draw the same object from other angles, and a reconstructor lifted those to 3D. Fast, but views disagree with each other.
5. Large reconstruction models (LRM, TripoSR, InstantMesh, 2023-24) skipped optimization entirely: a big transformer maps image(s) to 3D in one forward pass, seconds per object.
6. In 2024 the field changed again: "native 3D latent diffusion" (CLAY, TRELLIS, Hunyuan3D 2) trains a diffusion model directly on 3D shapes encoded as a compressed latent. No 2D detour; cleaner and sharper shapes.
7. 2025 was the resolution race: sparse voxels (Direct3D-S2, Sparc3D, TRELLIS.2) reached 1024-1536 cubed grids, and texture became a separate PBR stage (Hunyuan3D-Paint, RomanTex, MeshGen).
8. 2026 is about fidelity to the input and structure: Pixal3D aligns the 3D to the input pixels; part-aware models (PartCrafter, OmniPart, Hunyuan3D-Part) split objects into pieces; Hunyuan3D-Omni takes a skeleton pose as a control.
9. The best weights you can run locally (TRELLIS.2, Pixal3D, Step1X-3D, Direct3D-S2) are MIT or Apache; Tencent's Hunyuan line is open only up to 2.1 and excludes the EU, UK and South Korea; the newest Tencent (3.x), Meshy, Tripo and Rodin are hosted only.
10. Unsolved: clean artist-quality topology, reliable hands and unseen sides, and true rig-ready output. Those are exactly Homunculus's pain points.

## 2. Timeline

| Date | Development | Type | Open? |
|---|---|---|---|
| Mar 2020 | NeRF (arXiv 2003.08934, ID from memory) | Neural scene from many photos | Yes |
| Sep 2022 | DreamFusion (2209.14988, from memory) | Score distillation, text to 3D | Paper; community reimplementations |
| Mar 2023 | Zero-1-to-3 (2303.11328, from memory) | Novel-view diffusion | Yes |
| Aug 2023 | MVDream (2308.16512, from memory); 3D Gaussian Splatting (2308.04079, from memory) | Multi-view diffusion; fast scene representation | Yes |
| Nov 2023 | LRM (2311.04400, from memory); MeshGPT (2311.15475, from memory) | Feed-forward reconstruction; first autoregressive artist mesh | LRM weights not released; MeshGPT code unofficial |
| Mar 2024 | TripoSR (2403.02151, from memory), Stability + Tripo | LRM, open | MIT (from memory) |
| Apr 2024 | InstantMesh (2404.07191, verified) | Multi-view diffusion + sparse-view LRM | Yes |
| Jun 2024 | MeshAnything (2406.10163, from memory); CLAY (2406.13897, from memory) | Artist mesh from shape; native 3D latent diffusion | MeshAnything yes; CLAY (Rodin) no |
| Aug 2024 | MeshAnything V2 (2408.02555, verified); Stable Fast 3D | Adjacent tokenization; fast LRM | Yes (Stability Community License for SF3D) |
| Dec 2024 | TRELLIS (2412.01506, verified, 2 Dec); Meshtron (2412.09548, verified) | Structured latents; 64K-face artist meshes | TRELLIS MIT; Meshtron not released (unverified) |
| Jan 2025 | Hunyuan3D 2.0 (21 Jan, arXiv 2501.12202) | Shape DiT + Paint texture | Tencent community license |
| Mar 2025 | DeepMesh (2503.15265, verified); RomanTex (2503.19011, verified); Hunyuan3D 2mini/2mv/Turbo; TripoSG | RL-tuned artist mesh; texture | Mixed |
| May 2025 | Step1X-3D (13 May); Sparc3D (20 May); Direct3D-S2 (23 May); MeshGen; UniTEX | High-res native 3D | Step1X Apache 2.0; Direct3D-S2 MIT; Sparc3D weights not released (secondary) |
| Jun 2025 | Hunyuan3D 2.1 (13 Jun, open PBR); Hunyuan3D 2.5 report (2506.16504); PartCrafter (2506.05573) | PBR; 10B shape model; part-aware | 2.1 open (restricted), 2.5 hosted |
| Jul 2025 | OmniPart (2507.06165) | Part-aware, box planning | Yes |
| Aug 2025 | FastMesh (2508.19188, verified) | 8x faster artist mesh | See section |
| Sep 2025 | Hunyuan3D 3.0 (announced 16 Sep, hosted); Hunyuan3D-Omni (2509.21245, 25 Sep) | Higher-res; pose/skeleton control | 3.0 closed; Omni open |
| Oct 2025 | Seed3D 1.0 (2510.19944, verified) ; Meshy 6 preview | ByteDance hosted pipeline | Hosted |
| Nov 2025 | SAM 3D Objects (2511.16624, verified, 19 Nov); NaTex (2511.16317) | Single-image 3D with layout; native texture | SAM License |
| Dec 2025 | TRELLIS.2 (2512.14692, verified, 16 Dec); LATTICE paper (2512.03052) | O-Voxel, 4B | MIT |
| Jan 2026 | Hunyuan 3D 3.1 hosted; Meshy 6 GA | | Hosted |
| May 2026 | Pixal3D (2605.10922, verified, 11 May) | Pixel-aligned generation | MIT |
| Aug-Sep 2026 | Meshy 7 (12 Aug, secondary); Pixal3D multi-view inference (Sep) | | Hosted / MIT |
| Oct 2026 | UltraTex (2K multi-view texturing; weights status unverified) | Texture | Unverified |

Caveat: the 2026 rows rely partly on the aggregator at cinevva.com (secondary). It also reports that no new frontier open-weight shape model shipped in Q3 2026 and that TRELLIS.2 is still the best you can download (secondary).

## 3. The developments, one by one

### 3.1 NeRF and 3D Gaussian Splatting (2020, 2023): the foundation
**What**: Ways to store a 3D scene learned from many photos. NeRF stores it inside a small neural network; 3DGS stores explicit coloured blobs.
**How**: You know where each photo was taken. You adjust the scene until rendering it from those positions reproduces the photos. NeRF samples points along each camera ray and asks the network "colour and density here?". 3DGS projects blobs onto the screen, which is far faster.
**Why it mattered**: It showed 3D can be learned by comparing renders to pictures, the idea every later method builds on (the "renders look right" loss). It also gave the later generators a representation to output.
**Hardware / license**: Run on a single consumer GPU. The original code has research licenses (3DGS: non-commercial Inria license, from memory). **Not directly useful for Homunculus**: they need many photos and produce no rig-ready mesh.

### 3.2 DreamFusion and score distillation (2022)
**What**: Text-to-3D with no 3D training data.
**How**: Start with a random NeRF. Render it from a random angle, add noise, ask a frozen 2D diffusion model "how would you denoise this?", and nudge the NeRF in that direction. Repeat tens of thousands of times from all angles. The 2D model never sees 3D; it just acts as a critic.
**Why it mattered**: First proof a 2D image model contains enough 3D knowledge to make 3D. Spawned Magic3D, ProlificDreamer, DreamGaussian, and so on.
**Weaknesses**: Slow (tens of minutes to hours), over-saturated colours, the Janus problem (multiple faces), low resolution. Largely superseded for production use. ID from memory.

### 3.3 Multi-view diffusion: Zero-1-to-3, MVDream, Wonder3D, Era3D (2023-24)
**What**: Fine-tune an image diffusion model so that, given one image, it draws the same object from another camera angle (or 4-6 angles at once).
**How**: Take a 2D model (Stable Diffusion) and fine-tune it on renders of a large 3D dataset (Objaverse), conditioning on the camera change. MVDream generates several views jointly with attention across views so they agree. Wonder3D and Era3D add normal maps and better camera handling. A second step (reconstruction or optimization) turns the views into a mesh.
**Why it mattered**: It cut the time from an hour to about a minute and fixed Janus faces mostly. It is the family Homunculus is still emulating when it redraws a back view with Qwen-Image plus depth ControlNet (D-10).
**Weakness**: Views are only approximately consistent, so the fused 3D shows seams and mush; resolution is typically 256-512 px per view. IDs from memory; InstantMesh below is verified.

### 3.4 Feed-forward large reconstruction models: LRM, TripoSR, InstantMesh (2023-24)
**What**: One big transformer that maps one or a few images straight to a 3D representation (a "triplane") in one pass.
**How**: LRM encodes the image with a vision transformer (DINO), and cross-attends to a learned triplane (three 2D feature grids that together describe 3D). A small decoder reads colour and density from it. Trained on ~1M objects. TripoSR is an open reimplementation tuned for speed (under a second). InstantMesh first makes 6 views with a multi-view diffusion model, then feeds them to a sparse-view LRM that directly outputs a mesh via differentiable iso-surface extraction (verified from the paper title and abstract).
**Why it mattered**: Seconds per object, open weights; started the "image to 3D as a product" era. Quality limit: blurry, low detail, 3D mush behind the object.
**License / hardware**: InstantMesh Apache 2.0 (from memory, unverified); TripoSR MIT; both fit on 8-16 GB. Superseded by 3.5-3.7 in quality.

### 3.5 CLAY and the idea of native 3D latent diffusion (2024)
**What**: Train a diffusion model on 3D shapes themselves, not on images.
**How**: A shape VAE squeezes a 3D shape (sampled points with normals) into a short list of latent vectors; a diffusion transformer learns to generate such lists given an image or text. Decoding gives an implicit surface, extracted as a mesh.
**Why it mattered**: No fusing of inconsistent 2D views: the model directly knows what a plausible 3D shape is. CLAY became the engine of Rodin (closed). The same "vecset" recipe (3DShape2VecSet) powered Hunyuan3D 2, TripoSG, Step1X-3D and others. ID from memory.

### 3.6 TRELLIS (Microsoft, Dec 2024) -- verified
**What**: "Structured Latents" (SLAT): a sparse 3D grid of cells, each holding a feature vector gathered from many rendered views by a vision foundation model (DINOv2).
**How**: Two-stage generation. Stage 1 generates which cells are occupied (the coarse structure); stage 2 generates the feature vectors inside them. Decoders turn the same latents into 3D Gaussians, a radiance field or a mesh. Rectified flow transformers up to 2B parameters, 500K objects.
**Why it mattered**: First open model that was clearly better than the LRM family in appearance and could output multiple formats and be edited locally. It is MIT-licensed. It also moved the field from vecsets toward sparse structured voxels.
**Link**: https://arxiv.org/abs/2412.01506 and https://github.com/microsoft/TRELLIS

### 3.7 Hunyuan3D 1.0 / 2.0 / 2.1 / 2.5 / 3.x (Tencent, 2024-2026)
**What**: The most influential commercial-lab family, two parts: **Hunyuan3D-DiT** (shape) and **Hunyuan3D-Paint** (texture).
**How (2.0)**: A shape VAE encodes meshes into latents (vecset style, with importance sampling to keep sharp edges); a flow-matching diffusion transformer generates the latents from an image. Then Paint generates multi-view images of the textured object, conditioned on the shape's normal and position maps, and bakes them into a texture. 2.0 released 21 Jan 2025; Turbo, mini (0.6B) and multi-view variants followed Mar-Apr 2025.
**2.1 (13 Jun 2025, verified)**: first with PBR (albedo, metallic, roughness) and full training code. VRAM per the README: about 10 GB shape, 21 GB texture, 29 GB for both. (2.0 README: 6 GB shape, 16 GB both.)
**2.5 (report 23 Jun 2025)**: a 10B-parameter shape model ("LATTICE", from the same family as arXiv 2512.03052 -- the relationship is as stated in secondary sources) and better PBR texture. Hosted only.
**3.0 (announced 16 Sep 2025), 3.1 (28 Jan 2026)**: hosted via Tencent Cloud / platform; reports of 1536 cubed grids (secondary). No public weights, per the Cinevva timeline (secondary).
**License**: Tencent Hunyuan community license, which excludes the EU, UK and South Korea, and (2.1) caps at 1M monthly active users. Treat as "open weights, not open source".
**Links**: https://github.com/Tencent/Hunyuan3D-2, https://github.com/Tencent-Hunyuan/Hunyuan3D-2.1, https://arxiv.org/abs/2501.12202, https://arxiv.org/abs/2506.16504

### 3.8 Step1X-3D (StepFun, 13 May 2025) -- verified
**What**: Fully open (Apache 2.0) two-part system: 1.3B geometry model (hybrid VAE plus diffusion transformer, outputs watertight TSDF surfaces) and a 3.5B SD-XL-based texture module that keeps views consistent via geometric conditioning and "latent-space synchronization".
**Why it mattered**: The most permissive full pipeline (including training code and an 800K-asset list). Needs roughly 27-29 GB VRAM per the README for geometry plus texture, so it does not fit a 24 GB card without offloading.
**Link**: https://github.com/stepfun-ai/Step1X-3D, arXiv 2505.07747 (from search summary).

### 3.9 Direct3D-S2 and Sparc3D (May 2025) -- verified abstracts
**What**: Two answers to "how do we generate 1024 cubed shapes without 1024 cubed memory?"
**Direct3D-S2**: a sparse SDF volume with a "Spatial Sparse Attention" mechanism for the diffusion transformer (3.9x faster forward, 9.6x faster backward pass; trains at 1024 on 8 GPUs where dense methods at 256 needed 32). MIT. https://arxiv.org/abs/2505.17412
**Sparc3D**: "Sparcubes" (sparse deformable marching cubes) to make training meshes watertight at 1024 without losing thin parts, plus a Sparconv-VAE built only from sparse convolutions. Weights: unreleased per a secondary source. https://arxiv.org/abs/2505.14521
**Why it mattered**: Direct3D-S2's sparse-SDF design is the base on which the Pixal3D paper branch sits. Together they made fine detail (fingers, thin straps) possible in a shape model.

### 3.10 TRELLIS.2 (Microsoft, 16 Dec 2025) -- verified
**What**: 4B-parameter successor. New representation **O-Voxel**: a sparse voxel grid that stores geometry and PBR material together, with no iso-surface field, so it handles open surfaces, non-manifold geometry and internal enclosed structure.
**How**: A Sparse Compression VAE squeezes O-Voxel 16x spatially; large flow-matching transformers generate the compact latent. Converting textured mesh to O-Voxel takes under 10 s on one CPU core, and back under 100 ms on CUDA.
**Specs (README)**: MIT (nvdiffrast/nvdiffrec carry separate NVIDIA licenses); at least 24 GB GPU, tested on A100/H100, Linux only; resolutions 512-1536 cubed; on H100 about 3 s (512), 17 s (1024), 60 s (1536). Outputs full PBR (albedo, metallic, roughness, opacity).
**Why it matters**: Cinevva (secondary) still calls it the best downloadable model. **For Homunculus**: the README's 24 GB is a floor measured on NVIDIA; Homunculus is on AMD ROCm, and the repo depends on CUDA-specific kernels (natten, nvdiffrast, flash-attn) -- porting risk is real and unverified here.
**Link**: https://github.com/microsoft/TRELLIS.2, https://arxiv.org/abs/2512.14692

### 3.11 Pixal3D (Tencent ARC + Tsinghua, May 2026) -- verified
**What**: The model Homunculus already uses. Core idea: instead of generating the shape in an abstract standard pose and injecting the image through attention, **back-project** the image's multi-scale features into a 3D feature volume along the camera's rays. The 3D grid thereby has a direct pixel-to-3D correspondence, so the model produces geometry aligned to the input view.
**Claims**: approaches "reconstruction-level" fidelity to the input; extends to multi-view by aggregating back-projected volumes across views (this is what `--sheet` uses); scene generation through a modular pipeline.
**Details (README)**: MIT; the `main` branch is built on TRELLIS.2, the `paper` branch (SIGGRAPH 2026) on Direct3D-S2; low-VRAM mode defaults to 1024 grid, normal mode 1536; training code and data toolkit released May 2026; multi-view inference added Sep 2026 (secondary). No official VRAM figure.
**Why it matters here**: this explains both its strength (front matches the picture tightly) and its famous weakness: the back is **not constrained by any pixel**, so it is invented. That is why Homunculus draws a back view and feeds both.
**Link**: https://arxiv.org/abs/2605.10922, https://github.com/ldyang694/Pixal3D

### 3.12 Texture and PBR generation: Hunyuan3D-Paint, RomanTex, MeshGen, UniTEX, NaTex, Seed3D-PBR, UltraTex
**The problem**: A mesh needs a texture. You cannot just ask a 2D model for a UV map; unwrapped UVs look like garbage to an image model.
**Family 1, multi-view paint then bake** (Hunyuan3D-Paint, Step1X-3D texture, RomanTex, MeshGen): render the untextured shape from several angles (normals, depth), have an image diffusion model paint those views consistently (cross-view attention, 3D-aware rotary position embeddings in RomanTex), then project into UV space and inpaint holes. PBR variants paint albedo, roughness, metallic as separate channels. Weakness: seams and ghosting where views disagree, plus holes in unseen areas -- exactly Homunculus's patchwork and its D-8 "fill from neighbours" patch.
**Family 2, native 3D texture**: predict colour directly on the surface or in 3D space with no view stage (UniTEX, TEXGen, NaTex "latent colour diffusion in 3D", arXiv 2511.16317). Eliminates view disagreements; still maturing and heavier.
**Family 3, jointly generated** (TRELLIS.2 O-Voxel carries PBR in the same latent; Seed3D has separate PBR decomposition and UV completion modules, hosted).
**Licenses**: Hunyuan3D-Paint is under the Tencent community license; RomanTex, MeshGen, UniTEX, NaTex code status is **unverified** here. UltraTex (Oct 2026, 2K multi-view diffusion for texturing) status unverified.
**Links**: https://arxiv.org/abs/2503.19011 (RomanTex), https://arxiv.org/abs/2505.04656 (MeshGen), https://arxiv.org/abs/2505.23253 (UniTEX), https://arxiv.org/abs/2511.16317 (NaTex)

### 3.13 Part-aware, controllable and articulated generation: PartCrafter, OmniPart, Hunyuan3D-Part, Hunyuan3D-Omni
**What**: Generate an object as separate, named parts rather than one fused lump.
**PartCrafter** (MIT, arXiv 2506.05573): from one image, outputs up to ~16 distinct meshes in one pass, using a compositional latent (each part has its own tokens) and attention within and across parts. **OmniPart** (arXiv 2507.06165): first plans part bounding boxes (autoregressively, guided by 2D masks), then generates parts inside those boxes. Hunyuan3D-Part (Sep 2025) is Tencent's equivalent under a community licence (secondary).
**Hunyuan3D-Omni (arXiv 2509.21245, 25 Sep 2025)**: built on Hunyuan3D 2.1, it accepts point clouds, voxels, bounding boxes and **skeletal pose** as extra conditions in one model (3.3B, about 10 GB VRAM per a mirrored model card, secondary). Pose conditioning is the closest thing in the literature to "give me this character already in a T-pose".
**Why it mattered**: Fused shapes (fingers welded to the body, armour merged into skin) make rigging hard. Parts and pose control are the route to rig-ready geometry. Truly articulated generation (joints and skin weights from the generator) is still research-grade and not verified here beyond UniRig (VAST, MIT, Apr 2025, secondary) for rigging.

### 3.14 Artist-style meshes: MeshGPT, MeshAnything(V2), Meshtron, DeepMesh, FastMesh, FlashMesh
**The problem**: Everything above makes a mesh by marching cubes over a field: dense, uniform triangles with no edge flow (bad topology). Artists make low-poly, quad-ish meshes with loops around joints.
**The idea**: treat a mesh as a sentence. Turn each face into tokens (vertex coordinates quantized to a grid), and have a language-model-style transformer generate it one token at a time ("autoregressive"), conditioned on a point cloud, image or an existing shape.
**Progress**:
- MeshGPT (2023): the first, a few hundred faces.
- MeshAnything (2024) and V2 (arXiv 2408.02555, ICCV 2025, verified): convert any 3D shape to an artist mesh; V2's "adjacent mesh tokenization" uses one vertex per face where possible, roughly halving sequence length and doubling the face limit (still under 1.6K-ish faces).
- Meshtron (NVIDIA, 2412.09548, verified): up to 64K faces, versus about 1.6K for the previous best; code release unverified.
- DeepMesh (2503.15265, ICCV 2025, verified): better tokenizer (about 72% compression, secondary) and DPO (preference learning) so meshes are complete and more pleasing; code and weights on GitHub/HF.
- FastMesh (2508.19188, 3DV 2026, verified): generate vertices autoregressively and the faces in one shot with a bidirectional transformer; over 8x faster, about 23% of the tokens of the most compact tokenizer. FlashMesh (2511.15618) adds speculative decoding (up to 2x).
**Why it matters / honest status**: These make plausible low-poly output for props and furniture. For a fully-posed, thousand-detail character with fingers, they still break: meshes fail to close, faces flip, symmetrical limbs get lost. No verified evidence that any of them reliably handles a hand-complete character with a rig-friendly loop structure (my reading; unverified at character scale). A practical alternative today is non-learned remeshing (quad remesh in Blender, Instant Meshes) plus re-projecting skin weights.
**Licenses**: vary; check each repo (not verified here).

### 3.15 Meta SAM 3D Objects (19 Nov 2025) -- verified
**What**: A single-image model that predicts shape, texture and the object's **layout** (where it sits, pose, scale) in a scene, even when occluded.
**How**: two-stage transformer (coarse shape and pose, then refinement for texture and detail), DINOv2 encoder, and a human-in-the-loop data engine that produced about 3.14M mesh annotations on nearly 1M images. Meta reports at least a 5:1 human preference win rate on real-world objects (their own claim).
**License**: the SAM License (terms not read here). **Relevance**: strong on real photos, not designed for characters or T-poses; useful if Homunculus later composes multi-character scenes (ROADMAP).
**Link**: https://arxiv.org/abs/2511.16624

### 3.16 Seed3D 1.0 (ByteDance, Oct 2025) -- verified
**What**: Hosted, not open: four modules (Seed3D-DiT 1.5B geometry, Seed3D-MV multi-view, Seed3D-PBR material decomposition, Seed3D-UV texture completion) producing simulation-ready assets for robotics (Isaac Sim). Available through Volcano Engine. Useful as proof of the full "geometry -> views -> PBR -> UV" pipeline, not as a dependency. https://arxiv.org/abs/2510.19944

### 3.17 Commercial tools (hosted; check live terms) -- mostly secondary sources
| Tool | Notes |
|---|---|
| **Meshy** | Version 6 GA 18 Jan 2026; 7 reported 12 Aug 2026; text/image to 3D with auto-rig and animation presets, native 8K textures. Free tier output CC BY 4.0, paid tiers (Pro about $20/mo) allow commercial use. Closed. |
| **Tripo (VAST)** | Tripo 3.0 (Aug 2025), P1.0/H3.1 announced Mar 2026. API about 30 credits (about $0.30) per textured image to 3D; extras for low-poly (+10), parts (+20), auto-rig (+25). VAST open-sourced TripoSR, TripoSG, UniRig (MIT). |
| **Rodin / Hyper3D (Deemos)** | Gen-1 (May 2024), Gen-2 (Oct 2025), Gen-2.5 (26 May 2026). Built on CLAY. Strong on clean quad-ish output and PBR; API on business plans. Closed. |
| **Hunyuan 3D platform (Tencent)** | 3.1 hosted, free daily generations. |
| **Sloyd** | Parametric / template-based generator with an API (about 10 credits for image geometry plus 10 for texture, secondary); aimed at game props. |
| **Luma Genie** | One secondary source calls it stagnant since 2023; no current verified status. Treat as unverified. |
**Takeaway**: Commercial services are 6-18 months ahead on resolution, topology and rigging, but cost money per call, send your character off-machine (against D-1) and cannot be modified. They are a useful *quality benchmark* to compare Homunculus against.

## 4. What this means for Homunculus

Homunculus today: Pixal3D (MIT, TRELLIS.2- or Direct3D-S2-based) for shape from one or four views, with a Qwen-Image-drawn back view; Blender projection for colour; Make-It-Animatable for rig.

**Replace or complement Pixal3D?**
- **TRELLIS.2 as a second candidate generator (complement).** It is the base of Pixal3D `main`, MIT, native PBR, fits the 24 GB floor on paper. Its weakness for Homunculus is the same as Pixal3D's: the back is guessed. Value: PBR output (Pain Points lists "no PBR maps") and open-surface handling (thin cloth, capes). Risk: ROCm port of its CUDA-only parts (unverified; check whether Pixal3D already runs these kernels on this GPU, in which case the risk is mostly retired).
- **Hunyuan3D 2.1 (complement, texture mostly).** Open weights, PBR Paint model; but 29 GB shape+texture exceeds 24 GB without sequential loading (shape 10 GB then texture 21 GB, one at a time, is possible), and the licence excludes EU/UK/South Korea. The author's repo is public; check the licence suits that. Paint could replace the Blender projection for the unseen surfaces, though multi-view paint models also hallucinate (garbled logos) just like the current patchwork.
- **Hunyuan3D-Omni (complement, promising).** Built on 2.1 and accepts a skeleton pose (and a bounding box) as control. If it can be driven by the target Mixamo T-pose skeleton, it addresses "arms hang down / A-pose / hands open" directly in generation instead of redrawing a T-pose image with Qwen. ~10 GB reported (secondary). Unverified: output quality for stylized characters and whether hands improve. Worth a one-day experiment.
- **Step1X-3D (not now).** Apache 2.0 but 27-29 GB for the whole pipeline; shape alone fits.
- **Hosted tools (Meshy, Tripo, Rodin)**: use as an external yardstick, not in the pipeline.

**Known weaknesses and who attacks them**
| Weakness | Who solves it (verified status) |
|---|---|
| **Back / unseen sides guessed** | Pixal3D multi-view (already used with `--sheet`); the depth-guided redraw (D-10); Hunyuan3D-2mv multi-view shape (open, community licence); Seed3D-MV (hosted). No single-image method truly knows the back; the field's answer is "generate a plausible back view first" -- the same as Homunculus. |
| **Hands (fused fingers, paddle hands)** | No model has a verified fix. Mitigations in the literature: higher grid resolution (TRELLIS.2 at 1536 cubed; Pixal3D's default 1536) so five fingers span enough voxels; part-aware generation of hands as a separate part (PartCrafter, OmniPart style) -- directly analogous to Homunculus's Repair tab; pose-controlled generation with open hands (Hunyuan3D-Omni, unverified). Open hands in the input image remain the single biggest lever. |
| **Topology / rig-readiness** | Not solved by any shape model. Options: quad-remesh and reproject skin weights (non-ML, today); artist-mesh transformers (DeepMesh, FastMesh, Meshtron) are good on props but unproven on a 52-bone character with fingers; Rodin's hosted output is reported to be cleaner (secondary). For Homunculus the topology that matters is around joints, and Make-It-Animatable already tolerates dense meshes, so this is a quality, not a blocker. |
| **Texture quality and PBR** | TRELLIS.2 (joint PBR), Hunyuan3D-Paint 2.1 / RomanTex / NaTex (separate). The current approach (project the picture, fill unseen from neighbours) is sound and picture-faithful; PBR channels could come from a TRELLIS.2 pass or an intrinsic decomposition on the projected texture (unverified idea). |
| **Face and eyes** | Eye geometry is below grid resolution for every verified model. Keep texture-based eyes. |
| **Top/bottom views** | A limit of the image generator (Qwen), not of the 3D model; unsolved in the literature I checked. |

**Recommended experiments in order** (cheap first): (1) run TRELLIS.2 and Pixal3D `main` side by side on the same three characters for hands and PBR; (2) try Hunyuan3D-Omni with a T-pose skeleton prompt; (3) test Hunyuan3D-Paint 2.1 as the texturing stage for surfaces no view paints; (4) evaluate one artist-mesh model only after (1)-(3).

## 5. Open problems
1. **Topology**: no learned model produces animation-ready, joint-aware loops on a complex posed character. Autoregressive mesh models scale with face count (token length), RL and speculative decoding help but do not eliminate it.
2. **Unseen sides**: the back of a single-image object is a guess; there is no benchmark that scores "plausible back" for stylized characters.
3. **Fine articulated detail**: fingers, toes, eyes, thin straps, text on clothing.
4. **Multi-view consistency in generated images**: still the weakest link for texture and for generated turnarounds.
5. **Rigging in the loop**: generating a mesh that is already segmented into parts with joints, rather than rigging afterward.
6. **Evaluation**: most claims are authors' own metrics or preference studies; independent head-to-head benchmarks on stylized characters are missing (I found none).
7. **Licensing**: open code is not always open weights or open training data; Hunyuan's regional exclusions, SAM's license and NVIDIA non-commercial releases (PartPacker) make commercial use legally uneven.
8. **Hardware portability**: most new repos assume NVIDIA CUDA (flash-attn, nvdiffrast, natten); AMD ROCm support is a recurring unknown.

## 6. Sources
Verified this session (primary or close to it):
- TRELLIS: https://arxiv.org/abs/2412.01506 ; https://github.com/microsoft/TRELLIS
- TRELLIS.2: https://arxiv.org/abs/2512.14692 ; https://github.com/microsoft/TRELLIS.2
- Pixal3D: https://arxiv.org/abs/2605.10922 ; https://github.com/ldyang694/Pixal3D (project page: ldyang694.github.io/projects/pixal3d, from a secondary source)
- Hunyuan3D 2.0: https://github.com/Tencent/Hunyuan3D-2 ; https://arxiv.org/abs/2501.12202
- Hunyuan3D 2.1: https://github.com/Tencent-Hunyuan/Hunyuan3D-2.1
- Hunyuan3D 2.5: https://arxiv.org/abs/2506.16504
- Hunyuan3D-Omni: https://arxiv.org/abs/2509.21245
- Step1X-3D: https://github.com/stepfun-ai/Step1X-3D
- Direct3D-S2: https://arxiv.org/abs/2505.17412 ; Sparc3D: https://arxiv.org/abs/2505.14521
- Seed3D 1.0: https://arxiv.org/abs/2510.19944 ; SAM 3D: https://arxiv.org/abs/2511.16624
- MeshAnything V2: https://arxiv.org/abs/2408.02555 ; Meshtron: https://arxiv.org/abs/2412.09548 ; DeepMesh: https://arxiv.org/abs/2503.15265 ; FastMesh: https://arxiv.org/abs/2508.19188 ; FlashMesh: https://arxiv.org/abs/2511.15618
- RomanTex https://arxiv.org/abs/2503.19011 ; MeshGen https://arxiv.org/abs/2505.04656 ; UniTEX https://arxiv.org/abs/2505.23253 ; NaTex https://arxiv.org/abs/2511.16317 (existence and one-line summaries from search results, not read in full)
- PartCrafter https://arxiv.org/abs/2506.05573 ; OmniPart https://arxiv.org/abs/2507.06165 (summaries from search)
- InstantMesh: https://arxiv.org/abs/2404.07191 ; LATTICE: https://arxiv.org/abs/2512.03052 (search result only)

Secondary (aggregators; dates and prices need rechecking): https://app.cinevva.com/guides/ai-3d-model-generation-timeline-2026 ; https://comfyui-wiki.com/en/news ; https://costbench.com/software/ai-3d-generation/meshy/ ; https://costbench.com/software/ai-3d-generation/rodin-hyper3d/ ; https://www.3daistudio.com/state-of-ai-3d-generation-2026 ; https://mer.vin/2026/06/open-weight-ai-release-week-25-models-across-llms-image-audio-video-and-3d-june-2026/

From memory, not re-fetched (IDs standard but unchecked this session): NeRF 2003.08934; 3DGS 2308.04079; DreamFusion 2209.14988; Zero-1-to-3 2303.11328; MVDream 2308.16512; LRM 2311.04400; TripoSR 2403.02151; MeshGPT 2311.15475; MeshAnything 2406.10163; CLAY 2406.13897; Step1X-3D 2505.07747; TripoSG and Wonder3D/Era3D (no ID given). Not verified at all: Luma Genie status, Meshy 7 details, TripoSplat (a June 2026 item from one roundup), UltraTex weights, Meshtron code release, Hunyuan3D 3.x resolution claims.
