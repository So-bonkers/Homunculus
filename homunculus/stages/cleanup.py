"""Remove thin coloured streaks/residue that the redraw inherits from removed overlays (e.g. a caption's glow).
Only runs when the VLM reported a coloured streak/residue, and only touches thin features of that hue
(chroma differs from an 11-px median), so real clothing colours are kept. Luminance (shading) is untouched."""
import re, numpy as np
from PIL import Image
from scipy import ndimage as ndi

HUES = {"purple": (250, 345), "violet": (250, 345), "magenta": (250, 345), "pink": (250, 345), "lilac": (250, 345),
        "blue": (190, 250), "cyan": (160, 200), "green": (80, 160), "yellow": (40, 70), "orange": (15, 40), "red": (345, 15)}

def colours_from(problems):
    txt = " ".join(problems or []).lower()
    if not re.search(r"streak|residue|smudge|artefact|artifact|stain|tint", txt): return []
    return [c for c in HUES if c in txt]

def clean_residue(src, dst, problems, log=print):
    cols = colours_from(problems)
    if not cols: return src
    im = Image.open(src).convert("RGB")
    hsv = np.asarray(im.convert("HSV")).astype(float); hue = hsv[..., 0] * 360 / 255; sat = hsv[..., 1] / 255
    ycc = np.asarray(im.convert("YCbCr")).astype(float)
    med = np.stack([ndi.median_filter(ycc[..., c], size=25) for c in (1, 2)], -1)
    dev = np.abs(ycc[..., 1:] - med).max(-1)
    inhue = np.zeros(hue.shape, bool)
    for c in cols:
        a, b = HUES[c]; inhue |= ((hue >= a) & (hue <= b)) if a < b else ((hue >= a) | (hue <= b))
    # never touch residue-looking pixels inside skin (nipples, lips, blush): skip where the neighbourhood is skin-toned
    rgb = np.asarray(im).astype(float); medrgb = np.stack([ndi.median_filter(rgb[..., c], size=25) for c in range(3)], -1)
    mh = np.asarray(Image.fromarray(medrgb.astype(np.uint8)).convert("HSV")).astype(float)
    mhue = mh[..., 0] * 360 / 255; msat = mh[..., 1] / 255; mval = mh[..., 2] / 255
    skin = ((mhue <= 50) | (mhue >= 330)) & (msat > 0.12) & (msat < 0.75) & (mval > 0.25)
    mask = ndi.binary_dilation(inhue & (sat > 0.03) & (dev > 2.5) & ~skin, iterations=2) & ~skin
    out = ycc.copy(); out[..., 1:][mask] = med[mask]
    Image.fromarray(out.clip(0, 255).astype(np.uint8), "YCbCr").convert("RGB").save(dst)
    log(f"residue clean-up ({', '.join(cols)}): {int(mask.sum())} px recoloured")
    return dst
