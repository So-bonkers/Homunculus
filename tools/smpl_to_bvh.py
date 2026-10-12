"""Convert SMPL dance motion (AIST++ .pkl, FineDance .npy (6D rotations)) to a BVH file that tools/retarget_bvh.py reads with --map smpl.

    python3 -I tools/smpl_to_bvh.py <clip.pkl|clip.npy> <out.bvh> [--format aist|finedance] [--fps N] [--trans-scale S]

The SMPL model files need a licence and are not used: the rest pose is an idealised SMPL T-pose (limbs along the axes, adult proportions); only the bone DIRECTIONS matter to the retargeting, which works
with world orientations (see retarget_bvh.py). SMPL rest joints are axis aligned, so each joint's local axis-angle IS the BVH local rotation.
The floor is found from the feet (2nd percentile of the lowest foot height over the clip), so the root height does not rely on the dataset's translation units.
Translation: AIST++ translation divided by its smpl_scaling is in metres (checked: the planted foot slides least at scale 1 on three travelling clips), so --trans-scale defaults to 1. The printed foot slide at scale 0 and at the chosen scale is a sanity check.
Pickles from a download can run code when loaded, so .pkl files go through an unpickler that only allows numpy arrays."""
import sys, pickle, numpy as np
from scipy.spatial.transform import Rotation as Rot

NAMES = ["Pelvis", "L_Hip", "R_Hip", "Spine1", "L_Knee", "R_Knee", "Spine2", "L_Ankle", "R_Ankle", "Spine3", "L_Foot", "R_Foot", "Neck", "L_Collar", "R_Collar", "Head",
         "L_Shoulder", "R_Shoulder", "L_Elbow", "R_Elbow", "L_Wrist", "R_Wrist", "L_Hand", "R_Hand"]
PARENT = [-1, 0, 0, 0, 1, 2, 3, 4, 5, 6, 7, 8, 9, 9, 9, 12, 13, 14, 16, 17, 18, 19, 20, 21]
OFF = {"L_Hip": (0.06, -0.09, -0.01), "Spine1": (0, 0.11, 0), "L_Knee": (0, -0.39, 0), "Spine2": (0, 0.13, 0), "L_Ankle": (0, -0.40, 0), "Spine3": (0, 0.05, 0), "L_Foot": (0, -0.06, 0.12),
       "Neck": (0, 0.21, 0), "Head": (0, 0.10, 0), "L_Collar": (0.045, 0.10, 0), "L_Shoulder": (0.10, 0, 0), "L_Elbow": (0.26, 0, 0), "L_Wrist": (0.25, 0, 0), "L_Hand": (0.08, 0, 0)}
END = {"Head": (0, 0.12, 0), "L_Foot": (0, 0, 0.09), "R_Foot": (0, 0, 0.09), "L_Hand": (0.04, 0, 0), "R_Hand": (-0.04, 0, 0)}


def offset(n):
    if n == "Pelvis": return np.zeros(3)
    if n in OFF: return np.array(OFF[n], float)
    m = n.replace("R_", "L_"); o = np.array(OFF[m], float); o[0] = -o[0]; return o       # the right side mirrors the left


class _Safe(pickle.Unpickler):
    def find_class(self, mod, name):
        if mod.startswith("numpy") and name in ("ndarray", "dtype", "_reconstruct", "scalar", "_frombuffer"): return super().find_class(mod, name)
        if mod == "collections" and name == "OrderedDict": return super().find_class(mod, name)
        raise pickle.UnpicklingError(f"blocked {mod}.{name}")


def load(path, fmt):
    """-> (poses (N, 24, 3) axis-angle (FineDance's 6D rotations are converted), trans (N, 3), source fps)"""
    if fmt == "aist":
        d = _Safe(open(path, "rb")).load(); return np.asarray(d["smpl_poses"], float).reshape(-1, 24, 3), np.asarray(d["smpl_trans"], float) / float(np.ravel(d["smpl_scaling"])[0]), 60
    a = np.load(path, allow_pickle=False).astype(float)                                           # FineDance: 315 columns = 3 translation + 52 joints x 6D rotation (22 body joints first; hands unused here)
    d6 = a[:, 3:].reshape(len(a), -1, 6)[:, :22]; a1, a2 = d6[..., :3], d6[..., 3:]                 # 6D -> matrix, rows first (checked: with columns first the knees bend forward)
    b1 = a1 / np.linalg.norm(a1, axis=-1, keepdims=True); b2 = a2 - (b1 * a2).sum(-1, keepdims=True) * b1; b2 /= np.linalg.norm(b2, axis=-1, keepdims=True)
    M = np.stack([b1, b2, np.cross(b1, b2)], -2); rv = Rot.from_matrix(M.reshape(-1, 3, 3)).as_rotvec().reshape(len(a), 22, 3)
    return np.concatenate([rv, np.zeros((len(a), 2, 3))], 1), a[:, :3], 30


