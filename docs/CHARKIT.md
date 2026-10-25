# charkit: a character kit from one picture, judged locally

`homunculus/charkit` turns what was done by hand for Ren on 2026-10-24/25 into a staged, resumable pipeline. A local vision-language model makes the routine calls (which redraw keeps the
likeness, whether a mannequin shows, which TRELLIS seed is cleaner). Claude, or you, only works through `kits/<name>/needs_review.json` and looks at the final contact sheets.

    .venv/bin/python -m homunculus.charkit ~/Desktop/OFF-BEAT/art/characters/final/<name>.png --name <name> [--from STAGE] [--until STAGE] [--only STAGE] [--panel]
    .venv/bin/python -m homunculus.charkit .../ren.png --name ren --dry-run [--dry-run-cpu] [--fresh]          # no GPU: Ren's recorded outputs and answers

Options: `--describe FILE.json` gives the item list yourself instead of asking the judges. `--dressed-ref GLB` places the items on a model you choose (e.g. a fused one like `ren_fused.glb`).
`--thumb-engine cycles` renders the judges' thumbnails on the CPU. `--panel` makes all three judges of `config.JUDGES` vote; the default is Qwen3.8 alone (`config.SHEET_JUDGES`).

## Files

| path | what |
|---|---|
| `kits/<name>/charkit.json` | state: input, description, item list, per stage `{status, seconds, note, groups}`, the picks, every decision in order, the judge cache |
| `kits/<name>/needs_review.json` | list of entries `{id, stage, item, problem, status: "open", chosen, reasons, candidates (numbers + verdicts), images}` |
| `kits/<name>/sheets/` | a contact sheet per stage and item (pick framed green, rejected red, numbers and verdict under each); `final_pictures.png`, `final_meshes.png` |
| `kits/<name>/{prep,head,body,pictures/<item>,items,thumbs}/` | pictures: 4x, crop, candidates (`front_s<seed>.png`, `prompt_r<round>.json`), background cuts, mesh thumbnails |
| `runs/<name>_charkit/{trellis,place,assemble,gates,logs}/` | the heavy outputs (TRELLIS seeds, placement JSONs, the assembled .blend, poke test, logs of every unit) |

The state file is `charkit.json`, so it does not clash with `homunculus.kit`'s `kits/<name>/state.json`. A dry run writes only under `kits/_charkit_test/<name>` and `runs/_charkit_test/<name>`.

## Stages

