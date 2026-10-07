# Homunculus: picture → rigged, animated 3D character, fully local

Give it **one picture** of a character (or an existing **3D model**) and it gives back a **textured, rigged 3D character with a 52-bone Mixamo skeleton, fingers included, plus animation clips you describe in plain text** ("walks forward", "dances salsa", "does a spinning kick"). Everything runs on your own machine, on one 24 GB GPU, one heavy model at a time. Local vision-language models plan the work and judge each result; a web app orchestrates it and lets you step in at every decision.

![A finished run: input, redraw, 3D model, rig test, animation](docs/media/contact_sheet.jpg)

## What it does

`picture → upscale → plan → redraw (rig-friendly T-pose) → 3D shape → quick colour → auto-rig → rig check → text-to-animation → final texture → report`

| stage | what happens | model / tool |
|---|---|---|
| Ingest, Upscale | record the input; 4× upscale (photo / anime / 3D-render models chosen from the style) | RealESRGAN, 4x-UltraSharp (ComfyUI) |
| Plan | a VLM describes the character and fills the redraw prompt | Qwen3.8-VL 27B |
| Redraw, Pick | redraw as a clean full-body T-pose with open hands, several candidates, then pick (judges and/or you) | Qwen-Image 2.1 edit + a 3-judge panel (Qwen3.8, Gemma, Qwen3.6) |
| Prepare | clean-up and upscale the winner; redraw the face close-up at full resolution before 3D | RealESRGAN, Qwen-Image |
| 3D shape, Shape check | best of 3 shapes; silhouette carve removes fins/plates outside the picture's outline; judges check | Pixal3D (ComfyUI) |
| Colour | quick front projection onto the mesh so the rig is built and checked on a coloured model (CPU, seconds) | Blender |
| Auto-rig, Rig check | 52-bone Mixamo skeleton with skin weights; pose-test renders judged | Make-It-Animatable |
| Animate | text prompts → motion clips for *your* skeleton, 2 takes each | UniMate |
| Texture | face fit, multi-view clean-up, put on the rig and on every clip | Blender + Qwen-Image |
| Report | contact sheet + report.md | – |

### Sample animations

Prompts typed as plain text. Same motion, two different characters. *(The Spider-Man-style previews come from the preset library; clips on the male model render untextured.)*

| prompt | male | female |
|---|---|---|
| walks forward | ![](docs/media/walk_male.gif) | ![](docs/media/walk_female.gif) |
| does a spinning kick | ![](docs/media/spinning-kick_male.gif) | ![](docs/media/spinning-kick_female.gif) |
| dances hip hop, bouncing and swinging the arms | ![](docs/media/hip-hop_male.gif) | ![](docs/media/hip-hop_female.gif) |
| dances salsa, stepping side to side and swaying the hips | ![](docs/media/salsa_male.gif) | ![](docs/media/salsa_female.gif) |
| slashes forward with a sword | ![](docs/media/sword_male.gif) | ![](docs/media/sword_female.gif) |
| jumps forward | ![](docs/media/jump_male.gif) | ![](docs/media/jump_female.gif) |

And on a character the pipeline built from a single picture (a fantasy knight, finished run, final texture applied to every clip):

| walks forward | runs forward | fights, throwing a punch and then a kick | dances hip hop |
|---|---|---|---|
| ![](docs/media/run_walks_forward.gif) | ![](docs/media/run_runs_forward.gif) | ![](docs/media/run_fights_throwing_a_punch_.gif) | ![](docs/media/run_dances_hip_hop_bouncing_.gif) |

UniMate is an early research model: simple locomotion and gestures are good; acrobatics (backflips, handstands) and anything involving props are hit and miss. Clips are 1.6 s, 30 fps. The GIFs were rendered with Blender's workbench renderer (`tools/make_samples.sh`).

## The stages in pictures

Snapshots the app saves at each important moment of one real run (*knight_full*, from a single picture). They appear live in the run page's Activity tab.

