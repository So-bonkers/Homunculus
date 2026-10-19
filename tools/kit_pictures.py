"""The pictures of a character kit from one picture of the dressed character (Qwen-Image edit): the base body (shorts only, or shorts and a top) and one picture per garment alone on an invisible mannequin.

    .venv/bin/python tools/kit_pictures.py --picture dez.png --out kit_dez --body male --garment "the horizontally striped orange and teal t-shirt" --garment "the blue jeans" [--seeds 2]

Writes <out>/body_s<seed>.png and <out>/garment_<n>_s<seed>.png (n from 1).  Same size as the input.  The edit sees the picture and the prompt only: it can change the face a little or the pose; look at the result."""
import os, sys, argparse
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__))); sys.path.insert(0, ROOT)
from PIL import Image
from homunculus.stages import qwen_turbo as Q
ap = argparse.ArgumentParser(); ap.add_argument("--picture", required=True); ap.add_argument("--out", required=True); ap.add_argument("--body", choices=["male", "female"], default="male"); ap.add_argument("--garment", action="append", default=[]); ap.add_argument("--seeds", type=int, default=2); a = ap.parse_args()
BODY = {"male": "plain mid-thigh grey athletic shorts and nothing else on the body: bare chest and bare arms, bare legs, bare feet",
        "female": "plain mid-thigh grey athletic shorts and a plain fitted grey sports top that covers the chest, bare arms, bare legs, bare feet"}
im = Image.open(a.picture).convert("RGB"); W, H = im.size; os.makedirs(a.out, exist_ok=True); log = lambda m: print(m, flush=True)
Q.up(log)
try:
    for s in range(a.seeds):
        p = (f"Redraw this exact adult character as a neutral base body for 3D modelling: the same face, hair, skin tone and build, standing in the same relaxed pose facing the camera with the same proportions, wearing only {BODY[a.body]}. "
             "Nothing else: no jacket, no shirt over it, no jewellery, no headphones, no hat, no bag. Plain light grey background, soft even light, full body visible head to toe.")
        Q.edit_image(im, p, 100 + s, (W, H), 1024, log).save(os.path.join(a.out, f"body_s{100 + s}.png")); log(f"body_s{100 + s}")
    for n, g in enumerate(a.garment, 1):
        for s in range(a.seeds):
            p = (f"Show only {g} from this picture, as a clothing product photo on an invisible mannequin (a ghost mannequin): the garment alone, front view, hollow, in the same shape, colour, pattern and size as in the picture, arranged as if worn by an invisible person standing straight with the arms slightly away from the body. "
                 "No person, no body, no head, no skin, no other clothing, no shoes, no accessories. Plain light grey background, soft even light.")
            Q.edit_image(im, p, 200 + s, (W, H), 1024, log).save(os.path.join(a.out, f"garment_{n}_s{200 + s}.png")); log(f"garment_{n}_s{200 + s}")
finally:
    Q.down()
print("->", a.out)
