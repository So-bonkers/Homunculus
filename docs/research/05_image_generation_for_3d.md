# Image generation and editing for consistent characters and 3D-ready views

Researcher 5 of 6. Written 2026-10-13. Scope: the image-model side of Homunculus (redraw, back/side/top/bottom views, hands, detail, texture, upscaling, judging, AMD).

**How to read the evidence labels.** Items marked **[verified]** were confirmed with a web search or page fetch in this session. Items marked **[background]** come from my training knowledge (older, well-known work) and were not re-checked today; paper IDs for those are given from memory and should be opened before being quoted. Items marked **[unverified]** could not be confirmed. Many 2026 facts come only from secondary sources (blogs, news aggregators); I say so where it matters. Nothing here was benchmarked on the Homunculus machine.

---

## 1. Overview in ten lines

1. A diffusion model makes an image by starting from pure noise and repeatedly removing a little of it, guided by a text prompt. Training taught it what "a bit less noisy" looks like.
2. Modern models (Flux, Qwen-Image, Z-Image) swap the old U-Net for a transformer (a DiT) and swap the old noise-removal maths for *flow matching*: the model learns a straight-ish path from noise to image, which trains more stably and samples in fewer steps.
3. "Edit" models take your picture as extra input tokens next to the noise (in-context editing), so they can change a pose or style while copying identity. Qwen-Image-Edit, Flux Kontext and Nano Banana work this way.
4. A ControlNet is a side-network that feeds a structural map (depth, pose, edges) into a frozen base model so the layout is forced. A LoRA is a small add-on that nudges a model toward a style or a skill without retraining it. Turbo means distilled to about 8 steps.
5. Single-image editors are good at "same character, different pose" but poor at true geometry: asked for a back, side, top or bottom view they guess, and the guess is not tied to a 3D shape. This is exactly your logs (sides: arms drop; top and bottom: front view comes back).
6. Purpose-built multi-view generators (Zero123++, Wonder3D, Era3D, MV-Adapter, CharacterGen, Hunyuan3D-2mv) fix camera geometry by training on thousands of rendered 3D objects. They are the right tool for orthographic views, but older ones are low resolution and weak on stylised characters and hands.
7. In 2026 the practical trend is the opposite direction: instruction editors that were also trained on multi-angle data (Qwen-Image-Edit-2511 has "viewpoint generation" built in; camera-angle LoRAs exist) and video models used as "rotate the character" engines (RCM, Jan 2026).
8. Hands, logos and small text are the places where a latent diffusion model loses information (the VAE compresses 8x per side). The fixes are crop-and-redraw at higher effective resolution, mesh- or pose-guided hand repair, and compositing the original pixels back.
9. Everything runs on AMD now in principle (ComfyUI has native ROCm support), but speed and memory for specific large models on a 24 GB RDNA card are mostly **not** documented; you are already the best data source.
10. VLM judges are useful for coarse yes/no checks and bad at fine geometry, counting fingers, and anything where the generated image is persuasive but wrong. Back them with programmatic checks (your IoU outline test is the right idea).

---

## 2. Timeline

| Date | Development | Status of source |
|---|---|---|
| 2020-2021 | DDPM, latent diffusion (Stable Diffusion 1.x, Aug 2022), LoRA (2021) | [background] |
| Feb 2023 | ControlNet (arXiv 2302.05543), T2I-Adapter | [background] |
| Aug 2023 | IP-Adapter (image-prompt adapter, 2308.06721); MVDream | [background] |
| Oct 2023 | Zero123++, Wonder3D (CVPR 2024), LCM | [background] |
| Jan 2024 | InstantID; SUPIR; Marigold (Dec 2023) | [background] |
| Feb 2024 | CharacterGen posted (2402.17214; SIGGRAPH/TOG 2024) | [verified] |
| Mar 2024 | SD3 (MMDiT + rectified flow, 2403.03206) | [background] |
| Apr 2024 | PuLID (2404.16022); Hyper-SD | [verified]/[background] |
| May 2024 | Era3D (2405.11616); DMD2 (2405.14867, NeurIPS 2024 oral) | [verified] |
| Jun 2024 | Depth Anything V2; StableNormal (2406.16864) | [verified]/[background] |
| Aug 2024 | Flux.1 (BFL); Hand1000 | [background]/[verified] |
| Oct 2024 | In-Context LoRA for DiTs (2410.23775) | [verified] |
| Dec 2024 | MV-Adapter (2412.03632; ICCV 2025); Material Anything (2411.15138; CVPR 2025) | [verified] |
| Mar 2025 | Hunyuan3D-2mv multi-view shape (Mar 18) | [verified] |
| Apr 2025 | Step1X-Edit (2504.17761); ICEdit | [verified]/[background] |
| Jun 2025 | FLUX.1 Kontext (2506.15742); SeedVR2 (2506.05301) | [verified] |
| Aug 2025 | Qwen-Image (weights Aug 4, 2025; arXiv 2508.02324, Apache 2.0); Qwen-Image-Edit | [verified] (Edit date background) |
| Sep 2025 | HunyuanImage 3.0 (Sep 28, ~80B MoE autoregressive); Hunyuan 3D 3.0 (hosted); Qwen-Image-Edit-2509 | [verified] |
| Nov 2025 | FLUX.2 [dev] (Nov 25, 32B); Z-Image-Turbo (Nov 26/27, 6B, Apache 2.0); Depth Anything 3 (2511.10647) | [verified] |
| Dec 2025 | Qwen-Image-Edit-2511 (Dec 23); Qwen-Image-2512; Qwen-Image-Layered (2512.15603); Seedream 4.5 (late Nov / Dec, date disputed) | [verified] |
| Jan 2026 | FLUX.2 [klein] (Jan 15; 4B Apache, 9B non-commercial); Z-Image base (Jan 27/28); RCM "Rotate Your Character" (2601.05722) | [verified] |
| Feb 2026 | Qwen-Image-2.0 (Feb 10, 7B-class, unified); Nano Banana 2 / Gemini 3.1 Flash Image (Feb 26); Seedream 5.0 Lite | [verified] (secondary) |
| Apr 2026 | GPT Image 2 / "ChatGPT Images 2.0" (Apr 21) | [verified] (secondary) |
| Jul 2026 | Mage-Flow (Microsoft, 4B, 4-step Turbo, arXiv 2607.19064) | [verified] |
| Sep 2026 | Qwen-Image-2.1 (Sep 20, 7B, open weights, research-only licence per one source) and its Fun ControlNet Union (ComfyUI core support Sep 28) | [verified] (secondary) |

