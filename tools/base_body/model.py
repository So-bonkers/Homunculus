"""Differentiable parametric base body (torch, CPU-friendly): sliders -> morphed mesh -> joints derived from the mesh -> linear blend skinning with the Mixamo weights.
    B = Base();  v, J = B.forward(macro, sliders, pose)   (all torch tensors; metres; MakeHuman frame: y up, faces +z, the character's left is +x)
macro:   [gender, age, muscle, weight] in [0, 1] (0.5 = MakeHuman's default; age 0 baby, 0.1875 child, 0.5 young adult, 1 old), ethnic fixed to thirds unless given
sliders: [K] in [0, 1], one per detail target (B.slider_names)   pose: [52, 3] axis-angle per bone, in the world frame of the rest pose, about the bone's own joint"""
import os, sys, numpy as np, torch, scipy.sparse as sp
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__))); import sliders as SL
HERE = os.path.dirname(os.path.abspath(__file__))
def tri(v, stops, i):                                  # weight of stop i for a value on a piecewise-linear axis
    one = torch.ones(()); out = torch.zeros(())
    if i > 0: out = out + torch.clamp((v - stops[i - 1]) / (stops[i] - stops[i - 1]), 0, 1) * (v <= stops[i]).float()
    if i < len(stops) - 1: out = out + torch.clamp((stops[i + 1] - v) / (stops[i + 1] - stops[i]), 0, 1) * (v > stops[i]).float()
    if i == 0: out = out + (v <= stops[0]).float()
    if i == len(stops) - 1: out = out + (v > stops[-1]).float()
    return out
def rodrigues(r):
    th = r.norm(dim=-1, keepdim=True).clamp(min=1e-8); k = r / th; K = torch.zeros(r.shape[:-1] + (3, 3))
    K[..., 0, 1] = -k[..., 2]; K[..., 0, 2] = k[..., 1]; K[..., 1, 0] = k[..., 2]; K[..., 1, 2] = -k[..., 0]; K[..., 2, 0] = -k[..., 1]; K[..., 2, 1] = k[..., 0]
    s = torch.sin(th)[..., None]; c = torch.cos(th)[..., None]; return torch.eye(3) + s * K + (1 - c) * (K @ K)
def rot_between(a, b):                                 # minimal rotation taking unit vector a to unit vector b
    a = a / a.norm(); b = b / b.norm(); v = torch.linalg.cross(a, b); c = float(a @ b)
    if c < -0.999999: return -torch.eye(3) + 2 * torch.outer(a, a)
    K = torch.tensor([[0, -v[2], v[1]], [v[2], 0, -v[0]], [-v[1], v[0], 0]], dtype=torch.float32); return torch.eye(3) + K + K @ K / (1 + c)
