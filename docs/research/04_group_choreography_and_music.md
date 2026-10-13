# Research 04: Group choreography, multi-person motion and music-driven animation

Written 2026-10-13 for the Homunculus author (junior AI audio and speech engineer, new to 3D). Slice: multi-person motion, interaction, music-driven dance, scene-level concerns, and audio-driven character animation beyond dance.

Conventions. "Verified" means I read it on a primary or near-primary page (arXiv, official repo, conference page) during this session. "Unverified" means it comes from an aggregator, my memory, or I could not open the primary page. Licenses are the single most common gap: where I did not read the LICENSE file I say so. Research code from the dance field is very often non-commercial or "academic only", so check before shipping anything.

---

## 1. Overview in ten lines

1. Music-to-dance is a solved-looking but unsolved problem: models make plausible 10-60 second solo dances from a song, but no one has a reliable metric for "is this good dance".
2. The field moved from sequence models (FACT, 2021) to VQ-VAE + GPT (Bailando, 2022) to diffusion (EDGE 2023, Lodge 2024) and, in 2025-26, to Mamba hybrids, mixture-of-experts, LLM guidance and video diffusion that dances directly in pixels.
3. Group dance is a small sub-field (AIOZ-GDANCE 2023, TCDiff 2024/25, CoheDancers, ST-GDance/++ 2025-26). Almost all of it is "N dancers, one song, generated jointly with collision avoidance"; none is mature, and code releases are patchy.
4. Two-person interaction (InterGen, InterControl, in2IN, Duolando) is text-driven or leader-follower, mostly 2 people, with datasets of only hours.
5. The practical shortcut for Homunculus: a dance is just a skeleton animation. N characters can already dance together by playing N copies (or N different clips) of the existing Mixamo-skeleton animation with time offsets and floor positions. This needs no new model.
6. The first real research step is multi-person video capture: GVHMR (which Homunculus uses) is single-person; TRAM, PromptHMR-Vid and Human3R (ICLR 2026) handle several people in world coordinates.
7. Group "choreography" is mostly a layout problem (formation paths, spacing, collision) plus a timing problem (synchronise to the beat). Both are classical, cheap, and need no deep learning.
8. Scene representation is easy: glTF and USD both support many skinned characters; the hard part is the pipeline plumbing (one skeleton, many instances, per-instance clips).
9. The audio side is where the author's expertise transfers directly: beat/downbeat tracking, onset strength, section segmentation, music encoders (Jukebox, MERT, Wav2CLIP), and the metrics (beat alignment) are all audio-analysis problems that the dance papers handle crudely.
10. Co-speech gesture and audio-to-face (EMAGE, DiffSHEG, TalkSHOW, Audio2Face-3D) are the same pipeline shape as music-to-dance with speech instead of music: an obvious second product for a speech engineer.

---

## 2. Timeline

| Date | Item | Kind | Notes |
|---|---|---|---|
| 2021-01 (ICCV 2021) | FACT / AI Choreographer + AIST++ | model + dataset | Full-attention cross-modal transformer; AIST++ is 1408 sequences, 5.2 h (verified via search summary) |
| 2022-03 (CVPR 2022) | Bailando | model | VQ-VAE "choreographic memory" + actor-critic GPT |
| 2022-12 (ICCV 2023) | FineDance + FineNet | dataset + model | Optical mocap, 22 genres, ~14.6 h; only ~7.7 h downloadable per README |
| 2022-12 (CVPR 2023) | TalkSHOW | co-speech | Face + body + hands from speech, SMPL-X |
| 2022-11 (CVPR 2023) | EDGE | model | Diffusion transformer + Jukebox features; editing, in-betweening |
| 2023-03 (CVPR 2023) | AIOZ-GDANCE ("Music-Driven Group Choreography") | dataset | 16.7 h, in-the-wild group videos, 3D from video, 7 styles |
| 2023 (TPAMI) | Bailando++ | model | Rotation-domain pose, longer music context |
| 2023-04 (ICCV 2023) | TM2D | model | Music + text, shared VQ-VAE across two datasets |
| 2023-04 (IJCV 2024) | InterGen / InterHuman | model + dataset | Two-person text-to-motion diffusion |
| 2023-11 | InterControl | model | Zero-shot, joint-pair contact/distance control, any group size |
| 2024-01 (CVPR 2024) | EMAGE + BEAT2; DiffSHEG | co-speech | Holistic body+face from audio |
| 2024-03 (CVPR 2024) | Lodge | model | Coarse-to-fine, parallel long dance |
| 2024-03 (ICLR 2024) | Duolando + DD100 | duet | Follower GPT + off-policy RL; ~117 min duet data |
| 2024-03 (AAAI 2025) | TCDiff | group | Trajectory first, then per-dancer motion; collision-free navigator |
| 2024-04 | in2IN | interaction | Per-person text + interaction text |
| 2024-05 (CVPR 2024) | POPDG + PopDanceSet | model + dataset | Pop-music dance dataset, iDDPM |
| 2024-07 (ECCV 2024 oral) | Beat-It | model | Beat-synchronised, key-pose control |
| 2024-10 | Lodge++ | model | Adds penetration guidance, foot refinement, genre discriminator |
| 2024-12 | CoheDancers + I-Dancers | group | 3.8 h group data, 12 genres; code not confirmed |
| 2025-05 (NeurIPS 2025) | MEGADance | model | Mixture-of-experts, genre-aware, Mamba-Transformer |
| 2025-06 | DanceChat | model | LLM writes pseudo-choreography text to guide diffusion |
| 2025-06 | TCDiff++ | group | End-to-end version of TCDiff, long group sampling |
| 2025-07 (BMVC 2025) | ST-GDance | group | Graph conv spatial + sparse attention temporal, collision-free |
| 2025-10 (ICLR 2026) | Human3R | capture | One-pass multi-person SMPL-X + scene + camera, 15 FPS, 8 GB |
| 2026-01 | HINT, MAGNet (2025-12), ReMoGen (2026-04) | interaction | Autoregressive multi-human generation; unverified details |
| 2026-03 | InfiniteDance | dataset + model | 100.69 h auto-reconstructed from video; ChoreoLLaMA |
| 2026-03 | ST-GDance++ | group | Streaming, long-duration group choreography |
| 2026-07 | Wan-Dancer-14B | video | Minute-scale music-to-dance video; Alibaba Tongyi Lab |