---

## 3. Developments, one by one

### 3.1 Foundations in plain words

**Diffusion.** Train a network to predict the noise that was added to an image; at generation time start from noise and subtract predicted noise step by step. "Latent" diffusion does this in a compressed space made by a VAE (an autoencoder), which is why small text and fingers get damaged: the VAE never stored them precisely. [background]

**Flow matching / rectified flow.** Instead of predicting noise, the network predicts a *velocity*: the direction to move from the current noisy point toward the clean image. Training pairs are straight lines between a noise sample and a data sample, so sampling paths are nearly straight and need few steps. Introduced in 2022 (flow matching 2210.02747, rectified flow 2209.03003) and used at scale by SD3, Flux, Qwen-Image. [background]

**DiT / MMDiT.** A Diffusion Transformer replaces the convolutional U-Net with a transformer over image patches (DiT, 2212.09748). "Multimodal" DiT (MMDiT, SD3) processes text tokens and image tokens in the same attention, which is why prompts and in-context reference images mix so well. Qwen-Image pairs an MMDiT with a Qwen VL model as the text/condition encoder. [background; Qwen pairing verified by Qwen-Image-2.0 coverage]

**In-context editing.** Put the source image's tokens in the same sequence as the noisy target tokens and let attention copy what it needs. No special editing network: the model learns "copy identity, change what the instruction says". FLUX.1 Kontext is the cleanest statement of this ("sequence concatenation"). [verified for Kontext]

**ControlNet.** A trainable copy of the model's early layers is attached to the frozen base and fed a structural map (depth, pose, edges). The base keeps its image quality; the copy forces the layout. "Union" ControlNets handle many map types in one file. [background]

**LoRA.** Low-rank adapter matrices added to the base weights (a few MB to a few hundred MB). Used here for the 8-step "Turbo" behaviour and could be used for a "character turnaround" behaviour. [background]

**Distillation (Turbo, LCM, Hyper-SD, DMD2).** Train a student to match in 1-8 steps what a teacher does in 30-50. LCM (consistency), Hyper-SD (trajectory segments) and DMD2 (distribution matching plus a GAN loss; arXiv 2405.14867, NeurIPS 2024 oral, no regression loss needed) are the lineage. Z-Image-Turbo uses Decoupled-DMD plus an RL stage ("DMDR"). Cost: less diversity and sometimes weaker prompt adherence; benefit: seconds per image, which is what makes your multi-candidate Pick stage affordable. [DMD2, Z-Image verified; LCM/Hyper-SD background]

### 3.2 Base model lineage

**Stable Diffusion 1.x/2.x/SDXL (2022-2023).** U-Net latent diffusion; open; the ecosystem (ControlNet, IP-Adapter, LoRA) was built here. SDXL is still the base for MV-Adapter's best checkpoint. License: CreativeML OpenRAIL-style. [background]

**SD3 (Mar 2024).** First big MMDiT with rectified flow; license restrictive for commercial use. Mattered because it fixed the architecture everyone copied. [background]

**Flux.1 (Aug 2024, Black Forest Labs).** 12B rectified-flow transformer; [schnell] Apache-2.0, [dev] non-commercial. Became the base for most community work (In-Context LoRA, PuLID-Flux, Kontext). [background]

**FLUX.1 Kontext (Jun 2025).** Editing and generation in one 12B model by sequence concatenation; the paper claims better character preservation across multi-turn edits and reports degradation after many turns. Weights for [dev] are non-commercial (exact licence text: third-party summaries disagree; read the model card). Consumer GPU viable with quantisation. https://arxiv.org/abs/2506.15742 [verified]

**Qwen-Image (Aug 2025).** From Alibaba's Qwen team; strong text rendering (Chinese and English), released with technical report; Apache 2.0 (per model-card mirrors). Edit variants followed: Edit (Aug), 2509, 2511. The "2.1 int8" model you run is the 2026 successor (see below). https://arxiv.org/abs/2508.02324 [verified]

