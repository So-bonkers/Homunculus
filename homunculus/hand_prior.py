"""A prior for the palm direction from the arms: given a dancer's body motion (SMPL rotations, as GVHMR or FineDance give them), which way do the palms most likely face?

Trained on FineDance (real mocap with fingers, tools/train_hand_prior.py): the arm's geometry (upper arm and forearm directions, wrist and elbow positions relative to the chest, the wrist's velocity, the other
wrist, all in the torso's frame with the right hand mirrored into a left one, over a window of +-0.5 s) -> down / up / forward / back / in / out. It does not use the palm normal itself (that is the answer).
Held-out FineDance files: 58 % (guessing: 33 %). Pure numpy, so the web server's environment can run it. See docs/VIDEO_MOTION.md for what it can and cannot do (it predicts the palm only)."""
import os
import numpy as np
from scipy.spatial.transform import Rotation as Rot
from scipy.special import erf

DIRS = ("down", "up", "forward", "back", "in", "out")
_NAMES = ["Pelvis", "L_Hip", "R_Hip", "Spine1", "L_Knee", "R_Knee", "Spine2", "L_Ankle", "R_Ankle", "Spine3", "L_Foot", "R_Foot", "Neck", "L_Collar", "R_Collar", "Head", "L_Shoulder", "R_Shoulder", "L_Elbow", "R_Elbow", "L_Wrist", "R_Wrist"]
_PARENT = [-1, 0, 0, 0, 1, 2, 3, 4, 5, 6, 7, 8, 9, 9, 9, 12, 13, 14, 16, 17, 18, 19]
_OFF = {"L_Hip": (0.06, -0.09, -0.01), "Spine1": (0, 0.11, 0), "L_Knee": (0, -0.39, 0), "Spine2": (0, 0.13, 0), "L_Ankle": (0, -0.40, 0), "Spine3": (0, 0.05, 0), "L_Foot": (0, -0.06, 0.12),
        "Neck": (0, 0.21, 0), "Head": (0, 0.10, 0), "L_Collar": (0.045, 0.10, 0), "L_Shoulder": (0.10, 0, 0), "L_Elbow": (0.26, 0, 0), "L_Wrist": (0.25, 0, 0)}


def _offset(n):
    if n == "Pelvis": return np.zeros(3)
    if n in _OFF: return np.array(_OFF[n], float)
    o = np.array(_OFF[n.replace("R_", "L_")], float); o[0] = -o[0]; return o


_OFFS = np.stack([_offset(n) for n in _NAMES])


def fk(R):
    """(n, 22, 3, 3) local rotations -> global rotations and joint positions (an idealised SMPL skeleton: only directions matter)"""
    n = len(R); G = np.zeros_like(R); P = np.zeros((n, 22, 3))
    for j in range(22):
        if _PARENT[j] < 0: G[:, j] = R[:, j]
        else: G[:, j] = G[:, _PARENT[j]] @ R[:, j]; P[:, j] = P[:, _PARENT[j]] + (G[:, _PARENT[j]] @ _OFFS[j])
    return G, P


def hand_frames(G, P, side):
    s = 0 if side == "left" else 1; sh, el, wr = (16, 18, 20) if s == 0 else (17, 19, 21); ex = np.array([1.0, 0, 0]) if s == 0 else np.array([-1.0, 0, 0])
    fw = G[:, 9] @ np.array([0, 0, 1.0]); fw[:, 1] = 0; fw /= np.linalg.norm(fw, axis=1, keepdims=True) + 1e-9; up = np.array([0, 1.0, 0]); lf = np.cross(up, fw)
    tf = lambda v: np.stack([(v * lf).sum(1), v[:, 1], (v * fw).sum(1)], 1)                      # into the torso frame (x left, y up, z forward)
    mir = np.array([1, 1, 1.0]) if s == 0 else np.array([-1, 1, 1.0])                              # the right hand mirrored into a left hand
    c = P[:, 9]
    return dict(u=tf(G[:, sh] @ ex) * mir, f=tf(G[:, el] @ ex) * mir, wp=tf(P[:, wr] - c) * mir, ep=tf(P[:, el] - c) * mir, ow=tf(P[:, 21 if s == 0 else 20] - c) * mir)