| stage | job (deterministic) | numeric gates | judges | retries |
|---|---|---|---|---|
| prep | 4x-UltraSharp via spandrel (ComfyUI venv, GPU), rembg `birefnet-general` (CPU) | 4x size; cut: one main piece | - | rembg menu: `birefnet-general`, `isnet-general-use` |
| describe | - | - | list garments (region upper/lower/full/outer), shoes, hair, accessories (region head/face/neck/wrist/waist/hand) | none: if there is no usable answer, a generic list goes to review (fix it with `--describe`) |
| head | crop the head and shoulders from the 4x picture (27 % of the figure height, Ren's 0.935 aspect, 992 px high), 8 Qwen-Image edits (seeds 940..) | eye-line tilt ≤ 2.0° (exactly `tools/head_tilt.py`); mirror asymmetry of the face band ≤ 0.095 | all numerically passing candidates shown with the crop: same face, upright, no glasses, no ink lines; pick the likeness | 2 re-rolls |
| body | redraw of the original with the approved head as `--ref` (seeds 960..) | a free margin ≥ 0.8 % on every side (head and feet in), figure ≥ 55 % of the height, one figure, tilt ≤ 4° | framing, same face and clothes, hands, no ink, no glasses, style | 2 re-rolls |
| pictures | per item, 4 seeds (980..), all items in ONE ComfyUI session: base body (bald, shorts, barefoot, the head as a reference), garments on a ghost mannequin, shoes as a pair, hair as a hairpiece, accessories as products | foreground fraction per kind, one object (two for shoes), not cropped | the right item only; ANY mannequin part, person or skin rejects | 2 re-rolls; then the background cut of each pick (rembg menu) and of the clean body picture (the dressed reference) |
| trellis | TRELLIS.2 1024_cascade, 4K texture, seeds 42,7, the dressed reference + all items in ONE run | loads, ≥ 5000 faces, outline aspect within ×1.65 of the picture's (not for shoes), open / non-manifold edges, garment lid | thumbnails (front, side, back; also below for garments) next to the item's picture: whole item, no extra geometry, no lid | 2 re-rolls: seeds 123,2024 then 5,77 |
| place | `tools/ren_graft/align_item.py ITEM REF --box <region>` | residual ≤ 0.5 % of the reference height; placed height / region height in 0.4-1.7 | - | menu: upright/12 yaw steps/0.7, all axes/12/0.7, upright/24/0.6 |
| assemble | `tools/ren_graft/assemble_kit.py` via `blender_assemble.py` (the character's garment list replaces Ren's), the picked seed linked as `<item>/s42/textured.glb` | poke-through ≤ 0.5 % of the tested body vertices (rays along the body's normals) | a render: one coherent character, no poke-through, nothing misplaced | gap menu 0.004 then 0.008 |
| rig, bake | TODO hooks (status `todo`, run every time, do nothing) | | | |
| report | final contact sheets, the open review entries in the log | | | |

Regions (fractions of the dressed reference's height, from Ren's boxes on `ren_fused.glb`) are in `prompts.REGIONS`. Which garment openings may have lids (`assemble_kit.py` GARMENTS) is in `prompts.LIDS`.

### Where the thresholds come from (measured on Ren's recorded outputs)

- Head tilt: Ren's 8 redraws measure +0.9, −1.05 (941, the pick), −0.2, 1.5, 1.1, 0.1, 0.8 and 2.5°. 947 fails at 2.0°.
- Head symmetry: 0.076-0.107, with 941 at 0.085. 942 fails at 0.095. The number only gates. It does not rank likeness: 941 is 5th of 8 by the numbers, so the head question shows every passing candidate.
- Body: all 8 of Ren's pass (top margin 8-16 %, bottom 4-6 %).
- Kit pictures: all of Ren's pass the numbers, including hoodie 980 (mannequin hands) and 981 (a whole mannequin). Only the judges can reject those; the dry-run fixture records them as rejected.
- Mesh lid: 35 vertical rays (a 7x5 grid over the middle 60 % of the opening; one grid per leg at trouser cuffs) from outside the opening inwards. A lid is when >= 70 % of them stop within 8 % of the height.
  Ren's hoodie s7 has a real lid (its view from below shows the hem closed): 0.97. The open s42 measures 0.40 (some rays catch the double hem wall). The joggers measure 0.16 at the cuffs and 0.0 at the waist, open in the renders.
  A lid is informational (assemble_kit.py removes lids) plus 0.5 on the score, so a lid-free seed ranks first; the judges see the view from below.
- Placement: Ren's 4 hand-made placements are 0.24-0.34 % (`runs/ren_kit2/place.log`). The pipeline running `align_item.py` itself (`--dry-run-cpu`, 2026-10-25) gets the same numbers: body 0.335 %, hoodie 0.346 %, joggers 0.241 %, hair 0.245 %.
  It also placed the three items that were never placed by hand: headphones 0.33 %, glasses 0.20 %, and shoes, which **fail** (0.95 % at best after the 3 menu entries).
  TRELLIS makes the pair as ONE mesh laid out like the product photo, so its spacing does not match the feet. The fix (not built): split the pair into its two pieces (as `tools/ren_graft/pieces.py` does) and place each on one foot.
  A small residual on a small box does not prove the item sits right (the glasses are a tiny box): look at the assembly render.

## Judges

- `judge.Judge.session(queries)` answers a batch. Each judge in the list is loaded once (`vlm.load`: unload everything, wait for headroom), answers every query, and is unloaded; `gpu.unload_llms()` runs at the end.
- Every question asks for JSON only: `{"pick": i | -1, "candidates": [{"index", "pass", "issues"}]}`, `{"pass", "issues", "note"}` for a check, or the description shape.
- Issues come from the fixed vocabulary `prompts.ISSUES`; other words become `other`.
- `judge.parse_json` tolerates thinking text, code fences, trailing commas, single quotes and Python booleans. A reply that cannot be read is asked again with a firmer ending, twice.
- Panel (`--panel`): per candidate, the majority of the judges that answered (ties pass); the pick is the commonest pick (on a tie, the first judge's).
- Answers are cached in `charkit.json` by a hash of the question plus the pictures' size and mtime, so a resumed run never asks again.
- No usable answer at all: the numerically best candidate is taken and an entry goes to review.
- Self-test of the parser: `.venv/bin/python -m homunculus.charkit.judge --selftest`.

## VRAM hand-off

One heavy model at a time on the 24 GB card. Each phase takes the shared lock `runs/.homunculus.lock` (the orchestrator, `homunculus.kit` and `tools/redraw_front.py` use the same one) and releases it after, so other jobs can slip in between:

1. prep: upscale (lock; ComfyUI and Studio unloaded) → rembg on the CPU
2. describe: judges (lock) → unload
3. head: redraws, 8 (lock, ComfyUI) → judges (lock) → re-rolls repeat this pair at most twice
4. body: the same
5. pictures: ALL items' redraws in one ComfyUI session → ONE judge session for all items → re-rolls of only the failed items, batched again → background cuts (CPU)
6. trellis: `gpu.free_all` (stops ComfyUI, unloads Studio) → ONE TRELLIS run for every item and seed (a 38 GB-capped unit) → mesh gates and thumbnails (CPU, and workbench OpenGL) → ONE judge session
7. place: CPU only (12 GB units)
8. assemble: Blender on the CPU (16 GB unit) → a single judge question

Every unit is `systemd-run --user --wait --collect -p MemoryMax=...` (12 GB by default, 38 GB TRELLIS, 16 GB Blender assembly); its log goes to `runs/<name>_charkit/logs/`.

## Retry and escalation rules

- A group is one thing to choose (the head, the body, each item, each item's mesh). Round 0 is the first batch.
- A re-roll draws new seeds (the seed block shifted by one round). It also adds at most 2 sentences from the fixed menu `prompts.TWEAKS`, picked by the issues seen most often in the last round that produced candidates (numeric issues count too), never one tried before. TRELLIS re-rolls change only the seeds.
- At most `MAX_REROLLS = 2` re-rolls, so 3 rounds. A round that produces no new candidates still counts.
- Still unresolved: the best candidate is taken (judge pass > numbers pass > fewest issues > score) and an entry goes to `needs_review.json` with every candidate's numbers and verdicts, the issues seen and the tweaks tried. The run goes on with that candidate.
- A stage that crashes is marked `failed` and the run stops; resume with `--from`. A stage's own problems never stop the run.
- A re-run of a stage marks all of that stage's earlier open review entries `superseded`. An item that now passes leaves no open entry behind.

## Dry run

`--dry-run` uses `homunculus/charkit/fixtures/ren_dryrun.json`:

- **artifacts**: where the hand-made run left each output (the 4x picture, background cuts, candidates per stage and item, TRELLIS folders, placements, the assembled .blend).
- **answers**: the recorded decisions by file name: head 941, body 961; base body 980, hoodie 982 (980/981 rejected for the mannequin), joggers 983, the rest 982; TRELLIS s42 everywhere.

What runs for real in a dry run:

- the state and the stage order, the select/re-roll/escalation loop and the review queue
- every 2D numeric gate, the mesh gates (CPU, in the TRELLIS venv)
- the head crop, contact sheets, the placement-box arithmetic, building the assembly folder

What does not run: no upscale, no Qwen-Image, no judges, no TRELLIS, no Blender.

`--dry-run-cpu` also runs the CPU-only jobs for real: rembg, Cycles-on-CPU thumbnails, `align_item.py` ICP and the poke test.

Re-rolls in a dry run find no recorded candidates, so an unresolved group goes through both re-rolls to the review queue. A scenario fixture (all hoodie pictures rejected, the joggers' judge unusable) tested exactly that.

## Untested (as of 2026-10-25)

- **No live run of any GPU stage through charkit.** That covers the real judges (the prompts were never answered by Qwen3.8/gemma/Qwen3.6), the in-process batched redraws, the spandrel upscale script, the TRELLIS batch unit and the GPU-lock hand-off between phases. The GPU was in use by another session while this was built.
- Judge quality: whether Qwen3.8 at 640 px reliably sees mannequin hands, thin ink lines or glasses, and picks the likeness the user would. Calibrate against the recorded picks (`kits/_charkit_test/*/charkit.json` has the questions).
- The describe answer for other characters (item keys, regions); the generalised prompts for female, child, dress (`full`) and outer garments.
- Shoe placement as one rigid pair (fails, see above).
- The workbench thumbnails (only Cycles-on-CPU was tried: 16 meshes x 3-4 views in about 2 minutes), the assembly through `blender_assemble.py` and the poke test: there was no recorded `.blend`, because the other session's assembly now writes GLBs.
- The lid test is calibrated on one real lid (Ren's hoodie s7) only.
- The head crop on characters with hats or big hair (the crop height is a fixed fraction of the figure).
- Rigging and baking: hooks only.