| stage | snapshot |
|---|---|
| **1 · Upscale** the input 4× with the model that fits its style | ![](docs/media/stages/1-upscale.jpg) |
| **2 · Plan**: a VLM describes the character and writes the redraw prompt | ![](docs/media/stages/2-plan.jpg) |
| **3 · Redraw + pick**: rig-friendly T-pose candidates, the judges (and you) choose | ![](docs/media/stages/3-redraw-pick.jpg) |
| **4 · Face close-up** redrawn at full resolution *before* the 3D step | ![](docs/media/stages/4-face-closeup.jpg) |
| **5 · 3D shape check**: three Pixal3D shapes rendered from several sides and judged | ![](docs/media/stages/5-3d-shape-check.jpg) |
| **6 · Quick colour** projected onto the mesh so the rig is built on a coloured model | ![](docs/media/stages/6-quick-colour.jpg) |
| **7 · Rig check**: test poses of the 52-bone skeleton, judged for tearing | ![](docs/media/stages/7-rig-check.jpg) |
| **8 · Animate**: UniMate clips for your prompts, driven on this rig | ![](docs/media/stages/8-animate.jpg) |
| **9 · Final texture**: face fit plus cleaned side and back views, put on the rig and every clip | ![](docs/media/stages/9-final-texture.jpg) |

## The app in pictures

| | |
|---|---|
| ![Home](docs/media/screens/01-home.jpg) **Home**: a live 3D turntable of your latest character | ![Launcher](docs/media/screens/03-launcher.jpg) **New run**: every option in one form |
| ![Tour](docs/media/screens/02-tour-step4.jpg) **Guided tour** (the *Tour* button, offered on first visit): spotlights each control | ![Tips](docs/media/screens/05-tips.jpg) **Tips** for pictures, prompts and review modes |
| ![Presets male](docs/media/screens/04-preset-library-preview.jpg) **Preset library** with a 3D ▶ preview on a male character… | ![Presets female](docs/media/screens/04b-preset-preview-female.jpg) …and on a female one, with the creators credited |
| ![Runs](docs/media/screens/06-runs.jpg) **Runs** with live status, Stop and Fork | ![Pipeline](docs/media/screens/07-run-pipeline.jpg) **Run page**: the pipeline as a node graph, then Activity, downloads and the planner's notes |
| ![Animate](docs/media/screens/09-run-animate.jpg) **Animate** tab: type or pick prompts, play the clips | ![3D](docs/media/screens/10-run-3d-model.jpg) **3D model** viewer: final, rigged, clay, wireframe, bones |

## Features

