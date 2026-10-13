# Decision log

Why Homunculus is the way it is. One entry per decision that changed what the project does or how it is worked on: what was decided, why, what the evidence was, and which commit made it real. Newest first within each section; the numbers run in the order decisions were made inside a section, so they are not one global timeline.

How to add one: copy the template at the bottom, put it at the top of its section, and give it the next free number. Write it when you decide, not weeks later; a sentence of "why" now is worth a page of archaeology.

*The entries up to D-24 were reconstructed on 2026-10-13 from the git history, the commit messages and [PAIN_POINTS.md](PAIN_POINTS.md). Where a reason was not written down at the time it is marked **(inferred)**: treat those as a guess to confirm or correct.*

## Direction (where the project is heading)

Stated by the author on 2026-10-13, in this order of priority:

1. **Idea to visible product.** Largely achieved (v1.6: picture in, rigged and animated character out, a web app, a dance copied from a video).
2. **More than one 3D model in a scene, group choreography.** See [ROADMAP.md](ROADMAP.md) (several characters in one scene).
3. **Research what the project is genuinely useful for.** Applications first, features second.
4. **Understand the domain, and through it the codebase.** The code is written largely with an AI assistant; the author's goal is to learn the domain (diffusion conditioning, SMPL and retargeting, mesh topology) and let that lead to understanding the code, not the other way round.

## Open decisions

| # | Question | Leaning |
|---|---|---|
| O-1 | Make `/ui` the default at `/` and retire the classic interface? | Yes, once the new one has been used for real runs for a while; the classic one has screenshots in `docs/media/screens/` that are no longer linked |
| O-2 | Keep Studio (the 30-step model) as a fallback for image generation at all? | Keep until Turbo has run a few dozen jobs without needing it |
| O-3 | Top and bottom generated views | Not solved (they come out as front views); do not spend time here until the model changes |
| O-4 | Several characters in one scene: one scene file, or one clip per character composited? | Not decided; needs the application research first (see Direction, 3) |

## Process

