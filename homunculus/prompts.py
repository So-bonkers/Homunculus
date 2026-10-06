"""Prompts for the local VLM (planner + judge) and the Qwen-Image re-pose template."""

PLAN = """You are preparing a reference image for an image-to-3D pipeline that ends in an auto-rigged game character.
Look at the image and describe the main person so an image-editing model can redraw them in a neutral A-pose
without changing who they are or what they wear. Be concrete (colours, materials, logos, hairstyle, build).
Reply with ONLY this JSON:
{"style": "photo" | "anime" | "3d_render",
 "subject": "one sentence: who/what the character is, gender presentation, age range, body build",
 "body": "body shape, proportions, musculature and visible anatomy/skin details to preserve",
 "face": "facial features to preserve: face shape, eyes and eye colour, eyebrows, nose, lips, facial hair, skin, makeup. Describe the features only, NOT the current expression (no 'open mouth', 'shouting', 'smiling'). If a full-face helmet, mask or visor hides the face, say so and describe that object instead (colour, visor tint), not facial features",
 "face_visible": true | false,   (false when a full-face helmet, mask or visor hides the face, so there is no face to keep),
 "hair": "hairstyle, length and colour",
 "clothing": "every garment top to bottom with colours, materials, logos, numbers, stripes",
 "footwear": "shoes/boots or barefoot",
 "accessories": "gloves, jewellery, bands, or 'none'",
 "remove": ["every thing that is NOT part of the character: text overlays, captions, watermarks, logos on the image, background objects, other people, ball, ..."],
 "cropped": ["body parts cut off by the image border, e.g. 'right foot', or empty list"],
 "loose_parts": ["long hair, capes, skirts, scarves or other parts that could touch the arms/legs, or empty list"]}"""

ORIENT = """These are four grey renders of the same untextured 3D model, seen from four sides (the camera turns 90 degrees each time;
the label above each image gives its number). Reply with ONLY this JSON:
{"upright": true | false, "upside_down": true | false, "lying_down": true | false,
 "front_view": <number of the view that shows the character's FRONT (the face / chest side), 1-4>,
 "humanoid": true | false, "pose": "t-pose" | "a-pose" | "posed" | "other",
 "base": true | false, "notes": "one short sentence: what the model is"}
"upright" means standing the right way up (head at the top). "base" means a display base or plinth is attached under the feet."""

PLAN_MESH = """You are preparing to paint an untextured grey 3D model (the image is a grey front render of it) for a pipeline that ends in an
auto-rigged game character. There is no reference picture: invent a fitting, coherent colour scheme and materials that suit the shapes
(armour, clothing, skin, hair...). Be concrete about colours and materials. Reply with ONLY this JSON:
{"style": "photo" | "anime" | "3d_render",
 "subject": "one sentence: who/what the character is, gender presentation, age range, body build (as the shapes suggest)",
 "body": "body shape and proportions as modelled",
 "face": "facial features to paint: skin tone, eye colour, eyebrows, lips, facial hair (no expression). If the model wears a full-face helmet or mask, describe the helmet instead",
 "face_visible": true | false,   (false when a full-face helmet, mask or visor hides the face),
 "hair": "hairstyle as modelled and the colour you choose",
 "clothing": "every garment / armour piece top to bottom with the colours and materials you choose",
 "footwear": "shoes / boots and their colours, or barefoot",
 "accessories": "EVERY modelled item that is not skin or the main clothes: gloves / fingerless gloves, wrist straps, bracers, arm bands, belts, holsters, thigh straps, pouches, jewellery... each with its colour, or 'none'",
 "remove": [], "cropped": [], "loose_parts": []}
Look closely at the close-up images of the head and the hands (they follow the full view): small modelled details there (gloves on the palms,
straps around the wrists, earrings) are easy to miss in the full view and must be listed under accessories."""

PAINT = ("Paint this untextured grey 3D model render as a finished, fully coloured and textured character: {subject}. Face: {face}. Hair: {hair}. "
         "Clothing and colours: {clothing}. Footwear: {footwear}. Accessories: {accessories}. Keep the image EXACTLY as it is in shape: the same pose, "
         "silhouette, proportions, framing and size, every edge and fold in the same place; only add colour, materials, texture and surface detail. "
         "Paint every modelled item (gloves, straps, belts, holsters, pouches) as its own material in its listed colour, never as bare skin. "
         "Eyes clearly open, neutral expression, mouth closed. Plain light grey background, soft even lighting. No text. {style}")

