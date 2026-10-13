# Human motion: capture from video, and generation

Research note for Homunculus, written 2026-10-13. Slice 03 of six. Audience: a smart newcomer (the author is an audio/speech engineer new to 3D and vision), so terms are defined as they come up.

**Verification convention.** Items marked *(verified)* were checked against a primary page (the arXiv abstract, the GitHub README or LICENSE, or the model card) during this research. Items marked *(from memory)* are older, well-known work that I did not re-open; their arXiv numbers in the source list are from memory and should be spot-checked before citing. *(unverified)* means I looked and could not confirm it. I give no numbers I did not see.

---

## 1. Overview in ten lines

1. A human body in 3D is described by a **parametric body model**: a small set of numbers (pose = joint angles, shape = how tall/wide you are) that a fixed template mesh follows. **SMPL** is the standard one (24 joints, body only, no fingers or face); **SMPL-X** adds hands and face (55 joints); **MANO** is the hand-only model.
2. From 2018 to 2021 (HMR, SPIN, VIBE, PARE) the job was "one image in, SMPL numbers out", and the output lived in the *camera's* frame, so a dancer seemed to float and the camera's own motion contaminated everything.
3. In 2022 to 2024 the field moved to **world-grounded** motion: the person's path across a floor that does not move, even when the camera does (SLAHMR, WHAM, TRAM, GVHMR). GVHMR (SIGGRAPH Asia 2024), the method Homunculus uses, is the cheap, fast, camera-light member of this family.
4. In parallel, **big transformer backbones plus synthetic data** (4DHumans/HMR2.0, BEDLAM, CameraHMR) raised single-frame accuracy, and **hand** specialists (HaMeR, WiLoR) and **whole-body** models (SMPLer-X/SMPLest-X) made fingers and faces feasible.
5. Late 2025 to 2026 brought Meta's **SAM 3D Body** (single-image, body+feet+hands, new MHR rig) and a wave of **diffusion-based** video-to-world-motion papers (DuoMo, GEM/GENMO, DanceHMR for hands, OnlineHMR for streaming).
6. On the generation side, text-to-motion went from small models on a 14,616-clip dataset (MDM, T2M-GPT, MoMask on HumanML3D) to **scaled** models: HY-Motion 1.0 (1B parameters, 3,000+ hours, Dec 2025) and UniMate (one model for arbitrary skeletons, Sept 2026).
7. Physics-based control (DeepMimic, AMP, PHC, MaskedMimic) makes a simulated humanoid *track* a reference motion; it fixes foot sliding and floating but needs a simulator and the output is a simulated body, not a BVH on your rig (unless you export).
8. Monocular video has hard limits: depth is guessed, the global path drifts, feet slide, fast spins and floor work degrade, and fingers are mostly noise unless a hand model is run separately.
9. The practical frontier is therefore not "a better single model" but **GVHMR (or a successor) + a hand model + a foot-contact/physics cleanup + retargeting care**.
10. Licensing is the quiet constraint: the best research code (GVHMR, WiLoR, SMPL/SMPL-X, SAM 3D Body's SAM License) is non-commercial or custom; the permissive ones (TRAM, WHAM, HaMeR, 4DHumans, ProtoMotions) are MIT/Apache but depend on SMPL data licensed non-commercially.

---

## 2. Timeline

| Date | Development | Note |
|---|---|---|
| 2015 | SMPL body model (MPI) | the parametric body everyone uses (from memory) |
| 2017 | AMASS-style mocap unification begins; AMASS paper 2019 | 40+ hours of mocap in SMPL form (from memory) |
| 2018 | HMR (Kanazawa); DeepMimic (Peng) | first end-to-end image->SMPL; first strong RL mimicry (from memory) |
| 2019 | SPIN | regression + optimization loop (from memory) |
| 2020 | VIBE | video, temporal discriminator trained on AMASS (from memory) |
| 2021 | PARE; AMP; AIST++ | occlusion-aware attention; adversarial motion priors; dance dataset (from memory) |
| 2022 | MDM, MotionDiffuse; ASE; HumanML3D; SLAHMR | motion diffusion arrives (from memory) |
| 2023 | T2M-GPT, MotionGPT; BEDLAM; PHC; 4DHumans/HMR2.0; SMPLer-X; MoMask (Dec) | transformer backbones, synthetic data (from memory, arXiv IDs below) |
| 2023-12 | WHAM (CVPR 2024); HaMeR (CVPR 2024) | world-grounded with contact; 3D hands with ViT (WHAM repo verified) |
| 2024-03 | TRAM (ECCV 2024) | masked SLAM + metric scale (verified) |
| 2024-04 | MotionLCM | one-/few-step latent consistency text-to-motion (from memory) |
| 2024-09 | WiLoR; GVHMR (arXiv 2409.06662, SIGGRAPH Asia Dec 2024) | verified |
| 2024-12 | MaskedMimic (SIGGRAPH Asia 2024) | one physics controller for many tasks (verified exists) |
| 2025-01 | SMPLest-X; Motion-X++ | simpler scaled whole-body; bigger whole-body dataset (verified) |
| 2025-03 | GVHMR drops DPVO default for SimpleVO | verified on repo news |
| 2025-04 | PromptHMR (CVPR 2025) | prompt-able HMR, video variant with TRAM-style SLAM (verified) |
| 2025-05 | GENMO (ICCV 2025 highlight), now renamed GEM | one model for estimation and generation (verified) |
| 2025-11-19 | SAM 3D Body checkpoints (paper arXiv 2602.15989, Feb 2026; CVPR 2026 oral) | verified |
| 2025-12-30 | HY-Motion 1.0 weights and code | verified |
| 2026-01 | EA's physics-based refinement for video capture ("last mile") | arXiv 2601.19036, verified |
| 2026-03 | DuoMo (CVPR 2026); OnlineHMR (CVPR 2026); OpenT2M (CVPR 2026) | verified |
| 2026-05 | DanceHMR (hand-aware video SMPL-X); HTD-Refine on top of TRAM | verified abstracts |
| 2026-09-04 | UniMate (arXiv 2609.05415) | verified listing |

---

## 3. Developments, one by one

### 3.0 Vocabulary first

- **Kinematic chain**: joints connected parent-to-child (pelvis -> thigh -> shin -> foot). Pose is stored as each joint's rotation *relative to its parent*; rotate the thigh and everything below moves. "Forward kinematics" computes joint positions from these rotations.
- **SMPL / SMPL-X / MANO**: described above. SMPL has 24 joints and a 10-number shape code; SMPL-X adds finger joints, jaw and eyes. Body-model files need registration and are non-commercial.
- **Camera frame vs world frame**: in the camera frame the person is described relative to the lens; if the camera moves, the person's "path" includes the camera's motion. A **world-grounded** estimate puts the person on a static floor, with gravity pointing down, so you get a real walking path and a floor to put feet on.
- **Foot skating/sliding**: the foot moves while it should be planted. **Foot contact**: a flag or probability per foot per frame saying it is touching the ground, used to freeze or fix sliding.
- **Retargeting**: moving motion from one skeleton (SMPL) to another (your Mixamo-style rig) with different bone lengths and rest poses.
- **MPJPE / PA-MPJPE / W-MPJPE / WA-MPJPE**: average joint position error in millimetres. PA = after best rigid alignment (forgives global placement); W/WA = measured in world coordinates, the strict ones. Lower is better.

### 3.1 The first wave: image to SMPL (HMR, SPIN, VIBE, PARE) *(from memory)*

**What.** Regress SMPL pose and shape directly from a cropped person image. HMR (2018) used a CNN plus a discriminator that asks "does this look like a real pose?"; SPIN (2019) mixed regression with an iterative fitting loop (SMPLify) so each helps the other; VIBE (2020) took video and used a temporal network and a motion discriminator trained on AMASS; PARE (2021) used part-level attention so occluded limbs rely on visible context.

**How.** A network predicts joint angles and a weak-perspective camera; training mixes a few 3D-labelled datasets (Human3.6M, 3DPW, MPI-INF-3DHP) with 2D keypoint reprojection losses on in-the-wild photos.

**Why it mattered.** Proved monocular SMPL was practical. Their limits are what later work fixed: weak-perspective cameras (wrong near the lens), small backbones, per-frame jitter, camera-frame output.

**License/hardware.** Research repos, mostly MIT-ish code but SMPL required; run on one GPU. Link: see sources (HMR, SPIN, VIBE, PARE).

### 3.2 4DHumans / HMR2.0 (2023) *(verified repo; paper from memory)*

**What.** "Humans in 4D": a plain ViT (vision transformer) regressing SMPL, plus the PHALP tracker to link detections into per-person tracks over time.

**How.** A large ViT trained on a big pseudo-labelled mix; the video pipeline detects people (ViTDet), runs HMR2.0 on each crop, and PHALP associates them with appearance, pose and location cues. `track.py` writes a pickle with each tracklet's 3D pose and shape.

**Why it mattered.** Showed that scaling the backbone beats clever heads; it became the feature extractor of many later systems. **GVHMR's own pipeline uses HMR2 image features** (your docs list `hmr2` among the checkpoints).

**License/hardware.** Code MIT (verified). The README's install is for CUDA 11.7; on ROCm Homunculus already has it running as part of GVHMR. SMPL model needs registration. Link: https://github.com/shubham-goel/4D-Humans

### 3.3 BEDLAM (2023) and CameraHMR (3DV 2025) *(CameraHMR paper verified to exist; BEDLAM from memory)*

**What.** BEDLAM is a *synthetic* dataset: rendered people with real-looking clothing and hair, with perfect SMPL-X ground truth. CameraHMR ("Aligning People with Perspective") uses a model that predicts the camera's field of view and trains on better pseudo-ground-truth.

**How.** Synthetic data removes the label noise that plagues real photos; perspective-aware modelling replaces the weak-perspective shortcut, which matters for close-up or wide-angle footage.

**Why it mattered.** Better single-frame body shape and pose, and the training source behind TRAM's strong numbers (TRAM's repo lists BEDLAM among training data).

