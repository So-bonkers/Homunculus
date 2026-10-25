"""Everything charkit says to a model: the redraw prompts (generalised from Ren's hand-made run: kits/ren_kit2/make_pictures.sh and the head/body redraws of 2026-10-24),
the FIXED menu of prompt tweaks a re-roll may add, the closed vocabulary of issues the judges may name, the judge questions (all answered as JSON), and the regions of the
dressed reference model where each kind of item is placed (align_item.py --box, as fractions of the reference's height)."""

STYLE = ("Clean style: soft smooth painted shading like a high quality 3D animated film, NO ink outlines, no black line art. "
         "Even soft front lighting, plain light grey background, nothing else in the picture, no text.")

# what the judges may call a problem; anything else they write is mapped to "other" (judge.clean_issues)
ISSUES = ["glasses", "ink_outlines", "different_face", "tilted", "not_frontal", "asymmetric", "cropped", "bad_hands", "wrong_style", "wrong_pose", "wrong_clothes",
          "mannequin_visible", "person_visible", "skin_visible", "wrong_item", "extra_items", "missing_part", "multiple_objects", "text",
          "lid", "extra_geometry", "fused_parts", "wrong_shape", "texture_bad", "holes", "poke_through", "misplaced_item", "floating_item", "other"]

# the fixed menu a re-roll picks from (at most MAX_TWEAKS sentences, chosen by the issues seen most often in the failed round; numeric issues count too)
TWEAKS = {
    "glasses": "Remove the glasses completely: nothing in front of the eyes, the eyes and eyebrows fully visible.",
    "ink_outlines": "Absolutely no black outlines and no line art anywhere: the forms are painted with soft shading only.",
    "different_face": "Keep the face identical to the reference: the same eyes, nose, mouth, jaw, eyebrows and skin tone.",
    "tilted": "The head is perfectly upright and level: the two eyes at exactly the same height.",
    "not_frontal": "Facing the camera exactly straight on: both sides of the face and both ears equally visible.",
    "asymmetric": "The face is seen exactly from the front, left and right halves mirror images of each other.",
    "cropped": "The whole subject fits in the picture with a margin of empty background on every side.",
    "bad_hands": "Both hands relaxed and open with five separate fingers each, clearly visible beside the thighs.",
    "wrong_style": "Match the clean painted style of the reference picture exactly.",
    "wrong_clothes": "Keep every garment exactly as in the reference picture: the same cut, colours and details.",
    "mannequin_visible": "Nothing holds the item: no mannequin, no dress form, no stand, no hands, no neck form; the inside of the garment is visible at its openings.",
    "person_visible": "There is no person at all in the picture: the item alone on the background.",
    "skin_visible": "No skin anywhere in the picture.",
    "wrong_item": "Show exactly this one item from the reference picture and nothing else.",
    "extra_items": "Only this one item; remove every other object, garment and accessory.",
    "multiple_objects": "One single object in the middle of the picture.",
    "missing_part": "Show the complete item with all of its parts.",
}
MAX_TWEAKS = 2

def tweak_text(issues, used=()):
    """The tweak sentences for a re-roll: the commonest issues (a list with repeats) that have a menu entry and were not tried yet."""
    order = sorted(set(issues), key=lambda i: (-issues.count(i), ISSUES.index(i) if i in ISSUES else 99))
    keys = [i for i in order if i in TWEAKS and i not in used][:MAX_TWEAKS]
    return keys, " ".join(TWEAKS[k] for k in keys)

PRON = {"male": ("he", "his", "He", "His"), "female": ("she", "her", "She", "Her")}
UNDER = {"male": "plain fitted dark grey athletic shorts that end mid-thigh: bare chest, bare arms, bare legs, bare feet",
         "female": "plain fitted dark grey athletic shorts that end mid-thigh and a plain fitted dark grey sports top that covers the chest: bare arms, bare legs, bare feet",
         "child": "plain knee-length dark grey shorts and a plain fitted dark grey short-sleeved t-shirt: bare lower arms, bare lower legs, bare feet"}     # as homunculus.kit.UNDER: a child gets a modest base body

def _p(d): return PRON["female" if d.get("sex") == "female" else "male"]
def has_glasses(d): return any(a.get("region") == "face" for a in d.get("accessories", []))
def no_glasses(d): return f" {_p(d)[2]} does NOT wear glasses: no glasses at all, the eyes fully visible." if has_glasses(d) else ""

def head(d):
    who = d.get("who") or "character"
    return (f"Redraw this picture as a clean head-and-shoulders portrait of the same {who} for 3D modelling: exactly the same face, eyes, nose, mouth, eyebrows, skin tone, hairstyle "
            f"and the clothing at the shoulders; the head perfectly upright and level, facing the camera straight on, looking straight into the camera, symmetric.{no_glasses(d)} {STYLE}")