def paint_prompt(plan, fix_notes="", look="asis"):
    j = lambda x: (", ".join(x) if isinstance(x, list) else str(x or "")).strip().rstrip(".")
    p = PAINT.format(subject=j(plan.get("subject")) or "the character", face=j(plan.get("face")), hair=j(plan.get("hair")), clothing=j(plan.get("clothing")),
                     footwear=j(plan.get("footwear")), accessories=j(plan.get("accessories")) or "none", style=style_text(plan, look))
    return p + (" " + fix_notes if fix_notes else "")

POSES = {
    # video tip (PixelArtistry): "put character into a T-pose for 3D rigging, front view, arms spread apart" gives clean, aligned fingers
    "tpose": ("Pose: a T-pose for 3D rigging, standing upright and facing the camera, head straight, both arms stretched straight out "
              "sideways at shoulder height and horizontal, palms facing forward toward the camera (NOT down), all five fingers straight and "
              "fanned out flat in view with clear gaps between them, thumbs pointing up, "),
    "spread": ("Pose: a neutral A-pose standing upright and facing the camera, head straight, arms straight and held about 40 degrees away "
               "from the body with clear empty space between each arm and the torso, palms facing forward with all five fingers spread "
               "apart and visibly separated, thumbs pointing outward away from the hands, "),
    "relaxed": ("Pose: a neutral A-pose standing upright and facing the camera, head straight, arms straight and held about 25 degrees away "
                "from the body with clear empty space between each arm and the torso, hands relaxed with the palms facing the thighs, "
                "fingers straight and slightly apart with small visible gaps, thumbs forward, "),
}
HANDS = POSES   # backwards-compatible name
POSE_RULE = {"tpose": "T-pose facing the camera with the arms horizontal", "spread": "neutral A-pose facing the camera",
             "relaxed": "neutral A-pose facing the camera"}

EDIT = ("Redraw this exact character as a clean full-body reference image for 3D modelling. {subject}. "
        "Keep the identity exactly: {face}; hair: {hair}. "
        "Neutral relaxed facial expression: mouth closed with the lips gently together, eyes clearly wide open (not squinting, eyelids raised, whites of the eyes visible) looking straight at the camera, no smile, no frown. {outfit}"
        "{hands}legs straight and apart at shoulder width with a clear gap between the thighs and between the knees, "
        "feet flat on the ground pointing forward. {loose}"
        "Show the whole body from the top of the head to the soles of both feet, centred, nothing cut off{cropped}. "
        "Remove {remove}. Plain flat light grey studio background, soft even lighting, no shadows on the background, "
        "no text, no captions, no watermark. {style}")

STYLE = {"photo": "Photorealistic, sharp, highly detailed photograph.",
         "anime": "Same anime illustration style and colours as the input, crisp clean lines.",
         "3d_render": "Same 3D-render style and materials as the input, sharp and detailed."}

# target looks: the redraw restyles the character (the default "asis" keeps the input's own style, see STYLE)
LOOK = {
    "stylized": ("Restyle the character as a stylised 3D animated-film character (Pixar / Disney style): smooth simplified forms, soft clean skin, "
                 "slightly larger expressive eyes, clean solid colours, soft studio lighting, rendered like a frame from a 3D animated film. "
                 "Keep the same person recognisable: same hairstyle and hair colour, same skin tone, same outfit, colours and accessories."),
    "game": ("Restyle as a realistic high-end video-game character (Unreal Engine 5 render): clean realistic skin and materials, crisp detail, "
             "even neutral lighting, no photo grain, no depth of field. Keep the same person, hairstyle, hair colour, outfit, colours and accessories."),
    "anime3d": ("Restyle as a cel-shaded anime 3D game character (Genshin Impact style): flat clean colours with soft cel shading, thin clean outlines, "
                "anime facial features, crisp stylised hair locks. Keep the same hairstyle, hair colour, outfit, colours and accessories."),
    "clay": ("Restyle as a handmade claymation / vinyl toy figure: matte soft surfaces, simplified smooth sculpted shapes, subtle clay texture, "
             "gentle studio lighting. Keep the same hairstyle, hair colour, outfit, colours and accessories."),
    "chibi": ("Restyle as a chibi character: oversized head about one third of the body height, short limbs and a small body, cute simplified "
              "features, clean colours, rendered like a 3D figurine. Keep the same hairstyle, hair colour, outfit, colours and accessories. "
              "Hands still open with five separated fingers."),
}
LOOK_LABEL = {"asis": "As is", "stylized": "3D animated film", "game": "Game character", "anime3d": "Anime 3D (cel-shaded)", "clay": "Clay / vinyl toy", "chibi": "Chibi"}
LOOK_UPSCALE = {"stylized": "3d_render", "game": "3d_render", "anime3d": "anime", "clay": "3d_render", "chibi": "3d_render"}