**License/hardware.** CameraHMR: "code and pGT available for research purposes"; the exact licence text I could not confirm (unverified). Link: https://arxiv.org/abs/2411.08128

### 3.4 WHAM (CVPR 2024) *(repo verified)*

**What.** World-grounded Humans with Accurate Motion: video to SMPL in world coordinates, with foot-ground contact.

**How.** Stage one lifts 2D keypoints (ViTPose) to SMPL using a network trained on AMASS mocap; stage two fuses image features. A contact estimate drives a foot-aware global trajectory; the camera path comes from SLAM (DPVO or DROID-SLAM), or `--estimate_local_only` skips it. An optional Temporal SMPLify step refines further.

**Why it mattered.** First popular method to combine learned motion prior, contact and SLAM into world coordinates with less foot sliding.

**License/hardware.** MIT code (verified); SMPL needs registration. Evaluated on 3DPW, RICH, EMDB. Link: https://github.com/yohanshin/WHAM

### 3.5 TRAM (ECCV 2024) *(repo verified)*

**What.** "Global Trajectory and Motion of 3D Humans from in-the-wild Videos."

**How.** Three steps: (1) a DROID-SLAM variant with *masking*, so moving people do not confuse camera tracking, and a metric-depth model gives the scene a real-world scale; (2) VIMO, a video transformer that regresses body motion; (3) combine so the person's trajectory is in metres. The repo notes "better gravity and floor prediction" (Feb 2025) and integration into PromptHMR (June 2025).

