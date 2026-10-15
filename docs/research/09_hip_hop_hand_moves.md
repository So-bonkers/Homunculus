# Hip hop hand moves: what exists, what was built (2026-10-15)

Question: is there an inventory of dance moves across genres, or of hip hop hand moves, that could be used as a vocabulary of "compound poses" (a timed run of poses) for the hand editor and for the LLM annotation?

## What was found

| Source | What it has | Use |
|---|---|---|
| [Wikipedia: Glossary of dance moves](https://en.wikipedia.org/wiki/Glossary_of_dance_moves), [Dance terms](https://en.wikipedia.org/wiki/Dance_terms) | Alphabetic, cross-genre lists of step names | Names only; almost nothing about hands |
| [Wikipedia: Locking (dance)](https://en.wikipedia.org/wiki/Locking_(dance)) | A Moves section: Lock, Point, Wrist Twirl, Pacing, Hitch Hike, Floor Sweep, Funky Guitar, Up Lock, Scoobot, Whichaway... each with a line about the arms or hands | The only open source that names hand actions; used for 7 moves |
| Wikipedia: Popping, Tutting, Krumping, Hip-hop dance | Style definitions; tutting = right angles of arms, hands and wrists; krump = jab, arm swing, chest pop, stomp | Concepts only; hands not described |
| [Dance Spirit: finger tutting, P-Nut's beginner sequence](https://dancespirit.com/world-fingertips/) | Nine two-hand shapes in order (L shapes, thumb overlap, rectangle, collapse, heart) | Not usable: the shapes need the hands to touch, and the hand layer poses each hand alone |
| [List of mudras (dance)](https://en.wikipedia.org/wiki/List_of_mudras_(dance)) | 28 single-hand and 23-24 double-hand gestures of Indian classical dance | A real static hand-shape inventory, not hip hop; not used yet |
| [ARTeFACT Movement Thesaurus](https://dh-abstracts.library.virginia.edu/works/1503), [AniAge ontology](https://eprints.uet.vnu.edu.vn/eprints/id/eprint/3045/1/Dance.pdf) | 200+ captured movements (ballet, jazz, modern, tai chi); an ontology that builds compound movements from elementary poses by rules | The AniAge idea (elementary poses plus composition) is the model for the moves file; the data is not hip hop and its availability is unconfirmed |
| AIST++, [FineDance](https://arxiv.org/pdf/2212.03741), [InfiniteDance](https://arxiv.org/pdf/2603.13375), BRACE, PMSD | Mocap or video with genre labels (10, 22, 6+30 genres), breaking pose annotation, a street-dance set | None names individual moves |

No open source lists hip hop hand moves with joint detail; the descriptions of finger tutting, finger rolls and most hand work live in classes and video tutorials.

## What was built

`homunculus/static/hands/moves.json`: 83 moves in seven groups (basics 26, locking 11, popping and tutting 14, krump 6, breaking 3, party dances 9, gestures 14), each a short run of poses, wrist positions and palm directions with times and curves, dropped at the playhead of the hand editor on every lane it has. It began as 29 (the editor's 11 gestures and 18 hip hop moves) and was widened to 83 after a first review. Each move has `check`: **sourced** (the move and its hand action are named in a source), **knowledge** (general knowledge, no source describes it) or **estimate**. All timings are animation estimates. The editor reads the file; it replaces the hard-coded list in the web code.

## How the moves were tested

- Every pose, wrist and palm name in every move exists in the library (checked on each change).
- `python -m homunculus.move_pictures` draws every move on the dancer's rig (`blender_movesheet.py`): eight moments from just before the first key to just after the last, each from the side and from above, evaluated with the same curve code that bakes a timeline into a clip; the pictures are `static/hands/moves/<key>.jpg` and the editor shows them next to each move. All 83 were looked at. One was too weak to see (the strobe alternated `open` and `soft`) and was changed to `open` and `claw`.
- A throwaway clip with all of the first 29 moves in one timeline, both hands, palm lanes included, was baked by the normal path without error.
- Not tested: the moves on a full dance clip in motion, the timings against real footage, and any use of the moves by the LLM annotation (not built).

## Originality (US sources, not legal advice)

[Copyright Office Circular 52](https://www.Copyright.Gov/circs/circ52.pdf) and [Hanagami v. Epic Games](https://www.cll.com/CopyrightDevelopmentsBlog/hanagami-v-epic-games-one-small-step): single steps and poses, and short routines of a few moves, are not protectable; an organised arrangement can be. The Office's [Part 2 report on AI (January 2025)](https://www.lowenstein.com/news-insights/publications/client-alerts/us-copyright-office-issues-report-on-copyrightability-of-generative-ai-outputs-ai): prompts alone do not make a user the author; human selection and arrangement can be protected, only for the human part. A dance composed from generic moves is not a copy; a generator that reproduces a substantial run of a training dance would be.
