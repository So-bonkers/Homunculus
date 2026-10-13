# Research synthesis (2026-10-13)

Six parallel studies, each in its own file, read against each other and against the repository. This page is the short version: what they agree on, where they disagree or I corrected them, and what to do next. Everything here is a judgement from the reports, which tag their own claims *verified / secondary / from memory / unverified*; I carry those tags forward and mark where I checked something myself.

| File | Slice |
|---|---|
| [01](01_image_to_3d.md) | image(s) to 3D shape and texture |
| [02](02_rigging_and_skinning.md) | rigging, skinning, retargeting, cloth, hands |
| [03](03_human_motion.md) | motion from video, text-to-motion, physics |
| [04](04_group_choreography_and_music.md) | group dance, multi-person, music and speech to motion |
| [05](05_image_generation_for_3d.md) | image generation and editing for 3D-ready views |
| [06](06_applications_and_market.md) | applications, competitors, licences, ranked opportunities |

## The five conclusions

1. **The goal that comes next is cheap, because of an earlier decision.** Every character already gets the same 52-bone Mixamo skeleton, so one clip plays on any character. That makes *several characters in one scene* a scene-builder problem (placement, time offsets, formations), not a research problem. Reports 04 and 06 reached this independently and ranked the same thing first: **beat-synced multi-character dance previs**. It also settles open decision O-4 in [DECISIONS.md](../DECISIONS.md).
2. **No model for group dance is usable.** The group-dance papers (TCDiff, CoheDancers, ST-GDance) have no confirmed public code, the datasets are small, and the solo models (EDGE, Bailando) are older CUDA-era code. Generating new group choreography from a song is a research branch, not a feature. Real group motion is more reachable by capturing it from video (multi-person capture, below).
3. **Everyone found the same weakness in the metrics, and it is your field.** FID-style scores and the standard beat-alignment score are weak (jitter inflates the beat score), and there is no good group-synchronisation metric. A tempo- and phase-aware beat metric, and a group sync score, are open and audio-native. This is the clearest place where your background is an edge.
4. **The pipeline's three open quality problems have known next steps, none of them a new model.**
   - *Side views and the geometry gate:* replace the IoU-only outline check with a keypoint or depth-edge check run in code (the arms-down failure is an overlap blind spot); try a 45° view instead of 90°; judge geometry in code, not with a language model (VLM judges reported at 0.57–0.75 Spearman). [05]
   - *Hands:* redraw a hand crop with a hand-mesh depth guide and check with a keypoint detector; add a finger-curl test and clean up skin weights after rigging. [05, 02]
   - *Logos and text:* paste the original pixels back instead of regenerating them; avoid SUPIR/SeedVR2 on text. [05]
5. **Foot sliding: the same fix from three reports.** A contact-based foot lock with two-bone IK in the retarget step (02, 03, 04 all say so). No AI, no RL. It matters more once two characters stand next to each other, where skating is obvious.

## Where the reports agree

- No new model fixes **hands** or **rig-ready topology** (01, 02, 05). Mitigations are engineering around the current models.
- **Top and bottom views** should be dropped from generation (01, 05; matches what you found).
- **No verified drop-in replacement** for GVHMR, Make-It-Animatable or Pixal3D exists on this GPU. The newest motion papers (DuoMo, GEM, OnlineHMR, DanceHMR) have no confirmed code: re-check in a month. (01, 02, 03)
- **ROCm is the recurring risk** for every candidate (TRELLIS.2, UniRig, SkinTokens, Puppeteer, TRAM). Smoke-test on the AMD card before committing time. (01, 02, 03)

## Where I corrected or reconciled them