**Why it mattered.** The solution to "how far did the dancer actually move" for moving cameras. In OnlineHMR's own table (authors' numbers, not independent), TRAM scores better on WA-MPJPE_100 (76.4) than GVHMR (111.0) and WHAM (135.6) but with long offline runtimes of tens of seconds to minutes per clip.

**License/hardware.** MIT (verified); needs compiling DROID-SLAM; no GPU-memory figure stated. DROID-SLAM is CUDA-oriented, so porting to ROCm may be work (unverified). Link: https://github.com/yufu-wang/tram

### 3.6 GVHMR (SIGGRAPH Asia 2024; TPAMI 2026) *(verified)*

**What.** World-grounded human motion recovery via **Gravity-View coordinates**.

**How.** Instead of predicting motion in the camera frame and then chaining frame to frame (which accumulates drift), GVHMR defines for each frame a coordinate system from *gravity* (which way is down) and the *camera's viewing direction*. Estimating pose in this frame is easier because it removes ambiguity about yaw. Per-frame GV-space estimates are turned into one world trajectory by a transformer with relative-rotation inputs, so error does not accumulate frame by frame. A foot-contact stage sits on top. Camera motion comes from visual odometry, DPVO originally, then (since March 2025) SimpleVO; `-s` skips it for a static camera.

**Why it mattered.** Fast (your docs: model itself under 2 s for a 20 s clip) and does not require heavy SLAM; strong results on 3DPW, RICH, EMDB (the repo says its test command reproduces these).