def style_text(plan, look="asis"):
    return LOOK.get(look) or STYLE.get(plan.get("style", "photo"), STYLE["photo"])

PICK = """You are the quality gate for an image-to-3D-to-rig pipeline. Image 1 is the ORIGINAL character.
The following images are CANDIDATE redraws numbered 1..{n} (the label above each image says which).
A good candidate: {identity_rule}; {outfit_rule}; neutral facial expression with the mouth closed; {pose_rule};
arms clearly separated from the torso; both hands open with five separately visible fingers; legs apart with a gap
between the thighs; the full body from head to both feet inside the frame; plain grey background; no text, captions,
watermarks or coloured streak/residue artefacts on the clothes or skin (natural skin tones such as nipples, lips or blush are NOT residue);
no extra or missing limbs/fingers.
Ignore the background completely (it is cut away automatically before the 3D step), and treat small colour streaks or
residue ON the character as minor (they are cleaned automatically): report them in "problems" and set "clean": false, but
they must NOT make a candidate unusable. A candidate is unusable ONLY for real problems: wrong identity, wrong pose, arms or
legs touching the body, fused/missing/extra fingers or limbs, or body parts cut off by the frame.
Score every candidate, then pick the best usable one. Reply with ONLY this JSON:
{{"candidates": [{{"id": 1, "identity": 0-10, "outfit": 0-10, "pose_ok": true|false, "hands_ok": true|false,
                  "full_body": true|false, "clean": true|false, "problems": ["..."]}}],
 "best": <id of the best usable candidate, or 0 if none is usable>,
 "fix_notes": "if best is 0: one or two short sentences to add to the edit prompt to fix the common problems, else empty"}}"""

MESH_CHECK = """You are checking the SHAPE of a 3D model generated from a reference image. Image 1 is the reference image.
The next images are untextured grey renders of the 3D model (a label above each image says what it shows): full body FRONT and SIDE,
a FACE close-up, then each hand seen from FOUR directions. Use all four views of each hand together: a finger hidden in one view is usually visible in another when COUNTING; but a hand
FAILS if ANY view shows fingers that are twisted, bent in impossible directions, merged/fused, spiky or broken, an extra or missing
digit, or a thumb in the wrong place. Be strict about hands - they are the most common defect.
There is deliberately NO colour or texture yet (it is added at the end) - judge only the geometry:
- one single body with all limbs, no missing/extra limbs, no large detached pieces;
- arms not fused to the torso, legs not fused together;
- each hand has five distinct fingers (not a mitten blob);
- head and face have a plausible human shape (nose, eyes sockets, mouth, ears) roughly matching the reference build;
- clothing shapes roughly match the reference.
Noisy hair surface and small surface bumps are acceptable. Reply with ONLY this JSON:
{"pass": true|false, "score": 0-10, "problems": ["..."]}"""