---

## 3. Developments, one by one

### 3.1 Datasets and metrics (background for everything below)

**AIST++** (Li, Yang, Ross, Kanazawa, ICCV 2021). 3D dance reconstructed from the multi-view AIST Dance Database; 10 genres, 1408 sequences (about 5.2 h) per the search summary. Why it mattered: the first usable large public music-dance set, so every paper before 2024 reports on it. Weaknesses: motion is reconstructed from video, so it has jitter and foot errors; it is clipped to short segments; solo only. License: I could not confirm; the underlying AIST database has its own terms. Unverified. Link: https://google.github.io/aichoreographer/

**FineDance** (Li et al., ICCV 2023). Optical motion capture, 22 genres, about 14.6 h, 27 professional dancers, 346 song-dance pairs, with full-body including hands. Only a 7.7 h part is downloadable via Baidu according to the repo README (verified; may have changed). Average clip 152 s versus 13 s for AIST++. Link: https://github.com/THUSIGSICLAB/FineDance

**PopDanceSet** (POPDG, CVPR 2024). Pop-music dance clips aimed at younger audiences, claimed larger in genre range than AIST++. Code and data: https://github.com/Luke-Luo1/POPDG. Per a later paper (Skeleton2Stage) it has jitter from pose estimation. Verified via search.

**AIOZ-GDANCE** (CVPR 2023). 16.7 h of group dance, 7 styles, 16 music genres, 3D motion estimated from in-the-wild video, hence noisy. The only sizeable group dataset with real music. Link: https://aioz-ai.github.io/AIOZ-GDANCE/

**I-Dancers** (CoheDancers). 3.8 h, 12 genres, 20-60 s videos. Release status unknown.

**DD100** (Duolando). About 117 min of duets by professional dancers, mocap; public via Google Drive per repo.

**InfiniteDance's data**. 100.69 h reconstructed from monocular video with a "foot restoration diffusion model" (verified abstract). The first sign that the data bottleneck is being attacked with video capture, which is exactly the path Homunculus already has with GVHMR.

**Metrics and why they are weak.**
- FID_k / FID_g: Frechet distance between feature distributions of generated and real dance, using hand-crafted kinetic (k) and geometric (g) features. EDGE's authors argue these are unreliable on AIST++, partly because the test set is tiny and the features are superficial (verified from EDGE text). Skeleton2Stage reports FID rewards jitter when the ground truth is jittery.
- Beat Alignment Score (BAS): fraction of motion "beats" (local minima of joint speed) near music beats (librosa-style beat tracker). ConvoFusion notes it is inflated by jittery motion, since jitter creates many fake motion beats. Beat-It and others also note that dancing is not only "stop on the beat" (verified via search).
- Diversity (Div_k, Div_g): average pairwise distance of generated features. Rewards random motion.
- Physical Foot Contact (PFC): from EDGE; checks that foot acceleration is consistent with the body's centre-of-mass acceleration. Cheap physics proxy; also noisy.
- Group metrics: TCDiff/ST-GDance use collision rate and group coordination scores (exact definitions: check each paper; unverified here).
- Reality: human studies are small (16-20 participants in cases seen) and non-standardised. MDSC proposes a style-consistency metric. Net: no automatic metric correlates well with human judgment; treat all headline numbers as weak evidence.

**Audio bridge.** BAS uses a beat tracker on the music and an "onset-like" detector on motion. This is literally onset detection and beat tracking, and the choice of tracker, tolerance window (typically a Gaussian of a few frames) and the usual treatment of every motion minimum as a beat are all things a speech/audio engineer would immediately criticise. A better beat-consistency metric (tempo-aware, downbeat-aware, phase-based rather than nearest-minimum, with a cross-correlation between music onset strength and motion speed) is a small, publishable audio-side contribution.