**License/hardware.** **Not MIT.** The LICENSE (verified) is a custom Zhejiang University 3D Vision Group licence: "educational, research and non-profit purposes only"; modifications must be open-sourced and are non-commercial; commercial users must contact the authors. The checkpoint was trained on 2x RTX 4090. Homunculus ships no GVHMR code (setup clones it), which is fine for a personal/research tool but means **a commercial product cannot ship it**. The repo does not mention hands.
Link: https://github.com/zju3dv/GVHMR

### 3.7 PromptHMR (CVPR 2025) *(verified)*

**What.** Promptable human mesh recovery: a model that takes the image plus optional prompts (boxes, masks, text, interaction cues) and returns SMPL-X.

**How.** Camera-space estimate first; for video, temporal transformer layers; for world coordinates it pairs with TRAM-style metric SLAM (DROID-SLAM plus ZoeDepth). Authors say PromptHMR-Vid with TRAM's SLAM beats previous world-coordinate methods.

**Why it mattered.** Multi-person with prompts (you can say "this person") and SMPL-X output including hands; a direct candidate to replace GVHMR if one needs several dancers in one clip (Homunculus roadmap: group choreography).

**License/hardware.** I did not confirm the code licence (unverified); SMPL-X body model licensing applies. Link: https://arxiv.org/abs/2504.06397

### 3.8 SAM 3D Body (Meta, Nov 2025 release; paper Feb 2026; CVPR 2026 oral) *(verified)*

**What.** A promptable single-image model for full-body mesh including **body, feet and hands**, on a new parametric rig called **Momentum Human Rig (MHR)** that separates skeleton from surface shape.

**How.** Encoder-decoder; optional prompts (2D keypoints, masks); a separate hand decoder for finer fingers (per secondary write-ups; the exact split I could not confirm from the abstract). Training labels come from a multi-stage annotation pipeline (manual keypoints, differentiable optimisation, multi-view geometry). Output is in **camera coordinates** (verified), so it gives no world path by itself; a December 2025 paper (arXiv 2512.21573) builds world-coordinate retargeting on top of it, and a "Fast SAM 3D Body" paper (arXiv 2603.15603) targets real-time use. The model card quotes 3DPW MPJPE 54.8.

**Why it mattered.** First widely available "foundation" body+hand estimator from a big lab, and the most likely source of usable finger poses from *one frame*.

**License/hardware.** **SAM License** (a custom Meta licence; whether it permits commercial use I did not read; unverified). Hardware requirement not stated on the page. Outputs MHR, not SMPL: the repos I read do not describe an MHR-to-SMPL conversion (unverified), a real integration cost. Link: https://huggingface.co/facebook/sam-3d-body-dinov3 , https://github.com/facebookresearch/sam-3d-body

### 3.9 Hands: HaMeR and WiLoR; face: EMOCA, SMIRK

**HaMeR (CVPR 2024)** *(repo verified)*. A ViT regressing MANO (hand model) parameters, trained on a large mix of hand datasets. MIT code, but needs the registered **MANO right-hand** file (left hands are mirrored). CUDA 11.7 install. Link: https://github.com/geopavlakos/hamer

**WiLoR (2024)** *(verified)*. End-to-end hand localisation (a detector) and reconstruction, built for speed and in-the-wild images, and used in video setups. **The WiLoR models are CC BY-NC-ND** (non-commercial, no derivatives); the public code is a simplified demo version; depends on Ultralytics (AGPL-style licensing issues, check) and MANO. Link: https://github.com/rolpotamias/WiLoR

**How hand pipelines combine with the body**: run a body model for the wrist pose, run a hand model on the crop for the finger angles, then replace the SMPL hand joints. The wrist rotation is the hard seam.

**Face: EMOCA, SMIRK** *(from memory; not re-verified)*. They regress the FLAME face model (expression, jaw). Irrelevant for a rig without blendshapes, but relevant if the character gets facial animation later.

**DanceHMR (arXiv 2605.18102, May 2026)** *(verified abstract)*. Directly relevant: video to temporally smooth SMPL-X with "residual body-hand fusion" and an augmentation for close-up shots, claiming better hands than prior video methods and more temporally stable. **No code link on the arXiv page**, so it is not usable yet. Link: https://arxiv.org/abs/2605.18102

### 3.10 SMPLer-X, SMPLest-X, Motion-X (2023-2025) *(verified abstracts)*

**What.** Whole-body (body+hands+face, SMPL-X) estimation scaled up. SMPLer-X (NeurIPS 2023) trained ViT-Huge-based models on up to 4.5M instances from many datasets; SMPLest-X (Jan 2025) simplified it to a pure one-stage design and reports better hands.