def body(d):
    who = d.get("who") or "character"; he = _p(d)[2]
    return (f"Redraw the character from the first picture as a clean full-body front view for 3D modelling: exactly the same {who}, the same face as in the second picture, the same hairstyle, "
            f"the same clothes, colours, shoes and accessories, the same standing pose with the arms hanging slightly away from the body, facing the camera straight on.{no_glasses(d)} "
            f"The whole figure from the top of the hair to the soles of the shoes in view, with a little space above the head and below the feet. {STYLE}")

def base_body(d, build=""):
    he, his, He, His = _p(d); who = d.get("who") or "character"; under = UNDER["child" if d.get("age") == "child" else ("female" if d.get("sex") == "female" else "male")]
    gone = [g["key"].replace("_", " ") for g in d.get("garments", [])] + [a["key"].replace("_", " ") for a in d.get("accessories", [])]
    build = build or d.get("build") or "same"
    return (f"Redraw the character from the first picture as a neutral base body for 3D modelling: exactly the same {who}, the same face as in the second picture, the same skin tone, "
            f"the same {build} build and proportions, the same standing pose with the arms hanging slightly away from the body, facing the camera straight on. "
            f"{He} is completely BALD: no hair at all, a smooth shaved scalp of skin. {He} wears ONLY {under}. No {', no '.join(gone + ['glasses', 'shoes', 'jewellery'])}. "
            f"The whole body from head to feet in view. {STYLE}")

def item(it, d):
    """The kit picture of one item (garment on a ghost mannequin, shoes as a product pair, hair as a hairpiece, accessory as a product photo)."""
    k, desc = it["kind"], it.get("description") or it["key"]
    if k == "garment" and it.get("region") == "lower":
        return (f"Show only the {desc} from this picture as a clothing product photo on an invisible ghost mannequin: the trousers alone, front view, hollow, the same shape, colour, "
                f"length and fit as worn in the picture, with the waistband and the leg openings as in the picture, arranged as if worn by an invisible person standing straight. "
                f"No person, no skin, no shoes, no other clothing. {STYLE}")
    if k == "garment":
        return (f"Show only the {desc} from this picture as a clothing product photo on an invisible ghost mannequin: the garment alone, front view, hollow, the same shape, colour and size "
                f"as worn in the picture, with all of its details, arranged as if worn by an invisible person standing straight with the arms slightly away from the body. "
                f"No person, no head, no skin, no hands, no other clothing, no accessories. {STYLE}")
    if k == "shoes":
        return (f"Show only the pair of {desc} from this picture as a product photo: the two shoes side by side, a three-quarter front view from slightly above, the same design, laces and "
                f"colours as in the picture. No person, no feet, no legs, no socks, nothing else. {STYLE}")
    if k == "hair":
        return (f"Show only the {desc} of this {d.get('who') or 'character'} as a hairpiece on an invisible head: the same hairstyle, length, volume and fringe as in the picture, front view, "
                f"as if worn by an invisible person. No face, no skin, no ears, no neck, no clothing, nothing else, the space where the face would be is empty background. {STYLE}")
    return (f"Show only the {desc} from this picture as a product photo: a front or three-quarter front view, the same design, shape and colour. "
            f"No person, no face, no neck, no clothing, nothing else. {STYLE}")

# --- judge questions (every answer is JSON; judge.py parses and cleans them) ------------------------------------------------
_PICK_JSON = ('Answer with ONLY this JSON (no other text): {"pick": <index of the best acceptable candidate, or -1 if none is acceptable>, '
              '"candidates": [{"index": 0, "pass": true, "issues": []}, ...one entry per candidate...]}. '
              f'"issues" uses only these words: {", ".join(ISSUES)}.')

DESCRIBE = ("This is a painted reference picture of one game character. List what the character is made of, for building a 3D character kit in separate parts. "
            "Answer with ONLY this JSON (no other text):\n"
            '{"sex": "male" or "female", "age": "child" or "teen" or "adult" or "older", "who": "a short noun phrase such as young man or older woman", '
            '"build": "a few words on the body build", "skin": "skin tone in a few words", '
            '"hair": {"present": true, "description": "colour, length and style"}, '
            '"garments": [{"key": "one_word_name", "region": "upper" or "lower" or "full" or "outer", "description": "colour, material and details, as for a product listing"}], '
            '"shoes": {"present": true, "description": "colour and design of the pair"}, '
            '"accessories": [{"key": "one_word_name", "region": "head" or "face" or "neck" or "wrist" or "waist" or "hand", "description": "colour and design"}]}\n'
            "garments: every separate piece of clothing (a top, trousers or a skirt, a jacket worn over the top as region outer, a dress as region full). "
            "accessories: glasses (region face), headphones, hats, scarves, jewellery, bags, watches. Do not list underwear or anything that is not visible.")

