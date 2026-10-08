# Current pain points

Where Homunculus still hurts, as of 2026-10-08, in rough order of how much it gets in the way. "Done" means built and tried; "partly" means a first fix exists with a known gap.

## Quality of the character

| Pain point | What it looks like | Status | Next |
|---|---|---|---|
| **Hands** | Fused or cut-off fingers, paddle hands from Pixal3D; a repair that leaves the hand floating off the arm | Partly. Repair tab (now any region, several parts per job: clay redraw, Pixal3D, merged with enforced contact, never smaller than what it replaces), open-edge check that warns or repairs automatically, wrist-bend check after rigging | Fused-but-closed fingers are not detected; repaired hands have one flat colour; a repaired mesh has not been through a full rig, animation and texture run yet; do not stack repairs |
| **Fists and fingers in animation** | Motion models do not drive fingers, so punches had no fists and hands looked like claws | Done. Hand-pose layer (fist, open, grip, point, thumbs up) chosen from the prompt | Poses are static per clip; no per-moment changes |
| **Face and eyes** | Closed eyes, a face that does not match the picture, a face carved into a helmet | Partly. Face option (auto / no face / always) for helmets and masks; face texture taken from the original picture; face close-up redraw is optional | Eye geometry is too small for Pixal3D; no face version of Repair yet; no eye-open check |
| **Fine detail lost in the redraw** | Engravings, logos and text come back different (Titus's belt symbol): the redraw works at about 576x1024 | Partly. Retexture tab, *Use the original picture*, projects the original's detail onto a brushed part | Not automatic; only works where the pose barely changes; no detail-preserving redraw |
| **Back and sides of the model are guessed** | Pixal3D invents what it cannot see; its own baked texture is a patchwork of garbled fragments (logos become noise) | Partly. *Turnaround sheet* input (`--sheet`): multiview Pixal3D shape and a projection of the four real views. One test (an F1 driver, a ChatGPT sheet): hands with five separate fingers, real back and side logos | Needs a sheet you made elsewhere: the local Qwen redraw does not produce usable side and back views yet (the back came out with the front logos, the sides at 3/4); front of the lower legs, hands and visor still show some garbled texture |
| **Texture getting worse in the second pass** | Extra generated views (face close-up, cleaned sides and back) made the model look worse than the picture | Done. Simple texture is the default; Full is opt-in | Sides and back keep Pixal3D's own texture; no PBR maps (normal, roughness) yet |

## Repair of other parts

| Pain point | What it looks like | Status | Next |
|---|---|---|---|
| **Repaired parts are one flat colour** | New hands or boots keep one colour; surfaces no view faces (palm, back of the hand, boot top and sole) are never painted | Partly. The flat colour is now the right one (sRGB fix); sheet runs repair on the coloured mesh | Fill unseen surfaces from their painted neighbours instead of one flat colour |
| **Repaired feet are worse than the originals** | Blocky boots, no toe-cap or sole detail, ragged ankle seams | Open (repair only parts that are really broken) | Higher voxel resolution for feet, a merge that does not assume an arm |
| **A lone judge is noisy** | The same rig scored 4/10 twice and then 9/10; one false rejection costs minutes | Partly. A sheet run keeps the rig and flags it | Two judges, or re-ask once before acting |

## Animation

| Pain point | What it looks like | Status | Next |
|---|---|---|---|
| **Clips do not match the prompt** | "Gives a thumbs up" came out as a lunge, "shrugs" as hands to the face. UniMate follows coarse prompts (walk, run, kick, dance) but not fine gestures | Open | Trial of a human-specific model (HY-Motion or Kimodo) retargeted to the Mixamo skeleton (a big download, not started); a 10-prompt test set with a contact sheet; several takes with a preview grid to choose from |

## Running it

| Pain point | What it looks like | Status | Next |
|---|---|---|---|
| **GPU memory is not enforced** | The watchdog only logs (the Pixal3D one in `run_px` does stop ComfyUI above 22.5 GB: it did, on a helmet-top repair donor at 23.3 GB, and the job failed); the repair redraw reached 23.2 GB, above the 22.5 GB limit, before it was resized | Open (set aside on purpose for now) | Make the soft and hard limits actually cancel or shrink a job |
| **Studio is a single point of failure** | It stalled twice after jobs were interrupted and needed `systemctl --user restart unsloth-api` | Partly. The *Check* button and `doctor` report it | Auto-restart and retry |
| **A run takes about 53 minutes** | The 3D shape stage alone is about 21 minutes, texture about 13 | Open | Cache reuse between forks, cheaper candidate rounds |
| **Disk use** | Duplicate FBX and GLB copies; raw shapes of hundreds of MB | Done. GLB only, other formats on demand through *Accept*, optional cleanup | None |
| **The 3D viewer could not open the heavy shape candidates** | Empty viewer on an 890 MB candidate | Done (light previews); not yet seen on a live run | Watch the next run |
| **Setup has never been run from scratch** | `setup.sh` was written from the working machine; some model sources are only described | Open (needs big downloads) | Test on a clean machine |

## Not supported yet

Several characters in one scene, props that go with the character (a car, a weapon in a hand), non-human objects, and a high-poly export with baked normal maps. Notes on each are in [ROADMAP.md](ROADMAP.md).

## Not yet tried end to end

Image generation in the Retexture tab (the GPU step), the automatic repair running inside a real run, the Accept step's disk cleanup, and the Repair tab's new buttons for several parts (the job logic ran from the command line; the browser flow was not clicked through).
