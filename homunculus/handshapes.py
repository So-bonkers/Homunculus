"""A vocabulary of hand shapes for the hand timeline, defined the way sign-language handshapes are: a state per finger, a thumb position and how far the fingers are spread.

    finger state   ext straight | back hyperextended | lax barely curled | soft a dancer's natural hand | curved a held ball (C) | claw | hook (tips bent, knuckles straight)
                   | bent (knuckles bent, fingers straight: an L / table top) | half (a loose grip) | fist | tight
    thumb          side (along the index finger) | out (sideways, as in an L) | up (thumbs up) | across (over the fingers) | oppose (towards the fingertips, a pinch) | tucked (inside a fist)
    spread         none | slight | spread | wide    (fingers move away from the middle finger)

build() gives {pose name: library entry} in the form homunculus/handpose.py and blender_handpose.py use: degrees of curl for base / middle / tip of each finger, "thumb_out" (sideways turn of
the thumb) and "splay" (degrees away from the middle finger, per finger). SHAPES carries what the editor shows: label, category, a one-line description, search words.
The numbers are rough anatomy (a finger joint curls 0-100 degrees) tuned by looking at close-up renders on the rig (tools/hand_library.py), and checked against FineDance (dancers' hands average 20-25
degrees of curl, a real fist is not in it). Names the editor already used (open, relaxed, fist, grip, point, thumbs_up, pinch) are kept as they were: see handpose.LIB."""

STATES = {
    "ext": (0, 0, 0), "back": (-12, -6, 0), "lax": (10, 8, 5), "soft": (24, 24, 13), "curved": (35, 40, 28), "claw": (38, 66, 36), "hook": (6, 84, 48),
    "bent": (88, 3, 3), "half": (60, 70, 45), "fist": (88, 102, 66), "tight": (96, 108, 72),
}
THUMBS = {                       # (base, middle, tip) curl, thumb_out
    "side": ((4, 4, 4), 0), "out": ((0, 0, 0), 42), "up": ((0, 0, 0), 62), "across": ((46, 58, 38), 0), "oppose": ((52, 42, 22), 4), "tucked": ((16, 32, 16), 0), "hitch": ((0, 0, 0), 30),
}
SPREADS = {                      # degrees away from the middle finger: index, ring, pinky
    "none": {}, "slight": {"index": 5, "ring": 4, "pinky": 9}, "spread": {"index": 12, "ring": 9, "pinky": 20}, "wide": {"index": 20, "ring": 14, "pinky": 32},
}
FINGERS = ("index", "middle", "ring", "pinky")


def hand(index, middle, ring, pinky, thumb, spread="none"):
    e = {f: STATES[s] for f, s in zip(FINGERS, (index, middle, ring, pinky))}
    b, out = THUMBS[thumb]; e["thumb"] = b; e["thumb_out"] = out; e["splay"] = dict(SPREADS[spread]); return e


def same(state, thumb, spread="none"): return hand(state, state, state, state, thumb, spread)