**Qwen-Image-Edit-2511 (Dec 23, 2025).** Apache 2.0. Official docs say new viewpoint generation can now be done directly with the base model thanks to LoRAs merged in, plus less image drift and better character consistency. Third-party LoRAs add explicit camera control: fal's "Multiple Angles" LoRA offers 96 camera positions (4 elevations x 8 azimuths x 3 distances), trained on 3000+ Gaussian-splat renders; elevation down to -30 degrees. All claims are publishers' own. Relevance: this is the closest off-the-shelf answer to "draw this character from the side / from above" inside the model family you already use. https://huggingface.co/fal/Qwen-Image-Edit-2511-Multiple-Angles-LoRA [verified, quality unverified; trained on objects/scenes, character T-pose quality untested]

**Z-Image-Turbo and Z-Image (Nov 2025 / Jan 2026).** Tongyi-MAI, 6B, Apache 2.0, 8 steps, fits 16 GB. Base (undistilled) released about Jan 27-28, 2026. Edit and Omni-Base variants were listed "to be released" in the sources I saw (August 2026); I could not confirm they have shipped. A Fun ControlNet Union exists for Z-Image-Turbo (Dec 2025 coverage). Matters because it is a small, fast, permissively licensed model with ControlNet support. https://comfyui-wiki.com/news/2025-11-27-alibaba-z-image-turbo-release [verified, secondary]

**FLUX.2 (Nov 2025; klein Jan 2026).** [dev] 32B open-weight, non-commercial licence; FP8 about 32 GB class; too heavy for a 24 GB card without offload or remote text encoder. [klein] 4B is Apache 2.0, about 13 GB VRAM, 9B is non-commercial; klein does generation and editing and supports multi-reference. One 2026 paper's own table puts klein-9B above Qwen-Image-Edit-2511 on an unnamed benchmark; self-reported. [verified, secondary]

**HunyuanImage 3.0 (Sep 28, 2025).** Tencent; ~80B total parameters, 13B active (MoE), autoregressive rather than diffusion; needs multiple 80 GB GPUs per one source; licence not confirmed in my search. Irrelevant to a 24 GB machine; worth knowing because it shows the "unified multimodal LLM that draws" direction. https://arxiv.org/abs/2509.23951 [verified; licence unverified]

**Qwen-Image-2.0 (Feb 10, 2026) and 2.1 (Sep 20, 2026).** 2.0 unified generation and editing in one model with a Qwen3-VL condition encoder and a roughly 7B diffusion decoder (sources disagree on the exact split). 2.1 is 7B, open weights, native RGBA output, up to 10 reference images; one source says the weights carry a research-only licence and commercial use needs an agreement with Alibaba; Artificial Analysis ranks it 18th among open-weight entries in both text-to-image and editing (secondary). Its Fun ControlNet Union (one 7.5 GB file: Canny, Depth, Grayscale, HED, Lineart, MLSD, Pose, Scribble, plus inpainting) merged into ComfyUI core on Sep 28, 2026. This is the stack Homunculus already uses; check the 2.1 licence before any commercial claim. https://blog.comfy.org/p/qwen-image-21-in-comfyui-open-weight , https://comfyui-wiki.com/en/news/2026-09-24-qwen-image-2-1-fun-controlnet-union [verified, secondary; "Turbo LoRA" for 2.1 not confirmed by me]

**Closed frontier models: Nano Banana (Gemini image), Seedream, GPT Image.** Closed, API only. Nano Banana 2 (Gemini 3.1 Flash Image, Feb 26, 2026) and Nano Banana Pro (Gemini 3 Pro Image, date uncertain) accept multiple reference images and do plan-generate-review loops. Seedream 4.5 takes up to 14 references (one source); Seedream 5.0 Lite appeared Feb 2026 (promotional sources only). GPT Image 2 (Apr 21, 2026) is OpenAI's first image model with built-in reasoning; "thinking" mode returns up to 8 consistent images per prompt (secondary). Why they matter to you: they are the quality ceiling for "draw this character from behind", and a cheap way to *generate reference data* (for example turnaround sheets) if the project's rules allow API calls; they do not fit the "fully local" goal. Licensing of outputs is per provider terms [unverified here].

**Mage-Flow (Jul 2026, Microsoft).** 4B native-resolution flow-matching DiT with a light VAE, base/RL/4-step Turbo, editing variant; claims parity with much larger models (self-reported); 0.59 s per 1024 image on an A100. Weights/licence status not checked. Useful as a signal: small, fast, edit-capable models are where the field is going. https://arxiv.org/abs/2607.19064 [verified]

### 3.3 Instruction-based editing

**Qwen-Image-Edit family.** See above; strongest open option on your hardware class.

**FLUX.1 Kontext.** See above; the reference design for in-context editing.

**Step1X-Edit (Apr 2025).** A multimodal LLM plus a diffusion decoder; introduced GEdit-Bench; 19B for v1.2 per a 2026 comparison table. Open. Mostly of interest as a benchmark origin. https://arxiv.org/abs/2504.17761 [verified]

