"""The hand-pose layer: UniMate (and any other body-motion model) does not drive fingers, so the fingers of every clip are set from a small library of hand poses chosen from
the prompt: a punch gives fists, a wave an open hand, "holds a sword" a grip, "points" a pointing hand, "thumbs up" a fist with the thumb out.
Deterministic, no model, works with any motion source. The Blender side is blender_handpose.py.
    poses_for("An object throws a quick left jab and a right cross.") -> {"left": "fist", "right": "fist"}"""
import re

# curl angles in degrees per finger joint (base, middle, tip). Fingers curl toward the palm; the thumb has its own, smaller range.
LIB = {
    "open":      {"thumb": (0, 0, 0),    "index": (0, 0, 0),    "middle": (0, 0, 0),    "ring": (0, 0, 0),    "pinky": (0, 0, 0)},
    "relaxed":   {"thumb": (6, 8, 6),    "index": (14, 16, 10), "middle": (18, 20, 12), "ring": (22, 24, 14), "pinky": (26, 28, 16)},
    "fist":      {"thumb": (22, 38, 30), "index": (85, 100, 65), "middle": (88, 102, 66), "ring": (90, 104, 68), "pinky": (92, 106, 70)},
    "grip":      {"thumb": (18, 28, 22), "index": (60, 70, 45), "middle": (64, 74, 48), "ring": (68, 78, 50), "pinky": (72, 82, 52)},
    "point":     {"thumb": (22, 38, 30), "index": (0, 0, 0),    "middle": (88, 102, 66), "ring": (90, 104, 68), "pinky": (92, 106, 70)},
    "thumbs_up": {"thumb": (0, 0, 0),    "index": (85, 100, 65), "middle": (88, 102, 66), "ring": (90, 104, 68), "pinky": (92, 106, 70), "thumb_out": 62},
    "pinch":     {"thumb": (28, 24, 14), "index": (38, 36, 16), "middle": (14, 16, 10), "ring": (16, 18, 10), "pinky": (18, 20, 12)},
}

# order matters: the first rule that matches decides. (regex, pose, which hands when the prompt does not name a side)
RULES = [
    (r"thumbs?[- ]up|thumb up", "thumbs_up", "right"),
    (r"\bpoint(s|ing)?\b|\bgestures? (toward|to)\b|\bcommands? an attack\b", "point", "right"),
    (r"\bpinch|\bpick(s)? up (a )?(coin|pin|needle)\b|\bthread", "pinch", "right"),
    (r"\b(sword|bat|club|staff|axe|hammer|spear|golf club|racket|rifle|pistol|gun|bow|shovel|rope|wheel|lever|barbell|paddle|broom|handle|holds?|carr(y|ies)|grabs?|draws? a)\b", "grip", "both"),
    (r"\b(punch(es)?|jab|cross|uppercut|boxes?|boxing|fists?|fight(s|ing)?|brawl|hits?|slams?|clench(es)?|flex(es)?|victory|knock(s)? down|rage|angr(y|ily))\b", "fist", "both"),
    (r"\b(waves?|waving|greets?|hello|clap(s|ping)?|stop(s)?|stretch(es)?|reaches?|beckons?|cast(s)? a spell|casts?|summon(s)?|channel(s)?|dance(s)?|dancing|twirl(s)?|salsa|ballet|disco|hip hop|spin(s)?|bow(s)? politely|salutes?|surprise|scared|shrugs?|celebrat\w+|cheers?|juggl\w+|yoga|swim(s)?)\b", "open", "both"),
]


def poses_for(prompt):
    """{"left": pose, "right": pose} for a prompt. A prompt that names one side ("with the right hand", "left jab") gives the other hand the relaxed pose."""
    t = re.sub(r"\s+", " ", str(prompt).lower())
    left, right = bool(re.search(r"\bleft\b", t)), bool(re.search(r"\bright\b", t)); both_named = left and right
    for rx, pose, hands in RULES:
        if re.search(rx, t):
            if hands == "right" and not (left or right): return {"left": "relaxed", "right": pose}      # a single-handed gesture: the right hand by default
            if both_named or not (left or right): return {"left": pose, "right": pose} if hands == "both" else {"left": "relaxed", "right": pose}
            return {"left": pose if left else "relaxed", "right": pose if right else "relaxed"}
    return {"left": "relaxed", "right": "relaxed"}