- **UniMate's licence.** Report 06 says UniMate is MIT. That is its *code*; our own [THIRD_PARTY.md](../../THIRD_PARTY.md) records the **weights as CC BY-NC 4.0 (non-commercial)**. Treat UniMate output as non-commercial.
- **Pixal3D's licence is unresolved.** Our THIRD_PARTY.md says MIT (model card), 01 and 06 agree with that for the code, but 06 found two secondary sources saying academic-only. Check the NOTICE file and the upstream licences (TRELLIS.2, Direct3D-S2) before relying on it.
- **Make-It-Animatable** is MIT for code and Apache-2.0 for weights per our notes; the HF Space says Apache-2.0. Consistent enough; its *training data* licence is unverified.
- **I verified one claim myself:** the GVHMR `LICENSE` in our checkout (`gvhmr/repo/LICENSE`) is "educational, research and non-profit purposes only"; commercial use needs the authors' permission.
- **Report 02's claim that the pipeline already uses SkinTokens** is true (`homunculus/stages/tpose.py`, `riggers/skintokens/`).
- **Funding and pricing figures in 06** (Meshy ~$400M, Tripo's maker ~$446M, Ready Player Me closing) come from secondary sources and should not be quoted until checked.

## What this means for commercial use

Today the project as a whole is **research/hobby use only**, not a product. These are the pieces that block it:

| Piece | Why | Swap |
|---|---|---|
| GVHMR | custom licence, non-profit only (verified here) | TRAM or WHAM (MIT), still with SMPL's own terms |
| SMPL / SMPL-X | non-commercial | a different body model, or a licence from the authors |
| UniMate weights | CC BY-NC 4.0 | HY-Motion Lite (licence text not read), or drop text-to-motion |
| Qwen-Image 2.1 | Qwen Research Licence | original Qwen-Image (Apache-2.0), Z-Image-Turbo (reported Apache-2.0) |
| Pixal3D | unresolved (above) | TRELLIS.2 (MIT) |

This does not stop anything you plan next. It means that if an application from the research ever turns into a product, the licence swaps become the first work item, not the last.

## Recommended path (in your own priority order)

**1. Product: finish the loop on what exists (days).**
Add the **foot-lock IK pass** to `tools/retarget_bvh.py` and measure it with the metric you already used (body heights per second of sliding). Add a **finger-curl and weight-cleanup test** after rigging. These are the two cheapest, most visible quality gains, and both are prerequisites for the next step.

**2. Multiple models and group choreography (the 2–3 week plan).**
- *Design A first (report 04, days):* a **scene builder** (Blender Python or three.js) that loads N finished characters, assigns each a clip, a time offset and a formation slot (line, V, circle, staggered rows), with canon and mirror variants. Reuse existing runs as the cast. No new model.
- *Beat lock (audio-native, your part):* get beats, downbeats and sections from the song, and time-warp each clip (dynamic time warping between the clip's motion-energy peaks and the music's onset strength) so its accents land on the beat. Success metric from 06: 5 listeners or dancers rate "does it feel on the beat" against the unaligned version.
- *Design B next (weeks):* real group choreography from a multi-person video (Human3R, or tracking then GVHMR per dancer), with a UI step to confirm which track is which dancer. Needs the foot lock from step 1.
- *Design C last (months, research):* music-driven generation per dancer with formation constraints. Only as a research branch, and only after A and B give a baseline to beat.

**3. Application research (alongside, cheap).**
Use the ranked list in report 06 as the question, not the answer: previs for choreographers and music-video makers (1), speech-driven gestures and lip-sync (2), VRM export for VTubers (3). Each has a two-week experiment written out. Before building any, show the previs output from step 2 to three people who would use it; that is the cheapest test of whether it is *genuinely helpful*, which was your stated goal.

**4. Understanding the domain, in the order the work needs it.**
- Step 1 teaches retargeting, IK and skeletal hierarchies (the foot lock).
- Step 2 teaches scene representation (glTF multi-skeleton) and beat tracking (yours already).
- Read first: the vocabulary sections at the top of reports 01 and 02, then 03's overview of SMPL and world-grounded motion.

## What I would not do now

- Train or run reinforcement learning for physics cleanup on this GPU (03).
- Switch GVHMR for TRAM: better path accuracy in one authors-reported table, much slower, CUDA-oriented (03).
- Chase top and bottom views (01, 05).
- Build anything from the 2026 papers without released code.
- Quote funding or pricing figures from 06 without checking them.

## Cheap experiments to run when the GPU is free

1. Run Pixal3D `main` and TRELLIS.2 on the same three characters; compare hands and PBR output (01). Check ROCm first.
2. Try Hunyuan3D-Omni with a T-pose skeleton control (one day; 01). Mind the licence restrictions (EU, UK, South Korea excluded).
3. Try the Qwen-Image-Edit-2511 camera-angle LoRA for side views on three T-pose characters, filtered by the new geometry check (05). Unknown whether it loads on Qwen-Image 2.1.
4. Evaluate Make-It-Animatable v2 against v1 on the existing runs, using the finger and wrist-bend checks (02).
5. HaMeR on a clip with close-up hands, compared with the library finger pose (03).

## How much to trust this

Strong: the local checks above, and the points several reports reached independently (foot lock, Design A, the weak beat metrics, dropping top and bottom views). Weaker: anything that rests on a single secondary source (several 2026 facts, all funding and pricing numbers, most licences for models in 04). Every report lists its sources; verify a licence at the source before acting on it.