RIG_CHECK = """You are checking an automatically rigged 3D character posed by its skeleton. Images:
1 = rest pose, 2 = walking pose (front), 3 = walking pose (three-quarter), 4 = waving with an open hand,
5 = close-up of the waving hand, 6 = close-up of a closed fist (left hand), 7 = closed fist (right hand).
These poses are DELIBERATE test poses; judge only how the mesh deforms, not whether the pose looks natural.
Bad deformation: skin or clothing stretched into spikes or strings, torn/separated surfaces, limbs collapsing into thin shapes,
fingers merging into one mass or bending through each other, parts left floating in space.
Acceptable: mild pinching at the armpit/groin/knee, fingers slightly thick, a fist that is not perfectly tight.
Reply with ONLY this JSON:
{"pass": true|false, "score": 0-10, "tearing": true|false, "fingers_ok": true|false, "problems": ["..."]}"""
MESH_CHECK_NOHANDS = """You are checking the SHAPE of a 3D model generated from a reference image. Image 1 is the reference image.
The next images are untextured grey renders of the 3D model (a label above each image says what it shows): full body FRONT and SIDE, and a FACE close-up.
There is deliberately NO colour or texture yet (it is added at the end) - judge only the geometry:
- one single body with all limbs, no missing/extra limbs, no large detached pieces;
- arms not fused to the torso, legs not fused together;
- head and face have a plausible human shape (nose, eyes sockets, mouth, ears) roughly matching the reference build;
- clothing shapes roughly match the reference.
Do NOT judge the hands or fingers at all (they are not checked in this pipeline). Noisy hair surface and small surface bumps are acceptable.
Reply with ONLY this JSON:
{"pass": true|false, "score": 0-10, "problems": ["..."]}"""

RIG_CHECK_NOHANDS = """You are checking an automatically rigged 3D character posed by its skeleton. Images:
1 = rest pose, 2 = walking pose (front), 3 = walking pose (three-quarter), 4 = arm raised (waving).
These poses are DELIBERATE test poses; judge only how the mesh deforms, not whether the pose looks natural.
Bad deformation: skin or clothing stretched into spikes or strings, torn/separated surfaces, limbs collapsing into thin shapes, parts left floating in space.
Acceptable: mild pinching at the armpit/groin/knee. Do NOT judge the hands or fingers at all.
Reply with ONLY this JSON:
{"pass": true|false, "score": 0-10, "tearing": true|false, "problems": ["..."]}"""




OUTFIT = {
    "keep": "Keep the outfit exactly: {clothing}; footwear: {footwear}; accessories: {accessories}. ",
    "shirtless": ("REMOVE THE SHIRT: the character is shirtless - take off the jersey/shirt/top completely, no sleeves, no fabric on the "
                  "upper body; bare chest, bare shoulders, bare arms, bare wrists and bare hands with a natural athletic torso in the same "
                  "skin tone. Keep the same shorts, socks and {footwear} as in the input. "),
    "nude": ("The character is unclothed: keep the bare body exactly as in the input, {body}, including the breasts, nipples, "
             "genital area and skin details; do not add any clothing, underwear, censor bars, blur or smoothing. "
             "Barefoot unless the input shows footwear. Accessories: {accessories}. "),
}
PICK_OUTFIT = {
    "keep": "same outfit and colours as the original",
    "shirtless": "shirtless (bare torso and arms) with the rest of the outfit below the waist matching the original",
    "nude": "unclothed like the original with the body and anatomy preserved (no added clothing, underwear, censoring, blur or smoothed-away details)",
}

def pick_prompt(n, outfit="keep", pose="tpose", look="asis", mesh=False):
    from . import config as _C
    return _pick(n, outfit, pose, look, mesh, hands=_C.HAND_VIEWS)

def _pick(n, outfit, pose, look, mesh, hands):
    if mesh:     # mesh-first: Image 1 is the grey model; a candidate must keep its exact shape (it is projected back onto it)
        return PICK.format(n=n, identity_rule="a fully painted version of the grey 3D model in Image 1 with EXACTLY the same pose, silhouette and proportions",
                           outfit_rule="convincing, coherent colours and materials", pose_rule="the same pose as Image 1").replace(
                           "Image 1 is the ORIGINAL character.", "Image 1 is the untextured grey 3D model.")
    ident = ("same person/identity" if look not in LOOK else
             f"the same character deliberately RESTYLED as {LOOK_LABEL[look]} (the restyling of the face, proportions and rendering is intended: "
             f"judge identity by hairstyle, hair colour, outfit, colours and overall look, and score how well the {LOOK_LABEL[look]} style was achieved)")
    t = PICK.format(n=n, identity_rule=ident, outfit_rule=PICK_OUTFIT[outfit], pose_rule=POSE_RULE.get(pose, POSE_RULE["spread"]))
    if not hands:      # hands are not checked anywhere in the pipeline: do not let them decide the pick
        t = (t.replace("both hands open with five separately visible fingers; ", "").replace("no extra or missing limbs/fingers.", "no extra or missing limbs.")
              .replace("fused/missing/extra fingers or limbs", "fused/missing/extra limbs") + "\nIgnore the hands and fingers completely: always answer true for \"hands_ok\".")
    return t