**OmniGen / OmniGen2, ICEdit.** OmniGen (2409.11340) unifies generation, editing and subject-driven tasks in one transformer; ICEdit (2504.20690) does instruction editing on Flux Fill with a small LoRA and in-context frames. Both are [background]; neither has a documented advantage for character turnarounds over Qwen-Image-Edit.

**Qwen-Image-Layered (Dec 2025).** Decomposes an image into RGBA layers; Apache 2.0; arXiv 2512.15603. Possible use: separate hands, accessories or logo regions as layers before redraw, then recomposite. Untested [verified existence only].

### 3.4 Identity and character consistency

**IP-Adapter (2023), InstantID (2024), PuLID (2024).** Inject a face or image embedding into cross-attention. They preserve *faces* (identity embedding from a face recogniser) rather than full-body outfits and logos. PuLID's own SDXL tables show higher ID similarity than InstantID and IP-Adapter; independent blogs contradict each other, so treat rankings as unverified. On Flux, PuLID-Flux showed copy-paste artefacts and text-alignment loss in the InfiniteYou comparison (2503.16418). For stylised, non-human characters (Miles Morales in a suit) face-ID methods do little. [verified partly]

**In-Context LoRA (Oct 2024).** Tongyi Lab; the finding is that a DiT already does multi-image in-context generation; you concatenate several images (for example four panels of one character) into one canvas and fine-tune a small LoRA on a few dozen examples. Output: a character sheet of consistent panels in one pass, because attention inside one image canvas keeps panels coherent. Arxiv 2410.23775. [verified abstract; character-sheet use not confirmed by the sources I opened]

**Reference-based editors as identity engines.** In 2025-26 the practical way to keep a character is simply to feed the original to an edit model (Kontext, Qwen-Edit-2511 "improved character consistency", Nano Banana, Seedream multi-reference). Limits: drift over repeated edits (Kontext paper), logos and text drift (your known problem).

### 3.5 Multi-view diffusion for 3D

How they work in one paragraph: take a 2D diffusion model, fine-tune on renders of Objaverse-type 3D assets at *fixed known camera angles*, and make the views attend to each other so they agree. Output is a fixed set (for example front/back/left/right, sometimes with normal maps). Their strength is geometric consistency; their weakness is training data (objects, few humanoid T-poses, few stylised characters) and low resolution.

- **Zero123++ (Oct 2023).** One image to six fixed views tiled in one image; built on SD. [background]
- **Wonder3D (CVPR 2024).** One image to six colour views plus normal maps, assuming orthographic cameras; the Era3D authors note it distorts on perspective inputs. [verified, secondary]
- **Era3D (May 2024).** Higher resolution via row-wise attention, handles perspective camera; reports better novel-view quality and mesh metrics than Wonder3D (self-reported). arXiv 2405.11616. [verified]
- **MV-Adapter (Dec 2024; ICCV 2025).** A plug-in with duplicated self-attention layers that adds multi-view generation to existing text-to-image models without changing them; SDXL version at 768x768, six orthographic views, trained on about 70k Objaverse samples; also does geometry-guided generation (give it depth or normal maps) and works with LoRAs and ControlNets. This is the most "bolt-on" design: it is the architecture closest to what you do by hand (depth-guided back view), but with a camera-aware, trained consistency mechanism. arXiv 2412.03632, project page huanngzh.github.io/MV-Adapter-Page. Code licence not checked. [verified]
- **CharacterGen (Feb 2024; SIGGRAPH/TOG 2024).** Specifically for characters: a diffusion model outputs multi-view images in a canonical A-pose (pose embedding from OpenPose), then a transformer reconstructs the mesh; trained on 13,746 VRoid-Hub anime models. Relevant because it attacks "arbitrary input pose" the way your T-pose redraw does. Anime-domain; humanoid only. arXiv 2402.17214. [verified]
- **Hunyuan3D 2.0 / 2mv / 2.5 / 3.0.** 2.0 is Apache-2.0 (shape DiT + Paint texture model); 2mv (Mar 18, 2025) takes multi-view input for shape; 2.5 adds PBR via a multi-view texture architecture and a larger 10B shape model (report only, via a mirror). 3.0 (Sep 2025) was a hosted launch; open release of "Omni" was announced as planned, not confirmed. The shape-with-multiview + texture-with-multiview-PBR split is the thing to copy. [verified, secondary]
- **Rotate Your Character, RCM (Jan 2026).** Image-to-video diffusion for novel views of characters: maps arbitrary poses to a canonical pose, generates 1024x1024 orbit video, accepts up to 4 input images. Claims state-of-the-art NVS and 3D generation. Code/weights status not stated on the abstract page [unverified]. Why it matters: video models give a continuous orbit, which solves "front to back" by interpolation instead of guessing. arXiv 2601.05722. [verified]

### 3.6 Depth, normal, pose conditioning

