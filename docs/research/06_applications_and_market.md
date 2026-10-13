# 06 - Applications, users, market and competition

*Researcher 6 of 6. Written 2026-10-13. Scope: who could genuinely use "picture -> rigged animated character" and "video -> character motion", what they pay for today, who already sells it, what the licences allow, and what this author (a junior audio and speech engineer) should try first.*

**How to read the evidence.** I searched the web and, where I could, opened primary sources (GitHub LICENSE files, Hugging Face model cards, vendor docs). Many pricing and market numbers only came from aggregator or coupon sites that disagree with each other; those are labelled **(unverified)**. Nothing here is legal advice. Where a source conflicted with another, I say so rather than pick one.

---

## 1. Executive summary

1. **The core 3D-from-picture market is real but already owned by well-funded cloud companies.** Meshy reported (secondary sources) a ~$400M Series B in July 2026 at a reported ~$1.5B valuation and >$100M ARR; VAST (Tripo) reported ~$446M of Series B/B+ in September 2026. Meshy rigging and animation clips cost 0 credits on its official pricing page. A local clone of "picture -> rigged GLB" will not win on price or convenience.
2. **Homunculus's real edge is different: local, private, controllable, end-to-end with a standard skeleton, plus video-to-motion.** Nobody in the paid tools gives you "this specific character, dancing this specific video, rendered on your machine, with no upload". That matters to hobbyists, IP-sensitive studios and researchers, not to the mass market.
3. **Commercial use is currently blocked by the licence chain.** GVHMR's repo licence is a custom "research, education and non-profit only" licence, and SMPL/SMPL-X are non-commercial (commercial licences from Meshcapade start at a listed EUR 1,500/year for the Micro tier, **unverified as current**). Worse, the README's image model, Qwen-Image 2.1 Turbo, ships under the **Qwen Research License** (model card tag `qwen-research`), so it is also non-commercial by default. Hobby, research and portfolio use is fine; selling output or a service is not, until swaps are made.
4. **Several swaps are cheap.** The original Qwen-Image is Apache 2.0, Qwen3-VL-32B is Apache 2.0, UniMate's code and Make-It-Animatable's code are MIT, Pixal3D's README says MIT (two secondary sources claim academic-only; check the NOTICE and upstream licences before relying on it). The hard blockers are the SMPL-based video-to-motion path and any model trained on non-commercial data (unverified for each).
5. **Best-fit applications are the ones where hobby-grade quality is enough and privacy or ownership matters:** previs and music-video experiments, VTuber/VRChat avatars, dance learning, and research data for humanoid robots. Worst fits: anything needing production-grade topology, faces, or legal certainty about IP.
6. **Ready Player Me is gone.** Netflix acquired it in December 2025 and the public service was set to close on 31 January 2026 (secondary reports; terms undisclosed). That leaves a visible gap in "cross-game avatar" tooling, but it is a warning about platform risk, not a market to chase.
7. **Mixamo, which the whole project leans on for its skeleton and clips, is alive but in maintenance mode** (third-party guides, Sept 2026; no official shutdown notice found). Its terms allow commercial use of characters and animations in finished products. This is a dependency risk worth hedging.
8. **Audio and speech is the author's unfair advantage, and the competition there is thin on the *local + rigged + beat-aware* corner.** Music-synced group choreography previs and speech-driven gestures on a user's own character are the two places where audio skill converts directly into product value.
9. **Group choreography is a research-grade, not product-grade, area.** Public multi-dancer data is small (AIOZ-GDANCE: 16.7 hours, 2023) and solo datasets (AIST++, FineDance) have unclear licences. A realistic plan composes several solo copies of the same video or beat-aligned variations rather than learning true group dynamics.
10. **Recommended first move:** a two-week "beat-synced multi-character dance previs" experiment (opportunity 1 below), because it uses the audio edge, needs only hobby-grade quality, and is exactly the roadmap's "several characters in one scene" goal.

---

## 2. Application map

Verdict key: **promising** (clear user, pain, feasible), **niche** (real but small), **crowded** (strong incumbents), **weak** (poor fit). "Local matters" = does a private offline pipeline change the buying decision. "Quality bar" = hobby / prosumer / production.

