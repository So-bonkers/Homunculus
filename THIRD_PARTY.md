# Third-party code, models and assets

Homunculus itself is GPL-3.0-or-later (see LICENSE). It drives other projects that are **not** part of this repository and have their own licences; read them before you use the results, especially commercially.

| Component | Used for | Where | Licence note |
|---|---|---|---|
| [ComfyUI](https://github.com/comfyanonymous/ComfyUI) + Pixal3D weights | upscaling, image → 3D | `comfy/ComfyUI` (cloned by setup.sh) | GPL-3.0 (ComfyUI); Pixal3D weights (single-image and multiview checkpoints) MIT (model card) |
| [Unsloth Studio](https://github.com/unslothai/unsloth) | serves Qwen-Image 2.1 edit + the VLM judges | installed separately | see upstream |
| Qwen-Image 2.1, Qwen3.8, Qwen3.6, Gemma 4 (Unsloth GGUFs) | redraw, planning, judging | downloaded by Studio | Qwen-Image: Qwen Research licence; the three judges: Apache-2.0 (model cards). Full list with links: README, Setup |
| RealESRGAN, 4x-UltraSharp | upscaling | `comfy/ComfyUI/models/upscale_models` | RealESRGAN BSD-3; **4x-UltraSharp CC BY-NC-SA 4.0** |
| [Make-It-Animatable](https://github.com/jasongzy/Make-It-Animatable) | auto-rig, 52-bone Mixamo skeleton | `mia/repo` | weights Apache-2.0 (model card); its Mixamo template data may need a Hugging Face login |
| [UniMate](https://github.com/Friedrich-M/UniMate) | text → motion | `unimate/` | code MIT, **weights CC BY-NC 4.0 (non-commercial)** |
| [skin-tokens.cpp](https://github.com/localai-org/skin-tokens.cpp) + [SkinTokens GGUF](https://huggingface.co/LocalAI-io/SkinTokens-GGUF) | rigs odd-posed meshes so they can be put in a T-pose | `riggers/skintokens` | weights MIT (model card) |
| [UniRig](https://github.com/VAST-AI-Research/UniRig), [Puppeteer](https://github.com/Seed3D/Puppeteer) | evaluated as alternative riggers (not used by default) | `riggers/` | see upstream |
| Blender | renders, bakes, FBX/GLB export | system install | GPL |
| three.js | the 3D viewer in the web app | `homunculus/static/vendor/three` | MIT |
| MediaPipe face landmarker | face fit | `models/face_landmarker.task` | Apache-2.0 |

## Preview characters (animation previews)

Licensed under Creative Commons Attribution 4.0 (http://creativecommons.org/licenses/by/4.0/). Changes: the male model was stripped to its skeleton and skinned meshes and exported as FBX; the female model, an unrigged OBJ, was converted to a textured GLB (the rig is made by Make-It-Animatable at preview time).

- "miles Morales spiderman rigged" (https://skfb.ly/p8wOX) by J.azali is licensed under Creative Commons Attribution (http://creativecommons.org/licenses/by/4.0/). → `presets/male/`
- "Spider Gwen Low Poly" (https://skfb.ly/oxwZX) by So7ion is licensed under Creative Commons Attribution (http://creativecommons.org/licenses/by/4.0/). → `presets/female/`

The characters shown are Spider-Man-franchise likenesses; the CC BY licence covers the artists' models, not the underlying trademarks. Remove `presets/` and the sample GIFs if you redistribute this commercially.