### 3.2 FACT (AI Choreographer), 2021

What: a 12-layer full-attention cross-modal transformer that takes a short seed motion plus an audio feature sequence and predicts future motion. How: audio is converted to features (MFCC, MFCC delta, constant-Q chroma, onset, beat activation, a 35-d vector from librosa per the paper as I remember it; unverified detail), concatenated with seed motion, and a transformer predicts N future frames. Why it mattered: it created AIST++ and the first benchmark, with FID_k, FID_g, Div, BAS. Hardware/license: research code from Google; license unverified. Link: https://arxiv.org/abs/2101.08779

### 3.3 Bailando / Bailando++, 2022-23

What: music-to-dance in two stages. Stage 1: a VQ-VAE learns a codebook of short dance "units" (the "choreographic memory"), one for upper and one for lower body. Stage 2: a GPT predicts the next unit given music and previous units, and is fine-tuned with an actor-critic reinforcement learning step using a beat-alignment reward. Why it mattered: moved the field to discrete motion tokens and showed beat reward directly improves BAS. Bailando++ (TPAMI 2023) adds rotation-domain learning and better music context. License: NTU S-Lab License 1.0 (a non-commercial research license, per the Duolando README, which shares the same license; verified for Duolando, and Bailando via an aggregator). Hardware: PyTorch 1.x era, trained on V100-class GPUs; inference is light. Open source: yes. Link: https://github.com/lisiyao21/bailando and https://arxiv.org/abs/2203.13055

### 3.4 EDGE, CVPR 2023

What: a transformer-based diffusion model that generates dance directly in a continuous SMPL-like pose space from Jukebox music embeddings. How: a diffusion transformer denoises a 5 s motion window conditioned on audio features extracted by the Jukebox model (with a cross-attention and FiLM scheme as I recall; unverified detail), trained with classifier-free guidance. Long dances are made by stitching overlapping windows. Editing (joint-wise constraint, in-betweening, continuation) is done by diffusion inpainting at sampling time. Why it mattered: it made dance generation editable and showed that big pretrained audio features are the lever, not bespoke handcrafted features. It also introduced the PFC metric and argued FID is unreliable. License: MIT (verified on the repo). Hardware: README asks for 1-8 NVIDIA GPUs with at least 16 GB; Jukebox feature extraction for AIST++ takes about 24 h and 50 GB. CUDA 11.6 era, so on ROCm expect porting work (Jukebox, jukemirlib). Multi-dancer: none in the repo. Link: https://github.com/Stanford-TML/EDGE

Audio bridge: EDGE's quality comes from Jukebox, a music-generation model repurposed as an encoder (layer-wise features at ~345 Hz after the VQ-VAE codes; unverified detail). The author should know MERT (below) is a newer, smaller encoder meant for exactly this.

### 3.5 FineDance / FineNet, 2023

What: the mocap dataset above plus FineNet, which combines a diffusion model (variety) with expert networks (hands), and a retrieval module that matches genre and coherence. Also introduced the Genre Matching Score. Why it mattered: first dataset with hands and long clips. License: unverified; the full set is not public. Link: https://arxiv.org/abs/2212.03741

### 3.6 TM2D, ICCV 2023

What: bimodal dance generation from music and text. How: a 3D motion VQ-VAE maps motion from a music-dance dataset and a text-motion dataset (e.g. HumanML3D) into one discrete space, and a cross-modal transformer conditions on both. Why it mattered: showed you can borrow text-motion data to control dance, and proposed Motion Prediction Distance and Freezing Score. License/hardware: unverified. Link: https://arxiv.org/abs/2304.02419

### 3.7 Lodge and Lodge++, 2024

What: coarse-to-fine diffusion for dances of minutes. How: a global network produces coarse "characteristic dance primitives" (dance units with beats), and a second network fills each segment in parallel conditioned on primitives and music, so length is not limited by autoregression. Lodge++ adds a penetration-guidance module (self-penetration), a foot-refinement module and a multi-genre discriminator. Why it mattered: the long-dance state of the art on FineDance; the primitive idea matches how human choreographers think in "eight counts". License and release: unverified (code exists per author Ronghui Li; license not checked). Numbers (BAS 0.2423, FID_k 40.77 for Lodge++ on FineDance) are from an aggregator, unverified. Links: https://arxiv.org/abs/2403.10518 and https://arxiv.org/abs/2410.20389

### 3.8 POPDG and Beat-It, 2024

POPDG: iDDPM diffusion with a space augmentation algorithm (adds data diversity while keeping joint connectivity) and an alignment module for dance-music timing. License: unverified. Link: https://arxiv.org/abs/2405.03178.

Beat-It (ECCV 2024 oral): conditions on explicit beat information in the form of "nearest beat distance" per frame, plus key poses and music, fused hierarchically, with a beat alignment loss. Why it mattered: it is the cleanest example of passing an audio-analysis output (a beat grid) directly into the model rather than hoping the encoder finds it. This is the pattern the author can reuse. License: unverified. Links: https://arxiv.org/abs/2407.07554 and https://zikaihuangscut.github.io/Beat-It/