- **ControlNet / T2I-Adapter (2023).** See above. [background]
- **Union ControlNets (Fun).** Alibaba PAI's VideoX-Fun ships Qwen-Image-2512-Fun-Controlnet-Union (Canny, HED, Depth, Pose, MLSD, Scribble; a later 2602 checkpoint adds Gray; supports inpainting; `control_context_scale` trades control strength vs detail) and the 2.1 version above. This is what the depth phase uses. [verified]
- **Depth Anything V2 (2024) and V3 (Nov 2025).** V3 (arXiv 2511.10647, ByteDance Seed) predicts depth and camera rays for any number of views with a plain transformer; "on par" detail with V2 for single images; consistent multi-view geometry is the new part. Checkpoints on Hugging Face (DA3-BASE). V2 licence varies by model size [background, unverified]. For you: in your pipeline the depth comes from a proxy *mesh* rendered in Blender, which is more reliable than estimated depth. DA3 is useful if you ever need depth/normals from *generated* side views to check consistency. [verified]
- **Normal estimators.** Marigold (diffusion repurposed for depth/normals, Dec 2023, [background]); StableNormal (arXiv 2406.16864) reduces diffusion variance for sharp, stable normals [verified]; Lotus / Lotus-2 (Flux-based) dense geometry [verified via repackaging, secondary]. Normal maps from the proxy mesh (rendered, exact) are better ControlNet input than estimated ones; your top/bottom normal-map attempt matches that but still failed, suggesting the problem is the model's prior, not the signal.

### 3.7 Hands and anatomy

- **HandRefiner (2023).** Reconstruct the hand mesh, render its depth, inpaint the hand with a depth ControlNet. Weakness: palm vs back-of-hand ambiguity; may alter areas outside the hand. A 2025 paper adds 3D hand-mesh guidance and pose transformation (arXiv 2506.12680). [verified]
- **HandCraft (2024, arXiv 2411.04332).** Detect hands, build a control image from body pose plus a parametric hand template (MANO-style), regenerate only the region. [verified]
- **Hand1000 (2024).** Fine-tunes SD for hands with ~1,000 images; a generator-side fix, not for arbitrary poses. [verified]
- **Newer models (Qwen-Image 2.x, Flux.2, Z-Image)** reduce but do not eliminate fused fingers, especially at small scale in full-body images; the usual reason is resolution: a hand in a full-body 1024 image is perhaps 40 pixels wide, i.e. 5 latent tokens. Crop and redraw at scale is the dependable fix [reasoned, not sourced]. Homunculus already has a "Repair" path for torn hands at the mesh level and a pose library for finger poses; image-level hand redraw is an additional input option.

### 3.8 Few-step distillation

Covered in 3.1. Practical notes: your Turbo LoRA is the right trade for the pick-among-candidates loop. For *geometric* tasks (back view under depth) the loss of diversity helps (you want determinism); for *detail* tasks distillation costs a little sharpness, which is why a second pass or upscaler is useful. DMD2 shows distilled students can match teachers on quality metrics (FID) but quote only the paper's own numbers.

### 3.9 Upscalers and restorers

- **Real-ESRGAN (2021), 4x-UltraSharp.** GAN-based, fast, deterministic-ish; it sharpens but invents nothing large. Already in your pipeline. [background]
- **SUPIR (2024, 2401.13627).** Diffusion-based restoration with a large VLM-driven prompt; very high detail but can hallucinate text and logos. Heavy VRAM. [background]
- **SeedVR / SeedVR2 (ByteDance Seed; SeedVR2 arXiv 2506.05301; ICLR 2026 per the repo).** One-step diffusion restoration for images and video; Apache 2.0 per the model card; 3B and 7B variants; official VRAM numbers not found; community BlockSwap tricks exist for consumer GPUs. For logos/text the same warning applies as to any generative upscaler: it will "restore" plausible but wrong letters. [verified]

### 3.10 PBR and material estimation

- **IntrinsicAnything (2024, 2404.11593)** and **RGB<->X (2024, 2405.00666):** estimate albedo / material channels from single images, or the reverse. [background, not re-checked]
- **Material Anything (arXiv 2411.15138, CVPR 2025).** A diffusion framework that creates PBR materials for texture-less, albedo-only, generated or scanned meshes, with a confidence-mask-guided progressive strategy and a UV-space refiner. [verified]
- **MaterialMVP (arXiv 2503.10289)** (illumination-invariant multi-view PBR diffusion; part of the Hunyuan line per the title list) and **MatLat (CVPR 2026)** (material latent space for PBR) are newer; I only saw titles. [verified existence]
- **Hunyuan3D 2.5 Paint** produces PBR maps multi-view. [verified, secondary]

Honest status: none of these has been tested on stylised characters with baked-in lighting; photo-trained priors may read painted shading as albedo. Expect to get plausible roughness/metallic and unreliable albedo de-lighting.

### 3.11 AMD ROCm viability

AMD states ComfyUI now has native ROCm support including the Desktop app; the Windows installer uses ROCm 7.1.1; AMD reports ROCm 7.1.1 vs 6.4 speedups of 2.6x (SDXL), 5.2x (Flux.1 schnell) and 5.4x (Wan 14B) on their own tests. AMD's guide lists the RX 7900 XTX among tested GPUs but benchmarks on a 32 GB R9700. I found no published Qwen-Image timing on a 7900 XTX; a community Docker note says Qwen-Image-2512 works on Strix Halo with >40 GB system memory [verified, secondary]. Your own numbers (about 6 s per back-view image after load, about 3 min for the depth phase) are therefore evidence worth publishing. Typical ROCm friction points (VAE decode memory spikes, FP8 kernels missing, some custom nodes CUDA-only) are from experience, not sources [unverified].

