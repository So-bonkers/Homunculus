"""The fitted SMPL-X template as a Mixamo-skeleton character (52 bones, the app's rig): the skinning weights of the SMPL-X joints are summed onto the Mixamo bones they correspond to.
    gvhmr/.venv/bin/python tools/template_fit/to_mixamo.py FITDIR   (reads fit.npz, fit.obj; writes FITDIR/mixamo.npz: verts, faces, weights [V x 52], names, parents, joint index per bone)
Then `blender -b --python tools/template_fit/mixamo_rig.py -- FITDIR` builds the armature and exports a glb/fbx."""
import sys, os, numpy as np, torch, smplx, trimesh
d = sys.argv[1]; F = np.load(os.path.join(d, "fit.npz"), allow_pickle=True); gender = str(F["gender"])
model = smplx.create("gvhmr/smplsrc/smplx/models_lockedhead", model_type="smplx", gender=gender, use_pca=False, flat_hand_mean=True, num_betas=F["betas"].shape[1], batch_size=1)
W = model.lbs_weights.detach().numpy()                                   # 10475 x 55
# SMPL-X joints: 0 pelvis 1/2 hips 3 spine1 4/5 knees 6 spine2 7/8 ankles 9 spine3 10/11 feet 12 neck 13/14 collars 15 head 16/17 shoulders 18/19 elbows 20/21 wrists 22 jaw 23/24 eyes, 25-39 left hand, 40-54 right hand
# a hand is index, middle, pinky, ring, thumb (3 joints each)
names, parents, src = [], [], []
def add(n, p, j): names.append(n); parents.append(p); src.append(j)
add("Hips", None, 0); add("Spine", "Hips", 3); add("Spine1", "Spine", 6); add("Spine2", "Spine1", 9); add("Neck", "Spine2", 12); add("Head", "Neck", 15)
FING = [("Index", 0), ("Middle", 3), ("Pinky", 6), ("Ring", 9), ("Thumb", 12)]
for side, o in (("Left", 0), ("Right", 1)):
    add(side + "Shoulder", "Spine2", 13 + o); add(side + "Arm", side + "Shoulder", 16 + o); add(side + "ForeArm", side + "Arm", 18 + o); add(side + "Hand", side + "ForeArm", 20 + o)
    for f, k in FING:
        for i in range(3): add(f"{side}Hand{f}{i+1}", side + "Hand" if i == 0 else f"{side}Hand{f}{i}", 25 + 15 * o + k + i)
    add(side + "UpLeg", "Hips", 1 + o); add(side + "Leg", side + "UpLeg", 4 + o); add(side + "Foot", side + "Leg", 7 + o); add(side + "ToeBase", side + "Foot", 10 + o)
assert len(names) == 52
Wm = np.zeros((W.shape[0], 52)); idx = {j: [] for j in range(55)}
for b, j in enumerate(src): Wm[:, b] += W[:, j]
Wm[:, names.index("Head")] += W[:, 22] + W[:, 23] + W[:, 24]              # jaw and eyes follow the head
print("weights: every vertex sums to", Wm.sum(1).min().round(4), "-", Wm.sum(1).max().round(4), "; spine3 (9) is Spine2, collars are Shoulders")
m = trimesh.load(os.path.join(d, "fit.obj"), process=False)
np.savez(os.path.join(d, "mixamo.npz"), verts=np.asarray(m.vertices), faces=np.asarray(m.faces), weights=Wm, names=np.array(names), parents=np.array([p or "" for p in parents]), joints=F["joints"][:55][src])
print("wrote", os.path.join(d, "mixamo.npz"), len(m.vertices), "vertices")