- **One local web app** (http://127.0.0.1:8765): upload a picture or 3D model, choose every option, start, watch and review. Live node graph of the 14 stages, snapshots at every important moment, 3D viewer (textured / rigged / clay / wireframe / bones), activity timeline, log, downloads (FBX, GLB, Mixamo zip).
- **You or the judges decide:** Auto (judges only), Override (a 60 s window to overrule them), Manual (you are the judge: candidates come one at a time with *Use this / Try another*). Your call stops the remaining judges.
- **Broken-hands gate and wrist check:** when the 3D shape is final, the hands are checked for torn or cut-off fingers (they leave open edges in the surface: 0 per 1000 vertices on a healthy hand, about 40 on torn glove fingers). *Warn me* (default) points you to the Repair tab, *Repair automatically* runs the repair before rigging (about 12 extra minutes), *Off* skips it (`--auto-repair alert|auto|off`). After rigging, the rig check bends each wrist and measures whether the hand stays attached to the forearm. The check does not see fingers that are fused but closed.
- **Hand poses for the fingers:** the motion models do not drive fingers, so every clip gets its fingers set from a small pose library chosen from the prompt (fist for a punch, open for a wave, grip for a sword, point, thumbs up, relaxed otherwise). Deterministic, no model, works with any motion source; *Set hand poses* in the Animate tab applies it to clips you already have (`python -m homunculus.animate <run> --hands`).
- **The face of your own picture:** the face texture is taken from your original picture (upscaled), not from the redraw the image model made: the two pictures' face landmarks are matched against each other and the original face is blended into a copy of the redraw, which is then fitted to the model. Falls back to the redraw's face when a face is not readable in either picture. Option *Face texture from* in the launcher and the Fork dialog, `--face-source original|redraw` on the command line.
- **Simple texture (default):** the texture comes from your upscaled picture / the chosen redraw alone: projected onto the model with the face fitted by landmarks. The extra generated images of the older *Full* mode (a face close-up redraw as the reference, Qwen-cleaned side and back views) can make a model look worse than the picture it came from, so they are opt-in (`--texture full`, or Texture: Full in the launcher and the Fork dialog).
- **Your picture as is:** with *Use my picture as is* the redraw is skipped and the texture is projected from your own picture (upscaled, never redrawn); the face close-up redraw only helps the 3D shape.
- **Looks:** keep the picture's style or restyle (3D film, Game, Anime 3D, Clay, Chibi); *All · I pick* makes one candidate per look.
- **Fork** any stopped run from any stage with new instructions or settings, keeping the original untouched.
- **Starting from a 3D model** (STL, OBJ, PLY, GLB, FBX): no picture needed; the model is oriented, painted from its own renders and rigged. A model that isn't in a T-pose is put into one first (SkinTokens + a Blender bake).
- **Text-to-animation** with a typed prompt box and a **preset library** of 190 prompts in 10 categories, each with a 3D **preview** on a male and a female character.
- **Rigger choice** (Make-It-Animatable default or normal-aware weights) with automatic fallback.
- **Retexture a part:** brush part of a finished model, then either describe it and let the image model generate that view, or use a reference picture lined up with the model; the picture is projected onto the brushed area on the CPU and can then go onto the rig and every clip. See [docs/RETEXTURE.md](docs/RETEXTURE.md); wishes for later (several characters, props, non-human objects, high-poly) are in [docs/ROADMAP.md](docs/ROADMAP.md).
- **One package per character:** the *Package* button downloads one zip with the rigged FBX/GLB, the textures, every animation clip (GLB + FBX, named after the prompt) and a README with licence notes.
- **System check:** the *Check* button (or `python -m homunculus.doctor`) tests Studio, ComfyUI and its models, Blender, Make-It-Animatable, UniMate, GPU memory, disk and the Python packages, and says how to fix what is missing.
- **Delete runs:** the *Delete* button on a run card or run page removes the run and everything made for it (the run folder, the uploaded input, the Mixamo export and ComfyUI's Pixal3D outputs) after showing exactly what goes and how big it is. Runs that are running are protected; files are matched by exact names so another run's files are never touched.
- **Repair a broken region:** paint over fused or cut-off fingers (or press *Select hands*) in the 3D viewer and the pipeline redraws that part, rebuilds it in 3D and joins it at the wrist. Tested on real failed hands; see [docs/REPAIR.md](docs/REPAIR.md) for how it works and what it cannot do yet.
- **Face fidelity:** early face close-up, face reshape, landmark fit, multi-view texture clean-up.
- **Safe on one GPU:** a lock file allows one GPU job at a time, a VRAM watchdog cancels at 22.5 GB, and the pipeline unloads every other model before a stage; Studio unloads are verified.
- **Resumable and notified:** every stage is checkpointed in `runs/<name>/state.json`; desktop notifications say when a run needs you or why it stopped.
- **Clickable launcher:** `homunculus.html` starts the server and opens the app.

## Hardware it was built and tested on

| | |
|---|---|
| GPU | AMD Radeon RX 7900 XTX class (Navi 31), **24 GB VRAM** (ROCm 7.2, PyTorch 2.14) |
| CPU / RAM | AMD Ryzen 9 5950X (16 cores) / 60 GB |
| OS | Ubuntu 26.04 LTS (Linux 7.0), Blender 5.2 |
| Budget | the whole pipeline is kept under **22.5 GB VRAM**, one heavy model at a time; the desktop runs on the same GPU |

It is only tested on this one machine. NVIDIA should work for the PyTorch parts (the VRAM probe reads `/sys/class/drm`, see `config.py`, and would need adapting) but is untested.

## How long it takes

Measured on one finished image run, *knight_full* (a fantasy knight from a 576×1024 picture, 5 animation prompts × 2 takes, Look = As is, 60 s review windows left to expire):

| stage | time | notes |
|---|---|---|
| Ingest | 0 s | |
| Upscale | 16 s | RealESRGAN 4× |
| Plan | 37 s | VLM loaded and queried |
| Redraw + Pick | 7 min 20 s | 4 Qwen-Image candidates, judge panel, 60 s review window |
| Prepare | 2 min 37 s | clean-up/upscale + face close-up redraw |
| 3D shape + Shape check | 20 min 47 s | 3 Pixal3D candidates, carve, judges (60 s window), texture bake, face reshape |
| Colour | 23 s | CPU |
| Auto-rig + Rig check | 3 min 30 s | MIA + pose renders + judges (60 s window) |
| Animate | 4 min 30 s | 5 prompts × 2 takes (UniMate: ~1 min for the sample + ~2 min to drive the character, plus loading) |
| Texture | 12 min 41 s | face fit + 5 extra views through Qwen-Image |
| Report | 1 s | |
| **Total** | **52 min 47 s** | |

Other timings: a UniMate batch of 30 prompts × 2 takes takes about 15 minutes, so the whole preset library (190 prompts × 2 takes) is **~90 minutes per character**. These are single measurements, not averages; the Pixal3D and texture stages vary the most with how many candidates the judges reject. A run that is stopped for the judges' retries takes longer. The STL route has no timing yet.

## Setup

Homunculus is a thin orchestrator around other projects, so setup is mostly installing and downloading those. `./setup.sh [all|app|comfy|mia|unimate|skintokens]` does the scriptable parts; it is written from the author's working machine and **has not been run from a clean install**, so treat it as an executable checklist.

**You need:** Linux, a GPU with **24 GB** VRAM (tested on AMD/ROCm; NVIDIA should work for the PyTorch parts), ~**100 GB** of free disk for the models and environments, [uv](https://docs.astral.sh/uv/), git, Node.js (only for `preset_clips`), ffmpeg (only for sample GIFs), [Blender](https://www.blender.org/download/) on your `PATH` (tested with 5.2), the [Hugging Face CLI](https://huggingface.co/docs/huggingface_hub/guides/cli) (`uv tool install huggingface_hub`) and [Unsloth Studio](https://unsloth.ai/docs/new/studio).

1. **Clone and install the app:** `git clone https://github.com/So-bonkers/Homunculus && cd Homunculus && ./setup.sh app`
2. **Unsloth Studio** ([install guide](https://unsloth.ai/docs/new/studio), [GitHub](https://github.com/unslothai/unsloth)) serves Qwen-Image and the three judges. Run its API on `127.0.0.1:8888` (`unsloth studio --api-only -H 127.0.0.1 -p 8888`, ideally as a user service called `unsloth-api`). The models below load by name the first time the pipeline asks for them, so you do not need to download them by hand (to pre-fetch: `hf download <repo> <file>`).
3. **ComfyUI + Pixal3D + upscalers:** `./setup.sh comfy`
4. **Make-It-Animatable:** `./setup.sh mia`
5. **UniMate:** `./setup.sh unimate`, then install UniMate's requirements into `unimate/.venv` (its README lists them)
6. **SkinTokens** (optional, only for 3D models that are not in a T-pose): `./setup.sh skintokens`, then build it with CMake
7. `./launch.sh`, drop a picture, press **Start run**.

### Every model and where to get it

| role | model | size | licence | link |
|---|---|---|---|---|
| Redraw / face repaint / texture clean-up | **Qwen-Image 2.1 edit** (`qwen-image-2.1-F16.gguf`) via Unsloth Studio | 14.2 GB | Qwen Research | [unsloth/Qwen-Image-2.1-GGUF](https://huggingface.co/unsloth/Qwen-Image-2.1-GGUF) |
| Planner + judge 1 | **Qwen3.8 27B** vision (`UD-Q4_K_M` + `mmproj-F16`) | 16.5 + 0.9 GB | Apache-2.0 | [unsloth/Qwen3.8-27B-GGUF](https://huggingface.co/unsloth/Qwen3.8-27B-GGUF) |
| Judge 2 | **Gemma 4 26B-A4B** QAT (`UD-Q4_K_XL` + `mmproj-F16`) | 14.2 + 1.2 GB | Apache-2.0 | [unsloth/gemma-4-26B-A4B-it-qat-GGUF](https://huggingface.co/unsloth/gemma-4-26B-A4B-it-qat-GGUF) |
| Judge 3 | **Qwen3.6 35B-A3B** MTP (`UD-IQ4_NL` + `mmproj-F16`) | 18.5 + 0.9 GB | Apache-2.0 | [unsloth/Qwen3.6-35B-A3B-MTP-GGUF](https://huggingface.co/unsloth/Qwen3.6-35B-A3B-MTP-GGUF) |
| Image → 3D shape | **Pixal3D** `pixal3d_bf16` + DINOv3 encoder + two TRELLIS-2 VAEs, run in ComfyUI | 11 + 1.2 + 2 GB | MIT | [Comfy-Org/Pixal3D](https://huggingface.co/Comfy-Org/Pixal3D) · [ComfyUI](https://github.com/comfyanonymous/ComfyUI) |
| Upscaler (photos) | **RealESRGAN x4plus** | 67 MB | BSD-3 | [release v0.1.0](https://github.com/xinntao/Real-ESRGAN/releases/download/v0.1.0/RealESRGAN_x4plus.pth) · [project](https://github.com/xinntao/Real-ESRGAN) |
| Upscaler (anime) | **RealESRGAN x4plus anime 6B** | 18 MB | BSD-3 | [release v0.2.2.4](https://github.com/xinntao/Real-ESRGAN/releases/download/v0.2.2.4/RealESRGAN_x4plus_anime_6B.pth) |
| Upscaler (3D renders) | **4x-UltraSharp** | 67 MB | CC BY-NC-SA 4.0 | [Kim2091/UltraSharp](https://huggingface.co/Kim2091/UltraSharp) |
| Auto-rig | **Make-It-Animatable** weights (`output/best/new`) + Mixamo template data | 2.3 GB | Apache-2.0 | [jasongzy/Make-It-Animatable](https://huggingface.co/jasongzy/Make-It-Animatable) · [jasongzy/Mixamo](https://huggingface.co/datasets/jasongzy/Mixamo) · [code](https://github.com/jasongzy/Make-It-Animatable) |
| Text → motion | **UniMate** `unimate_uniml3d_f60_v3` (one checkpoint) | 1.2 GB | **CC BY-NC 4.0** | [Linzhan/UniMate](https://huggingface.co/Linzhan/UniMate) · [code](https://github.com/Friedrich-M/UniMate) |
| T-pose for odd-posed 3D models | **SkinTokens** F16 GGUF | 1.2 GB | MIT | [LocalAI-io/SkinTokens-GGUF](https://huggingface.co/LocalAI-io/SkinTokens-GGUF) · [skin-tokens.cpp](https://github.com/localai-org/skin-tokens.cpp) |
| FBX → GLB converter used by MIA | **FBX2glTF** | small | see repo | [release v0.9.7](https://github.com/facebookincubator/FBX2glTF/releases/tag/v0.9.7) |
| Face landmarks | **MediaPipe Face Landmarker** (included in `models/`) | 3.6 MB | Apache-2.0 | [guide](https://ai.google.dev/edge/mediapipe/solutions/vision/face_landmarker) |

Licences are taken from each model card at the time of writing; read them before commercial use. The judge models are interchangeable: change `JUDGES` and `VLM_MODEL` in `homunculus/config.py`. UniRig ([VAST-AI-Research/UniRig](https://github.com/VAST-AI-Research/UniRig)) and Puppeteer ([Seed3D/Puppeteer](https://github.com/Seed3D/Puppeteer)) were evaluated as alternative riggers but are not used.

## Quick start

```bash
git clone https://github.com/So-bonkers/Homunculus && cd Homunculus
# install everything first: see Setup above
./launch.sh                # starts the app and opens http://127.0.0.1:8765
```

You also need **Unsloth Studio** running its API on `127.0.0.1:8888` (it serves Qwen-Image 2.1 edit and the VLM judges; `systemctl --user restart unsloth-api` is what the pipeline suggests when it stalls) and Blender on your `PATH`. Then drop a picture on the home page, press **Start run**. From a terminal:

```bash
.venv/bin/python -m homunculus.orchestrate ~/Downloads/my_picture.jpg --name myhero \
    --anim "walks forward" --anim "dances salsa, stepping side to side and swaying the hips"
```

Close other GPU-heavy applications first. Output: `runs/myhero/07_rig/myhero_final.fbx` (+ `.glb`), clips in `runs/myhero/09_animate/clips/`, `contact_sheet.png`, `report.md`.

Double-clicking **`homunculus.html`** also works: it opens the app if the server is up, otherwise starts it (the first time your browser asks which app opens `homunculus://` links; choose *homunculus launcher*).

## The app
Everything happens in one local web app. The server only runs while you work with the pipeline: a run starts it, or use `./web.sh start` / `./web.sh stop` / `./web.sh open [name]`.
- **Home:** a live 3D turntable of your latest character, the **New run** launcher (drop an image, choose outfit, review mode and window, image style, start-from stage and the Mixamo zip, then **Start run**) and the library of runs with live status and **Stop** buttons. Runs started here run as their own background unit, so closing the browser or restarting the server doesn't stop them; start the same name again to resume.
- **Run page** (`/#/run/<name>`): the pipeline as a node graph (drag to pan, Ctrl/⌘+scroll to zoom, click a stage for its details and snapshots), a **Your call** panel at every judge decision (large candidates, enlarge, choose / accept / reject, notes, countdown), and tabs for the **Activity** timeline, an interactive **3D model** viewer (textured / rigged, clay, wireframe, bones) and the live **Log**. Downloads (FBX, GLB, Mixamo zip) are in the side panel.
- **Look = All · I pick (the default):** the first redraw makes one image per look (As is + the five styles below). The run waits for you to pick one, in any review mode except Off (Off uses As is). That image becomes the chosen redraw, and its look is used for the rest of the run. **Redraw all looks** makes a new set (your notes go into it).
- **Look:** restyle the character in the redraw: *As is* (keep the picture's style), *3D film* (Pixar-like), *Game* (Unreal-like realistic), *Anime 3D* (cel-shaded), *Clay* (claymation / vinyl toy) or *Chibi* (big head; risky for the auto-rigger). The judges then score identity by hair, outfit and colours instead of the exact face. On the command line: `--look choose|asis|stylized|game|anime3d|clay|chibi`.
- **Looks tab** (run page): **Generate look previews** makes one redraw per look from that run's input (about a minute each; it queues behind a running run), shown next to the raw input and the run's own redraw. **Fork with this look** restarts from Redraw with that look. Command line: `.venv/bin/python -m homunculus.look_preview <name>`.
- **Manual review = you are the judge:** redraws and 3D shapes come one at a time (**Use this** / **Try another**, with your notes going into the next try), the rig is yours to accept or reject, and the AI judges are skipped entirely. The redraw model stays loaded between tries, so each new redraw starts right away.
- **Your call beats the judges:** in Override or Manual review, the review panel opens as soon as the candidates exist. If you choose, accept, reject or ask for a redo before the judges finish, the remaining judges are skipped (the running one is stopped and unloaded) and your decision is used. "Keep judges' decision" lets them finish. With review Off the judges always decide.
- **Fork** (on a run that isn't running): pick a stage to restart from, add instructions (they go into the redraw prompt and to every judge from then on), change outfit / review / zip, and start either a **new run** (only the finished stages before that point are copied; the original stays untouched) or **restart the same run**.
- `runs/<name>/progress.html` is now just a shortcut that opens the run page.

## Hands
Hand-specific steps are **off** (`HAND_REFINE_EARLY` and `HAND_VIEWS` in `homunculus/config.py`): no hand close-up redraw before the 3D step, no hand renders or finger counting in the shape check (the judges are told not to judge hands), and no hand/fist close-ups in the rig check (4 pose images instead of 7). The redraw prompt still asks for an open-hand pose, and the code stays in place if you ever switch them back on.

## Order of the stages, rigger and animation
`ingest → upscale → plan → redraw → pick → prepare → 3D shape → shape check → colour → auto-rig → rig check → animate → texture → report`
- **Colour** (before rigging, CPU, ~20 s) projects the redraw's front onto the mesh, so the rig is built and checked on a coloured model. **Texture** (last) is the full one (fitted face, extra views); it is put on the rig and on every animation clip.
- **Rigger:** pick it in the launcher or the Fork dialog (`--rigger mia|mia_normal`): Make-It-Animatable with its default or its normal-aware skin weights. The one you pick is tried first; the other is the fallback.
- **Animate** uses [UniMate](https://github.com/Friedrich-M/UniMate) (text to motion for any rig, run locally from `unimate/`, own python 3.10 environment). Type prompts in the launcher ("Animations", one per line) or any time later in the run page's **Animate** tab; each gives clips of 1.6 s that play in the 3D viewer and download as GLB and FBX with the final texture. Wherever you type prompts (launcher, Fork dialog, Animate tab) there is a **Preset library** of 190 ready-made prompts in 10 categories (walk & run, jump & move, idle, combat, ranged & magic, dance, gestures, sports, everyday & work, hero & drama): click a prompt to add or remove it, search across all of them, or press 🎲 Surprise me. Every preset can be **previewed**: a ▶ on the prompt plays it in a small 3D player with a **Male / Female** switch (2 takes each, Add / Remove right there, credits under the player); see *Preset previews* below. Prompts describe one motion, not the character ("walks forward"; the "An object ..." wording UniMate was trained on is added for you). Command line: `--anim "walks forward" --anim "jumps in place" --anim-reps 2`, or for a finished run `python -m homunculus.animate <run> --prompt "..."`.
- **Licence:** UniMate's code is MIT, but its **weights are CC BY-NC 4.0 (non-commercial)** and part of its training data has provenance questions: fine for experiments, check before commercial use.

### Preset previews

The ▶ previews in the prompt library are clips generated once by `python -m homunculus.preset_clips` (resumable, waits for the GPU lock, ~90 min per character) and written to `homunculus/static/presets/`. They are **not stored in git** (about 3 GB); the library works without them, just without the ▶ buttons. Characters: male "miles Morales spiderman rigged" by J.azali, female "Spider Gwen Low Poly" by So7ion, both CC BY 4.0 (see [THIRD_PARTY.md](THIRD_PARTY.md)). The female model has no skeleton, so the job rigs it with Make-It-Animatable first. Edit `homunculus/static/prompt_library.js` and rerun to animate new presets.

## Starting from a 3D model (STL, OBJ, PLY, GLB, FBX)
Drop the model into the launcher instead of a picture (command line: give the model file as the input). There is no reference picture, so:
1. **Prepare:** parts are welded, loose debris and a separate display base removed, heavy meshes reduced to ~300k triangles, the model scaled to 1.8 m with UVs and a blank texture.
2. **Orient and describe:** the planner looks at four grey views to find up and the front (you can pick the front on the run page), then invents colours and materials for it.
3. **Paint:** the image model paints the exact grey front render (one per look by default); paintings whose outline moved are flagged, since the painting is projected back onto your mesh pixel for pixel.
   **Not in a T-pose?** If the planner sees a humanoid that is not in a T/A-pose (arms hanging, an action pose), the model is first rigged with SkinTokens (`riggers/`, any pose in, ~3 min on the GPU), the skeleton's joints are rotated into a T-pose, and that pose is baked into the mesh (`blender_tpose.py`), so the painting, rig and animation all see a T-posed model. Limits: humanoids only; capes, long hair and loose cloth get dragged along with the arms; SkinTokens' skeleton has no finger bones (the hands keep their own shape); a model without legs stays without legs. Switch off with `TPOSE_POSED = False`.
4. **Texture, rig, rig check:** as for picture runs; your geometry is kept as it is (no Pixal3D, no face reshape). Action poses get a warning: the auto-rigger expects a T/A-pose.

## How the face and texture are made (new runs)
1. **Sharp face before 3D:** the chosen redraw's face is redrawn as a close-up at full resolution *before* Pixal3D, so the mesh gets real eye sockets, nose and lips.
2. **Face reshape (before rigging):** the mesh's eyes, nose and mouth are moved (front of the face only, at most a few mm) to where the reference has them. If the mesh face is featureless, features are first painted onto a render of it to find where they belong.
3. **Texture (before rigging, so the rig is built on the finished textured model):** the redraw's front is projected onto the clothes and body; the face is fitted with landmarks (or painted onto the mesh render, then the reference warped onto it); then the model is turned (head ±35°, body ±60°, back), the image model cleans each view's render without changing its layout, and each view is projected back where it sees the surface best. A view whose outline the image model changed is skipped.
Switches in `homunculus/config.py`: `FACE_REFINE_EARLY`, `FACE_RESHAPE`, `TEXTURE_VIEWS`, `FACE_FIT`.

## Handy options

| you want to… | do this |
|---|---|
| continue after a crash or reboot | run the exact same command again (finished steps are skipped) |
| redo from a step, e.g. the 3D model | add `--from mesh` (steps: `ingest upscale plan edit pick upscale_edit mesh mesh_check texture rig rig_check report`) |
| redo one step only | add `--only rig_check` |
| tell it the picture is anime/cartoon art | add `--style anime` (or `photo`, `3d_render`) |
| review / override the judges | after every judge decision (redraw pick, 3D shape check, rig check) the progress page at `http://127.0.0.1:8765/<name>/progress.html` shows a yellow **Review** box with the renders and the judges' verdict. You can **Use #k** / **None of these – redraw again** (pick), **Accept – continue** / **Reject – try again** (shape, rig), or keep the judges' decision, and type **observations** that are added to the next redraw prompt and shown to the judges. `--review override` (default): you have 60 s (`--review-grace 300` for longer) before the judges' decision stands. `--review manual`: the run waits for you. `--review off`: fully automatic. |
| get a zip to upload to Mixamo (their free auto-rigger and animations) | add `--zip` → `exports/mixamo_<name>.zip` (OBJ + MTL + texture; Mixamo rejects Blender's FBX, so use this). For a finished run: `.venv/bin/python -m homunculus.export_zip <name>` |
| shirtless character (bare torso and arms; avoids sleeve-cuff layers that tear at the wrists) | add `--outfit shirtless` |
| unclothed character (keep the bare body and anatomy, no clothing or censoring added) | add `--outfit nude` (default `--outfit keep` redraws the outfit from the image). Only for generated or fictional adult characters. |
| change the redraw wording itself | edit the templates in `homunculus/prompts.py` (`EDIT`, `OUTFIT`, `HANDS`, `STYLE`). The prompt actually used for a run is saved in `runs/<name>/02_plan/edit_prompt.txt`. |
| run it in the background (survives closing the terminal) | `systemd-run --user --unit=homunculus-myhero --working-directory=$HOME/homunculus --setenv=DISPLAY=$DISPLAY --setenv=WAYLAND_DISPLAY=$WAYLAND_DISPLAY --setenv=DBUS_SESSION_BUS_ADDRESS=$DBUS_SESSION_BUS_ADDRESS .venv/bin/python -m homunculus.orchestrate ~/Downloads/my_picture.jpg --name myhero`, then watch `runs/myhero/progress.html` (the `--setenv` parts let it open the page and send notifications) |

## Tips for good results
- **Framing:** one person, full body, facing the camera.
- **Pose:** arms away from the body and hands open work best. The pipeline redraws everyone into this "A-pose" anyway, but a closer start keeps the face more faithful.
- **Size:** small or blurry pictures are fine (it upscales first). Text overlays and busy backgrounds get removed for you.

## When something goes wrong
- **The terminal shows an error and stops:** look at the end of `runs/<name>/run.log`, then rerun the same command.
- **Studio stopped answering:** `systemctl --user restart unsloth-api`, then rerun.
- **The pose test shows torn or stretched skin:** rerun with `--from edit` for a new redraw.
- **A stale GPU lock after a crash:** delete `runs/.homunculus.lock` if no run is alive.

## Limitations (honest list)
- Tested on one AMD machine; `setup.sh` has not been run from a clean install, and some model sources (Pixal3D bf16, the SkinTokens GGUF, the UniMate checkpoint) are only described, not scripted.
- One character at a time; humanoids only for the rig, the T-pose bake and the animation.
- Hands are not rebuilt: the hand close-up steps are off, and Pixal3D's fingers are as good as they come out of the shape model.
- UniMate output quality varies (see above); its weights are non-commercial.
- UniRig and Puppeteer were evaluated as alternative riggers but are not wired into the pipeline.

## Project layout
`homunculus/` orchestrator, stages, web server and static app · `comfy/` ComfyUI helpers and graphs · `mia/` rigger runner and pose test · `unimate/bin/` Blender shim for UniMate · `presets/` preview characters · `tools/` sample-GIF rendering · `systemd/` the web unit · `setup.sh`, `launch.sh`, `web.sh`, `homunculus.html`.

## Credits and licences
Code: GPL-3.0-or-later ([LICENSE](LICENSE)): anyone may use and modify it, and distributed modifications must stay open under the same licence. Third-party tools, models and the two CC BY preview characters, with their required attribution: [THIRD_PARTY.md](THIRD_PARTY.md).