def fk(rots, root):
    """world joint positions (N, 24, 3), root at `root` (N, 3); rots: (N, 24) Rotation objects"""
    n = len(root); pos = np.zeros((n, 24, 3)); glob = [None] * 24
    for j in range(24):
        if PARENT[j] < 0: glob[j] = rots[j]; pos[:, j] = root
        else: glob[j] = glob[PARENT[j]] * rots[j]; pos[:, j] = pos[:, PARENT[j]] + glob[PARENT[j]].apply(offset(NAMES[j]))
    return pos


def write_bvh(path, euler, root, fps):
    out = ["HIERARCHY"]
    def node(j, ind):
        n = NAMES[j]; pad = "\t" * ind; o = offset(n); kids = [k for k in range(24) if PARENT[k] == j]
        out.append(f"{pad}{'ROOT' if j == 0 else 'JOINT'} {n}\n{pad}{{\n{pad}\tOFFSET {o[0]:.5f} {o[1]:.5f} {o[2]:.5f}")
        out.append(f"{pad}\tCHANNELS {'6 Xposition Yposition Zposition ' if j == 0 else '3 '}Zrotation Xrotation Yrotation")
        for k in kids: node(k, ind + 1)
        if not kids: e = END[n]; out.append(f"{pad}\tEnd Site\n{pad}\t{{\n{pad}\t\tOFFSET {e[0]:.5f} {e[1]:.5f} {e[2]:.5f}\n{pad}\t}}")
        elif n in END: e = END[n]; out.append(f"{pad}\tEnd Site\n{pad}\t{{\n{pad}\t\tOFFSET {e[0]:.5f} {e[1]:.5f} {e[2]:.5f}\n{pad}\t}}")
        out.append(f"{pad}}}")
    node(0, 0)
    out.append(f"MOTION\nFrames: {len(root)}\nFrame Time: {1.0 / fps:.8f}")
    for i in range(len(root)):
        row = [*root[i]] + [x for j in range(24) for x in euler[i, j]]
        out.append(" ".join(f"{v:.5f}" for v in row))
    open(path, "w").write("\n".join(out) + "\n")


def main():
    a = sys.argv[1:]
    def opt(f, d, c=str):
        if f in a: i = a.index(f); v = a[i + 1]; del a[i:i + 2]; return c(v)
        return d
    fmt = opt("--format", None); fps = opt("--fps", None, float); ts = opt("--trans-scale", None, float)
    src, dst = a[0], a[1]; fmt = fmt or ("aist" if src.endswith(".pkl") else "finedance")
    poses, trans, sfps = load(src, fmt); fps = fps or sfps; n = len(poses)
    rots = [Rot.from_rotvec(poses[:, j]) for j in range(24)]
    local = fk(rots, np.zeros((n, 3)))                                                              # pose with the pelvis at the origin
    up = float(np.mean(local[:, 15, 1] - np.minimum(local[:, 10, 1], local[:, 11, 1])))              # head above the feet?
    feet = np.minimum(local[:, 10:12, 1].min(1), local[:, 7:9, 1].min(1) - 0.06)
    horiz = trans[:, [0, 2]] - trans[0, [0, 2]]
    def slide(s):                                                                                      # horizontal speed of the lower foot, median over the frames it is low
        w = local[:, 10:12, [0, 2]] + (horiz * s)[:, None, :]; low = np.argmin(local[:, 10:12, 1], axis=1)
        P = w[np.arange(n), low]; v = np.linalg.norm(np.diff(P, axis=0), axis=1); lowfoot = local[np.arange(n), 10 + low, 1]; m = lowfoot[1:] < np.percentile(lowfoot, 25)
        return float(np.median(v[m])) if m.any() else 9e9
    ts = 1.0 if ts is None else ts
    ty = (trans[:, 1] - trans[:, 1].mean()) * ts                                                    # vertical translation: jumps and squats; which sign makes the lowest foot stay on the floor?
    c = float(np.corrcoef(ty, -feet)[0, 1]) if ty.std() > 1e-6 and feet.std() > 1e-6 else 0.0              # a lowered pelvis (squat) raises the feet relative to it; jumps are free
    sy = 1.0 if c > 0.2 else -1.0 if c < -0.2 else 0.0
    root = np.zeros((n, 3)); root[:, [0, 2]] = horiz * ts; root[:, 1] = sy * ty - np.percentile(feet + sy * ty, 2)
    eul = np.stack([rots[j].as_euler("ZXY", degrees=True) for j in range(24)], 1)
    write_bvh(dst, eul, root, fps)
    print(f"[smpl_to_bvh] {src}: {n} frames at {fps:g} fps = {n / fps:.1f} s; head above feet by {up:.2f} m on average (negative = y is not up); translation scale {ts:g} "
          f"(planted-foot slide {slide(0):.4f} m/frame without translation, {slide(ts):.4f} with); root travels {np.ptp(root[:, 0]):.2f} x {np.ptp(root[:, 2]):.2f} m; pelvis height {root[:, 1].min():.2f}..{root[:, 1].max():.2f} m (vertical sign {sy:+g}) -> {dst}")


if __name__ == "__main__": main()