**Why it mattered.** Evidence that *data diversity and scale* beat architecture tricks; and that one-image whole-body is workable. Motion-X++ (Jan 2025) extends a large whole-body dataset with text labels for motion generation.

**License.** Not confirmed (unverified). Link: https://arxiv.org/abs/2501.09782

### 3.11 DuoMo, GEM/GENMO, HTD-Refine, OnlineHMR (2025-2026) *(verified abstracts; claims are the authors')*

- **DuoMo (CVPR 2026)**: two diffusion models, one camera-space, one that lifts to world space and refines; outputs mesh-vertex motion directly. Reports 16% lower world error on EMDB (with low foot skating) and 30% on RICH. Release of code not stated. https://arxiv.org/abs/2603.03265
- **GENMO, renamed GEM (NVIDIA, ICCV 2025 highlight)**: *estimation as constrained generation*: one diffusion model that takes video, 2D keypoints, text, music or 3D keyframes, even mixed at different time spans. Code link exists (github.com/NVlabs/GENMO); licence and whether weights are released not stated on the page (unverified). https://research.nvidia.com/labs/dair/gem
- **HTD-Refine (arXiv 2605.26879)**: a refinement on top of TRAM that matches velocities and accelerations, aimed at "natural" dynamics. https://arxiv.org/html/2605.26879
- **OnlineHMR (CVPR 2026)**: streaming world-grounded HMR, about 0.30 s delay per frame by the authors' table. https://arxiv.org/html/2603.17355v1

**Why they matter.** Direction of travel: generative priors clean up noisy per-frame estimates, and one model serves both capture and generation. None is a drop-in for Homunculus today (code/licence unclear).

### 3.12 Markerless products and datasets *(products: pricing unverified)*

**Products.** Move AI (single and multi-camera markerless capture), Rokoko (inertial suit ~US$2,999 plus ~US$999 gloves per one secondary roundup; plus video tool), DeepMotion (Animate 3D, credit-based; reported prices range from ~US$9/month annual to US$83/month depending on source), Plask, Autodesk Flow Studio (formerly Wonder Studio/Dynamics; reported Free to ~US$100/month; it replaces an actor with a CG character in live footage). Pricing sources disagree and are secondary (blogs); **verify on vendor sites**. All are closed cloud services; useful as a quality benchmark and a fallback, not as part of a local pipeline.

**Datasets** *(from memory unless noted)*.

| Dataset | What it is |
|---|---|
| AMASS | 40+ hours of optical-marker mocap unified as SMPL; prior for nearly all motion models |
| Human3.6M, 3DPW, RICH, EMDB | pose benchmarks: lab, outdoor IMU-based, scene-contact, and moving-camera world-coordinate (EMDB used by GVHMR/TRAM/WHAM, verified) |
| BEDLAM | synthetic people with exact SMPL-X |
| AIST++ | 1,400-ish dance sequences from multi-view video with music; basis for dance-from-music |
| FineDance | long, finer dance dataset with mocap and genre labels |
| HumanML3D | ~14.6k motions with text, the standard text-to-motion benchmark (used by MoMask results above) |
| Motion-X / Motion-X++ | millions of whole-body frames with text, includes hands/face (verified for X++ existence) |
| OpenT2M (CVPR 2026) | 2,800+ hours of open motion; paper reports train/val leakage in existing text-to-motion benchmarks (verified) |

### 3.13 Text-to-motion: MDM -> MoMask -> HY-Motion -> UniMate

**MDM (2022), MotionDiffuse (2022)** *(from memory)*. Diffusion on the sequence of poses (like image diffusion, but each "pixel row" is a frame of joint rotations), conditioned on CLIP text. Showed diffusion works for motion.

**T2M-GPT (2023), MotionGPT (2023), MoMask (CVPR 2024)** *(MoMask verified abstract)*. Quantise motion into discrete tokens and generate them like language. MoMask uses residual vector quantisation and a masked transformer plus a residual transformer; reports FID 0.045 on HumanML3D (versus 0.141 for T2M-GPT) by its own paper. HumanML3D uses a 22-joint, 20 fps, 263-dim representation, which is *not* the Mixamo skeleton, so a retarget is always needed.

**MotionLCM (2024)** *(from memory)*. Latent consistency distillation for one-to-few-step generation, real-time speed.