def ask_head(d, n):
    return (f"Picture 1 is a crop of a painted {d.get('who') or 'character'}. Pictures 2 to {n + 1} are candidates 0 to {n - 1}: redraws of it for 3D modelling. "
            "A candidate passes only if ALL of these hold: it is clearly the same person (same face shape, eyes, nose, mouth, eyebrows, skin tone); the head is upright and faces the camera straight on; "
            "it has NO glasses; it has NO black ink outlines or line art (soft painted shading only); head and shoulders fully in the picture. "
            "Pick the passing candidate whose face is most like picture 1. " + _PICK_JSON)

def ask_body(d, n):
    return (f"Picture 1 is a painted {d.get('who') or 'character'}; picture 2 is the approved clean head. Pictures 3 to {n + 2} are candidates 0 to {n - 1}: clean full-body redraws for 3D modelling. "
            "A candidate passes only if ALL of these hold: the whole figure is in the picture (top of the head and both feet visible, nothing cut off); the same face as picture 2 and the same clothes and colours as picture 1; "
            "a front view in a relaxed standing pose; both hands look like normal hands; soft painted shading with NO black ink outlines; no glasses; the style matches picture 2. "
            "Pick the best passing candidate. " + _PICK_JSON)

def ask_item(it, n):
    what = {"base": "the character's neutral base body: bald, wearing only plain fitted shorts (and a plain top for a woman or a child), barefoot, the same face",
            "garment": f"ONLY the {it.get('description') or it['key']} on an INVISIBLE ghost mannequin (hollow garment, nothing inside it)",
            "shoes": f"ONLY the pair of {it.get('description') or 'shoes'} as a product photo, no feet",
            "hair": f"ONLY the {it.get('description') or 'hair'} as a hairpiece on an invisible head (no face, no skin)",
            "accessory": f"ONLY the {it.get('description') or it['key']} as a product photo"}[it["kind"]]
    extra = ("Reject any candidate where hair, clothes other than the shorts, shoes, glasses or accessories remain, or the face differs. " if it["kind"] == "base" else
             "Reject any candidate where a mannequin or ANY part of one is visible (a full figure, a torso form, a neck form, mannequin hands or feet, a stand), "
             "or a person, skin, a face, or any other item is visible. ")
    return (f"Picture 1 is the reference the item was taken from. Pictures 2 to {n + 1} are candidates 0 to {n - 1}, each meant to show {what}. "
            f"{extra}Also reject a candidate whose item differs in shape or colour from the reference. Pick the best passing candidate. " + _PICK_JSON)

def ask_mesh(it, n):
    return (f"Picture 1 is the picture of a {it.get('description') or it['key']} that was turned into 3D. Pictures 2 to {n + 1} are candidates 0 to {n - 1}: renders of each 3D model "
            "from the front, the side and the back. A candidate passes only if the model is the whole item with the right shape and colours, with no extra geometry, no parts fused that should be apart, "
            "no big holes, and (for clothing) its openings are OPEN: a flat cap or 'lid' closing a hem, cuff, collar or waistband is the issue lid. Pick the best passing candidate. " + _PICK_JSON)

def ask_assembled(n_items):
    return ("This is a render of a 3D character assembled from separate parts (a base body with garments, shoes, hair and accessories placed on it). "
            "Does it look like one coherent dressed character? Problems: poke_through (body visible through clothing), misplaced_item, floating_item, missing_part, extra_geometry, other. "
            'Answer with ONLY this JSON: {"pass": true, "issues": [], "note": "one short sentence"}')

# --- where each kind of item sits on the dressed reference (y up, faces +z): half-width in x, bottom and top as fractions of the height from the feet, half-depth in z,
#     all in units of the reference's height (Ren's boxes on ren_fused.glb, height 1.0: hoodie -0.35..0.35, -0.06..0.40; joggers -0.2..0.2, -0.45..0.05; hair -0.1..0.1, 0.40..0.52)
REGIONS = {"upper": (0.35, 0.44, 0.90, 0.20), "outer": (0.40, 0.40, 0.92, 0.24), "full": (0.40, 0.15, 0.90, 0.24), "lower": (0.20, 0.05, 0.55, 0.20),
           "hair": (0.10, 0.90, 1.02, 0.12), "feet": (0.20, -0.02, 0.10, 0.20), "head": (0.13, 0.87, 1.04, 0.15), "face": (0.10, 0.88, 0.97, 0.15),
           "neck": (0.15, 0.78, 0.92, 0.15), "wrist": (0.45, 0.35, 0.62, 0.20), "waist": (0.22, 0.48, 0.62, 0.20), "hand": (0.45, 0.30, 0.55, 0.20), "body": (0.60, -0.10, 1.10, 0.60)}
LIDS = {"upper": ("bottom",), "outer": ("bottom",), "full": ("bottom",), "lower": ("bottom", "top")}     # which openings of a garment TRELLIS may close with a lid (assemble_kit.py GARMENTS)
