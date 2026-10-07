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
