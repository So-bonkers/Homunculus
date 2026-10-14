# 08. Hand label vocabularies, quick-gesture timing, and smooth transitions

Researched 2026-10-14 for the hand timeline editor (`homunculus/handpose.py`, `web/src/features/animate/HandTimeline.tsx`). Goal: a precise, extensive set of hand labels for hip-hop / street dance, with a ready library to borrow from.

**How to read the tags.** Every claim is tagged:
- **[V]** verified: I read it on the primary page or paper this session (URL given).
- **[S]** secondary: a search snippet, a blog, a press article, or a third party quoting the source. Probably right, check before relying on it.
- **[U]** unverified: my own knowledge or my own engineering estimate. Treat as a starting value to tune, not a fact.

Where a page could not be fetched (HamNoSys PDF is image-heavy, a press site returned 403), I say so. No URL below was invented; each was returned by search or fetched.

**Plain-language glossary** (you are new to animation):
- **Finger joints.** Each of index/middle/ring/pinky has 3 hinge joints: MCP (knuckle at the palm), PIP (middle), DIP (near the tip). The thumb has CMC (base, a saddle joint that also swings sideways), MCP and IP. Mixamo names these `Hand<Finger>1/2/3` (thumb 1/2/3).
- **Curl.** The bend angle of a joint in degrees. 0 = straight, about 90 = a right angle. Your `LIB` in `handpose.py` already stores curl per joint (base, middle, tip).
- **Spread / abduction.** Fingers fanning apart sideways. Your current LIB has no spread; most vocabularies below do (or need it).
- **Opposition.** The thumb pad touching a fingertip (as in pinch/OK).
- **Easing.** A curve that makes a change start/end gently instead of linearly.
- **Slerp.** Spherical linear interpolation, the standard way to blend two rotations stored as quaternions.

---

## 1. Static hand shapes: what exists

### 1.1 Summary table (how each is defined, and what you can download)