def features(H):
    base = np.concatenate([H["u"], H["f"], H["wp"], H["ep"], H["ow"]], 1); vel = np.gradient(H["wp"], axis=0) * 30
    return np.concatenate([base, vel], 1)                                                          # 18 numbers per frame


def window(F, offs=(-15, -8, 0, 8, 15)):
    n = len(F); idx = np.clip(np.arange(n)[:, None] + np.array(offs)[None], 0, n - 1); return F[idx].reshape(n, -1)


def rot6d_to_mat(d6):
    a1, a2 = d6[..., :3], d6[..., 3:]; b1 = a1 / np.linalg.norm(a1, axis=-1, keepdims=True); b2 = a2 - (b1 * a2).sum(-1, keepdims=True) * b1; b2 /= np.linalg.norm(b2, axis=-1, keepdims=True)
    return np.stack([b1, b2, np.cross(b1, b2)], -2)


def body_matrices(smpl_global):
    """the 22 body joints as rotation matrices from a GVHMR smpl_global.npz (global_orient + 21 body joints, axis-angle)"""
    n = len(smpl_global["body_pose"]); aa = np.concatenate([smpl_global["global_orient"].reshape(n, 1, 3), smpl_global["body_pose"].reshape(n, 21, 3)], 1)
    return Rot.from_rotvec(aa.reshape(-1, 3)).as_matrix().reshape(n, 22, 3, 3)


_net = {}


def _load():
    if not _net:
        d = np.load(os.path.join(os.path.dirname(__file__), "data", "hand_prior.npz")); _net.update({k: d[k] for k in d.files})
    return _net


def _forward(X):
    m = _load(); gelu = lambda x: 0.5 * x * (1 + erf(x / np.sqrt(2)))
    h = gelu(((X - m["mu"]) / m["sd"]) @ m["W1"] + m["b1"]); h = gelu(h @ m["W2"] + m["b2"]); o = h @ m["W3"] + m["b3"]
    e = np.exp(o[:, :6] - o[:, :6].max(1, keepdims=True)); return e / e.sum(1, keepdims=True)


def predict_palm(smpl_global):
    """{"left": (n, 6), "right": (n, 6)} probabilities of DIRS for every frame (30 fps) of a body motion"""
    G, P = fk(body_matrices(smpl_global)); return {s: _forward(window(features(hand_frames(G, P, s)))) for s in ("left", "right")}


def draft_track(probs, fps=30, smooth=0.5, min_len=0.3):
    """probabilities (n, 6) -> a palm timeline [[seconds, "palm_<dir>"], ...]: the direction most likely over a short average, with changes shorter than min_len seconds dropped"""
    k = max(1, int(round(smooth * fps))); p = np.stack([np.convolve(probs[:, i], np.ones(k) / k, "same") for i in range(probs.shape[1])], 1); lab = p.argmax(1)
    runs = []; i = 0
    while i < len(lab):
        j = i
        while j < len(lab) and lab[j] == lab[i]: j += 1
        runs.append([i, j, int(lab[i])]); i = j
    changed = True
    while changed and len(runs) > 1:                                                              # absorb the shortest too-short run into its longer neighbour
        changed = False; short = [r for r in runs if (r[1] - r[0]) / fps < min_len]
        if not short: break
        r = min(short, key=lambda r: r[1] - r[0]); idx = runs.index(r); nb = runs[idx - 1] if idx > 0 and (idx == len(runs) - 1 or runs[idx - 1][1] - runs[idx - 1][0] >= runs[idx + 1][1] - runs[idx + 1][0]) else runs[idx + 1]
        nb[0] = min(nb[0], r[0]); nb[1] = max(nb[1], r[1]); runs.remove(r); changed = True
        merged = []
        for r in runs:
            if merged and merged[-1][2] == r[2]: merged[-1][1] = r[1]
            else: merged.append(r)
        runs = merged
    return [[round(r[0] / fps, 3) if i else 0.0, "palm_" + DIRS[r[2]]] for i, r in enumerate(runs)]