class Base:
    def __init__(self, path=os.path.join(HERE, "library.npz")):
        L = np.load(path); self.V = torch.tensor(L["verts"], dtype=torch.float32); self.N = len(self.V); self.n = int(L["faces"].max()) + 1; self.faces = L["faces"]
        self.macro_names = [str(s) for s in L["macro_names"]]; self.slider_names = [str(s) for s in L["slider_names"]]; self.bone_names = [str(s) for s in L["bone_names"]]; self.parent = [int(p) for p in L["bone_parent"]]
        def sparse(idx, dl, ptr):
            K = len(ptr) - 1; cols = np.repeat(np.arange(K), np.diff(ptr)); rows = (idx[:, None] * 3 + np.arange(3)).reshape(-1); c3 = np.repeat(cols, 3)
            return torch.tensor(sp.coo_matrix((dl.reshape(-1), (rows, c3)), shape=(self.N * 3, K)).toarray(), dtype=torch.float32).to_sparse()
        self.M = sparse(L["macro_idx"], L["macro_delta"], L["macro_ptr"]); self.S = sparse(L["slider_idx"], L["slider_delta"], L["slider_ptr"])
        self.W = torch.tensor(L["weights"], dtype=torch.float32)
        self.defs = SL.defs(self.slider_names); self.J = len(self.defs); self.target_names = self.slider_names
        self.pos = torch.tensor([d["pos"] for d in self.defs]); self.neg_has = torch.tensor([d["neg"] >= 0 for d in self.defs]); self.neg = torch.tensor([max(d["neg"], 0) for d in self.defs])
        self.lo = torch.tensor([d["lo"] for d in self.defs]); self.hi = torch.tensor([d["hi"] for d in self.defs]); self.slider_names = [d["name"] for d in self.defs]
        key = {}; self.lr_pairs = []                                                                  # left/right partners, tied softly by the fit (not the asym group)
        for i, d in enumerate(self.defs):
            if d["side"] and d["group"] != "asym":
                k = (d["group"], d["name"].split("/", 1)[1].replace("l-", "", 1) if d["side"] == "l" else d["name"].split("/", 1)[1].replace("r-", "", 1))
                if k in key: self.lr_pairs.append((key[k], i))
                else: key[k] = i
        hp, hi = L["bone_head_ptr"], L["bone_head_idx"]; rows = np.repeat(np.arange(len(self.bone_names)), np.diff(hp)); w = np.concatenate([np.full(hp[i + 1] - hp[i], 1.0 / (hp[i + 1] - hp[i])) for i in range(len(self.bone_names))])
        self._pre = True
        self.Hm = torch.tensor(sp.coo_matrix((w, (rows, hi)), shape=(len(self.bone_names), self.N)).toarray(), dtype=torch.float32)       # joint = mean of its vertices
        self.R0 = self._rest_pose()
    def _rest_pose(self, arm_deg=25.0):
        """The base mesh rests with its forearms and hands pointing forward: a fixed per-bone rotation straightens each arm chain and lowers it to `arm_deg` from the vertical (outward), so every fit starts from a plain A-pose."""
        n = self.bone_names; J = self.Hm @ self.V; R0 = torch.eye(3).repeat(len(n), 1, 1); th = np.radians(arm_deg)
        for side, sgn in (("Left", 1.0), ("Right", -1.0)):
            ia, ie, ih, im = (n.index(f"mixamorig:{side}{b}") for b in ("Arm", "ForeArm", "Hand", "HandMiddle1"))
            d = torch.tensor([sgn * np.sin(th), -np.cos(th), 0.0], dtype=torch.float32)
            Rw_arm = rot_between(J[ie] - J[ia], d)                                                  # world rotation of the upper arm (about its joint)
            Rw_fore = rot_between(J[ih] - J[ie], d); Rw_hand = rot_between(J[im] - J[ih], d)        # the forearm and the hand lie along the same direction
            R0[ia] = Rw_arm; R0[ie] = Rw_arm.T @ Rw_fore; R0[ih] = Rw_fore.T @ Rw_hand
        return R0
    def macro_weights(self, macro, ethnic=(1 / 3, 1 / 3, 1 / 3)):
        g, a, m, w = macro; ga = {"female": 1 - g, "male": g}; aa = {n: tri(a, [0, 0.1875, 0.5, 1.0], i) for i, n in enumerate(("baby", "child", "young", "old"))}
        ma = {n: tri(m, [0, 0.5, 1.0], i) for i, n in enumerate(("minmuscle", "averagemuscle", "maxmuscle"))}; wa = {n: tri(w, [0, 0.5, 1.0], i) for i, n in enumerate(("minweight", "averageweight", "maxweight"))}
        eth = dict(zip(("caucasian", "african", "asian"), ethnic)); out = []
        for nm in self.macro_names:
            t = nm.split("/")[1].split("-")
            if t[0] == "universal": out.append(ga[t[1]] * aa[t[2]] * ma[t[3]] * wa[t[4]])
            else: out.append(eth[t[0]] * ga[t[1]] * aa[t[2]])
        return torch.stack(out)
    def rest(self, macro, sliders, ethnic=(1 / 3, 1 / 3, 1 / 3)):
        tw = torch.zeros(self.S.shape[1]).index_add(0, self.pos, torch.relu(sliders)).index_add(0, self.neg[self.neg_has], torch.relu(-sliders)[self.neg_has])        # slider -> weights of its two stock targets
        d = torch.sparse.mm(self.M, self.macro_weights(macro, ethnic)[:, None]) + torch.sparse.mm(self.S, tw[:, None]); return self.V + d.reshape(-1, 3)
    def forward(self, macro, sliders, pose, ethnic=(1 / 3, 1 / 3, 1 / 3), offsets=None):
        Vr = self.rest(macro, sliders, ethnic)
        if offsets is not None: Vr = torch.cat([Vr[: self.n] + offsets, Vr[self.n:]])                                   # a free per-vertex residual (SMPL+D style), before the joints and the skinning
        J = self.Hm @ Vr; R = rodrigues(pose) @ self.R0; G = [None] * len(self.parent)
        for i, p in enumerate(self.parent):
            loc = J[i] - (J[p] if p >= 0 else 0 * J[i]); T = torch.eye(4); T[:3, :3] = R[i]; T[:3, 3] = loc
            G[i] = T if p < 0 else G[p] @ T
        A = torch.stack([g @ torch.cat([torch.cat([torch.eye(3), (-J[i])[:, None]], 1), torch.tensor([[0., 0, 0, 1]])]) for i, g in enumerate(G)])      # [52, 4, 4]: rest -> posed
        Ablend = torch.einsum("vb,bij->vij", self.W, A); vh = torch.cat([Vr[: self.n], torch.ones(self.n, 1)], 1)
        return torch.einsum("vij,vj->vi", Ablend, vh)[:, :3], torch.stack([g[:3, 3] for g in G]), Vr[: self.n]