FACE_REFINE = ("This is a close-up crop of a character's head from a full-body image. Redraw it as a sharp, highly detailed close-up of "
               "the same face at higher resolution. Keep EVERYTHING in exactly the same place: same framing, same head size and position, "
               "same pose and angle, same hairline and hairstyle, same eyes, eyebrows, nose, lips, ears, skin tone and lighting, same "
               "neutral expression with the mouth closed, and the eyes clearly open (not squinting). Only add fine detail and sharpness. Same background. No text. {style}")

HAND_REFINE = ("This is a close-up crop of a character's hand from a full-body image (arm held out to the side). Redraw the hand as a sharp, "
               "detailed open hand turned so its PALM FACES THE VIEWER (not seen edge-on): five fingers fanned out flat in view with clear gaps "
               "between them, the thumb pointing up and clearly apart, natural finger joints and fingernails. Keep the wrist where it is and the "
               "same sleeve, cuff, bracer or glove, the same skin colour, lighting and background. Same hand size. No text. {style}")

FACE_REPAINT = ("This is a front render of a 3D model's head whose face is blank or blurry. Paint a clear, detailed face onto it exactly where "
                "its face is: {face}. Eyes open looking straight ahead, mouth closed, neutral expression. Keep the image layout exactly the same: "
                "same head position, size and outline, same hair, ears, neck and clothing, same background. Only add the facial features. {style}")

VIEW_FIX = ("This image is {shot} of a textured 3D character model, seen {view}. Improve only the texture quality: make blurry, smeared, "
            "stretched, doubled or patchy areas of {what} clean and sharp, consistent with the rest ({desc}). Do not change the composition: keep "
            "the exact same framing and crop, the same pose, silhouette, size and position of everything, the same colours and design and the "
            "same plain background. Do not add, remove, move or redraw anything else. {style}")

VIEW_PAINT = ("This image is {shot} of a 3D character model seen {view}. Parts of it are still untextured plain grey. Paint those grey parts so "
              "they match the already painted parts and the character ({desc}): the same colours, materials and style, continuing the clothing, "
              "hair, skin and boots naturally around the body; also clean up any smeared areas. Do not change the composition: keep the exact same "
              "framing, pose, silhouette, size and position of everything and the same plain background. Do not add or remove anything. {style}")

def edit_prompt(plan, fix_notes="", hands="tpose", outfit="keep", look="asis"):
    def j(x):
        return (", ".join(x) if isinstance(x, list) else str(x or "")).strip().rstrip(".")
    remove = j(plan.get("remove")) or "any text or background clutter"
    loose = plan.get("loose_parts") or []
    loose_txt = (f"Keep {j(loose)} hanging behind or beside the body so it does not touch or cover the arms, hands or legs. " if loose else "")
    cropped = plan.get("cropped") or []
    cropped_txt = (f"; complete the {j(cropped)} that was cut off" if cropped else "")
    if outfit == "shirtless":        # the shirtless instruction goes first so the redraw model does not keep the shirt
        pass
    outfit_txt = OUTFIT[outfit].format(clothing=j(plan.get("clothing")), footwear=j(plan.get("footwear")),
                                       accessories=j(plan.get("accessories", "none")) or "none", body=j(plan.get("body")) or "same proportions")
    p = EDIT.format(subject=j(plan.get("subject", "The character")), face=j(plan.get("face")), hair=j(plan.get("hair")), outfit=outfit_txt,
                    loose=loose_txt, cropped=cropped_txt, remove=remove, hands=POSES[hands],
                    style=style_text(plan, look))
    if look in LOOK: p = p.replace("Keep the identity exactly: ", "Keep the character recognisable: ")
    return p + (" " + fix_notes if fix_notes else "")


def no_face(p):
    """The judge prompt for a character whose face is hidden (full-face helmet, mask): nobody should look for eyes, a nose or a mouth."""
    return p.replace("head and face have a plausible human shape (nose, eyes sockets, mouth, ears) roughly matching the reference build;",
                     "the head has a plausible shape roughly matching the reference build; a full-face helmet, visor or mask is expected, so do NOT look for eyes, nose, mouth or ears;")