| Application | Who | Pain solved | What they pay today | Local matters? | Quality bar | Verdict |
|---|---|---|---|---|---|---|
| Indie / mobile game prototyping and asset pipelines | solo devs, jam teams | placeholder characters fast | Meshy/Tripo/Rodin subs (~$16-120/mo, unverified), Mixamo free | Medium (IP, no per-credit cost) | prototype = hobby; ship = production | **crowded**, niche for private/IP-sensitive teams |
| VTubing and avatars (VRM, VRChat) | streamers, VRChat creators | a custom avatar from your own art | commissions: 3D VRM roughly $300-$10,000+ (one vendor's survey, unverified); VRoid free | High (own art stays private) | prosumer (faces, blendshapes needed) | **promising** if VRM export + face blendshapes are solved |
| Live2D vs 3D | same | 2D rigs cheaper, 3D for events | Live2D rigs ~$200-$5,000+ (unverified) | n/a | n/a | not our area; 3D wins only for events and VR |
| Social / AR filters | creators, brands | a character that dances in a filter | Lens Studio/Spark are free; asset commissions | Low | low-poly, tight budgets | **weak** (platform size and poly limits) |
| Previs and animation for film, ads, YouTube | indie filmmakers, YouTubers, agencies | cheap stand-in animation, motion from reference | Autodesk Flow Studio $10/$45/$95 per month (reported, Aug 2025 tiers), Move AI, Rokoko, DeepMotion | Medium to High for unreleased IP | hobby to prosumer for previs | **crowded** at the top; **niche** for offline, any-character |
| Education / kids' drawing-to-animation | teachers, parents, children | magic of seeing your drawing move | Meta Animated Drawings is free and open source (2D) | High (children's drawings, privacy) | hobby | **niche**; 3D adds wow but not a paying market |
| Mascot / brand characters | small brands, agencies | consistent character in many poses and media | agency work, Kaedim-style services | High (brand IP) | production | **weak** today (consistency and topology not good enough), possible later |
| E-commerce / virtual try-on | retailers | garment on body | specialised SaaS | n/a | production | **weak**: different problem (cloth, body shape); not recommended |
| Digital twins, humanoid robotics, sim | robot-learning researchers | cheap human motion data retargeted to robots | open source (GMR, TRAM, GVHMR) plus lab time | High (research) | hobby / research | **promising** as a niche; does not need the character half |
| Accessibility: sign-language avatars | Deaf community, broadcasters | sign output for text/speech | research projects, a few vendors (unverified) | Medium | very high accuracy needed | **weak** for this pipeline (needs hand and face linguistics, community trust) |
| Fitness and dance learning | learners, teachers | compare my motion to a reference | consumer apps (Move Mirror AI, LeapNow, Dance Helper: store listings) | High (video of your body) | pose accuracy, not mesh quality | **crowded but shallow**; audio-aware timing is an open angle |
| Choreography previs, stage and live events | choreographers, event designers | see a group routine before rehearsing | bespoke 3D work, existing previs studios | High | prosumer | **promising niche**; matches the roadmap |
| Music videos | musicians, small labels | animated performer without mocap | commissions, Viggle-style tools (price unverified) | Medium | prosumer | **promising** for hobby-grade creators |
| Audio-driven avatars (co-speech gesture, assistants) | podcasters, game NPCs, assistants | gestures that match speech | mostly research (EMAGE etc.) plus cloud avatar vendors | High | hobby to prosumer | **promising** and the author's edge |

---

## 3. Application areas in more detail

### 3.1 Indie and mobile game prototyping, asset pipelines

*User.* A solo developer or jam team that needs a few characters with animations, fast. *Pain.* Placeholder art blocks gameplay iteration. *Today.* They use Meshy, Tripo or Rodin (monthly credits), Mixamo (free) and Blender. Meshy's official docs list Free, Pro, Studio and Enterprise tiers with rigging and animation clips at 0 credits each, image-to-3D at roughly 20-25 credits, and free-tier output licensed CC BY 4.0, with paid plans giving full commercial use. Exact monthly prices conflict between sources ($16-$20 Pro, $48-$60 higher tiers, a sixth plan added July 2026); treat as unverified.

*Does local matter?* Somewhat: no per-generation fees, and nothing is uploaded. But game developers mostly care about speed and topology, and the cloud tools win both. Storefront policy is another wrinkle: Epic's Fab requires an AI-generated tag for content with a material AI-generated portion, and Unity's Asset Store requires disclosure; Steam disclosure rules were only found in a legal blog (unverified).

