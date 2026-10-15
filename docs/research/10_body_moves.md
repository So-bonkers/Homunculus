# A vocabulary of full-body dance moves, starting with breaking (2026-10-15)

Why: the hand vocabulary ([09](09_hip_hop_hand_moves.md)) names what the hands do; the same idea one level up names what the whole body does, so that a dance can be labelled in moves, described to a model, and one day composed from moves.

## What exists

| Source | What it has | Use |
|---|---|---|
| [Wikipedia: List of breakdance moves](https://wikipedia2007.classicistranieri.com/l/i/s/List_of_breakdance_moves.html) (a 2007 mirror of the article) | 79 named moves in categories (footwork, drops, ground and air freezes, power moves, floats, spins, others), most with a one-line description; the drops have none | The backbone of the vocabulary |
| [Wikipedia: Breakdancing](https://en.wikipedia.org/wiki/Breakdancing), [Red Bull: the basic elements of breaking](https://www.redbull.com/int-en/understand-the-basic-elements-of-breaking) | Categories (toprock, go-downs, footwork, freezes, power moves, tricks), named examples, and how a round flows: toprock, a drop to the floor, footwork and power moves, a freeze on a strong beat; stacks; blow-up style | The categories and the flow |
| [BRACE](https://arxiv.org/pdf/2207.10120) (ECCV 2022) | 3.5 h of Red Bull BC One breaking as keypoints (the video is not released), labelled with three element types: toprock, footwork, powermove | The only labelled breaking motion found; the labels are element types, not move names. Mean segment lengths (7.0, 11.5, 9.9 s) come from a [third-party paper](https://arxiv.org/abs/2510.20287) and are unchecked |
| AIST++, FineDance, InfiniteDance, PMSD | Genre-labelled dance motion; breaking is one genre | No per-move labels |

Not found: a public inventory with joint-level descriptions of breaking moves, or a motion library with one clip per named move. The old Wikipedia list has no description for the eight drops.

## What was built

`homunculus/static/dance/body_moves.json`: 105 moves in 12 categories (toprock 5, go-downs 10, footwork 9, ground freezes 10, air freezes 10, power moves 8, floats 5, spins 9, tricks and others 16, standing hip hop foundations 4, popping and locking 14, krump 5), the round structure as a flow of categories, and BRACE's segment lengths. Per move: category, orientation (standing, floor, inverted, mixed), points of support, kind of motion (static, steps, rotation, jump, transition), whether it loops, a description in my own words, aliases, and `check`: **sourced** (named with a description in a source, 73), **name_only** (named, no description anywhere in the sources, 18: these need looking up), **knowledge** (14). The flow edges between the non-adjacent categories are my reading of how breakers chain moves.

## What it is for, and what is missing

1. **Labels.** A lane of full-body moves on the dance timeline (start, end, move), written by a person or proposed by a vision-language model that is given the vocabulary. Not built.
2. **A grammar.** The flow edges describe which categories follow which; a generator could walk them. Not built.
3. **Motion.** A move name does not move a character. The motion for floor work and inversions needs either BRACE's keypoints (2D, without video), clips cut from our own footage, or a generator. GVHMR, which reads our dance clips, is trained mostly on upright motion and has not been tried on headspins, flares or freezes; it may fail on them.

For originality (US sources, not legal advice) see the end of [09](09_hip_hop_hand_moves.md): single moves are not protectable; an arrangement can be, and only the human part.