# name: (label, category, description, search words, entry)
SHAPES = {
    # --- neutral
    "flat": ("Flat", "Neutral", "All fingers straight and together, thumb alongside: a flat hand, a blade.", "blade chop karate palm stop salute", same("ext", "side")),
    "spread": ("Spread", "Neutral", "All fingers straight and apart, thumb out: jazz hands, spirit fingers.", "jazz hands spirit fingers fan five", same("ext", "out", "spread")),
    "spread_wide": ("Spread wide", "Neutral", "Fingers as far apart as they go.", "fan star explode burst", same("ext", "out", "wide")),
    "soft": ("Soft", "Neutral", "A dancer's natural hand: fingers loosely curled (about 25 degrees), thumb alongside.", "natural idle loose", same("soft", "side")),
    "lax": ("Lax", "Neutral", "Barely curled: a hand that hangs limp.", "limp hang drop", same("lax", "side")),
    "back": ("Bent back", "Neutral", "Fingers pulled back past straight: a hyperextended stretch.", "stretch hyperextended arch flare", same("back", "out", "slight")),
    # --- curved
    "cup": ("Cup", "Curved", "Fingers curved and together, thumb alongside: a cupped hand.", "catch scoop hold water", same("curved", "side")),
    "c_shape": ("C shape", "Curved", "Fingers and thumb curved apart, like holding a can.", "c can ball hold", same("curved", "out", "slight")),
    "ball": ("Ball", "Curved", "Fingers curved and spread, thumb opposing: holding a ball.", "sphere orb grab hold", same("curved", "oppose", "spread")),
    "o_shape": ("O shape", "Curved", "Fingers curved, thumb meeting the fingers: an O.", "circle ring zero", same("curved", "oppose")),
    "claw": ("Claw", "Curved", "Knuckles and middle joints bent, tips curled: a claw.", "talon grab rake monster", same("claw", "out", "slight")),
    "claw_spread": ("Claw spread", "Curved", "A claw with the fingers apart.", "talon rake menacing", same("claw", "out", "spread")),
    "hook": ("Hook", "Curved", "Knuckles straight, the two upper joints bent: a hook.", "hooked bait pull", same("hook", "side")),
    "tabletop": ("Table top", "Curved", "Knuckles bent 90 degrees, fingers straight: a flat L / table top.", "bent hand l shelf", same("bent", "side")),
    # --- closed
    "fist_loose": ("Loose fist", "Closed", "A half-closed hand, thumb across.", "half fist relaxed grip", same("half", "across")),
    "fist_tight": ("Tight fist", "Closed", "Fingers pressed hard into the palm, thumb across.", "clench power punch", same("tight", "across")),
    "fist_thumb_in": ("Fist, thumb in", "Closed", "A fist with the thumb tucked inside.", "tucked baby", same("fist", "tucked")),
    "fist_thumb_out": ("Fist, thumb out", "Closed", "A fist with the thumb stuck out sideways.", "hitchhike", same("fist", "hitch")),
    "grip_wide": ("Grip, wide", "Closed", "A wide loose grip, as on a thick pole.", "hold pole bar handle", same("half", "oppose", "slight")),
    # --- pointing and counting
    "point_up": ("Point (gun)", "Pointing", "Index straight, thumb up, the rest closed: a finger gun.", "gun pistol shoot pow", hand("ext", "fist", "fist", "fist", "up")),
    "point_two": ("Two fingers", "Pointing", "Index and middle straight together, the rest closed: a double point.", "two finger double gun guns", hand("ext", "ext", "fist", "fist", "across")),
    "peace": ("Peace", "Pointing", "Index and middle straight and apart, the rest closed: a V.", "victory v bunny scissors two", hand("ext", "ext", "fist", "fist", "across", "slight")),
    "three": ("Three", "Pointing", "Index, middle and ring straight, pinky closed, thumb across.", "w count", hand("ext", "ext", "ext", "fist", "across", "slight")),
    "w_shape": ("W", "Pointing", "Index, middle and ring straight and apart, thumb on the pinky.", "w three", hand("ext", "ext", "ext", "fist", "across", "spread")),
    "four": ("Four", "Pointing", "Four fingers straight, thumb across the palm.", "count", hand("ext", "ext", "ext", "ext", "across")),
    "pinky_point": ("Pinky", "Pointing", "Only the little finger straight.", "little finger swear", hand("fist", "fist", "fist", "ext", "across")),
    "l_shape": ("L", "Pointing", "Index straight, thumb out, the rest closed: an L.", "loser l corner", hand("ext", "fist", "fist", "fist", "out")),
    # --- signs
    "rock": ("Rock on", "Signs", "Index and pinky straight, middle and ring closed, thumb across: horns.", "horns metal devil", hand("ext", "fist", "fist", "ext", "across")),
    "ily": ("I love you", "Signs", "Index, pinky and thumb out, middle and ring closed.", "love spiderman web", hand("ext", "fist", "fist", "ext", "out", "slight")),
    "shaka": ("Shaka", "Signs", "Thumb and pinky out, the other fingers closed: hang loose, call me.", "hang loose call phone surf", hand("fist", "fist", "fist", "ext", "out")),
    "ok": ("OK", "Signs", "Thumb and index meet in a ring, the other three straight and slightly apart.", "okay perfect ring", hand("curved", "ext", "ext", "ext", "oppose", "slight")),
    "thumb_out": ("Thumb out", "Signs", "Fingers loosely closed, thumb sticks out sideways.", "hitchhiker", hand("half", "half", "half", "half", "hitch")),
    # --- pinch and snap
    "pinch_open": ("Pinch, open", "Pinch & snap", "Thumb and index almost meeting, the other fingers soft: a beak.", "beak peck almost", hand("curved", "soft", "soft", "soft", "oppose")),
    "pinch_all": ("Pinch, all", "Pinch & snap", "All four fingertips gathered to the thumb tip.", "bunch gather tulip", same("curved", "oppose")),
    "snap_ready": ("Snap, ready", "Pinch & snap", "Thumb pressed on the middle fingertip, the other fingers soft: the loaded finger snap.", "snap click load", hand("soft", "claw", "soft", "soft", "oppose")),
    "snap_hit": ("Snap, hit", "Pinch & snap", "The middle finger slapped into the palm, thumb across: the moment of the snap.", "snap click slap", hand("soft", "fist", "soft", "soft", "across")),
    "flick_ready": ("Flick, ready", "Pinch & snap", "Index curled under the thumb, loaded to flick out.", "flick fling load", hand("tight", "fist", "fist", "fist", "across")),
    # --- finger wave (each finger closes in turn from the pinky)
    "wave1": ("Wave 1", "Finger wave", "Only the pinky curled, the rest straight.", "ripple pinky", hand("ext", "ext", "ext", "fist", "side")),
    "wave2": ("Wave 2", "Finger wave", "Pinky and ring curled.", "ripple ring", hand("ext", "ext", "fist", "fist", "side")),
    "wave3": ("Wave 3", "Finger wave", "Pinky, ring and middle curled.", "ripple middle", hand("ext", "fist", "fist", "fist", "side")),
    "wave4": ("Wave 4", "Finger wave", "All four fingers curled, thumb out.", "ripple index", hand("fist", "fist", "fist", "fist", "out")),
}