*Quality bar.* Prototype grade is enough for jams; for shipping, 250k-vertex meshes with generated textures and Mixamo-style rigs need cleanup (Homunculus's own pain-points file documents torn hands and fused fingers).

*Verdict.* **Crowded.** Homunculus will not beat Meshy at "fast cheap asset". It could win only as a free, private, hackable workflow for people already in Blender.

### 3.2 VTubing and avatars

*User.* A streamer or VRChat creator who wants an avatar from their own concept art. *Pain.* VRoid Studio is free but anime-template-bound; custom models are commissioned. One vendor-sourced survey lists 3D VRM commissions at about $300-$800 (basic) to $3,000-$10,000+ (pro), and a Mordor-sourced VTuber market figure of $3.13B for 2026; both **unverified** and from parties selling to this audience.

*Format facts.* VRM (built on glTF 2.0) is the dominant 3D VTuber format; VRoid exports VRM 1.0; VSeeFace only reads VRM 0.x while Warudo reads both; VRChat uses its own .vrca via Unity, so VRM needs a community converter. Live2D is the 2D standard and cheaper; 3D is preferred for concerts and VR.

*What is missing from Homunculus.* Face blendshapes (visemes, blink, expressions), spring bones for hair/cloth, and a humanoid-bone mapping. The 52-bone Mixamo skeleton maps naturally to the VRM humanoid spec, so a VRM exporter is realistic; blendshapes are the hard part, and they are also where speech-driven lip-sync (audio edge) plugs in.

*Ready Player Me's fate.* Netflix acquired Ready Player Me in December 2025 (terms undisclosed); services including the avatar creator and SDK were to close on 31 January 2026, with about 20 staff joining Netflix (secondary reports, not primary). Lesson: hosted avatar platforms are fragile; a local exporter that produces VRM files you keep is a defensible niche.

*Verdict.* **Promising**, conditional on VRM export and face rigging. Hobby-grade is enough for the VRChat/indie crowd, who accept rough models; the hardest customers will compare against hand-made models.

### 3.3 Social and AR filters

Lens Studio and Spark AR-style platforms demand tiny, low-poly assets with strict file limits and focus on face tracking, not full-body dance. The pipeline's 250k-vertex meshes would need heavy decimation and bake. **Weak.**

### 3.4 Previs and animation for film, ads and YouTube

*Incumbents.* Autodesk Flow Studio (formerly Wonder Studio, from Wonder Dynamics) replaces a live-action actor with a CG character in footage, now freemium: Free, Lite $10, Standard $45, Pro $95 per month per an August 2025 press release and an aggregator (current 2026 rate card unverified on Autodesk's own site). DeepMotion (reported from $9/month, annual), Rokoko (software free, paid tiers ~$20-$50/month, unverified), Move AI (pricing not disclosed in sources), Plask (no pricing found), Cascadeur (physics-aware keyframe tool; free tier is non-commercial; paid tiers reported at $99-$399/year or $19-$49/month, sources conflict) and Viggle (pricing aggregator-only, $9.99-$79.99, unverified) all attack "video -> motion".

*Where Homunculus differs.* Those tools take *your video* and output motion or a rendered clip; most accept a character you supply, but none generate that character from one picture and run offline. For previs the quality bar is low, so hobby-grade works. The honest limitation: Flow Studio and Viggle composite into live video with lighting; Homunculus outputs a rigged mesh you render yourself.

*Verdict.* **Crowded** at the cloud/video end; **niche** for offline, any-character previs where the footage or the character is confidential.

### 3.5 Education and kids' drawing-to-animation

Meta's Animated Drawings (April 2023) turned children's drawings into 2D animations from preset motions and open-sourced the models, code and a dataset of about 180,000 annotated amateur drawings (Meta developer blog; licence and recent activity not confirmed). The audience is parents and teachers; payment is near zero. 3D dancing from a drawing is a stronger "wow", and privacy (children's drawings, no upload) is a real selling point. But monetisation is poor and compute needs (24 GB GPU, minutes per character) fit a classroom badly. **Niche, charm-driven.**

### 3.6 Mascot and brand characters

Brands need *consistency* across poses, media and years, and clean topology. Today's image-to-3D output is one-shot; Kaedim (reported $16.5M raised; pricing figures unverified) sells human-in-the-loop quality for exactly this reason. Hobby-grade is not enough. **Weak now; revisit** if repair and retexture tools mature.

### 3.7 E-commerce and virtual try-on

Try-on is about garment simulation on a user's body shape; it is not what this pipeline does. **Weak, skip.**

### 3.8 Digital twins, humanoid robotics and simulation

*Opportunity.* Robot-learning labs need human motion retargeted to robot kinematics. The standard chain is video -> SMPL (GVHMR or TRAM) -> retargeting (GMR, "Retargeting Matters", arXiv 2510.02252) -> RL tracking policy on e.g. a Unitree G1 (search results from 2026 papers; I did not open each). A March 2026 paper (NMR) argues optimisation-based retargeting can hit local optima and proposes a neural retargeter trained on ~30,000 physics-refined motions. Homunculus already has the first step (GVHMR video to SMPL to BVH) and a retargeting layer to Mixamo.

*Does local matter?* Yes: research labs run offline on their own GPUs. *Quality.* Research quality only needs correct kinematics and no foot sliding. *Catch.* The character half (picture -> mesh) is irrelevant here; and this is a crowded academic area. For a newcomer the value is learning and a small, honest "video to G1 reference motion" tool; not a business. **Promising as a niche, weak for the audio edge.**

### 3.9 Accessibility: sign-language avatars

Patents and research projects exist (generating avatars that sign spoken dialogue; real-time speech-to-sign work from AAU, 2025). I found no evidence about Deaf community acceptance in my search, and that is a known concern in this field (accuracy, grammar and facial non-manual signals): **unverified here, but anyone entering must work with Deaf linguists.** Sign languages need precise finger and face articulation that a Mixamo skeleton plus an image-derived mesh cannot yet guarantee. **Weak for this pipeline, high stakes if attempted.**

### 3.10 Fitness and dance learning

Consumer apps already do reference-vs-learner comparison: Move Mirror AI (side-by-side with skeleton overlay and per-body-part scores), LeapNow (adds beat/timing analysis and 8-count splitting), Dance Helper (on-device processing), per App Store listings (vendor claims, unverified); Dance Demy was reported inactive since November 2023. A Stanford CS231N project used pose estimation plus Dynamic Time Warping to align learner and reference, noting that rigid frame-by-frame comparison fails with timing and move-order differences.

*Where an audio engineer adds value.* Alignment to the *music* (beat grid, downbeats, 8-counts) rather than to a frame index, and tempo-robust DTW. Homunculus adds a nicer reference: the learner sees the move on *a character they chose*, in 3D, from any angle. *Privacy:* video of your body staying local is a real point. **Crowded but shallow; promising as an audio-aware twist.** Output quality is not a constraint here; pose accuracy is.

### 3.11 Choreography previsualisation and live events

*User.* A choreographer, school dance team, wedding or event planner, or a small production laying out a group routine before renting a studio. *Pain.* Formation and timing problems are discovered at rehearsal. *Today.* Spreadsheets, stick-figure software, or bespoke 3D work (prices unverified). *Why Homunculus.* Multiple characters (the roadmap's top open item) each performing a copied or generated routine on a stage, with camera moves, rendered locally. *Quality bar.* Prosumer: needs correct timing and spacing, not beautiful meshes. **Promising niche.** Data caveat: AIOZ-GDANCE (2023) is the main public group-dance set I found (16.7 hours, 7 styles, 16 genres) and FineDance/AIST++ are solo; their licences were not confirmed. A practical product does not need learned group dynamics: duplicate and offset a captured dance, time-shift for canon effects, assign roles, and snap to beats.

### 3.12 Music videos

Independent musicians want an animated performer without mocap rigs. Homunculus already produced a 2-minute Miles Jackson showcase with Mixamo's Thriller clips and cut-to-music rendering. Hobby-grade suffices. The audio angle: automatic beat/section-aware cuts and gesture accents. **Promising for DIY creators**, though the market is "free or cheap" so revenue is unlikely; the payoff is portfolio and community.

### 3.13 Audio-driven avatars (the author's edge)

Co-speech gesture generation (e.g. EMAGE, CVPR 2024, with the BEAT2 SMPL-X + FLAME dataset; code licence unconfirmed, dataset and body models carry their own terms) is academic and uses SMPL-X, so it inherits the SMPL licence problem commercially. I found no 2026 update in my searches. The product shape: a character (from a picture) that speaks a TTS or recorded narration with lip-sync visemes, head nods and beat gestures, exported as VRM/GLB or rendered. Users: podcasters turned video-creators, game NPC authors, educators, assistant builders. Competition: hosted talking-avatar services (not researched here; unverified). The edge is real: phoneme timing, prosody features (pitch/energy/pauses) as gesture drivers, and speech-to-lip-sync are standard audio skills, and a local pipeline means voices stay private. **Promising; best skills-to-market match.**

---

## 4. Competitive landscape and licences

### 4.1 Products

| Product | What it does | Funding / state (as reported) | Pricing (verification) |
|---|---|---|---|
| **Meshy** | text/image to 3D, texturing, remesh, auto-rig, animation clips | Series B ~$400M, Jul 2026, valuation reported ~$1.5B (one Dealroom piece says ~$970.6M); ARR reported >$100M (company claim relayed by Dealroom; conflicting analyses). Secondary sources | Official docs: Free 100 credits/month, CC BY 4.0 on free; paid plans commercial; rigging/animation 0 credits. Plan prices conflict across sources (unverified) |
| **Tripo (VAST)** | image/text to 3D, rigging (v2.5 per Scenario's guide, incl. non-humanoid) | ~3B yuan (~$446M) Series B/B+ reported Sept 2026; ~5B yuan in under six months; HK IPO considered (secondary) | Free 300 credits/month; paid ~$15.9-$111.9 or ~$23-$130 depending on source (unverified) |
| **Rodin / Hyper3D (Deemos)** | image to 3D (Gen-2.5 per June 2026 report) | new round of hundreds of millions of yuan, June 2026 (Yicai) | Creator ~$24/mo, Business ~$120 (aggregator; unverified) |
| **Kaedim** | image to production-ready 3D with human QA | $16.5M raised, Series A March 2024 (aggregator, unverified) | $50-$1,200/month (aggregator, unverified) |
| **Scenario** | game-asset AI platform that resells models (Tripo, Rodin) | not researched (unverified) | not researched |
| **Luma** | not researched in this pass | unverified | unverified |
| **Autodesk Flow Studio (ex Wonder Dynamics)** | video: replace actor with CG character, mocap, 3D asset generation (20 credits per generation, aggregator) | Autodesk product | Free $0, Lite $10, Standard $45, Pro $95 / month (Autodesk press release Aug 2025; 2026 unchanged per aggregator) |
| **Mixamo (Adobe)** | free web auto-rig + animation library | working, in maintenance mode per third-party guides (Sept 2026); Blender add-on no longer supported; no official discontinuation found; a ~1h outage Jul 2026 and a multi-day outage June 2025 reported | free with Adobe account; Adobe FAQ (relayed): commercial use of characters/animations OK inside a finished product, no resale of raw files |
| **Cascadeur** | physics-assisted keyframe animation | Nekki | free non-commercial tier (.casc export only); paid prices conflict (unverified) |
| **DeepMotion, Rokoko, Move AI, Plask, Viggle** | video to motion / mocap | not researched | all aggregator-only (unverified) |
| **Ready Player Me** | cross-game avatars | acquired by Netflix Dec 2025; public service shutting 31 Jan 2026 | n/a |
| **Meta Animated Drawings** | 2D drawing animation, open source | released Apr 2023 | free |
| **Sorceress, Tripo rigging, Rigel3D, RigMo, GenRA, AniGen** | emerging in-browser rigging and research for animation-ready generation | research and vendor blogs, Jan-2026 papers | unverified |

*Open-source end-to-end projects.* I did not find a project that does picture -> textured rigged character -> video-copied animation entirely locally. Research prototypes address pieces (RigAnything, Rigel3D, AniGen: animation-ready generation; GVHMR/TRAM/WHAM: video motion). Homunculus's distinctive combination is plausible, but I only searched briefly; **treat "no direct open-source competitor" as likely, not proven.**

### 4.2 Licences of what Homunculus depends on

| Component | Role | Licence found | Source quality | Commercial implication |
|---|---|---|---|---|
| **GVHMR** (zju3dv) | video to SMPL motion | custom ZJU 3D Vision Group licence: research, education, non-profit only; modifications must stay open and non-commercial; commercial use by email request | primary: repo LICENSE file | **Blocks commercial use** of the video-dance path unless Zhejiang University grants permission |
| **SMPL / SMPL-X** | body model behind GVHMR | non-commercial research (incl. non-commercial artistic projects); commercial via Meshcapade; Micro EUR 1,500/yr, SME EUR 25,000/yr listed; R&D licence EUR 0 / 7,500 forbids product development | primary-ish: smpl-x licence page and Meshcapade page via search; price page currency unverified | **Blocks commercial use**; also forbids redistribution of the body model files |
| **Qwen-Image 2.1 Turbo** | redraw, back views | Qwen Research License (HF model card tag `qwen-research`): non-commercial research/evaluation only; commercial needs separate licence (outlets, not the licence text) | model card (primary) + press | **Blocks commercial use** of redraws; hosted API is a separate route (terms not read) |
| **Qwen-Image (original)** | possible fallback | Apache 2.0 | primary: model card | allows commercial use; quality vs 2.1 unknown |
| **Qwen3-VL 32B** | judge / planner family | Apache 2.0 (32B Instruct card). The README names "Qwen3.8-VL 27B"; I could not open its card (HTTP 401) | primary for 32B only | check the 27B card; likely same family terms (unverified) |
| **Pixal3D** (TencentARC) | image to 3D shape | README: MIT; third-party components keep their own terms; upstream named as Trellis.2 and Direct3D-S2. Two secondary sources claim "academic only / not for EU" (probably wrong or a different version) | primary README; NOTICE file not retrievable | **Unresolved**: read LICENSE, NOTICE and upstream licences before any commercial plan |
| **Make-It-Animatable** | auto-rig to Mixamo skeleton | repo LICENSE is MIT (copyright line reads "Zhiyang Guo"); HF Space metadata earlier said CC BY-NC 4.0, later Apache-2.0 | primary LICENSE (raw file) + HF Space | code is permissive now; **training data (Mixamo characters) and weights terms unverified** |
| **UniMate** | text to motion on arbitrary skeletons | repo LICENSE: MIT (c) 2026 Linzhan Mou; SIGGRAPH Asia 2026 paper; dataset UniML3D | primary LICENSE | code OK; training data and the underlying human motion datasets (often AMASS/SMPL-linked) unverified |
| **Mixamo animations** | clip library, skeleton | Adobe terms: free, commercial OK in finished work, no raw redistribution (relayed by third-party guide) | secondary | usable in outputs; cannot ship a clip pack; check Adobe terms directly |
| **HY-Motion 1.0** (roadmap) | text to motion | Tencent community licence: free commercial except platforms >100M MAU (one news item); another aggregator says licence unstated | secondary, conflicting | verify repo LICENSE before use |
| **Kimodo (NVIDIA)** (roadmap) | text to motion, humanoid | NVIDIA Open Model License; HF cards say ready for commercial use (licence text not read) | model cards | likely usable; read licence |
| **EMAGE / BEAT2** (if adopted) | co-speech gestures | code licence unconfirmed; dataset uses SMPL-X + FLAME | unverified | inherits SMPL-X restriction |

*What this means.* Today the project is clean for **non-commercial, research, portfolio and personal artistic** use (SMPL's own terms include non-commercial artistic projects). For any paid product or service you would need to: (a) replace Qwen-Image 2.1 Turbo with an Apache-licensed generator or a paid licence; (b) replace or license GVHMR+SMPL (options: Meshcapade commercial licence, or a non-SMPL pose estimator with its own licence, or only video-free motion sources like Mixamo/UniMate/Kimodo); (c) confirm Pixal3D's chain and the Make-It-Animatable weights and data; and (d) check whether *outputs* are encumbered separately from software (the licences above govern software and data use; whether generated meshes inherit restrictions is a legal question I cannot answer). Also note that purely AI-generated assets have uncertain copyright protection (a legal-blog source, unverified), which affects brand-character use.

---

## 5. Ranked opportunities for this author

Scoring is judgement: value (who would use it), feasibility on this codebase in weeks, and edge from audio/speech skills. 1-5 each; total is the product, not a measurement.

| Rank | Opportunity | Value | Feasibility | Audio edge | Product |
|---|---|---|---|---|---|
| 1 | Beat-synced multi-character dance previs | 4 | 4 | 5 | 80 |
| 2 | Speech-driven gestures and lip-sync on your own character (VTuber / narrator) | 4 | 3 | 5 | 60 |
| 3 | VRM export: from one picture to a VTuber/VRChat-ready avatar | 4 | 3 | 3 | 36 |
| 4 | Audio-aware dance-learning comparison | 3 | 4 | 4 | 48 |
| 5 | Video to humanoid-robot reference motion | 3 | 4 | 1 | 12 |

(Rank follows the product score, except I place #3 above #4 because VRM output is the shortest path to real users; read the scores as a guide, not a law.)

### Opportunity 1: Beat-synced multi-character dance previs

*Why.* It is the stated roadmap goal, hobby quality suffices, and the audio edge is large: beat and downbeat tracking, section segmentation (verse/chorus), onset-aligned accents. *Who.* Choreographers, dance teams, music-video makers.

*First two weeks.*
- Week 1: take one song and the existing dance clip. Use an off-the-shelf beat tracker (e.g. librosa or madmom; pick one and record its accuracy on 10 songs by hand) to get beats, downbeats and section boundaries. Compute the clip's own motion-energy peaks (wrist and foot velocity) and align them to beats with DTW; output a time-warp that makes any clip land on the beat.
- Week 2: spawn 3-4 characters (reuse existing runs) in one Blender scene with formation presets (line, V, circle), per-character time offsets (canon) and optional mirrored motion; render a 30-second preview with a moving camera. Success metric: 5 listeners/dancers rate "does it feel on the beat" vs the unaligned version.
- Output: a repeatable script plus a short video; decide after that whether to learn anything (probably not; rule-based first).

### Opportunity 2: Speech-driven gestures and lip-sync on your own character

*Who.* Podcasters, educators, NPC authors. *Why audio.* Phoneme/viseme timing, prosody (pitch, energy, pauses) as gesture triggers, TTS and voice handling are all yours already. Note SMPL licensing hits learned co-speech models (EMAGE/BEAT2), so start rule-based.

*First two weeks.*
- Week 1: pick a 60-second narration (own voice or local TTS). Extract word timestamps with a local ASR (e.g. Whisper family) and energy/pitch contours. Drive head nod, brow and a small set of hand beat gestures from stressed syllables, using existing Mixamo clips or UniMate prompts retargeted to the rig.
- Week 2: add visemes: map phonemes to 6-8 mouth shapes as shape keys on a simple face (note the pipeline's face needs blendshapes; start with a jaw bone or shape keys on the head); render a 60-second clip. Success metric: blind A/B against a static or looped idle animation with 10 viewers.
- Deliverable: a clip and a short note on what the rig lacks for faces.

### Opportunity 3: VRM export for VTubers and VRChat creators

*Who.* Streamers and creators with their own character art. *Why.* The 52-bone Mixamo skeleton maps onto VRM humanoid bones; VRM is the standard format; Ready Player Me's closure leaves custom-avatar tooling thin (though VRoid is free and strong in anime style).

*First two weeks.*
- Week 1: write the Mixamo-to-VRM humanoid bone map; export one existing character through Blender's VRM add-on or UniVRM via Unity; test in VSeeFace/Warudo (VSeeFace needs VRM 0.x; Warudo supports 0.x and 1.0; verify yourself).
- Week 2: add the minimal expression set (blink, A-I-U-E-O visemes) as shape keys on the face mesh; test with webcam tracking. Success metric: three VTuber-curious testers can drive the avatar without help. Record where the mesh breaks (hair, loose clothing, teeth).
- Also write down the commercial-use question for your outputs first (section 4).

### Opportunity 4: Audio-aware dance-learning comparison

*Who.* Dance learners and teachers. *First two weeks.*
- Week 1: use the existing GVHMR path to get a reference motion; run a pose estimator on a learner phone clip; align with DTW on joint-angle features plus a beat grid from the music; output per-8-count scores for six body parts.
- Week 2: render the reference as the user's chosen character next to the learner's skeleton overlay. Success metric: for 5 learners the tool's "worst 8-count" matches a teacher's pick at least 3 times in 5. Be honest that three consumer apps already do something similar (section 3.10).

### Opportunity 5: Video to humanoid-robot reference motion

*Who.* Robot-learning students. *First two weeks.*
- Week 1: reproduce GVHMR -> SMPL -> GMR -> Unitree G1 retarget on one dance clip, record foot-slide and joint-limit violations.
- Week 2: visualise in simulation (MuJoCo) and write up where retargeting fails. Success metric: a clip that plays in simulation without self-collision. Low audio edge; chosen for learning, not product.

---

## 6. Risks

1. **Licence risk dominates any commercial path** (Qwen research licence, GVHMR custom licence, SMPL). Mitigation: keep a licence ledger in docs; build a "clean" substitution plan before charging anyone.
2. **Cloud competitors get rigging and animation for free.** Meshy shows 0 credits for rigging and animation; Tripo has rigging; their funding (hundreds of millions) means rapid improvement. Homunculus cannot compete on convenience; it should compete on privacy, control, video-to-motion and extensibility.
3. **Quality ceiling.** The project's own notes record fused fingers, torn hands, melted feet and weak back views. Many applications (brand mascots, sign language, e-commerce) need production quality.
4. **Dependency fragility.** Mixamo is in maintenance mode; Pixal3D and other research releases change fast; Ready Player Me showed that platforms disappear. Pin versions and keep exports in open formats (FBX, GLB, VRM, BVH).
5. **Market numbers are weak.** Most pricing and size figures came from aggregators, affiliate pages and vendors selling to the same audience; do not build a business case on them.
6. **Group choreography is mostly research.** Public data is small (AIOZ-GDANCE 16.7 hours) with unclear licences; promising learning-based group dance is not a safe two-week task. Rule-based composition is.
7. **Ethics and law.** Characters from copyrighted art (the showcase character is a Miles Morales-style design) raise IP issues if shared commercially; AI-generated assets have uncertain copyright; sign-language and children's-data uses carry ethical duties.
8. **Scope drift.** The author's stated goal also includes understanding the domain. A pile of applications could displace the learning goal; pick one experiment at a time.
9. **Hardware.** One 24 GB GPU and minutes per run limit classroom or live use.

## 7. Sources

Primary or near-primary (opened):
- Pixal3D GitHub README (MIT claim; NOTICE referenced): https://github.com/TencentARC/Pixal3D
- Make-It-Animatable LICENSE (MIT): https://raw.githubusercontent.com/jasongzy/Make-It-Animatable/main/LICENSE
- GVHMR LICENSE (custom, non-commercial): https://raw.githubusercontent.com/zju3dv/GVHMR/main/LICENSE
- UniMate LICENSE (MIT): https://raw.githubusercontent.com/Friedrich-M/UniMate/main/LICENSE
- Qwen-Image (Apache 2.0): https://huggingface.co/Qwen/Qwen-Image
- Qwen-Image-2.1-Turbo (Qwen Research License): https://huggingface.co/Qwen/Qwen-Image-2.1-Turbo
- Qwen3-VL-32B-Instruct (Apache 2.0): https://huggingface.co/Qwen/Qwen3-VL-32B-Instruct
- Meshy pricing and credits docs: https://docs.meshy.ai/en/webapp/pricing

Search-result sources (not independently verified; secondary):
- SMPL-X model licence: https://smpl-x.is.tue.mpg.de/modellicense.html
- Meshcapade body-model licensing: https://meshcapade.com/assets/body-models
- SMPL licence overview (Meshcapade): https://meshcapade.notion.site/The-SMPL-Model-Licenses-2144560e54388085af5eff111fcdf266
- Ready Player Me and Netflix: https://www.pocketgamer.biz/netflix-acquires-avatar-creation-platform-ready-player-me ; https://www.cobalt.legal/news-cases/netflix-acquired-gaming-avatar-maker-ready-player-me/
- Meshy funding: https://dealroom.co/news/139828-meshy-raises-400m-series-b-at-1-5b-valuation-for-3d-ai/ ; https://dealroom.co/news/158079-meshy-hits-100m-arr-first-ai-3d-firm-to-reach-milestone/
- Meshy pricing change note: https://costbench.com/changelog/meshy-plan-added-2026-07/
- Tripo / VAST funding: https://investgame.net/news/matrix-partners-china-has-led-a-446m-series-b-and-b-into-vast-maker-of-tripo-ai-in-its-fourth-round-of-2026/ ; https://aiweekly.co/alerts/tripo-ai-hits-10m-users-as-vast-raises-200m
- Tripo pricing aggregator: https://toolradar.com/tools/tripo-ai/pricing
- Tripo rigging (Scenario guide): https://help.scenario.com/articles/4692888910-tripo-family-the-complete-guide
- Rodin / Deemos: https://www.yicaiglobal.com/news/chinese-ai-startup-deemos-raises-new-funds-for-hyper3d-rodins-global-rollout ; https://costbench.com/software/ai-3d-generation/rodin-hyper3d/
- Kaedim: https://neuronfeed.com/compare/kaedim-rodin-deemos
- Autodesk Flow Studio pricing: https://adsknews.autodesk.com/en/?p=53687 ; https://www.cgw.com/Press-Center/News/2025/SIGGRAPH-2025-Autodesk-Flow-Studios-new-freemium.aspx ; https://usagepricing.com/blueprint/wonder-dynamics
- Mixamo status (third-party): https://app.cinevva.com/guides/free-character-animations-rigging ; https://app.cinevva.com/guides/mixamo-to-blender-2026
- Cascadeur pricing aggregator: https://toolradar.com/tools/cascadeur/pricing
- DeepMotion/Rokoko/Move AI comparison: https://neuronfeed.com/compare/move-ai-vs-deepmotion ; https://www.renderhub.com/blog/budget-motion-capture-options-worth-considering
- Viggle pricing aggregator: https://bityclips.com/tool/viggle-ai/pricing
- Qwen-Image 2.1 Turbo licence coverage: https://aiweekly.co/alerts/qwen-ships-image-21-turbo-as-8-step-7b-research-license-model
- UniMate: https://arxiv.org/pdf/2609.05415 ; https://huggingface.co/Linzhan/UniMate
- HY-Motion / Kimodo licences: https://cgworld.jp/flashnews/01-202604-Kimodo.html ; https://huggingface.co/vigneshk0702/Kimodo-SOMA-RP-v1
- Humanoid retargeting: https://arxiv.org/pdf/2603.22201 ; https://github.com/ryanrudes/GMR ; https://arxiv.org/pdf/2502.01143
- VTuber formats and market: https://news.viverse.com/post/vrm-models-explained ; https://news.viverse.com/post/vtuber-model-pricing-2026
- Co-speech gesture (EMAGE): https://arxiv.org/html/2401.00374v3
- Group dance: https://arxiv.org/pdf/2303.12337 ; FineDance https://arxiv.org/pdf/2212.03741
- Dance-learning apps: https://apps.apple.com/md/app/id6763208339 ; https://apps.apple.com/cd/app/id6771540435
- Sign-language avatar research: https://athena.itec.aau.at/?p=5907
- Meta Animated Drawings: https://developers.facebook.com/blog/post/2023/04/13/meta-os-animated-drawings/
- Fab / Unity AI policies: https://80.lv/articles/epic-games-adresses-ai-generated-content-plaguing-fab ; https://support.unity.com/hc/en-us/articles/16456407029524

Not researched or unverified in this pass: Luma and Scenario pricing and funding, Plask and Move AI pricing, Deaf community views on sign avatars, hosted talking-avatar competitors, Steam's current AI rules, the "Qwen3.8-VL 27B" model card, Pixal3D's NOTICE file and the training-data licences behind Make-It-Animatable and UniMate.
