"""Draft the palm-direction lanes of a clip with the palm prior (homunculus/hand_prior.py) from the body motion GVHMR gave:

    .venv/bin/python tools/draft_palm.py <run> <clip id> <smpl_global.npz> [--duration SECONDS]

The proposal is saved as an unreviewed draft (the editor shows "auto draft: check it"), and kept apart so that, once a person has labelled the palm lanes, the editor can say how often the model agreed
(hands.agreement). Only the palm lanes are filled: nothing here predicts the fingers or the wrist."""
import argparse, os, sys
import numpy as np
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__))); sys.path.insert(0, ROOT)
from homunculus import hand_prior, hands
ap = argparse.ArgumentParser(); ap.add_argument("run"); ap.add_argument("clip"); ap.add_argument("npz"); ap.add_argument("--duration", type=float, default=None); a = ap.parse_args()
g = dict(np.load(a.npz)); n = len(g["body_pose"]); P = hand_prior.predict_palm(g); dur = a.duration or n / 30
tracks = {"left": [], "right": [], "left_wrist": [], "right_wrist": [], "left_palm": hand_prior.draft_track(P["left"]), "right_palm": hand_prior.draft_track(P["right"])}
meta = {"source": "draft", "model": "palm prior v1 (arm geometry -> palm direction, trained on FineDance)", "duration": dur, "how": "The palm direction lanes were proposed by a model that reads the arms (58 % on unseen FineDance files); the fingers and the wrist are empty: nothing here predicts them. Not reviewed."}
hands.save(a.run, a.clip, tracks, meta=meta, wait=True)
print(a.clip, {k: len(v) for k, v in tracks.items()})