def build():
    """{name: entry} for every shape in SHAPES."""
    return {k: v[4] for k, v in SHAPES.items()}


def catalogue():
    """What the editor lists: [{key, label, category, description, search}] (the older poses first)."""
    older = {"open": ("Open", "Neutral", "All fingers straight, thumb alongside.", "flat palm"), "relaxed": ("Relaxed", "Neutral", "A slightly curled, easy hand.", "idle natural"),
             "fist": ("Fist", "Closed", "Fingers curled hard into the palm, thumb across.", "punch clench"), "grip": ("Grip", "Closed", "A firm half-closed grip, as on a handle.", "hold sword bat"),
             "point": ("Point", "Pointing", "Index straight, the other fingers curled.", "index finger"), "thumbs_up": ("Thumbs up", "Signs", "Fist with the thumb stuck up.", "like good"),
             "pinch": ("Pinch", "Pinch & snap", "Thumb and index pressed together.", "pick small")}
    rows = [{"key": k, "label": v[0], "category": v[1], "description": v[2], "search": v[3]} for k, v in older.items()]
    rows += [{"key": k, "label": v[0], "category": v[1], "description": v[2], "search": v[3]} for k, v in SHAPES.items()]
    return rows


# --- the wrist: how the hand sits on the forearm. flex: degrees the hand bends toward the palm (negative: back, away from the palm); dev: degrees it swings sideways (positive: toward the thumb, negative: toward
# the little finger). Human range: about 80 in, 70 back, 20 toward the thumb, 35 toward the little finger. Named by the movement, so it holds whichever way the palm faces.
WRISTS = {
    "neutral": ("Neutral", "Straight", "The hand in line with the forearm.", "level normal rest", 0, 0),
    "flex_20": ("In, small", "Bent in", "The hand bends slightly toward the palm side.", "down droop soft", 20, 0),
    "flex_40": ("In, medium", "Bent in", "The hand bends toward the palm side (about 40 degrees).", "down droop drop limp", 40, 0),
    "flex_70": ("In, deep", "Bent in", "The hand folds toward the palm side as far as it goes.", "down fold hook", 70, 0),
    "ext_20": ("Back, small", "Bent back", "The hand bends slightly back, away from the palm.", "up lift", -20, 0),
    "ext_40": ("Back, medium", "Bent back", "The hand bends back (about 40 degrees): a push, a stop sign.", "up push stop", -40, 0),
    "ext_65": ("Back, deep", "Bent back", "The hand bends back as far as it goes.", "up cock lift", -65, 0),
    "radial_10": ("Toward thumb, small", "Sideways", "The hand tilts slightly toward the thumb side.", "radial", 0, 10),
    "radial_20": ("Toward thumb", "Sideways", "The hand tilts toward the thumb side as far as it goes.", "radial", 0, 20),
    "ulnar_15": ("Toward pinky, small", "Sideways", "The hand tilts slightly toward the little-finger side.", "ulnar", 0, -15),
    "ulnar_30": ("Toward pinky", "Sideways", "The hand tilts toward the little-finger side.", "ulnar karate chop", 0, -30),
    "flex_ulnar": ("In and toward pinky", "Combined", "Bent toward the palm and tilted toward the little finger.", "down ulnar slash", 35, -25),
    "flex_radial": ("In and toward thumb", "Combined", "Bent toward the palm and tilted toward the thumb.", "down radial", 35, 15),
    "ext_ulnar": ("Back and toward pinky", "Combined", "Bent back and tilted toward the little finger.", "up ulnar", -35, -25),
    "ext_radial": ("Back and toward thumb", "Combined", "Bent back and tilted toward the thumb.", "up radial", -35, 15),
}