### 3.9 MEGADance, NeurIPS 2025

What: genre-aware dance generation by mixture-of-experts. How: stage 1 compresses motion with Finite Scalar Quantisation; stage 2 maps music into that latent space with a Mamba-Transformer backbone whose experts are split into "universal" ones shared across genres and genre-specific ones. Claims state-of-the-art on FineDance and AIST++ (authors' claim). Code: https://github.com/XulongT/MEGADance (link from the NeurIPS listing; license not checked). Link: https://arxiv.org/abs/2505.17543

### 3.10 DanceChat (2025) and other 2025 solo models

DanceChat: an LLM acts as a stand-in choreographer, reading musical descriptors (key, tempo, chord progression, genre) and writing text instructions that condition a diffusion motion model. This is notable for the author: it uses classical music-information-retrieval features as LLM prompt. Link: https://arxiv.org/abs/2506.10574. Others from the same wave, abstracts only seen: MATHDance (2505.14222), MotionRAG-Diff (2506.02661, retrieval), FlowerDance (2511.21029, MeanFlow), TokenDance (2603.27314). All unverified beyond titles.

### 3.11 InfiniteDance, March 2026

What: scales data via an automated video-to-3D-dance pipeline (with a foot restoration diffusion model) to 100.69 h, and trains ChoreoLLaMA, a language-model-style generator, claimed to generalise to in-the-wild music. Repo (MotrixLab/InfiniteDance) is listed as under active development. License unverified. Why it matters: validates the "extract mocap from video at scale" path that GVHMR gives Homunculus. Link: https://arxiv.org/abs/2603.13375

### 3.12 Wan-Dancer, July 2026 (video, not skeleton)

What: Alibaba Tongyi Lab's minute-scale music-to-dance video generator: global keyframe planning plus local temporal refinement, up to 160 s, with LoRA customisation. Third-party pages call it Apache 2.0 and say inference was tested on 8 x A800 80 GB; the model card's code and checkpoints were still on a to-do list when seen. Relevance: it renders pixels, not a skeleton, so it cannot drive a Homunculus rig directly, and it does not fit a single 24 GB card. Only useful as a motion source if a pose estimator (GVHMR) is run on its output. Links: https://arxiv.org/abs/2607.09581 and https://huggingface.co/Wan-AI/Wan-Dancer-14B (license and hardware unverified from primary page). Similar family: MusicInfuser (2503.14505), MACE-Dance (2512.18181).

### 3.13 Group dance: AIOZ-GDANCE, TCDiff, CoheDancers, ST-GDance

**AIOZ-GDANCE (CVPR 2023)**: the dataset above plus a baseline that generates each dancer in turn with a group-aware module. Link: https://arxiv.org/abs/2303.12337.

**TCDiff (AAAI 2025) and TCDiff++ (2025)**. What: two-stage group dance. A "Dance-Trajectory Navigator" predicts non-overlapping floor trajectories for every dancer from music, with a distance-consistency loss for spacing; then a "Trajectory-Specialist Diffusion" generates each dancer's body motion conditioned on the trajectory, with a "footwork adaptor" and relative forward-kinematics loss to reduce foot sliding. TCDiff++ is end-to-end (single stage) with dancer positioning embeddings, a swap mode embedding and a long-group sampling strategy. Why it mattered: it states the group problem correctly as "layout plus per-dancer motion". Code: I could not find a public repository (verified that I could not find one; the first guess URL returned 404). Links: https://arxiv.org/abs/2403.06189 and https://arxiv.org/abs/2506.18671

**CoheDancers (Dec 2024)**. Splits group coherence into synchronisation, naturalness and fluidity, each addressed by one trick (cycle-consistency, autoregressive exposure-bias correction, adversarial training). A 167 s dance in about 47 s on an RTX A6000. Code announced, not confirmed. Link: https://arxiv.org/abs/2412.19123

**ST-GDance (BMVC 2025) and ST-GDance++ (March 2026)**. Graph convolutions for distance-aware spatial modelling and sparse attention for time; claims collision-free long group dances and, for the ++ version, streaming generation with 29.32 GFLOPs versus much heavier TCDiff++ (paper's own table). Code not confirmed. Project page: https://yilliajing.github.io/ST-GDance-Website/. Links: https://arxiv.org/abs/2507.21518 and https://arxiv.org/abs/2603.22316

Honest status: group dance generation exists only as papers with weak release status. A Homunculus user cannot `pip install` any of them today (as far as I could verify). Datasets are small and noisy.

### 3.14 Two-person interaction: InterGen, InterControl, in2IN, Duolando, newer

**InterGen** (Liang et al.; IJCV 2024). Diffusion for two-person motion from text; two denoisers with shared weights and mutual attention; relative positions encoded in a shared world frame; InterHuman dataset with 23,337 descriptions. Link: https://arxiv.org/abs/2304.05684.

**InterControl** (Wang et al., 2023). Zero-shot: treats an interaction as pairs of joints that should touch or keep a distance, then uses a single-person motion diffusion model plus a controller and works for any number of people. It is the most relevant for Homunculus because it is not limited to 2 and expresses spacing and contact as geometric constraints. Link: https://arxiv.org/abs/2311.15864.

**in2IN** (CVPR 2024 workshop). Conditions on both an overall interaction description and per-person descriptions; DualMDM mixes with a single-person prior. Link: https://arxiv.org/abs/2404.09988.

**Duolando** (ICLR 2024). Follower GPT: a VQ-VAE tokenises body parts, a GPT predicts the follower's next tokens given music, the leader's motion and its own past, and off-policy RL with human-defined rewards fixes out-of-distribution drift (e.g. penalising collisions/ contact). DD100 dataset (about 117 min). License: NTU S-Lab License 1.0 (verified on the repo); training used 8 GPUs; weights on Google Drive. The README "in the wild" section is marked TBD. Link: https://github.com/lisiyao21/Duolando

**2025-26 autoregressive multi-human**: HINT (2601.20383), MAGNet (2512.17900), ReMoGen (2604.01082), graph-driven interaction sampling (2505.17860). I saw abstracts only. They move from fixed-length, fixed-count to streaming, variable agent count. Treat as unverified beyond the titles.

### 3.15 Multi-person video capture

- **GVHMR** (SIGGRAPH Asia 2024): what Homunculus uses. Per a later paper, it handles one person (typically the largest in frame) and fails in heavy multi-person occlusion. Repo license: not read (LICENSE file not shown on the page). Checkpoint trained on 2 x RTX 4090.
- **4D Humans / HMR 2.0 + PHALP** (ICCV 2023): per-frame mesh recovery with a tracker (PHALP) that keeps identities through occlusion; camera-frame, not world frame. SMPL licensing applies. Link: https://shubham-goel.github.io/4dhumans/ (license unverified).
- **TRAM**: world-coordinate multi-person capable (per Human3R paper). Link not verified here; search "TRAM global trajectory and motion of 3D humans".
- **PromptHMR / PromptHMR-Vid** (CVPR 2025): promptable by boxes, masks or text (including interaction labels); video version integrates metric SLAM and depth, giving world-coordinate multi-person motion. Reported W-MPJPE 71.0 mm on EMDB-2 in one summary (secondary source). Link: https://openaccess.thecvf.com/content/CVPR2025/html/Wang_PromptHMR_Promptable_Human_Mesh_Recovery_CVPR_2025_paper.html
- **Human3R** (arXiv Oct 2025, ICLR 2026): one forward pass gives global multi-person SMPL-X bodies, scene geometry and camera trajectory; built on CUT3R, trained on BEDLAM in about a day on one GPU; reported 15 FPS and 8 GB. Code and checkpoint (`human3r_896L.pth`) exist on GitHub; license file not read. Output format not documented on the page. For a 24 GB ROCm GPU the memory is fine; the dependency stack (CUDA-era) is the risk. Link: https://github.com/fanegg/Human3R and https://arxiv.org/abs/2510.06219

Practical issues for dance videos: dancers cross and occlude each other, identities swap (ID switches break a per-person trajectory), identical costumes confuse re-identification, floor contact in a moving-camera shot needs world-frame estimation, and each person's SMPL body has its own shape (beta), so retargeting must be done per person.

### 3.16 Crowd simulation and formations (classical, cheap)

- **Boids** (Reynolds, 1986): separation, alignment, cohesion rules. Good for loose flocks, bad for rigid formations.
- **ORCA / RVO2** (UNC GAMMA): each agent computes velocity constraints as half-planes against neighbours and solves a small linear program; fast and smooth for hundreds of agents; local avoidance only, global path planning is yours. Apache 2.0 since v2.0.2 (verified). Link: https://gamma.cs.unc.edu/RVO2/. Python bindings exist (`rvo2`, unverified version).
- **Massive-style** (Weta; Lord of the Rings): agent brains with motion-clip libraries, blend-trees chosen by a fuzzy-logic brain. Commercial; the idea (per-agent state machine picking clips) is the part worth borrowing. Unverified details.
- **Formation planning**: assign dancers to target slots with the Hungarian algorithm, move them with ORCA or straight-line paths timed to the beat, and treat formation changes as transitions between keyframes at bar boundaries. This is how group choreography is annotated by humans ("counts of eight", floor charts).

### 3.17 Scene representation and tools

- **glTF 2.0**: scenes may contain several skins and several animations; each character is a node tree with a skin. Two characters sharing the same Mixamo skeleton can reuse animation clips by joint name. Common pitfalls (from three.js forum): Blender's glTF exporter needs NLA tracks to export multiple actions; clip names follow NLA track names; multi-material characters become several skinned meshes. three.js supports this directly (AnimationMixer per character, `SkeletonUtils.clone` for copies).
- **OpenUSD / UsdSkel**: designed for crowds; the bind state of a skeleton can be instanced and each instance gets its own SkelAnimation, with the constraint that animation prims cannot be children of an instanced prim and must be referenced through the skeleton's animation source (verified in the OpenUSD docs). Heavier toolchain, but the right target if the scene goes to Omniverse or Houdini.
- **Blender**: Python scripting and NLA strips make "N characters, shifted clips" trivial; Homunculus already uses it for rendering (`tools/render_dance.py`), so the lowest-risk multi-character output is a Blender scene built by script.
- **Unreal MetaHuman, Unity**: both provide crowd and retargeting systems (Unreal IK Retargeter, Unity Humanoid), but they need a Mixamo-skeleton-to-engine-rig step, and MetaHuman has its own licence terms (not checked here). Not necessary for a first version.
- **Collision and penetration**: skeleton-level checks (capsule or joint-distance) are cheap and enough to prevent dancers walking through each other; mesh-level interpenetration (arms inside another body) needs mesh collision or SDF queries. Lodge++'s "penetration guidance" is single-body self-penetration; TCDiff's distance-consistency loss and Duolando's RL contact reward are the group analogues. Foot sliding and floor contact: all characters must share one floor plane and one up axis; unify units (metres) and root height per character since Mixamo rigs differ in scale.
- **Camera**: with several characters the camera must frame a bounding box of all of them; a spline or look-at target at the group centroid, with dolly speed tied to the beat or section changes, is enough. This is where audio features again help (cut on downbeats).

### 3.18 Audio-driven animation beyond dance

- **TalkSHOW** (CVPR 2023): speech to face (FLAME) and body+hands (SMPL-X); face autoencoder, compositional VQ-VAE for body and hands, cross-conditional autoregressive model. Code under the Max Planck project; license (MPI non-commercial, I believe) unverified. https://arxiv.org/abs/2212.04420
- **EMAGE + BEAT2** (CVPR 2024): masked audio-gesture transformer; full body and face from audio, with the BEAT2 SMPL-X + FLAME dataset. https://arxiv.org/abs/2401.00374. SemTalk's comparison notes jitter in EMAGE legs and shoulders.
- **DiffSHEG** (CVPR 2024): diffusion, face-to-gesture one-way flow, outpainting for long sequences, real-time claim. https://arxiv.org/abs/2401.04747
- **LivelySpeaker** (ICCV 2023): I could not confirm details in this session. Unverified.
- **Audio2Face-3D** (NVIDIA): audio to blendshape/face animation; models released on Hugging Face (v3.0, Aug 2025) under the NVIDIA Open Model License; SDK reported MIT and Unreal/Maya plugins MIT (secondary source); the NIM container has different terms. https://huggingface.co/nvidia/Audio2Face-3D-v3.0
- **EMO / Wan2.2-S2V**: EMO (Alibaba 2024) animates a portrait from audio in pixels (not open at launch). Wan2.2-S2V (Aug 2025) is the open, 14B version (Apache 2.0 per a hosting page; unverified), so it exceeds a 24 GB card without offload or quantisation.
- **Link to Homunculus**: Mixamo skeleton has no face blendshapes in the default pipeline. Lip-sync would need ARKit-style blendshapes on the face, which the auto-rig step does not produce today. Co-speech gesture could target the 52-bone skeleton directly (upper body + fingers) via SMPL-X to Mixamo retargeting.

### 3.19 Audio encoders that matter for the author

- **Jukebox** (OpenAI, 2020): a generative music model whose internal activations are strong features; used by EDGE. Large and slow.
- **MERT** (m-a-p, ICLR 2024): self-supervised music encoder, 95M-330M parameters, 16 kHz in, 50 Hz features, trained with an RVQ-VAE acoustic teacher and a CQT musical teacher. The musical CQT teacher is a nice nod to pitch/harmony. License: conflicting; one aggregator lists CC-BY-NC-4.0 for the FullSong variant. Check the model card before use. https://arxiv.org/abs/2306.00107
- **Wav2CLIP**: I did not verify it this session; the idea (distil CLIP's audio-visual alignment into an audio encoder) is from memory and unverified.
- **Speech models for music**: Whisper/wav2vec 2.0 encoders are not designed for music; the author's instinct that speech SSL features carry rhythm but little harmony is probably right but untested here.

---

## 4. What this means for Homunculus

Setting: every Homunculus character already has the same 52-bone Mixamo skeleton, so clips are interchangeable between characters. This is the single strongest enabler; it is why the cheap designs below work.

### Design A (lowest effort, days): N characters, same or different Mixamo/UniMate clips, with offsets

How: add a scene builder (Blender Python, or a three.js page) that loads N rigged characters, assigns each a clip (the same one, or a pool of clips already produced), a start time offset, and a floor position and facing from a formation preset (line, circle, V, staggered rows). Beat-lock: detect beats once in the song, and quantise the start offset and any speed scaling to bar boundaries. Add canon / mirror / unison variants (canon = each dancer delayed by k beats; mirror = negative x scale of the clip, careful with the skeleton's left/right naming). Add a simple ORCA or spacing rule only if formations move. Collision: ignore, since dancers stay in their slots.
Why first: it answers open decision O-4 with "one clip per character composited into one scene", requires no new model, and is already how stage group dance is often staged (unison, canon, formation changes).
Risks: all dancers look identical in timing (robotic), root drift in clips (fix by using in-place root and driving the root with the formation path), differing character heights.
Audio-side work the author could own: beat and downbeat tracking, section (verse/chorus) segmentation to schedule formation changes, and a "beat-lock" tool that snaps clip phase to the beat grid (time-warp the clip so its own motion beats land on music beats; this is dynamic time warping between two onset-strength curves, a familiar problem).

### Design B (medium effort, 1-3 weeks): N dancers extracted from one multi-person video

How: replace or complement GVHMR with a multi-person world-frame estimator (Human3R for one-pass; PromptHMR-Vid or TRAM with PHALP-style tracking for stronger tracking), producing one SMPL-X sequence per tracked person plus one shared world frame; run the existing smpl_to_bvh retarget per person onto each character's rig; place all characters in one scene using the estimated world positions (scaled to the characters). Needs: identity QC (a UI step where the author confirms which track is which dancer and fixes ID switches), per-person shape handling, occlusion repair (interpolate low-confidence segments), and a contact-based foot-lock pass.
Why: it gives real, human choreography, with real relative spacing and interaction, and the dataset needed for Design C. The same pipeline is how InfiniteDance built its 100 h set.
Risks: ID switches in crowded or costumed dancers, depth ambiguity between people, ROCm compatibility of CUT3R-based stacks (unverified; Human3R repo does not state requirements), SMPL licence for any redistribution.
Audio-side work: align each person's motion to the song (cross-correlation of motion energy with onset strength to find the video's audio offset); extract the music for the clip with source separation if the video is noisy; compute beat consistency between dancers as a group sync score (a good QC metric).

### Design C (highest effort, months, research-grade): music-driven generation per dancer with formation constraints

How: two layers. Layer 1, layout: a formation planner (hand-authored charts or a small learned model) produces per-dancer floor trajectories timed to the music structure, with ORCA-style collision avoidance. Layer 2, motion: a conditional generator per dancer (EDGE or MEGADance as the base; EDGE has an MIT license and clear inpainting for constraints) conditioned on music features and on that dancer's trajectory (as TCDiff does) and, optionally, on the neighbour's motion (as Duolando does for follower). Training data would be AIST++/FineDance/PopDanceSet for solo, AIOZ-GDANCE and DD100 for group; swap in Homunculus-extracted data from Design B. Evaluate with collision rate, beat consistency, and group sync, plus a small human study.
Why: it is the only design that produces new choreography from a new song. Reality check: no group-dance model with public code and a permissive licence was found (TCDiff, CoheDancers, ST-GDance: code not confirmed), and the available solo models were mostly built on CUDA-era toolchains (EDGE states CUDA 11.6, Python 3.7) and trained on non-commercial data. Start with solo generation per dancer plus differing seeds and an offset trajectory layer, rather than a joint group model.
Audio-side work the author could own: this is where most of the value is. (1) a clean music front-end: beat/downbeat/tempo, phrase boundaries, onset strength, and mel/chroma features, exported as a conditioning file; (2) swap the encoder (Jukebox vs MERT vs a mel-spectrogram baseline) and ablate; (3) a better beat-alignment and group-synchronisation metric; (4) speech/music overlap: dance to singing voice with separation (vocals drive gestures, drums drive footwork) is an open idea; (5) time-stretch robustness: does the dance follow when the same song is played at 90 percent speed.

### Ranking and recommendation

Order of effort: A < B < C. Recommend A first (it makes the "multiple characters" goal visible quickly and settles O-4), then B (turns the existing video-to-dance strength into group capture), then C only as a research branch led by the author's audio skills. A is also the baseline that C must beat.

### Other audio-side options beyond dance

- Co-speech gestures and lip-sync as a second product line (Section 3.18). The author's expertise (speech features, alignment, prosody) transfers more directly here than in dance, where audio is one weak conditioning signal; but it needs a face rig that Homunculus does not yet produce.
- A shared "audio timeline" artifact: one JSON per song or voice track (beats, downbeats, sections, onsets, optionally speech phones) that every downstream tool (scene builder, camera, generator) reads.

---

## 5. Open problems

1. No reliable metric for dance quality or for group coherence; FID_k and BAS can be gamed by jitter. A tempo/phase-aware beat metric and a group-sync metric are needed.
2. Group data is scarce, short and noisy (AIOZ-GDANCE 16.7 h from video; I-Dancers 3.8 h; DD100 duets 117 min).
3. Public code and usable licences for group-dance models: unconfirmed for TCDiff, CoheDancers, ST-GDance/++. S-Lab and many academic licences forbid commercial use.
4. Long-range structure: choreography follows musical sections (verse, chorus, drop); most models only see a window and do not plan form.
5. Physical plausibility between dancers: contact, lifts, partner dance, mesh-level penetration.
6. Identity and occlusion in multi-person capture; world-frame consistency with moving cameras.
7. Stylised characters: all these models assume human proportions (SMPL); a cartoon character with big head or short legs needs retargeting that keeps contacts and silhouette (this links to Homunculus's existing retarget work).
8. Real-time and streaming group generation (ST-GDance++ and HINT point this way).
9. Dance-to-music alignment for non-beat-driven genres (rubato, polyrhythm, voice-led songs) where beat tracking itself fails.
10. ROCm: almost every repo here targets CUDA with old PyTorch versions; porting cost is real and unmeasured.

---

## 6. Sources

Dance and music
- FACT / AIST++: https://arxiv.org/abs/2101.08779 , https://google.github.io/aichoreographer/
- Bailando: https://arxiv.org/abs/2203.13055 , https://github.com/lisiyao21/bailando
- EDGE: https://arxiv.org/abs/2211.10658 , https://github.com/Stanford-TML/EDGE
- FineDance: https://arxiv.org/abs/2212.03741 , https://github.com/THUSIGSICLAB/FineDance
- TM2D: https://arxiv.org/abs/2304.02419
- Lodge: https://arxiv.org/abs/2403.10518 ; Lodge++: https://arxiv.org/abs/2410.20389
- POPDG: https://arxiv.org/abs/2405.03178 , https://github.com/Luke-Luo1/POPDG
- Beat-It: https://arxiv.org/abs/2407.07554
- MEGADance: https://arxiv.org/abs/2505.17543 , https://github.com/XulongT/MEGADance
- DanceChat: https://arxiv.org/abs/2506.10574
- MATHDance: https://arxiv.org/abs/2505.14222 ; MotionRAG-Diff: https://arxiv.org/abs/2506.02661
- MusicInfuser: https://arxiv.org/abs/2503.14505 ; ChoreoMuse: https://arxiv.org/abs/2507.19836 ; MACE-Dance: https://arxiv.org/abs/2512.18181
- InfiniteDance: https://arxiv.org/abs/2603.13375
- Wan-Dancer: https://arxiv.org/abs/2607.09581 , https://huggingface.co/Wan-AI/Wan-Dancer-14B
- Metric critiques: Skeleton2Stage https://arxiv.org/abs/2602.13778 ; ConvoFusion https://arxiv.org/abs/2403.17936 ; Controllable dance with style-guided diffusion https://arxiv.org/abs/2406.07871 ; MDSC https://arxiv.org/abs/2309.01340

Group and interaction
- AIOZ-GDANCE: https://arxiv.org/abs/2303.12337 , https://aioz-ai.github.io/AIOZ-GDANCE/
- TCDiff: https://arxiv.org/abs/2403.06189 ; TCDiff++: https://arxiv.org/abs/2506.18671
- CoheDancers: https://arxiv.org/abs/2412.19123
- ST-GDance: https://arxiv.org/abs/2507.21518 ; ST-GDance++: https://arxiv.org/abs/2603.22316
- InterGen: https://arxiv.org/abs/2304.05684 ; InterControl: https://arxiv.org/abs/2311.15864 ; in2IN: https://arxiv.org/abs/2404.09988
- Duolando: https://arxiv.org/abs/2403.18811 , https://github.com/lisiyao21/Duolando
- HINT: https://arxiv.org/abs/2601.20383 ; MAGNet: https://arxiv.org/abs/2512.17900 ; ReMoGen: https://arxiv.org/abs/2604.01082 ; graph-driven sampling: https://arxiv.org/abs/2505.17860

Capture
- GVHMR: https://github.com/zju3dv/GVHMR ; https://arxiv.org/abs/2409.06662
- PromptHMR: https://openaccess.thecvf.com/content/CVPR2025/html/Wang_PromptHMR_Promptable_Human_Mesh_Recovery_CVPR_2025_paper.html
- Human3R: https://arxiv.org/abs/2510.06219 , https://github.com/fanegg/Human3R
- 4D Humans: https://arxiv.org/abs/2305.20091

Crowds and scenes
- RVO2/ORCA: https://gamma.cs.unc.edu/RVO2/
- UsdSkel instancing: https://openusd.org/dev/api/_usd_skel__instancing.html
- three.js forum on separate glTF models and animations: https://discourse.threejs.org/t/recommended-setup-for-separate-gltf-models-and-animations/22066

Audio-driven animation
- TalkSHOW: https://arxiv.org/abs/2212.04420
- EMAGE: https://arxiv.org/abs/2401.00374 ; DiffSHEG: https://arxiv.org/abs/2401.04747 ; SemTalk comparison: https://arxiv.org/abs/2412.16563
- Audio2Face-3D: https://huggingface.co/nvidia/Audio2Face-3D-v3.0
- EMO: https://arxiv.org/abs/2402.17485 ; Wan2.2-S2V (Aug 2025, third-party pages only)
- MERT: https://arxiv.org/abs/2306.00107

Not verified in this session: LivelySpeaker details, Wav2CLIP, Massive internals, TRAM link, licenses for FACT/AIST++, Lodge, POPDG, MEGADance, TalkSHOW, MERT, Human3R, GVHMR; TCDiff/CoheDancers/ST-GDance code.
