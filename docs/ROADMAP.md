# Roadmap (ideas, not promises)

Collected wishes, with what exists today and a first idea for each.

## Several characters in one scene
Today: one character per run (Pixal3D builds one object from one picture; rigging, animation and texture all assume one body).
Idea: split the input picture per character (segmentation), run each as its own sub-run, then compose them in one scene with transforms; the app would show a scene with several rigged characters, each animated by its own prompt.

## Props and other artifacts with the character (a car, a weapon, ...)
Today: a prop in the picture is treated as part of the character or cut away.
Idea: generate props as **separate rigid objects** (same Pixal3D route, no rig), place them in the scene, and let a weapon follow a hand bone (parent constraint) so it moves with the animation.

## Non-human objects
Today: the pipeline assumes a humanoid (T-pose redraw, face and hand steps, Make-It-Animatable's Mixamo skeleton).
Idea: an *object mode*: skip the humanoid checks and steps, keep shape + texture (+ retexture / repair), make rigging optional (a generic skeleton for creatures; UniMate already animates arbitrary skeletons).

## High-poly shapes (millions of vertices) - distant
Today: Pixal3D's raw output is already about 4.5 million vertices; the pipeline decimates to about 250k for rigging and keeps `mesh_hi.glb`.
Idea: ship the carved raw mesh as a *high-poly export* with a baked normal map for the low-poly rig, then look at geometry super-resolution for models that start low-poly (e.g. an STL).

## Animation quality
See the notes in the project chat: a hand-pose layer (fist / open / point / thumbs-up) for fingers, best-of-N takes with a preview grid, and a trial of a human-specific text-to-motion model (HY-Motion or Kimodo) retargeted to the Mixamo skeleton.

## Turnaround sheets made locally
Today: a sheet has to come from outside (ChatGPT, a 3D render). The local Qwen-Image edit did not manage one: asked for a "back" view it drew the helmet from behind on a suit that still had the front logos and belt, and the "side" views came out as 3/4 views with the arms spread forward. Idea: one view per call with the other views as extra references, a judge gate that rejects 3/4 sides and a back that shows front logos, and a check that the four figures have the same scale and costume before the multiview shape step.

## Colour for surfaces no view faces
Today: the four horizontal views of a sheet cannot see the top of the head, palms and backs of the hands, the top and sole of a boot; they keep one flat colour, and a repaired part is one flat colour. Idea: fill the unseen texels from their painted neighbours (texture-space dilation inside each UV island), or project a generated top and bottom view.