| Source | Size of inventory | How a shape is DEFINED | Machine-readable? | Licence / access | Tag |
|---|---|---|---|---|---|
| **HamNoSys 4** (Hamburg Notation System) | Not a closed list: shapes are *composed*. Hanke's slides: 6 open base shapes + 6 thumb combinations, then modifiers. A 2023 paper says "12 standard hand shapes" x 4 thumb positions x 6 finger-bending types. A 2026 dataset paper took the official "HamNoSys 4 Handshapes Chart" and got **160 classes (106 selection + 54 thumb-opposition)**. The counts disagree because sources group differently. | Base form (which fingers are extended: flat, fist, index-point ...) + thumb position (4) + bending of individual fingers (6 types), fingers numbered 1 thumb to 5 pinky. | Unicode symbol set (a font) and SiGML XML; no joint angles. | Docs free to read at the Hamburg DGS-Korpus site. I did not find a licence statement. | counts [S], structure [S] |
| **SignWriting ISWA 2010** | Handshapes "from over 40 sign languages" placed in **10 groups**, keyed to ASL numbers 1 to 10. (30 is the count of *all* symbol groups, not handshapes.) Total handshape symbol count: not found. | Group (e.g. the "index" family) + fill (palm/back/side view) + rotation. Each base symbol has a Unicode code point. | Yes: Unicode/fonts, symbol keys (ISWA). No joint angles. | "All symbols in the ISWA are free to use under the SIL Open Font License" [V via search quote of the Sutton/Frost manual]. | [S] |
| **ASL-LEX 2.0 / SLPA** | 2,700+ ASL signs with phonological coding based on Brentari 1998; handshape coded by selected fingers, flexion of base/non-base joints, thumb, etc. | Per-sign features: selected fingers, flexion, thumb position, spread (the SLPA system; SLPAnnotator is the free coding tool). | Yes: CSV on OSF. Not joint angles but categorical per-finger fields. | Data: <https://osf.io/zpha4/>, browser <https://asl-lex.org>. Licence NOT confirmed (a Chapman repository copy of the *paper* is CC BY-NC-ND 4.0; the data licence must be read on OSF). SLPAnnotator is "free, open-source" per the Interspeech 2017 paper. | [S] |
| **Stokoe / Battison / others (ASL)** | Stokoe 1960: 19 "dez" shapes. Later counts: Klima ~40, Battison 45, Newkirk 54, Johnson & Liddell 150. Modern estimate 40-45 phonemes. | Letter/number symbols (A, B, 5, O, 1/G, C ...). Battison's "unmarked" core set: S/A, B, 5, O, 1/G, C. | Names/drawings only. | Academic texts. | [S] (Wikipedia and study-guide level) |
| **Feix GRASP taxonomy** (Feix, Romero, Schmiedmayer, Dollar, Kragic, IEEE T-HMS 46(1), 2016) | **33** grasp types for one hand, collapsing to **17** general hand configurations if you ignore object size | Arranged by opposition type, virtual-finger assignment, power / precision / intermediate, and thumb position (abducted/adducted). Static stable grasps only. | The Yale GRAB Lab page offers one diagram image (`taxonomy.png`); no table or database found on it. No joint angles. | Paper PDF: <https://www.eng.yale.edu/grablab/pubs/Feix_THMS2016.pdf>; page <https://www.eng.yale.edu/grablab/research_taxonomy.html> (states only "(c) 2012", no licence). | [V] |
| **Cutkosky** (1989 grasp taxonomy) | ~16 grasps (my recollection) | Power vs precision, object size/shape | Diagram only | - | [U] (not searched) |
| **HaGRID / HaGRIDv2** | v1: 18 gesture classes + `no_gesture` (553,991 images). v2: 33 classes + `no_gesture` (1,086,158 images) | Just a class name per hand crop plus boxes. Per-hand 2D landmarks auto-labelled by MediaPipe (21 points). | Images + COCO-style boxes + landmarks. Real photos, not rigs. | GitHub <https://github.com/ai-forever/hagrid>: "a variant of CC BY-SA 4.0" [V]. (A Hugging Face subset claims MIT; ignore, third-party.) | [V] |
| **VRChat standard gestures** | 7 poses (+ neutral) | Table of curled/extended per finger (below) | Yes, trivially (per-finger boolean) | Docs: <https://docs.vrchat.com/docs/valve-index> | [V] |
| **OpenXR hand tracking** (`XR_EXT_hand_tracking`) | Not shapes: a **26-joint skeleton** (wrist, palm, thumb 4, other fingers 5 each) | Joint poses | Yes, the standard joint layout | Khronos spec <https://registry.khronos.org/OpenXR/specs/1.1/man/html/XR_HAND_JOINT_COUNT_EXT.html> | joint count [V], per-finger breakdown [S] (vendor doc) |
| **MANO** (the hand model used by HaMeR, WiLoR, ARCTIC ...) | Parametric hand: **45 pose numbers = 15 joints x 3 axis-angle** (+10 shape, +3 global) | A pose is 15 rotations, so any named shape can be stored as a MANO vector | Yes | "Freely available for research purposes", **registration + licence agreement required** (<https://mano.is.tue.mpg.de/>). Commercial terms not stated on that page. | [V] for the access rule, [S] for the 45-number layout |
| **Indian mudras** (Asamyuta = one-hand, Samyuta = two-hand hastas) | Abhinaya Darpana: **28 Asamyuta + 24 Samyuta**; Natyashastra: 24 Asamyuta; Samyuta counts vary 13/23/24 by source | Name + finger description in verse ("pataka": fingers straight, thumb bent ...) | Names/pictures only; no angles | Ancient texts; modern books (e.g. "Hastha Prayogaah") are copyrighted | [S], and sources disagree on counts |
| **Ballet hand positions** | A handful ("soft/relaxed hand", fingers slightly curved, thumb near middle finger) | Prose | Names only | - | [U] |
| **Finger tutting** | Not a list but "structures": rectangle/square, triangle, diamond/rhombus, circles/loops; mostly right angles (90 degrees). Beginner sequence names: "L" shape, "field goal", rectangle, heart. | Both hands' thumbs + index fingers arranged into angular frames | Names only | Dance Spirit article <https://dancespirit.com/world-fingertips/> [V] | [V] for the names above |
| **Hip-hop slang shapes** (claw, blade, gun, "W", diamond, jazz hands, spirit fingers) | No authoritative list found. My searches did not confirm these as codified terms (Dance Spirit does not mention jazz hands or claw). | - | - | - | [U]: definitions in section 4 are mine |

VRChat table (verified, <https://docs.vrchat.com/docs/valve-index>): Fist (all curled), Open Hand (all extended), Point (index extended, rest + thumb curled), Thumbs Up (fingers curled, thumb extended), Victory (index + middle extended), Hand Gun (index + thumb extended), Rock N Roll (index + pinky extended, thumb curled).

### 1.2 What this means for you

1. **No source gives ready joint angles for named shapes.** Sign-language and dance vocabularies are *names + finger-state descriptions*. The closest to machine-readable are ASL-LEX/SLPA (per-finger categories in a CSV) and VRChat/HaGRID (class names). You must author the angle table yourself, as `LIB` already does. That is not a loss: the useful thing to borrow is the **definition scheme**.
2. **The scheme that appears everywhere** (HamNoSys, SLPA/Brentari, Feix, VRChat): per-finger *state* from a small set (extended / curved / bent / closed), plus *which fingers are selected*, plus *thumb position*, plus *spread*. Adopt that as the label's internal definition. Then a label is a short recipe, and a pose = recipe expanded to angles.
3. **Real 3D hand data with licences:** MANO and the datasets built on it (GRAB, ARCTIC) are research-licence, registration required. They are useful to *check* that your angles look like a real hand, not to ship. Licences for GRAB: register + accept per-subject restrictions, research purposes, commercial via ps-licensing@tue.mpg.de [V, <https://grab.is.tue.mpg.de/>: 10 subjects, 51 objects]. ARCTIC: ~2.1M frames, MANO/SMPL-X ground truth, licence in the repo LICENSE file, not read [S, <https://arctic.is.tue.mpg.de/>].
4. **HaGRID class names are the best borrowable list of everyday gestures** (v2, verified from the README): call, peace, grabbing, dislike, peace_inverted, grip, fist, rock, hand_heart, four, stop, hand_heart2, like, stop_inverted, holy, mute, three, little_finger, ok, three2, middle_finger, one, two_up, point, palm, two_up_inverted, take_picture, three3, three_gun, thumb_index, thumb_index2, timeout, xsign. Note: `middle_finger` is offensive; keep it out of a shipped list or rename it. Several are two-handed (heart, timeout, xsign, holy).
5. Mixamo/VRM/OpenXR agree on 3 phalanges per finger and 3 for the thumb at the animation level, so a per-joint curl table maps cleanly. (VRM bone naming not verified.)

---

## 2. Dynamic quick gestures: timing numbers

**Honest summary: there is almost no published, dance-specific timing for finger snaps, flicks, waves or shakes.** Mocap corpora (GRAB, ARCTIC) are about grasping objects, not gesturing. Verified numbers exist only for biomechanics. The rest below is my engineering estimate; use it as default values you tune by eye against video.

### 2.1 Verified biomechanics numbers

| Fact | Value | Source | Tag |
|---|---|---|---|
| Finger snap: time for the snap | about **7 ms**; peak angular acceleration 1.6e6 deg/s^2; peak rotational velocity about 7,800 deg/s | Acharya, Challita, Ilton, Bhamla, "The ultrafast snap of a finger is mediated by skin friction", J. R. Soc. Interface 18(184), 2021, DOI 10.1098/rsif.2021.0672. I verified "1.6e6 deg/s^2 in 7 ms" from the abstract; the 7,800 deg/s figure is from press coverage. | 7 ms and acceleration [V], velocity [S] |
| Fast grip / release, peak joint speeds (22 healthy adults, glove, 10 cycles in 5 s) | long-finger PIP flexion ~1394 deg/s, extension ~1368; MCP ~1260 / 1270; DIP ~1110 / 1144; thumb IP ~738 / 752; thumb MCP ~375 / 336 | Li et al., "Finger Kinematics during Human Hand Grip and Release", Biomimetics 2023;8(2):244, <https://pmc.ncbi.nlm.nih.gov/articles/PMC10296280> | [V] |
| Ordering inside a grip | thumb starts first and stops last; pinky is last to start; flexion starts at PIP, extension starts at DIP/MCP | same paper | [V] |
| Max finger tapping rate | about 6 Hz simulated for the index; synchronisation studies 5-7 Hz (older), up to 8-10 Hz with sound cues | ASME J. Comput. Nonlinear Dyn. 12(5) 051009 (2017); sensorimotor-synchronisation review; both via search snippets | [S] |
| Physiological hand/finger tremor | peak 6-12 Hz (90% of 237 subjects had a 7-11 Hz peak); finger postural tremor has an extra 20-25 Hz component | Lakie et al. 2015, J. Physiol., <https://pmc.ncbi.nlm.nih.gov/articles/PMC4594250> | [S] |

Take-aways: (a) a human finger tops out around 1,000-1,400 deg/s per joint in a deliberate grip/release, so a full 90 deg curl takes **about 65-90 ms at best**; anything labelled "instant" on screen should still last >= 2 frames at 30 fps. (b) A snap's *release* is 7 ms (far below one video frame, 33 ms at 30 fps), so the *visible* snap is a pose change plus a small recoil, not a modelled 7 ms event. (c) Voluntary shakes cannot go much beyond ~6-10 Hz.

### 2.2 Dance-level estimates (all [U] unless noted)

At 90 BPM a beat is 667 ms (20 frames at 30 fps); at 120 BPM it is 500 ms. Express timings as fractions of a beat when you can.

| Gesture | Phases | Suggested timing (30 fps) | Basis |
|---|---|---|---|
| **Finger snap** | prepare (thumb pressed on middle finger, fingers tense) 100-250 ms; hit (middle finger flicks to the palm) 1-2 frames; recoil/open 2-4 frames | whole event 200-400 ms; hit lasts 33-66 ms on screen | 7 ms physical snap [V]; rest [U] |
| **Flick** (finger pulled back by thumb, released outward) | cock 3-6 frames, release 1-2 frames, follow-through/settle 3-5 frames | 150-350 ms total | [U] |
| **Finger wave / ripple** (each finger curls then extends in turn) | one finger: curl + extend 250-400 ms; delay between neighbouring fingers 40-80 ms | thumb->pinky sweep of 4 delays = 160-320 ms | delay is [U]; the thumb-leads/pinky-last grip ordering is [V] (Li 2023) |
| **Jazz hands / spirit-fingers shake** | spread open and oscillate the wrist/fingers | 4-8 Hz (each 125-250 ms period), amplitude 10-25 deg spread | upper bound from tapping/tremor numbers [S]; rest [U] |
| **Clench-release pulse** | clench 3-5 frames, hold 0-3, release 3-6 frames; repeat on the beat | 120-300 ms per half, usually 1 pulse per beat or half beat | grip/release speed [V]; rest [U] |
| **Finger tut transition** (angular shape to next) | hard hold on the shape, fast move between | move 60-150 ms, hold 1/2 beat or more; zero easing at the ends ("snappy") | [U], inferred from "angular poses" description [S] |
| **Point/stab accent** | quick extend with slight overshoot, hold | 80-150 ms, overshoot 5-10 deg | [U] |

The principle to apply: the *accent* happens in 1-4 frames; the preparation (anticipation) before it, and the settle after it, are what make it read. A practitioner rule quoted in a skill page is "2-4 frames of reverse motion before the main action" [S, not from Illusion of Life; I did not find that book's own numbers].

---

## 3. Smooth transitions between poses

### 3.1 What to interpolate

- **Per-joint angle** (what `blender_handpose.py` does with curl numbers) is fine for fingers: they are hinges with almost one degree of freedom, so there is no gimbal problem and blending angles is the same as blending rotations about the fixed hinge axis. It also lets you apply **different timing per finger** (the wave) or per joint.
- **Quaternion slerp** matters where a joint has 2-3 degrees of freedom: the thumb CMC and the finger MCP when spread changes. For small angle differences, slerp and linear angle blend are almost identical. Rule: store each pose as per-joint quaternions (or MANO axis-angle), `slerp` between them, and only use raw Euler lerp if the rig is hinge-only. [U: standard graphics practice, not searched.]
- **Do not blend through "straight" lines in joint space when the pose is a *target*, e.g. fist to open:** all joints arrive together and look robotic. Use a small per-joint stagger (Section 3.3).

### 3.2 Easing curves

| Method | Formula / idea | When to use | Tag |
|---|---|---|---|
| Linear | x = a + (b-a) t | never for fingers (looks mechanical) | - |
| Smoothstep (cubic ease-in-out) | 3t^2 - 2t^3 | default for slow relaxed changes | [U] |
| **Minimum jerk** | x = a + (b-a)(10 t^3 - 15 t^4 + 6 t^5), t = elapsed/duration. Zero speed and acceleration at both ends, bell-shaped speed. | Matches human point-to-point movement. Best "looks human" default for deliberate moves. | The model (Flash & Hogan 1985: minimise squared jerk gives a 5th-order polynomial and bell-shaped speed) [S]; the exact polynomial is my recollection, verify against the paper before quoting [U] |
| **Critically damped spring** | Closed form x(t) = (j0 + j1 t) e^(-y t) + c with y = d/2; parameterise by **halflife** (d = 4 ln2 / halflife); no overshoot, handles interrupted/retargeted moves, continuous velocity | Best for a **live/retargetable** timeline: when a new label arrives mid-move, the hand continues smoothly. | Holden, "Spring-It-On" <https://theorangeduck.com/page/spring-roll-call> [V]; code licence not stated on the page (check <https://github.com/orangeduck/Spring-It-On>) |
| **Under-damped spring** | same with damping ratio < 1 | snappy accents with natural overshoot and settle | [U] |
| Inertialization / dead blending | decay the *offset* between old and new animation with a spring instead of cross-fading two clips | Useful if you ever blend your hand layer over a changing body clip | Holden, <https://theorangeduck.com/page/dead-blending> (Feb 2023) [S via search] |

For a baked, offline timeline like yours, use **minimum jerk** for normal transitions, **a fast ease-out with overshoot** for accents, and **no ease at the ends of tutting holds**. Keep the existing `ease` parameter as the default duration/halflife.

### 3.3 Anticipation, overshoot, stagger

- **Anticipation:** before a fast open/clench, go 10-20% of the opposite way over 2-4 frames [U rule of thumb; [S] that a motion-graphics page states 2-4 frames].
- **Overshoot and settle:** for a snap or flick, pass the target by 5-15 deg and return over 3-6 frames (a tutorial example: overshoot at frame 11, settle at frame 19 of 24 fps for a head turn [S]).
- **Stagger across joints/fingers:** PIP leads flexion, thumb leads the fingers, pinky trails [V, Li 2023]. Implementation: add 20-60 ms of start delay per finger in order thumb, index, middle, ring, pinky for a closing move; reverse order for opening gives a fan-like relaxed feel. [U for the numbers.]
- **Joint coupling:** DIP follows PIP in a natural curl. I could not verify a human DIP/PIP ratio (the oft-quoted 2/3 is NOT confirmed; robot papers use their own mechanical ratios). Keep your hand-authored (base, middle, tip) triples, which already encode this.

### 3.4 Durations that look natural (all [U] except the speed ceiling)

| Change | Duration | Note |
|---|---|---|
| Slow relaxed change (open to relaxed) | 300-600 ms (about 1 beat) | min-jerk or smoothstep |
| Normal change on the beat (open to fist) | 120-250 ms | min-jerk |
| Fast / accent (clench, point) | 66-120 ms (2-4 frames at 30 fps) | the ceiling: full 90 deg curl at the measured ~1,300 deg/s is ~70 ms [V], so never go below ~2 frames |
| Held tutting shapes | move 60-150 ms, hold at least 1/2 beat | linear-ish with sharp ends |
| Maximum overall speed to clamp at | ~1,300 deg/s per joint | Li 2023 [V]; useful as a validator: warn if a label pair demands faster |

A validator idea: for each adjacent pair of labels, compute the largest joint-angle change / time gap; if it exceeds ~1,300 deg/s, flag "impossible for a human" in the editor.

---

## 4. Recommended label set for hip-hop / street-dance hands

Definitions use per-finger states: **E** extended (straight), **S** slightly curved (15-30 deg, relaxed), **C** curved/claw (about 45-60 deg per joint, fingertips pointing at palm), **H** hooked (MCP straight, PIP+DIP bent), **B** bent/closed (fist-like, ~90 deg), **T** tucked (inside, thumb across). Thumb: **out** (abducted away), **in** (adducted along index), **across** (over fingers), **opp-X** (pad touches fingertip X). Spread: **0** fingers together, **+** natural, **++** fanned wide.

Provenance letters: **V**=VRChat table, **H**=HaGRID v2 class name, **F**=Feix grasp (concept), **N**=sign-language notation (HamNoSys/ISWA/ASL names), **M**=mudra name (Abhinaya Darpana), **T**=tutting (Dance Spirit), **D**=my dance-slang definition (unverified). Numeric angles are yours to tune; the recipes are the point. All recipes are [U] as definitions even where the *names* come from a verified source.

### 4.1 Core open/closed (12)

| # | Label | Definition | From |
|---|---|---|---|
| 1 | open | all E, thumb out, spread + | V |
| 2 | relaxed | all S, thumb in, spread 0 | existing |
| 3 | flat (blade) | all E, together, thumb in; karate/"knife" hand | N (ASL B), M pataka, D |
| 4 | fist | all B, thumb across | V, H |
| 5 | fist_thumb_out | all B, thumb out (thumbs-up body) | V |
| 6 | loose_fist | all C-ish ~60% curl, thumb across | D |
| 7 | grip | fingers C ~70%, thumb opp (holding a bar) | existing, F power grasp |
| 8 | cup | all S together, thumb in, palm hollow | N (ASL cupped), D |
| 9 | spread (fan, "5") | all E, spread ++, thumb out | N (ASL 5), D |
| 10 | four | index-pinky E, thumb across | H |
| 11 | three | index+middle+ring E, thumb+pinky B | H, N (ASL 3 variant) |
| 12 | stop_palm | open, fingers together, palm forward | H (stop, palm) |

### 4.2 Pointing and counting (10)

| # | Label | Definition | From |
|---|---|---|---|
| 13 | point | index E, rest B, thumb across | V, H, N (ASL 1/G) |
| 14 | point_thumb_up (gun) | index E, thumb E out, rest B | V (Hand Gun), H (three_gun/thumb_index) |
| 15 | finger_gun_two | index+middle E together, thumb up | D |
| 16 | L_shape | index E, thumb out at 90 deg, rest B | T, N (ASL L) |
| 17 | two (peace/victory) | index+middle E spread +, rest B | V, H |
| 18 | peace_inverted | as two, palm toward self | H |
| 19 | two_close | index+middle E together | H (two_up) |
| 20 | one_hook | index H (hooked), rest B | N, D (beckon) |
| 21 | come_here | all fingers H, curling twice (static: all H) | M-like, D |
| 22 | pinky_point | pinky E, rest B | H (little_finger) |

### 4.3 Thumb-opposition and pinch (10)

| # | Label | Definition | From |
|---|---|---|---|
| 23 | pinch | thumb opp-index, others S | existing, F precision pinch |
| 24 | ok | thumb opp-index circle, middle-pinky E | H |
| 25 | pinch_all (beak/"O") | all fingertips meet thumb | N (ASL O), F |
| 26 | tripod | thumb+index+middle meet, ring/pinky B | F |
| 27 | c_shape | all C, thumb out, wide gap | N (ASL C) |
| 28 | small_c | as C but gap narrow (take-a-picture frame use) | H take_picture (two hands), D |
| 29 | thumb_middle (snap-ready) | thumb pad pressed on middle fingertip, others S | D |
| 30 | thumb_ring | thumb opp-ring (counting "mudra" feel) | M (e.g. mudras with ring-thumb; exact names unverified) |
| 31 | thumb_pinky | thumb opp-pinky, others E | D |
| 32 | lateral_pinch | thumb pad on side of index, others B | F (lateral) |

### 4.4 Rock / call / iconic gestures (12)

| # | Label | Definition | From |
|---|---|---|---|
| 33 | rock (horns) | index+pinky E, middle+ring B, thumb across | V, H |
| 34 | rock_thumb | horns + thumb out ("I love you" / spider-man) | N (ASL ILY), D |
| 35 | call (shaka) | thumb+pinky E, rest B | H, D |
| 36 | thumbs_up | fist, thumb E up | V, H (like) |
| 37 | thumbs_down | fist, thumb E down | H (dislike) |
| 38 | mute (shh finger) | index E at lips, rest B | H (mute) |
| 39 | holy / prayer | two hands palms together (two-handed) | H (holy) |
| 40 | x_sign | two forearms crossed, fists or open | H (xsign) |
| 41 | timeout_T | one hand flat on the other (two-handed) | H (timeout) |
| 42 | heart_hands | two hands forming heart, thumbs+index | H (hand_heart), T heart |
| 43 | claw | all C strong (~60% each joint), spread +, thumb opp pinky side | D (not confirmed as a codified term) |
| 44 | eagle (spread claw) | claw with spread ++ | D |

### 4.5 Street-style and tutting structures (14)

| # | Label | Definition | From |
|---|---|---|---|
| 45 | tut_L | index E, thumb out 90 deg (an "L") | T |
| 46 | tut_field_goal | thumb + thumb touching, index up (two-handed) | T |
| 47 | tut_rectangle | two L's closing into a rectangle (two-handed) | T |
| 48 | tut_square | rectangle with equal sides | T |
| 49 | tut_triangle | index+thumb tips meet, 3 corners | T |
| 50 | tut_diamond | two hands, index+thumb meet at 4 points | T |
| 51 | tut_circle_loop | thumb+index make a circle, others E | T (circles/loops), N (ASL F) |
| 52 | tut_cross | index fingers crossed (two-handed) | D |
| 53 | tut_knuckle_flat | fist with flat knuckles forward | D |
| 54 | tut_box_hand | all E, fingers together, 90 deg at MCP (flat blade bent at knuckle) | D |
| 55 | tut_fingers_90 | index E, middle H at 90 deg (angular zig-zag) | D |
| 56 | w_sign | index+middle+ring E spread, thumb/pinky B ("W" - same as three but spread) | N (ASL W), D |
| 57 | gangster_dual_gun | both hands finger gun forward | D |
| 58 | dab_hand | flat blade, palm down | D |

### 4.6 Dance-expressive hand poses (12)

| # | Label | Definition | From |
|---|---|---|---|
| 59 | jazz_hand | open fan, fingers ++ spread, wrist rotated | D (not found in Dance Spirit) |
| 60 | spirit_finger | as jazz_hand but fingers tense/E | D |
| 61 | ballet_soft | all S, thumb near middle finger, 10-20 deg curl | D (prose; [U]) |
| 62 | flat_wave_hand | blade with palm down, slightly cupped | D |
| 63 | pataka | all E together, thumb bent in | M (Asamyuta) |
| 64 | tripataka | pataka with ring finger bent | M |
| 65 | ardhapataka | pataka with ring+pinky bent | M |
| 66 | mayura (peacock) | thumb+ring touch, others E | M |
| 67 | mushti | fist, thumb over index/middle | M (fist) |
| 68 | suchi | index E, rest B | M (= point) |
| 69 | katakamukha | thumb+index+middle meet (like holding a flower), ring+pinky E | M |
| 70 | alapadma (lotus) | all fingers fanned and curved back, thumb out | M |

Mudra definitions in the rows above are my paraphrase; the *names* are from the Abhinaya Darpana list reported by [S] sources, and the finger configurations here are NOT verified against a treatise (counts and details vary between sources).

### 4.7 Dynamic gestures (14)

Times at 30 fps; `b` = beat. All timings [U] except where noted in section 2.

| # | Label | Definition | Timing |
|---|---|---|---|
| D1 | snap | thumb_middle to open-with-thumb-on-palm to relaxed | prepare 100-250 ms, hit 33-66 ms, settle 100 ms. Physical snap 7 ms [V] |
| D2 | double_snap | two snaps | 1/2 b apart |
| D3 | flick_index | index cocked by thumb then released out | cock 100-200, release 33-66, settle 100-150 ms |
| D4 | flick_all | four fingers flick open from fist (shake-off) | 100-200 ms |
| D5 | finger_wave (ripple) | each finger curl+extend in sequence thumb->pinky | per finger 250-400 ms, offset 40-80 ms |
| D6 | wave_reverse | pinky->thumb | same |
| D7 | jazz_shake | spread fan, oscillate | 4-8 Hz, 1-4 beats [S upper bound] |
| D8 | pulse_clench | open to fist to open | 1 b or 1/2 b cycle; half-cycles 120-300 ms |
| D9 | pulse_pinch | open to pinch to open | same |
| D10 | claw_snap | open to claw sharply with hold | 66-120 ms in, hold 1/2 b |
| D11 | point_stab | relaxed to point with overshoot | 80-150 ms, overshoot 5-10 deg |
| D12 | tut_morph | one tut structure to next | move 60-150 ms, hold >= 1/2 b |
| D13 | fan_open | closed fist to spread fan, fingers staggered | 150-250 ms, stagger 20-40 ms |
| D14 | grab_release | open to grip to open (catch) | 120-250 ms each way |
| D15 (optional) | beckon_curl | index/all fingers H to E, repeat | 300-500 ms per curl |

---

## 5. Suggested implementation path

1. Extend `LIB` entries from (base, middle, tip) to also carry **spread** and **thumb opposition target**. Use the Section 4 recipes to generate angles from per-finger state codes (E/S/C/H/B/T) so the table stays editable.
2. In the editor add *categories* (Section 4 headings) and a "dynamic" kind that stores the gesture name plus a time stretch, expanded to a short keyframe sequence (prepare, hit, settle) at bake time.
3. Use minimum-jerk or a critically damped spring for transitions, with overshoot parameter for accents, per-finger stagger, and the ~1,300 deg/s speed-limit validator.
4. If you want real measured shapes, fit MANO poses (research licence, registration at <https://mano.is.tue.mpg.de/>) from HaGRID close-ups (CC BY-SA 4.0) via a hand-pose estimator already covered in `07_hand_datasets_and_estimators.md`, then use them to *calibrate* your hand-authored angles. Do not redistribute MANO.
5. Static class list for a classifier: start from the 33 HaGRIDv2 classes (drop `middle_finger`), plus the dance-specific rows in 4.4-4.6.

## 6. Gaps (not found; do not trust any number I did not tag)

- No published measurement of finger-wave inter-finger delay, flick duration, or dance shake frequency. Section 2.2 numbers are estimates.
- HamNoSys: the 2018 PDF at <https://www.sign-lang.uni-hamburg.de/dgs-korpus/files/inhalt_pdf/HamNoSys_2018.pdf> could not be text-extracted here (images), so basic-shape names and the licence are unconfirmed; use the printed chart.
- ASL-LEX data licence on OSF, MANO commercial terms, HaGRID v1 class list, Cutkosky count, VRM finger-bone names, and the Brentari feature geometry were not verified.
- The cosmosmagazine snap article returned 403; snap phase breakdowns beyond the abstract are not verified.
- Hip-hop slang shapes (claw, blade, gun, W, diamond, jazz hands) have no codified source I could find; definitions are mine.

## Sources

- Feix et al. 2016 GRASP taxonomy: <https://www.eng.yale.edu/grablab/pubs/Feix_THMS2016.pdf>, <https://ieeexplore.ieee.org/document/7243327>
- HaGRID: <https://github.com/ai-forever/hagrid>; paper (WACV 2024) <https://openaccess.thecvf.com/content/WACV2024/papers/Kapitanov_HaGRID_--_HAnd_Gesture_Recognition_Image_Dataset_WACV_2024_paper.pdf>
- VRChat gestures: <https://docs.vrchat.com/docs/valve-index>
- SignWriting ISWA 2010: <https://www.signbank.org/iswa/>, hand-symbol manual <https://www.signwriting.org/archive/docs7/sw0618_SignWriting_Hand_Symbols_Manual_Sutton_Frost.pdf>
- HamNoSys: <https://www.sign-lang.uni-hamburg.de/dgs-korpus/files/inhalt_pdf/HamNoSys_2018.pdf>; 2026 dataset <https://arxiv.org/pdf/2608.10588>; <https://arxiv.org/pdf/2302.10768>
- ASL-LEX: <https://osf.io/zpha4/>, <https://asl-lex.org>; SLPAnnotator Interspeech 2017 <https://www.isca-archive.org/interspeech_2017/hall17_interspeech.html>
- MANO: <https://mano.is.tue.mpg.de/>, paper <https://arxiv.org/abs/2201.02610>; GRAB <https://grab.is.tue.mpg.de/>; ARCTIC <https://arctic.is.tue.mpg.de/>
- OpenXR: <https://registry.khronos.org/OpenXR/specs/1.1/man/html/XR_HAND_JOINT_COUNT_EXT.html>
- Finger snap: Acharya et al. 2021, DOI 10.1098/rsif.2021.0672 (<https://par.nsf.gov/biblio/10302108>)
- Finger kinematics: <https://pmc.ncbi.nlm.nih.gov/articles/PMC10296280>
- Tremor: <https://pmc.ncbi.nlm.nih.gov/articles/PMC4594250>
- Tapping: <https://asmedc.silverchair.com/computationalnonlinear/article-abstract/12/5/051009/474515/Estimation-of-Maximum-Finger-Tapping-Frequency>
- Springs: <https://theorangeduck.com/page/spring-roll-call>; dead blending <https://theorangeduck.com/page/dead-blending>
- Min-jerk: Flash & Hogan 1985 (PDF found via search at newmanlab-mit-edu mirror; cite the original J. Neurosci. 5(7))
- Finger tutting: <https://dancespirit.com/world-fingertips/>
- Mudras: Abhinaya Darpana summaries, e.g. <https://www.narthaki.com/info/articles/art484.html> (not read in full)