def wrist_lib():
    """{name: {"flex": degrees, "dev": degrees}} for the Blender layer."""
    return {k: {"flex": v[4], "dev": v[5]} for k, v in WRISTS.items()}


def wrist_catalogue():
    return [{"key": k, "label": v[0], "category": v[1], "description": v[2], "search": v[3], "kind": "wrist"} for k, v in WRISTS.items()]


# --- the palm direction: which way the palm faces, set by rolling the forearm (the elbow's twist). Absolute, not an offset: the clip's own palm direction is replaced while a label is on, and given back
# ("As the clip") when it ends. up / down are the world's; forward, back, in and out follow the torso. GVHMR sees a forearm's twist only very weakly, so this is where a person's eye does better than the video.
PALMS = {
    "as_clip": ("As the clip", "Palm", "Hand the palm back to the motion the video gave.", "reset free natural video", None),
    "palm_down": ("Palm down", "Palm", "The palm faces the floor.", "down floor press pronated", "down"),
    "palm_up": ("Palm up", "Palm", "The palm faces the ceiling: an open offering.", "up ceiling offer supinated cup", "up"),
    "palm_forward": ("Palm forward", "Palm", "The palm faces the way the dancer faces: a stop.", "front stop push", "forward"),
    "palm_back": ("Palm back", "Palm", "The palm faces behind the dancer.", "behind rear", "back"),
    "palm_in": ("Palm in", "Palm", "The palm faces the body's middle line.", "inward toward body", "in"),
    "palm_out": ("Palm out", "Palm", "The palm faces away from the body.", "outward away side", "out"),
}


def palm_lib():
    """{name: direction code or None} for the Blender layer."""
    return {k: v[4] for k, v in PALMS.items()}


def palm_catalogue():
    return [{"key": k, "label": v[0], "category": v[1], "description": v[2], "search": v[3], "kind": "palm"} for k, v in PALMS.items()]