**HY-Motion 1.0 (Tencent Hunyuan, 30 Dec 2025)** *(verified)*. A **1.0B-parameter diffusion transformer with flow matching** trained in three stages: pretraining on 3,000+ hours, fine-tuning on 400 hours curated, then RL from human feedback and reward models. A **Lite 0.46B** version also exists. The repo lists a **minimum of 26 GB VRAM (standard) and 24 GB (Lite)** *excluding* the LLM prompt-rewriting feature (disable with `DISABLE_PROMPT_ENGINEERING=True`); shorter prompts (<30 words), one seed, and motions under 5 s reduce memory. Limits listed: non-humanoid characters and multi-person interaction. I could not read the licence text (a License.txt exists; terms unverified: Tencent Hunyuan licences have in the past excluded some territories, which should be checked before use). Output format not stated on the page (SMPL-H/FBX mentioned only in acknowledgements). Link: https://github.com/Tencent-Hunyuan/HY-Motion-1.0

**UniMate (Mou et al., Princeton, arXiv 2609.05415, 4 Sept 2026)** *(verified listing; claims the authors')*. Generates motion for a rigged asset from a text prompt **for arbitrary skeleton topologies**, with no per-skeleton retraining. A topology-aware diffusion transformer injects skeleton structure into attention (graph-aware attention bias, spectral rotary position embedding from the graph Laplacian, a global conditioner from the rest pose). Trained on UniML3D (13,006 sequences over thousands of skeletons: bipeds, quadrupeds, birds, fish, insects, snakes, rigid objects). Also claims zero-shot in-betweening and text-guided editing. Link: https://arxiv.org/abs/2609.05415 , project page linzhanmou.com/unimate/ (from listing). Homunculus already uses it; I did not verify its code or licence.

**LLM-based motion (MotionGPT and descendants)** *(from memory)*. Treat motion tokens as a foreign language of an LLM so one model does text<->motion; today's trend (HMVLM, OpenT2M's autoregressive "MonoFrill", verified existence) is scale plus tokenisers.

### 3.14 In-betweening, style transfer *(from memory; thin verification)*