### 3.12 VLMs as judges

What the literature I found says: a 2026 survey notes VLM judges hallucinate, are biased toward AI-generated content, and reach only moderate agreement with humans (reported Spearman about 0.57-0.75), and recommends a cascade of cheap programmatic checks, then VLM judges for semantic questions, then humans for calibration (arXiv 2604.28185). "Fooling the LVLM Judges" (EMNLP 2025) found every tested judge inflates scores for visually manipulated images and the bias survives prompt mitigation. "Trust but Verify" (ICCV 2025) shows many benchmark contexts are too thin for hallucination judging. [verified]

Reliable (from this evidence plus common experience): is the character recognisably the same (coarse), is there a visible text/logo, is the pose a T-pose, did the image show front vs back, obvious artefacts. Not reliable: counting fingers, detecting subtle limb geometry, verifying that two views are the same 3D object, rating "better" between two close candidates, rare-script text. Mitigations: forced-choice with a fixed rubric, pairwise comparisons with order swapped, scoring against a reference rather than in a vacuum, and programmatic metrics (mask IoU, depth-edge agreement, colour histograms, OCR match for logos, hand-detector keypoint count).

---

## 4. What this means for Homunculus

Current state (from the repo docs): back view works under a proxy depth map, IoU about 0.88; sides fail (arms drop or stretch, IoU 0.78/0.91, check misses it because of overlap); top and bottom return a front view or foreshortened body; outputs only feed texture anyway; the shape model takes four sides.

### 4.1 Back, side, top, bottom views

Ranked by value per effort:

1. **Replace the IoU-only check with a stronger one for sides.** The failing case (arm overlaps torso) is a silhouette-overlap blind spot. Add a keypoint or limb-direction check: run a pose estimator on the generated side view and compare wrist height/extent with the proxy's projected skeleton, or compare *depth-edge* agreement (render the proxy's depth edge map and compare to a Depth Anything estimate on the generated view). Programmatic, no VLM. [engineering idea]
2. **Draw sides with a pose ControlNet in addition to depth.** The Fun Union already has Pose; the failure is that the depth map of a T-pose seen exactly side-on collapses the arms to a line, so the model has nothing to hold them out. Use a three-quarter view (45 degrees, arms visible in depth) rather than 90 degrees, or give the pose skeleton rendered from the proxy rig as the control, and use two views (back plus a 3/4) for the shape model if Pixal3D accepts arbitrary azimuths [Pixal3D input constraints: not researched here].
3. **Try the 2511 camera-angle LoRA route** for left/right only as an unguided candidate generator, then filter with the programmatic check above. It is trained on rendered objects, so test it on three T-pose characters before trusting it; cheap to try in ComfyUI. Note the LoRA is for 2511; whether it loads on Qwen-Image 2.1 is unverified (different architecture generation).
4. **Use a purpose-built multiview model as a view prior, not as the final texture.** MV-Adapter (SDXL, geometry-guided, six orthographic views, accepts depth/normal condition) or CharacterGen (A-pose canonical) can supply *consistent orthographic sides* at about 768 px; then run a Qwen-Image-Edit pass (reference = original front, structure = the multiview output via ControlNet or as a second reference) to restore detail and style. This "two-stage: geometry model proposes, style model repaints" mirrors what Hunyuan3D does internally. Cost: a second model family on ROCm; risk: SDXL-era low detail and non-humanoid failures. SDXL runs well on ROCm per AMD numbers.
5. **Video-orbit route (RCM-style).** If RCM or similar weights appear, generating an orbit video from the front picture and picking frames at 90/180/270 degrees would give geometry-aware sides, but weights are unconfirmed and a 1024 video diffusion model is heavy for 24 GB. Watch, do not build. Meanwhile an existing open video model with camera control is a possible stand-in but is outside my slice.
6. **Top and bottom: drop from generation entirely** (matches D/O-3). The shape model does not take them. Fill unseen surfaces from neighbours in texture space (already done for sheets) and, if desired, use a texture-space inpainting model (Material Anything's UV refiner idea, or Hunyuan3D-Paint-style multi-view baking) rather than asking an image model for a view it cannot draw. Top-of-head and soles are small areas.

### 4.2 Hands

- Keep T-pose with open hands (good), and add an **image-level hand crop redraw**: detect each hand (a hand detector or the rig's projected wrist), crop at least 512 px, redraw with Qwen-Image-Edit using a hand depth ControlNet fed from a *mesh-rendered hand template* (MANO/HandRefiner/HandCraft idea; you already have a finger pose library and a rig), then paste back with a soft mask. Verify with a hand keypoint detector (five fingers visible, joint lengths plausible) rather than a VLM.
- Fall back on mesh-level repair (existing path) when the crop redraw fails; ask less of the image model by choosing a flat open palm pose that matches the library.

### 4.3 Detail preservation (logos, text)

- **Do not let a generative model re-draw logos you can copy.** Mask logo/text regions in the original (OCR or a VLM bounding-box proposal, confirmed by OCR), and composite the original pixels (warped by a homography or by the depth/UV mapping) onto the redraw or the texture. Generative redraw followed by "paste the original patch" beats prompting harder. [engineering reasoning]
- Prefer a model with strong text rendering for the redraw stage (Qwen-Image family's headline strength) and keep the Turbo steps, but run a **non-generative upscaler (RealESRGAN-style) for logo regions** rather than SUPIR/SeedVR2, which can invent letters.
- Keep the front picture as the colour source (already done); the back view contributes shape only unless the check passes.
- Qwen-Image-Layered is a candidate to isolate logo layers; test before committing.

### 4.4 PBR textures

- Today the texture is a projected albedo-like colour with baked shading. A cheap, likely-effective step is **de-lighting the front picture** (IntrinsicAnything-style albedo estimation) before projection, so shading does not bake into the mesh. Test on three characters; judge by relighting in Blender.
- For roughness/metallic/normal, **Material Anything** (needs albedo-only or textureless meshes; CVPR 2025) is the most directly applicable published method; Hunyuan3D 2.5 Paint is the same idea but only partly open [verified existence, weights status unverified]. Treat PBR as optional polish: for stylised characters a hand-set roughness and constant metallic per region (from a segmentation) is often indistinguishable.
- Evaluate with fixed-light turntable renders, not VLM opinions.

### 4.5 Judging

Keep VLM judges for coarse gates (right character, T-pose, back not front). Put geometry gates in code. Calibrate the judges on 30 labelled examples from your own runs (fail cases are already in the logs: sides arms-down, top/bottom front-copy) and report agreement; swap candidate order to remove position bias.

### 4.6 Model watch-list for the Redraw stage

Qwen-Image 2.1 is current and is what you run; check its licence before any redistribution (one source: research-only). Candidates to benchmark on the 24 GB card if a second opinion is wanted: Z-Image-Turbo (Apache 2.0, 6B, ControlNet Union exists), FLUX.2 klein 4B (Apache 2.0, editing, multi-reference), Mage-Flow if weights ship. None has been verified on ROCm by me.

---

## 5. Open problems

1. **No open model reliably draws a canonical side/top/bottom of an arbitrary stylised character.** Object-trained multiview models do not know characters; character models are mostly anime A-pose.
2. **View consistency verification** (are two generated views the same 3D object?) has no cheap robust metric; silhouettes miss self-occlusion; feature-matching across views is fragile for textureless clothing.
3. **Fine detail under latent compression.** Logos, text, hands remain limited by VAE resolution and by repaint drift; fixes are workflow (crop, composite) rather than model.
4. **Distillation vs fidelity** for Turbo models: published claims (DMD2 etc.) are about FID, not logo fidelity.
5. **PBR for stylised art:** training data is photo-real or object-scan; albedo/lighting separation on painted characters is largely untested.
6. **Licences are drifting restrictive** in 2026 (Qwen-Image-2.1 reportedly research-only, Flux [dev]/FLUX.2 [dev] non-commercial, klein-9B non-commercial). If Homunculus is ever distributed, audit each model.
7. **AMD data gap:** few published per-model timings; fp8/int8 kernels, VAE memory spikes and attention backends vary by ROCm version.
8. **Judge reliability** on exactly the failures you care about (fingers, geometry) is poorly benchmarked; the evidence found is general-purpose.
9. **Unverified items I could not close:** Qwen-Image-Edit "2512" does not exist per search; Qwen-Image-2.1 Turbo LoRA; Qwen-Image-2.1 licence text; RCM weights; Hunyuan3D-Omni open release; Z-Image-Edit release; Seedream 5.0 official details; Nano Banana Pro exact date.

---

## 6. Sources

All URLs were returned by searches or fetches this session unless marked [background].

- Qwen-Image Technical Report: https://arxiv.org/pdf/2508.02324 ; model card https://huggingface.co/Qwen/Qwen-Image
- Qwen-Image-Edit-2511: https://huggingface.co/Qwen/Qwen-Image-Edit-2511 (via https://gigazine.net/gsc_news/en/20251224-qwen-image-edit-2511 , https://docs.comfy.org/tutorials/image/qwen/qwen-image-edit-2511.md)
- Multiple Angles LoRA (fal): https://huggingface.co/fal/Qwen-Image-Edit-2511-Multiple-Angles-LoRA
- Qwen-Image-2512 / Layered: https://learn.rundiffusion.com/qwen-image-2512-edit-2511-layers , https://fugumt.com/fugumt/paper_check/2512.15603v1
- Qwen-Image-2.0 coverage: https://www.analyticsvidhya.com/blog/2026/02/qwen-image-2-0-is-here/ , https://alternativeto.net/news/2026/2/alibaba-launches-qwen-image-2-0-with-improved-typography-rendering-and-lighter-architecture
- Qwen-Image-2.1: https://blog.comfy.org/p/qwen-image-21-in-comfyui-open-weight , https://datanorth.ai/news/qwen-releases-qwen-image-2-1 , https://www.eesel.ai/blog/qwen-image-2-1-review
- Qwen Fun ControlNet Union: https://huggingface.co/alibaba-pai/Qwen-Image-2512-Fun-Controlnet-Union , https://comfyui-wiki.com/en/news/2026-09-24-qwen-image-2-1-fun-controlnet-union
- Z-Image-Turbo: https://comfyui-wiki.com/news/2025-11-27-alibaba-z-image-turbo-release , https://howaiworks.ai/models/z-image
- FLUX.2: https://venturebeat.com/ai/black-forest-labs-launches-flux-2-ai-image-models-to-challenge-nano-banana , https://the-decoder.com/flux-2-small-brings-ai-image-generation-and-editing-to-consumer-graphics-cards/
- FLUX.1 Kontext: https://arxiv.org/abs/2506.15742
- HunyuanImage 3.0: https://arxiv.org/abs/2509.23951
- Nano Banana 2 / Pro: https://www.gsmarena.com/google_launches_nano_banana_2-news-71742.php , https://docs.comfy.org/zh/tutorials/partner-nodes/google/nano-banana-2
- Seedream 4.5 / 5.0: https://www.hedra.com/models/image/bytedance/seedream-45 , https://artlist.io/blog/new-seedream-5-0-announcement/
- GPT Image 2: https://neurohive.io/en/news/chatgpt-images-2-0-openai-launches-image-generation-model-with-reasoning-2k-resolution-and-multilingual-text/
- Mage-Flow: https://arxiv.org/pdf/2607.19064 , https://microsoft.github.io/Mage/flow/
- Step1X-Edit: https://arxiv.org/abs/2504.17761
- In-Context LoRA: https://arxiv.org/abs/2410.23775
- PuLID: https://arxiv.org/pdf/2404.16022 ; InfiniteYou: https://arxiv.org/pdf/2503.16418
- MV-Adapter: https://arxiv.org/pdf/2412.03632 ; https://openaccess.thecvf.com/content/ICCV2025/html/Huang_MV-Adapter_Multi-View_Consistent_Image_Generation_Made_Easy_ICCV_2025_paper.html
- CharacterGen: https://arxiv.org/pdf/2402.17214.pdf
- Era3D: https://arxiv.org/pdf/2405.11616 ; Wonder3D++: https://arxiv.org/html/2511.01767v1 ; MVDiffusion++: https://arxiv.org/pdf/2402.12712
- Rotate Your Character (RCM): https://arxiv.org/abs/2601.05722
- Hunyuan3D: https://comfyui-wiki.com/en/models/hunyuan3d ; https://www.notebookcheck.net/Tencent-s-new-Hunyuan-3D-3-0-brings-realistic-AI-model-generation-to-developers-and-creators.1116964.0.html
- Material Anything: https://arxiv.org/pdf/2411.15138 ; MaterialMVP: https://arxiv.org/pdf/2503.10289 ; MatLat: https://openaccess.thecvf.com/content/CVPR2026/html/Yeo_MatLat_Material_Latent_Space_for_PBR_Texture_Generation_CVPR_2026_paper.html
- Depth Anything 3: https://arxiv.org/pdf/2511.10647 ; https://huggingface.co/depth-anything/DA3-BASE/blob/main/README.md
- StableNormal: https://arxiv.org/pdf/2406.16864 ; Lotus-2 repack: https://huggingface.co/1038lab/Lotus-2
- DMD2: https://arxiv.org/html/2405.14867v2
- SeedVR2: https://arxiv.org/pdf/2506.05301 ; https://huggingface.co/ByteDance-Seed/SeedVR2-3B ; https://docs.comfy.org/tutorials/utility/seedvr2.md
- Hands: HandRefiner https://ar5iv.labs.arxiv.org/html/2311.17957 ; HandCraft https://arxiv.org/html/2411.04332v2 ; Hand1000 https://arxiv.org/pdf/2408.15461 ; mesh-guided refinement https://arxiv.org/html/2506.12680v2
- AMD ROCm + ComfyUI: https://www.amd.com/en/blogs/2026/amd-comfyui-advancing-professional-quality-generative-ai-ryzen-radeon.html ; https://rocm.blogs.amd.com/artificial-intelligence/comfyui-radeon-9000/README.html ; https://gigazine.net/gsc_news/en/20260107-amd-comfyui-rocm
- VLM judging: https://arxiv.org/pdf/2604.28185 ; https://underline.io/lecture/130934-fooling-the-lvlm-judges-visual-biases-in-lvlm-based-evaluation ; https://arxiv.org/pdf/2410.13121 ; https://arxiv.org/html/2411.17451v2
- [background, not re-verified; open before quoting] ControlNet 2302.05543; LoRA 2106.09685; flow matching 2210.02747; rectified flow 2209.03003; DiT 2212.09748; SD3 2403.03206; IP-Adapter 2308.06721; InstantID 2401.07519; Zero123++ 2310.15110; Wonder3D 2310.15008; LCM 2310.04378; Hyper-SD 2404.13686; Marigold 2312.02145; Depth Anything V2 2406.09414; Real-ESRGAN 2107.10833; SUPIR 2401.13627; RGB-X 2405.00666; IntrinsicAnything 2404.11593; OmniGen 2409.11340; ICEdit 2504.20690; Hunyuan3D 2.0 2501.12202. Prefix with https://arxiv.org/abs/.