**D-24 · 2026-10-13 · Push one commit at a time, oldest first; tags only when asked.**
Why: every commit stays reviewable on GitHub and a bad one can be reverted without untangling a batch. (The author's rule; reason partly inferred.) All tags v1.0–v1.6 were pushed on request.

**D-23 · 2026-10-13 · Versions are named after milestones, not release dates.**
v1.0 is the early animation video (`4d4ac23`), then v1.1 `300c915`, v1.2 `7b555d1`, v1.3 `456e14e`, v1.4 `e8e6c80` (video to dance), v1.5 `ef37b72` (texture fill), v1.6 `ab254f4`. Why: the author's call; the first public thing that moved was the point at which it felt like a product.

**D-22 · 2026-10-13 · Two Claude sessions may work in the same repository; each stages only its own hunks.**
Why: a second session fixed `smpl_to_bvh` and the video-to-dance path while the first built the UI; staging the whole tree would have mixed the two. Not a commit but a working rule.

## Interface

**D-21 · 2026-10-13 · A new web interface in React + Vite + Tailwind with a dark studio look, built next to the classic one.**
Why: the author wanted a cutting-edge application, not a page; chose React + Vite + Tailwind and "Studio dark" over keeping the single-file HTML app. The classic one stays at `/` and the new one is at `/ui` until it covers every feature (it does now). Built files are committed so running Homunculus needs only Python. `32a2735`

**D-20 · 2026-10-13 · Animating a finished character with a fresh video is its own page, and a dance is a job with stages, reports and a time estimate.**
Why: the author wanted to reuse a model without a new run, and to see what is happening and when it will end. Each stage reports (the cut frame, whether the camera moved, retarget numbers, the previews); the time left is the remaining estimates scaled by how fast the finished stages went (0.5–2×). `6b37d9d`

**D-19 · 2026-10-13 · The result is shown next to the reference video, on one clock.**
Why: the author wanted the user to judge the result themselves. The video drives the 3D clip's time every frame, so scrub, pause and speed move both. This needed the server to answer HTTP Range requests (browsers could not seek in any served video before). `6b37d9d`

**D-18 · 2026-10-13 · The showcase video is uploaded through GitHub's web editor, not linked from the repository.**
Why: GitHub strips `<video>` tags that point at repository files; only a `user-attachments` link plays inline, with sound (10 MB limit on free plans, so the video was recompressed to 9.4 MB). `6a477bf`, `14b23a1`

## Animation

**D-17 · 2026-10-13 · A video of a dance is the default source of the Animate stage; text prompts remain.**
Why: text-to-motion (UniMate) follows coarse prompts (walk, run, kick) but not fine gestures ("thumbs up" came out as a lunge); a video of the dance you want gives exactly that. `4372d3d`

**D-16 · 2026-10-13 · The BVH motion columns follow the hierarchy's depth-first order.**
Why: every conversion so far (AIST++, FineDance, GVHMR) had scrambled limbs (47° mean error against GVHMR's own joints) because the rows were written in joint-index order. Found by a second session comparing limb directions. Everything made before was regenerated. `1a1cf9e`

**D-15 · 2026-10-13 · The retarget floor is the lowest foot or toe joint of the target.**
Why: the previous choice (the lowest mesh point, `91b1c16`, made for glTF rigs whose bone tails mean nothing) put the Thriller FBX target 5× too small and the feet 3.7 heights below the floor. `ab254f4`

**D-14 · 2026-10-13 · The camera's own motion is tracked from the background and taken out of the dancer's path; a steady camera is left alone.**
Why: GVHMR assumes a static camera, so a moving, zooming camera shows up as the dancer walking around. Tracking is skipped below 1.5° of movement and 3 % zoom, or when under half the background is found. `6ead3a3`

**D-13 · 2026-10-12 · GVHMR for video-to-motion; AIST++ and FineDance as datasets; everything goes through one retargeter.**
Why: any dance a person can film becomes usable, not only the ones in a dataset; BVH is the common format, so CMU, AIST++, FineDance and video all share `retarget_bvh.py`. (Choice of GVHMR over alternatives not recorded: inferred.) `ed31733`, `83aaed3`, `e8e6c80`

**D-12 · 2026-10-07 · Fingers are set by a hand-pose layer chosen from the prompt.**
Why: motion models do not drive fingers, so punches had no fists and hands looked like claws. Poses are static per clip. `ebe6b7e`

## Image and 3D quality

**D-11 · 2026-10-13 · Qwen-Image 2.1 Turbo (8 steps) is the image model for every redraw; the 30-step Studio model is the fallback.**
Why: on a hand crop it took 6 s per redraw after a 32 s load against about 45 s, with five clean fingers on all three seeds; it also made the depth ControlNet usable. `d09b6ee`, `0d9c844`

**D-10 · 2026-10-13 · A depth phase before the 3D shape draws the back view.**
Why: Pixal3D invents the back of a character. A proxy shape gives a depth map from behind, and the back is drawn under it with Turbo + the Fun ControlNet. The back is first drawn unguided and that is the reference, so the front's logos cannot leak. A view is kept only if its outline overlaps the proxy's (IoU ≥ 0.8, no language model involved). Side views are opt-in (the arms hang down); top and bottom views do not work (see O-3). `09ee356`

**D-9 · 2026-10-13 · Repair's graft trims both parts exactly at a plane, pairs every ring of the cut and bridges each pair.**
Why: the old cut went through whole vertices (a staircase edge) and bridged one loop pair, so double-walled sleeves left ragged bands and open loops. Measured on the F1 hands: one region closed with 0 open edges, another (11 loops) bridged 5 pairs. The author called the graft "the only piece that keeps breaking". `d1f4d69`

**D-8 · 2026-10-13 · Texels no view painted are filled from the nearest painted surface in 3D (median of 24 neighbours).**
Why: repaired hands and boots, and the surfaces no view faces, were one flat colour. The fill is added to the full-size texture so painted detail is untouched. `ef37b72`

**D-7 · 2026-10-13 · Hand repair is part of the pipeline: automatic by default, the user's choice in manual mode.**
Why: hands were the most frequent failure (fused fingers, paddle hands); finding them after the run was too late. `529a510`

**D-6 · 2026-10-08 · A turnaround sheet is a supported input (multiview Pixal3D and a four-view projection).**
Why: a single picture makes Pixal3D guess the back and sides, and its own baked texture is a patchwork of garbled fragments. One test (an F1 driver) gave five separate fingers and real logos on the back. `5c77653`

**D-5 · 2026-10-07 · Texture is "simple" by default (the picture alone); generated extra views are opt-in.**
Why: extra generated views (face close-up, cleaned sides and back) made the model look worse than the picture. `95a16e4`

## Pipeline and operation

**D-4 · 2026-10-13 · `--no-llm`: a run with no planner, no shape judges and no rig judges.**
Why: the author wanted to test the pipeline without any language-model judgement, and to judge the results themselves. `77f2b2c`

**D-3 · 2026-10-07 · GLB only by default; FBX, USD, OBJ, STL on demand through Accept, with optional cleanup.**
Why: duplicate FBX and GLB copies and raw shapes of hundreds of MB filled the disk. `b40750e`

**D-2 · 2026-10-06 · Three judges decide at each gate, and the user can overrule them (Override), judge alone (Manual) or opt out.**
Why: a single judge is noisy (the same rig scored 4/10 twice and then 9/10), and the author wanted to stay in control. The gates are redraw pick, shape check and rig check. `b63f42a`

**D-1 · 2026-10-06 · Everything runs locally on one GPU (24 GB, AMD ROCm): a lock allows one GPU job at a time, a watchdog watches VRAM, and every other model is unloaded before a heavy stage.**
Why: one picture should not leave the machine, and the card cannot hold the models at once. The VRAM limit is only logged, not enforced yet (see [PAIN_POINTS.md](PAIN_POINTS.md)). **(Privacy motive inferred.)** `ad08800`

---

### Template

```
**D-N · YYYY-MM-DD · What was decided, in one line.**
Why: the problem, the evidence (a number, a failure, a test), what else was considered. `commit`
```
