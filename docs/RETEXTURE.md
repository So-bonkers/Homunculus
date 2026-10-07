# Retexture: change the look of one part of a finished model

The **Retexture** tab of a run page changes the texture of a brushed part, from any viewpoint, on the CPU.

1. **Brush** the part (size: slider, `[` / `]`, or Alt + scroll; no brush = the whole visible surface).
2. **Orbit** to a view that shows it (quick Front / Right / Back / Left buttons).
3. **Source of the new look**
   - **Describe it (default):** type what the part should look like and press *Generate this view*. The image model (Qwen-Image) redraws exactly what the viewer shows; the result is aligned with that camera by construction. Needs the GPU, about a minute for two takes.
   - **Reference picture (alternative):** upload a picture from any angle, orbit until the model lines up with it (the *Picture* slider overlays it), and optionally paint on the picture which pixels may be used.
4. **Apply** (CPU, about a minute): the picture is projected from the locked camera onto the brushed area and baked into the model's own UV atlas. A before / after pair rendered from the same camera shows what changed.
5. **Keep** puts the new texture on the rig and on every animation clip (the previous final files are kept as `*_before_retex`); the retextured model becomes the starting point of the next retexture.

How the projection works (`blender_retex.py`): the viewer's camera (in the model's own coordinates) gives each vertex its position in the picture; its weight is brush (soft edge) x visible (a ray cast from the camera) x facing the camera (grazing angles fade out) x inside the picture, times the picture's own mask. The baked texture is `mix(old texture, picture, weight)` through a Cycles EMIT bake at 1 sample, so seams and the rest of the model are untouched. Checked by projecting a render of the model back onto itself: the result differs from the original by 5.7 / 255 on average.

Limits: one picture and one viewpoint per job (repeat from other views for the back or sides); texture detail is limited by the picture's resolution and by the 4096 atlas; a generated view can change details inside the brushed area, so check the *after* preview before keeping it; the generation step has not yet been exercised end to end on the GPU in this build.