In-betweening fills the gap between keyframes (Robust Motion In-betweening, 2020; now folded into diffusion models: MDM-style inpainting, MaskedMimic, UniMate's claimed in-betweening). Style transfer (Xia et al. 2015, MotionPuzzle and diffusion style methods) restyles a motion ("old man", "happy"). For Homunculus the near-term use is **looping and blending clips**; I have not verified any specific open implementation.

### 3.15 Physics-based and RL character control

**DeepMimic (2018)**, **AMP (2021)**, **ASE (2022)**, **PHC (ICCV 2023)**, **MaskedMimic (SIGGRAPH Asia 2024)**.

**How.** The character is a physically simulated humanoid (joints with motors, gravity, collisions). A neural network policy sees the body state and a target pose from the reference motion and outputs joint torques; the reward is how well the sim tracks the reference. AMP replaces hand-written rewards with an adversarial "does this look like mocap" score; ASE learns reusable skills; PHC makes one policy track nearly all of AMASS and recover from falls (Meta/CMU); MaskedMimic casts control as **motion inpainting** with masked conditions (full tracking, sparse keyframes, text, joystick), one controller for many tasks.

**Why it mattered.** A physics-tracked motion cannot slide, float or penetrate the floor, so it is the principled foot-sliding fix, and it is the bridge to humanoid robots (H2O and Unitree retargeting use the same machinery; I did not verify these specific projects here).

**Tooling.** **ProtoMotions (NVIDIA)** is the maintained framework: Apache-2.0 (verified), supporting Isaac Gym, Isaac Lab, Newton, MuJoCo (verified), MaskedMimic as an example policy. **AMD/ROCm support is not mentioned**; MuJoCo-based paths are the most plausible on AMD (unverified). Training runs quoted use 4 to 24 A100s, so *training* a tracking policy locally on 24 GB is unrealistic; using a pre-trained tracker is the feasible route (availability unverified).

**EA "last mile" paper (arXiv 2601.19036, Jan 2026)** *(verified abstract)*: a physics-based refinement for video capture that targets floating and interpenetration and works for several characters. That is almost exactly Homunculus's foot-sliding problem; code availability unknown.

---

## 4. What this means for Homunculus

**Context.** Your GVHMR path (docs/VIDEO_MOTION.md) gives body-only SMPL motion, guessed depth, sliding feet (0.6 to 0.7 body heights per second in the first low-pose test), weaker fast spins and floor work, and a heading you must fix with `--yaw`.

**1. Better video-to-motion than GVHMR?**
- *For accuracy of the global path:* TRAM wins in the one cross-method table I saw (OnlineHMR's, authors' own), at the price of masked DROID-SLAM (CUDA-oriented, ROCm port unverified) and much longer runtime. Not worth switching for a single dancer with a mostly fixed camera.
- *For multi-person (roadmap: group choreography):* PromptHMR (+TRAM) or 4DHumans/PHALP tracking feed one-person-at-a-time GVHMR; the pragmatic route is "track, crop each dancer, run GVHMR per track". PromptHMR's code and licence need checking.
- *For future:* DuoMo, GEM, DanceHMR, OnlineHMR are promising but I found no confirmed released code. Re-check in a month.
- *Licensing alert:* GVHMR's licence is non-commercial. Fine for research and personal use. If Homunculus ever becomes a product, plan for TRAM (MIT) or WHAM (MIT) instead, with their own SMPL licence caveat.

**2. Hands and fingers from video.** GVHMR does not mention hands (verified README), so your pose-library fingers are the right default. To get real fingers: run **HaMeR** (MIT code, MANO needed, CUDA install to port) or **WiLoR** (CC BY-NC-ND, non-commercial) on hand crops, or **SAM 3D Body** (hand decoder; SAM License; MHR output needs conversion). Expect fingers to be noisy: hands are small in frame, often occluded or motion-blurred; temporal smoothing is mandatory (DanceHMR exists precisely because per-frame hands jitter). A sensible experiment: add wrist-to-finger blending only when hands are large in frame (close-up shots) and keep library poses otherwise.

**3. Accuracy to expect.** A single camera cannot measure depth; the model guesses from body proportions and learned priors, so expect: plausible arm/leg poses (as you saw at five checked moments), good timing and rhythm, wrong absolute heading, drifting travel path under camera motion, bad results for floor work and rapid spins, and clothes (long skirts, baggy dark clothes) confusing the body shape. Benchmark errors on EMDB-style moving-camera data are tens to hundreds of millimetres at best (the OnlineHMR table quotes WA-MPJPE_100 in the 76 to 136 range for the three methods; units are mm per that table's convention (unverified)). Do not expect mocap-suit fidelity.

**4. Cleaning foot sliding.** In increasing effort:
1. *Contact-based IK (no AI):* use GVHMR's contact estimate (it has a foot-contact stage) or detect "foot velocity below threshold and height near zero", lock the planted foot in world space, and re-solve the leg with two-bone IK in Blender. Cheap, reliable for walking and idle dance.
2. *Smooth the hips path* (low-pass) to stop skating that comes from jitter, not true travel.
3. *Physics tracking:* feed the retargeted motion to a pre-trained humanoid tracker in ProtoMotions/MuJoCo and export the simulated joints. Fixes floating and penetration, but changes the motion slightly, needs a humanoid whose proportions match your character, and needs hardware/AMD work I could not verify.
4. *Learned refinement:* the EA "last mile" approach or a DuoMo-style prior, once code appears.

**5. What to try next (ordered by payoff per effort).**
1. Add a **foot-lock IK pass** to `tools/retarget_bvh.py` using the contact/velocity heuristic; measure with the same sliding metric you already used (body heights per second).
2. A **fixed-camera preference**: tell users to use `-s` and cut at camera cuts (already in docs); add an automatic check that warns when sliding exceeds a threshold.
3. **Hands experiment**: HaMeR on a clip with close-up hands, compare to the library pose; or try SAM 3D Body on key frames only.
4. **Multi-dancer**: tracking (PHALP/4DHumans) -> per-dancer GVHMR -> shared floor alignment.
5. **Text generation**: evaluate **HY-Motion Lite** (0.46B; 24 GB VRAM minimum is exactly your card's limit, so run alone, short prompts, and offload your other models) against UniMate for dance prompts; check licence first (License.txt not read).
6. **Do not** invest in training or RL on this GPU.

---

## 5. Open problems

- **Absolute scale and depth** from one camera; global drift on long clips.
- **Moving-camera accuracy**: SLAM with moving people, dark/low-texture scenes (your dark clothes with coloured lights test is a hard case).
- **Hands and faces** in the same pass as the body, temporally stable and in the same coordinate frame.
- **Fast motions, floor work, self-contact, inter-person contact**: scarce training data. HY-Motion lists multi-person interaction as a limitation.
- **Foot contact and physical plausibility** without a simulator in the loop.
- **Benchmarks**: leakage found in text-to-motion benchmarks (OpenT2M); FID on HumanML3D rewards the dataset's style rather than usefulness.
- **Skeleton diversity**: only UniMate-type models attempt non-SMPL skeletons; retargeting onto stylised characters (Miles-style proportions) is still lossy.
- **Licences**: nearly every strong component is research-only; a clean commercial stack barely exists.
- **Rig mismatch**: MHR (SAM 3D Body) vs SMPL vs Mixamo vs HumanML3D skeletons: each conversion adds error.

---

## 6. Sources

Verified in this session (primary page opened or surfaced in search):
- GVHMR repo: https://github.com/zju3dv/GVHMR ; licence: https://raw.githubusercontent.com/zju3dv/GVHMR/main/LICENSE ; paper: https://arxiv.org/abs/2409.06662
- TRAM repo: https://github.com/yufu-wang/tram ; paper: https://arxiv.org/abs/2403.17346
- WHAM repo: https://github.com/yohanshin/WHAM ; paper: https://arxiv.org/abs/2312.07531
- 4DHumans: https://github.com/shubham-goel/4D-Humans
- HaMeR: https://github.com/geopavlakos/hamer
- WiLoR: https://github.com/rolpotamias/WiLoR ; paper https://arxiv.org/abs/2409.12259
- CameraHMR: https://arxiv.org/abs/2411.08128 ; https://camerahmr.is.tue.mpg.de
- PromptHMR: https://arxiv.org/abs/2504.06397
- SAM 3D Body: https://arxiv.org/abs/2602.15989 ; https://huggingface.co/facebook/sam-3d-body-dinov3 ; https://github.com/facebookresearch/sam-3d-body ; Fast SAM 3D Body https://arxiv.org/abs/2603.15603 ; world-coordinate retargeting https://arxiv.org/abs/2512.21573
- SMPLest-X: https://arxiv.org/abs/2501.09782 ; Motion-X++: https://arxiv.org/abs/2501.05098
- GENMO/GEM: https://research.nvidia.com/labs/dair/gem ; https://arxiv.org/abs/2505.01425
- DuoMo: https://arxiv.org/abs/2603.03265 ; OnlineHMR: https://arxiv.org/abs/2603.17355 ; HTD-Refine: https://arxiv.org/abs/2605.26879 ; DanceHMR: https://arxiv.org/abs/2605.18102
- Last Mile physics refinement: https://arxiv.org/abs/2601.19036
- HY-Motion 1.0: https://github.com/Tencent-Hunyuan/HY-Motion-1.0 ; https://arxiv.org/abs/2512.23464
- UniMate: https://arxiv.org/abs/2609.05415
- OpenT2M: https://research.beingbeyond.com/opent2m
- MoMask: https://arxiv.org/abs/2312.00063
- ProtoMotions: https://github.com/NVlabs/ProtoMotions ; MaskedMimic: https://research.nvidia.com/labs/par/publication/maskedmimic/ ; PHC: https://openaccess.thecvf.com/content/ICCV2023/papers/Luo_Perpetual_Humanoid_Control_for_Real-time_Simulated_Avatars_ICCV_2023_paper.pdf
- Mocap product pricing roundups (secondary, conflicting): https://mocaponline.com/blogs/mocap-news/motion-capture-cost-guide ; https://www.renderhub.com/blog/budget-motion-capture-options-worth-considering

From memory, not re-opened (arXiv IDs to check): HMR 1712.06584; SPIN 1909.12828; VIBE 1912.05656; PARE 2104.00390; DeepMimic 1804.02717; AMP 2104.02180; ASE 2205.01906; PHC 2305.06456; MDM 2209.14916; MotionDiffuse 2208.15001; T2M-GPT 2301.06052; MotionGPT 2306.14795; MotionLCM 2404.19759; BEDLAM 2306.16940; AMASS 1904.03278; AIST++ 2101.08779; HumanML3D (Guo et al., CVPR 2022); SLAHMR 2302.12827; EMOCA 2204.11312; SMIRK 2404.04104.

Unverified: licences of PromptHMR, CameraHMR, SMPLest-X, GEM, DuoMo, DanceHMR, MaskedMimic, PHC, HY-Motion (text not read), UniMate; SAM License commercial terms; ROCm compatibility of DROID-SLAM, HaMeR, ProtoMotions, HY-Motion; current prices of Move AI, DeepMotion, Rokoko, Plask, Autodesk Flow Studio.
