# Hand datasets and hand estimators: what to train, what to download, what will run on an AMD GPU

Research note for Homunculus, written 2026-10-14. Slice 07. Audience: a smart newcomer (the author is an audio/speech engineer new to 3D and vision), so terms are defined as they come up.

**Verification convention.** *(verified)* = read on a primary page during this research (arXiv abstract or PDF text, GitHub README / LICENSE / setup.py, project page, Hugging Face page). *(secondary)* = seen on a search-result summary or a third-party page. *(unverified)* = from my memory or inference; check before relying on it. When a page did not state something I write "not stated" rather than guess. Licences are quoted as the page states them; none of this is legal advice, and for anything you might ship commercially, read the actual licence text.

---

## 0. Vocabulary in one screen

- **Hand keypoints, "21 keypoints".** The standard way to describe a hand pose as points: 1 wrist + 4 points per finger (three joints and the fingertip) x 5 fingers = 21. A pose is a list of 21 (x, y) points in the image (2D) or (x, y, z) in space (3D). RHD's paper describes exactly this layout (verified).
- **MANO.** A parametric *hand model* (Romero et al., Max Planck): ~16 joints, a mesh of 778 vertices (verified in the HaMeR paper), driven by a **pose** vector (finger bending angles) and a **shape** vector (fat/thin, long/short fingers). "Estimating MANO" means regressing those numbers from an image; the result is a full 3D hand mesh, not just points. MANO is the hand part of SMPL-H / SMPL-X (the full-body models), which is why a MANO pose can be dropped onto a body rig.
- **Crop.** Hand estimators do not look at the whole frame. A detector finds a box around each hand, the box is cut out ("cropped") and resized to a fixed square, and the network sees only that. So "how many pixels is the hand" really means "how much real detail survives in the crop before it is resized".
- **MPJPE** (Mean Per-Joint Position Error): average 3D distance, usually in millimetres, between predicted and true joints. **PA-MPJPE** first aligns the prediction to the truth (rotation, scale, shift: "Procrustes alignment"), so it measures pose shape only. **PCK@x** (Percentage of Correct Keypoints): the fraction of predicted 2D keypoints that land within a threshold of the truth; the threshold is a fraction of the box size (PCK@0.05 = within 5% of the box). Higher PCK is better, lower MPJPE is better.
- **In the wild** = ordinary photos/video, not a lab with calibrated cameras.

---

## 1. Datasets

### 1.1 Summary table

"Login" means whether getting the files needs an account, a form or an approval, as far as the pages say.

| Dataset | Year | Size | Annotated | Hand scale / image size | Licence (as stated) | Login? |
|---|---|---|---|---|---|---|
| **HaGRID v1 / v2 / v2-full** | 2022 / 2023 / 2024 | v1: 552,992 images, 18 classes. v2 (2024 "HaGRIDv2"): 1,086,158 FullHD images, 33 gestures + no_gesture, 65,977 persons (all verified) | Gesture **class labels** + hand boxes; MediaPipe landmarks files | FullHD frames, person at 0.5-4 m (verified); a 512 px-min-side version is 119.4 GB | "a variant of CC BY-SA 4.0" with a separate licence PDF; I could not read the PDF text, so **exact terms unverified** | No login mentioned (verified: `download.py` or direct zips) |
| **FreiHAND** | 2019 | 130,240 train samples (32,560 unique, each in 4 background versions), 3,960 eval (verified) | 3D keypoints (21), 3D shape (MANO), segmentation | 224x224 images, hand fills the frame, green-screen capture (verified) | Research only, **commercial use prohibited** (verified) | No (direct download, 3.7 GB + 724 MB eval) |
| **InterHand2.6M** | 2020 | 2.6M labelled single/interacting hand frames (verified abstract); 5 fps set 2,590,347 frames = 80 GB, 30 fps set 12,469,899 frames = 365 GB (verified) | 3D joints, MANO fits (NeuralAnnot), boxes, camera params | Resolution not stated on pages I read | **CC-BY-NC 4.0** (verified) | No login mentioned; images on S3 index pages, annotations on Google Drive (verified) |
| **COCO-WholeBody** | 2020 | COCO person images; 133 keypoints per person incl. 42 for hands (verified); hand-instance count not stated | 2D hand keypoints + left/right hand boxes | **Real, small, in-the-wild hands** (COCO photos) | Annotations CC BY-NC 4.0, "ONLY for research and non-commercial use"; images follow Flickr terms (verified) | No (images from COCO site; annotations on OneDrive / Google Drive / Baidu) |
| **HInt** (HaMeR's) | 2023 | 40.4K annotated hands: 12.0K New Days, 5.3K VISOR, 23.2K Ego4D (verified, HaMeR paper) | 2D keypoints for 21 joints + per-keypoint "existence" and "occluded" flags | Mostly egocentric / hand-object; resolution not stated | Repo MIT; **dataset terms not separately stated**; underlying sources have their own terms (verified) | Partial archive (annotations + New Days + VISOR frames) by direct `wget`; **Ego4D frames need Ego4D access (page says ~48 h)** (verified) |
| **RHD** (Rendered Handpose Dataset) | 2017 | 41,258 train + 2,728 test (verified) | 21 keypoints per hand (2D, 3D, visible/occluded flag), depth, 33-class segmentation | 320x320 render of a whole person with a random camera near one hand (verified, see section 3) | Research only, **"Any commercial use is prohibited"** (verified) | No login (7.1 GB zip) |
| **GANerated Hands** | 2018 | >330,000 images (verified) | 2D + 3D for 21 keypoints | 256x256 colour images (verified) | "only be used for scientific/non-commercial purposes" (verified) | No registration mentioned; 33.7 GB zip (verified) |
| **ObMan** | 2019 | ~150K synthetic images of hands grasping ShapeNet objects (verified) | hand + object meshes (SMPL+H/MANO poses), 2D/3D keypoints, segmentation, depth | resolution not stated | not stated on page I read; separate licence page | **Yes: download request form** (verified) |
| **HO-3D** (v3) | 2020 | v3: 103,462 annotated images; v2 originally 77,558 (verified; the paper text gives 77,558 / 68 sequences in one place and "80,000 / 65" in the abstract) | hand + object 3D pose (HOnnotate, depth-based; need MANO to use) | real hand-object RGB-D | no named licence; "academic research only", no redistribution, no commercial use (verified) | No registration stated (OneDrive links); test set via CodaLab |
| **DexYCB** | 2021 | ~119 GB archive, 10 subjects (verified); image/camera counts not read | 3D hand pose, 6D object pose, 2D keypoints | not stated | **CC BY-NC 4.0** (verified) | No (direct download / toolkit) |
| **GRAB** | 2020 | 10 subjects, 51 objects (verified); size not stated | full-body+hands SMPL-X motion, object pose, contact (mocap) | n/a (motion capture, not images) | Licence agreement on site; commercial needs ps-licensing@tue.mpg.de (verified) | **Yes: account + licence** |
| **ARCTIC** | 2023 | ~2.1M images, 8 third-person + 1 egocentric view, 54 Vicon cameras (verified) | SMPL-X + MANO 3D ground truth, articulated objects | "high-resolution" (not quantified) | "not available for commercial use" (verified) | **Yes: account on arctic.is.tue.mpg.de** |
| **BEAT2** (and BEAT) | 2024 | 4,108 rows, 20.3 GB on HF (verified); hours not stated on the pages I read | SMPL-X + FLAME motion with speech/gesture | n/a (mocap) | HF card says **apache-2.0** (verified); repo itself shows no LICENSE file | No gating shown (verified); `git clone` from Hugging Face |
| **Motion-X** | 2023 | 81.1K clips, 15.6M frames (verified); a search summary says 144.2 h (secondary) | SMPL-X incl. `pose_hand` (finger articulation) and hand text labels (verified) | n/a (some subsets from online video via estimation) | "Motion-X License for non-commercial purposes"; AMASS/GRAB parts under MPI licences (verified) | **Yes: authorisation form**, plus AMASS and GRAB registration for those parts (verified) |
| **FineDance** | 2023 | paper: 14.6 h, 22 genres (verified); **public download is only a 7.7 h part** (verified) | SMPL-H motion; paper says "fine-grained hand motions" (verified) | n/a (mocap) | **Non-commercial research licence** (Tsinghua, Prof. Xiu Li); no distribution; no commercial/military/surveillance use (verified from LICENSE) | No login (Google Drive / Baidu) |

### 1.2 Notes by dataset

**HaGRID (verified).** The only one here with *class labels* of the kind you want (it has "fist", "palm", "one" (point), "like", etc.; I did not list all 33 names, check the README). But: the hands are big and sharp (FullHD frames, a person facing a webcam within 0.5-4 m, mostly indoors), the poses are deliberate gestures rather than the half-relaxed hands of dancers, and the classes are gesture-language classes, not your open/relaxed/fist/grip/point/thumbs-up/pinch set. Useful for pre-training a classifier or for synthetic-to-real sanity checks; it will not look like a 40 px dancer's hand.

**FreiHAND (verified).** Real hands, accurate MANO annotations, but captured in a studio on green screen then composited onto backgrounds, hand fills a 224x224 crop. Good for *close-up estimator* training/benchmarking, not for tiny hands.

**InterHand2.6M (verified).** The biggest real 3D set, includes two interacting hands, studio capture. Huge (80 GB for the 5 fps subset). The 5 fps subset is enough for anything you will do. CC-BY-NC.

**COCO-WholeBody (verified).** This is the only entry in the table with *real photographs of people at ordinary distances with 2D hand keypoints*, so it contains genuinely small, blurry hands. HaMeR trains on it. A caution I could not resolve from the page: the keypoints are 2D and were produced with a model-in-the-loop plus human correction; I did not verify per-hand quality at tiny sizes.

**HInt (verified).** Built specifically to measure *in-the-wild* hand performance (egocentric, hand-object). It is the best public 2D benchmark for "does the estimator hold up on messy real hands". It is egocentric/kitchen data, so it does not contain dance or distant crowds either.

**RHD, GANerated, ObMan (verified).** Synthetic. See section 3 for RHD. GANerated is synthetic hands pushed through a GAN to look more like real photos, 256x256; the real images from the same project are separate (30.6 GB "Real Hands" zip, verified). ObMan is hands holding objects (grasp poses: grip-like, not open/point).

**HO-3D, DexYCB, GRAB, ARCTIC (verified).** Hand-object manipulation datasets. Their poses are grasps and manipulation: useful for "grip" and for a motion prior of closed hands, but they contain no dance. GRAB and ARCTIC require an account; GRAB and Motion-X are tied to MPI licences.

**BEAT2 (verified partly).** Conversational gesture with SMPL-X. Whether its finger channels are mocap or estimated I did not verify (the page does not say). Licence on the HF card is Apache-2.0, but treat that carefully: BEAT's underlying release terms and the SMPL-X model itself carry their own licences (see 2.3).

**Motion-X (verified).** Includes an online-video subset (32.5K clips, 6.0M frames, verified) whose pose came from a video estimator, so those fingers are as noisy as any video estimator's. The mocap subsets (AMASS, GRAB) are cleaner. Everything is non-commercial and gated by a form.

### 1.3 Does FineDance really contain fingers?

- **Paper (verified, arXiv 2212.03741 abstract):** "fine-grained hand motions"; 14.6 hours, 22 genres. A search summary also says it uses the standard 52 joints (secondary).
- **Your local copy (checked, shape only):** `mocap_test/finedance/fd/finedance/motion/001.npy` has shape (2928, 315). 315 = 3 (root translation) + 52 joints x 6 (the 6-number rotation form). That is consistent with 52 joints = 22 body + 30 hand (verified shape; the 6D-rotation reading is my inference). The 52 count matches the "SMPL-H, 52 joints" you already described. I did not inspect whether the finger channels move (vs. being constant), so do one quick check: the std of the 30 hand-joint rotations over time should be clearly non-zero.
- **How the fingers were obtained:** the repo README says only "SMPLH format". The paper says the motion is accurate; whether the fingers were mocap (glove / marker) or optical-fitted I **did not verify**.
- **Only 7.7 h of 14.6 h is downloadable** (README, verified). Do not assume you have the full set.
- **Licence (verified):** non-commercial scientific research, education or artistic projects; no commercial, pornographic, military or surveillance use *including training models for those purposes*; no sharing or sublicensing. So a model trained on it and shipped in a product is off-limits without asking the licensor. Research and personal art use is fine.

### 1.4 Dance / performance / sign datasets with hands

| Dataset | What | Hand data | Access / licence |
|---|---|---|---|
| FineDance | dance, 22 genres | 30 finger joints (above) | non-commercial, 7.7 h public (verified) |
| SoulDance (ICCV 2025) | professional mocap music-dance, body + hands + face, SMPL-X | yes | **not released**: the project page says legal issues delay open-sourcing as of Sept 2025 (secondary; re-check) |
| InterDance (arXiv 2412.16982) | duet dance, SMPL-X | hands from **inertial data gloves** because optical hand capture was occluded (secondary) | not verified |
| Music2Dance (2020) | older dance set | finger motion (secondary) | not verified |
| Motion-X (online-video part) | includes dance/martial arts performances | estimated fingers | non-commercial, form (verified) |
| SignAvatars (arXiv 2310.20436) | sign language, 70K videos, 153 signers, 8.34M frames, SMPL-X + MANO | **estimated** hand poses (automatic annotation) (secondary) | paper says CC BY-NC-SA; GitHub says "contact the authors"; contradictory (secondary) |
| How2Sign / DGS / WLASL | sign videos (source of SignAvatars) | no 3D | non-commercial licences (secondary) |
| GRAB, ARCTIC, DexYCB, HO-3D | grasp / manipulation | accurate, but not expressive | see table |
| Conducting | I searched for hand motion in conducting and found no dedicated public dataset. **Unverified / not found.** | | |

Takeaway: for *finger motion that looks like dance*, FineDance is the only clean, public option I found; I found no public dataset of fingers in *group* dance. DanceHMR (arXiv 2605.18102, ByteDance, May 2026) is a method paper for hand-aware body recovery from video that names dancing as a use case; its results are on ARCTIC and do not cover very small hands (secondary; figures not verified).

---

## 2. Estimators

### 2.1 Comparison

| Method | Code licence | Weights / model licence | MANO / body-model file needed? | Input | Notes on AMD |
|---|---|---|---|---|---|
| **HaMeR** (CVPR 2024, arXiv 2312.05251) | **MIT** (verified) | not separately stated on the repo; ViTPose backbone code is under `third-party`; weights come from `fetch_demo_data.sh` (verified). Treat as non-commercial in practice because of MANO and the training sets | **Yes: `MANO_RIGHT.pkl`** after registering on the MANO site (verified); only right-hand model is needed (left is handled by mirroring) | ViT-H backbone; config `MODEL.IMAGE_SIZE = 224` (verified); bbox/crop details not read | No ROCm mention (verified: README silent, repo search for ROCm/AMD returns 0 issues). See 2.2 |
| **WiLoR** (arXiv 2409.12259, 2024) | **Models: CC-BY-NC-ND** (verified); code licence not separately stated | same | **Yes: MANO** (register, put `MANO_RIGHT.pkl` in `mano_data/`) (verified) | YOLO hand detector (Ultralytics 8.1.34) + transformer reconstructor; `--fast` flag gives "up to 1.6x faster" (verified) | tested on PyTorch 2.0.0 / CUDA 11.7 (verified); no pytorch3d/detectron2 in requirements (verified) |
| **WiLoR-mini** (third-party) | licence not stated on page | auto-downloads weights | MANO still needed in principle | pip package; supports CPU or CUDA and float16 | convenient; **licence unverified** |
| **SAM 3D Body** (Meta, 2025-26) | "SAM License" (verified: both code and checkpoints); read the LICENSE file for terms | **gated** Hugging Face checkpoints (`facebook/sam-3d-body-dinov3`, `-vith`), must request access and authenticate; access refused from sanctioned jurisdictions (verified) | **No MANO**: uses Meta's **MHR** rig (Apache-2.0, 5 of 45 identity coefficients are for hands) (verified). Output would need conversion to SMPL-X/MANO to drive your rig | whole body + feet + hands, optional hand-decoder refinement, 2D keypoint/mask prompts (verified) | needs detectron2 (pinned commit, built from source), MoGe optional; GPU memory not stated (verified) |
| **MediaPipe Hands / Hand Landmarker** | **Apache-2.0** for the repo (verified) | model-card terms not read | no | palm detector, then landmark model at 192x192 / 224x224; 21 landmarks x, y and *relative depth* (secondary); trained on ~30K real images plus synthetic hands (secondary) | runs on CPU/TFLite; no GPU/ROCm needed |
| **RTMPose / RTMW (MMPose)** | repo licence not stated on page I read (MMPose is generally Apache-2.0, unverified) | per model card | no | hand 2D: RTMDet-nano detector (320x320) + RTMPose-m hand (256x256, 21 keypoints); alpha versions (verified) | `rtmlib` runs with ONNXRuntime, no PyTorch/MMCV (verified) |
| **Hand4Whole** (CVPRW 2022) | **MIT** (verified) | n/a | **Yes: SMPL, SMPL-X, MANO, FLAME files** downloaded from their sites (verified) | box in `demo.py` | needs pyrender/PyOpenGL for headless |
| **MANO model files** | n/a | Free "for research purposes"; sign-up + licence acceptance required; commercial use: **terms on a separate page I did not read**. The site was updated in 2026 with SMPL+H 300-shape files (verified) | | | |

### 2.2 Accuracy, and what happens on small or blurry hands

- **HaMeR (verified, paper text):** trained on a consolidated 2.7M-example set (FreiHAND, HO3D, MTC, RHD, InterHand2.6M, H2O3D, DexYCB, COCO-WholeBody, Halpe, MPII-NZSL), "4x larger than FrankMocap's". Claims "2-3x improvement in PCK@0.05" over baselines on HInt and shows qualitative robustness to occlusion, gloves and motion blur. On HInt PCK is much lower for joints annotated *occluded* than for visible ones (Table 3, verified in structure; I deliberately do not quote the per-column numbers because the table text extracted ambiguously). Fine-tuning on HInt's own training set raised PCK mainly on the egocentric subsets (Table 4, verified).
- **What the paper does not show:** results on hands of ~40 px. All its evidence is on crops that are, after the detector, big enough to resize to the network input. The paper contains no study of resolution and I found no primary source that benchmarks HaMeR/WiLoR at 40 px. **So its behaviour on your wide shots is unmeasured: treat as unverified and measure it yourself.** My expectation (unverified inference): 40 px hands upsampled to 224 px give plausible-looking, MANO-prior-regularised hands whose finger detail is hallucinated by the prior; open vs fist may survive, individual finger bends will not.
- **A published relevant observation (secondary):** a 2025 gesture-recognition review notes distance and low resolution corrupt discriminative hand features; a long-range gesture paper (arXiv 2311.15361) addresses this for webcams at up to 25 m. I found no work on fist-vs-open at 40 px specifically.
- **Detector is the first failure point.** All the above need a hand box first. At 40 px, hand detectors (YOLO in WiLoR, ViTPose-wholebody or RTMDet in HaMeR/RTMPose) miss or jitter. You already have body keypoints from GVHMR/its 2D tracker; **wrist keypoints can define the hand box** (square of a fixed multiple of the forearm length centred slightly past the wrist) and skip the detector. This is design advice, not a verified result.

### 2.3 Does it run on your ROCm GPU? What I could and could not verify

Your environment has `torch 2.7.1+rocm6.2.4` (verified locally with `pip list`).

| Dependency | Where | ROCm status |
|---|---|---|
| `torch` / `torchvision` / `timm` / `einops` / `pytorch-lightning` | HaMeR, WiLoR | pure PyTorch: **should work** (unverified for these specific models; no ROCm report found) |
| `detectron2 @ git+...` | listed in HaMeR `setup.py` (verified); README says it appears in acknowledgements only (verified). From memory, HaMeR's demo uses it for the optional body detector (unverified) | detectron2 is built from source against the torch in the environment; building against ROCm is **unverified**. WiLoR avoids it |
| `mmcv==1.3.9` | HaMeR `setup.py` (verified) | very old; it ships CUDA ops and pins ancient torch. **Highest risk** for a port: it will most likely fail to install against torch 2.7. HaMeR uses it for the bundled ViTPose (unverified detail) |
| `pyrender` | HaMeR, WiLoR | only for *drawing* the mesh via OpenGL; not needed for getting MANO parameters. Skip it |
| `xformers` | **not in HaMeR's setup.py** (verified) | not applicable; for general ROCm use, official prebuilt ROCm wheels are claimed by a third-party summary (secondary), and a forum thread shows an RX 7900 XTX user hitting a missing ROCm attention kernel (secondary). Avoid |
| `pytorch3d` | not in HaMeR's setup.py or WiLoR's requirements (verified) | not required |
| `ultralytics==8.1.34` | WiLoR | pure PyTorch, generally fine on ROCm torch (unverified) |
| `chumpy`, `smplx==0.1.28` | both | pure Python; chumpy is old and breaks on new NumPy (common known issue, unverified); MANO pickle loading needs it or a patched loader |

**Verdict.** No source I found reports HaMeR or WiLoR on AMD. My assessment (unverified): **WiLoR is the easier port** (no detectron2, no mmcv; pure PyTorch plus Ultralytics). **For HaMeR the port work is mainly dependency surgery**: drop detectron2 and mmcv by feeding your own boxes and loading only the ViT-H + head weights. No CUDA kernels appear to be needed for inference. Budget: half a day to a day for either, with the realistic failure being an old pinned package, not the GPU. Memory: neither README states GPU memory (verified); ViT-H plus a small head at 224 px in fp16 is likely fine inside 24 GB (unverified estimate).

**SAM 3D Body:** needs detectron2 at a pinned commit (verified), gated weights, MHR rather than MANO (so a conversion layer), and a licence you must read. It is a heavier, more restrictive port; I would not start there.

**Licence reality check for HaMeR/WiLoR.** HaMeR code is MIT but you must register for MANO and accept its research licence; WiLoR's weights are CC-BY-NC-ND (no commercial, no derivatives: *fine-tuning and redistributing a modified model counts as a derivative, which is a problem; unverified legal reading*). For a personal or research animation tool this is fine. For something sold, ask the MANO and WiLoR owners first.

---

## 3. RHD for your two uses

**What RHD is (verified, project page + paper text).** 41,258 training and 2,728 test images, 320x320, rendered in Blender from 20 free Mixamo characters performing 39 actions (16 characters/31 actions train, 4 characters/8 actions validation). For each frame a random camera is placed near one hand (hand centres 40-65 cm from the camera), a random background from 1,231 Flickr photos *without persons* is pasted, 0-2 random lights, random specular reflection, and JPEG quality randomised "from no compression up to 60%". Labels: 21 keypoints per hand (2D, 3D, visible/occluded), depth, and 33 segmentation classes (3 per finger, palm, person, background). Licence: research only, no commercial use.

**Hand shapes and poses.** The poses are whatever the Mixamo body animations do (walking, gesturing, fighting, etc.). They are **not** hand-specific: Mixamo characters generally have simple hand animation, so the pose variety is narrow and heavy on relaxed/slightly curled hands. I did not count poses, but nothing in the paper suggests dedicated fist/point/grip sets; treat the distribution of open/fist as **unknown** until you check it from the 3D keypoints (finger flexion angle histograms; easy to do with the keypoint files).

**Resolution.** Because the camera is 40-65 cm from the hand in a 320x320 frame, hands are fairly large in the image (unverified size; measure bounding boxes from the keypoints). So RHD is not natively a "tiny hand" dataset; you create tiny hands by downsampling.

**Is it a good fit?**

| Question | Answer |
|---|---|
| Classifier for open/fist on 40 px blurry real hands | **Weak as the only source, fine as one ingredient.** Positives: free keypoints let you derive open/fist labels automatically from finger flexion (a rule, not hand-labelling), depth and segmentation masks let you cut clean hand crops. Negatives: cartoon-ish Mixamo skin/clothes, 20 characters only (16 for train), no person-with-person occlusion, backgrounds without people, narrow poses. Domain gap synthetic-to-real is real (the original paper's own Dexter test needed training on RHD and still reported cross-dataset difficulty, verified qualitatively). |
| Hand *estimator* for tiny real hands | **No.** It is small, from 2017, not MANO-parameter labelled, and HaMeR already uses it as one among ten sets. |
| Cross-dataset sanity check | Yes: it is a free reference set for testing your degradation pipeline. |

**How to degrade to ~40 px (design guidance, unverified as a recipe).** Cut the hand box from the 320x320 frame (use the 21 keypoints; add a margin), then simulate the camera chain in the order reality does it: (1) random-size downsample to a target of 24-60 px on the long side with a random filter (area/bilinear/bicubic), (2) optional motion blur kernel (length 2-8 px, random direction) and/or defocus (Gaussian sigma 0.5-1.5), (3) video compression: JPEG quality 20-60 or actual H.264 re-encode, (4) mild noise and colour shift, (5) upsample to the classifier input (e.g. 64x64) the same way real crops will be resized. Calibrate the strengths by taking your **own hand-labelled real crops** and comparing the pixel statistics (Laplacian variance, edge width). Note RHD's own JPEG-augmentation range (to quality 60) is milder than a 1080p H.264 group shot.

---

## 4. Recommendation (ranked, per goal)

### Goal A: classifier (open / fist / point / grip ...) for tiny blurry hand crops

Ranked, cheapest first:

1. **Your own labels are the real asset.** Make the editor also dump per-frame hand crops (already planned) so each timeline block becomes hundreds of labelled crops. Realistic risk: the labels are *per timeline block* (a pose is held between changes, eased), so frames near transitions are mislabelled; down-weight or drop the transition frames (the ease length is already a parameter). Effort: a day to wire up; labels cost your time. Very high value because they are the target domain.
2. **Synthetic hands from your own rig** (already planned) with the degradation chain above. Plus RHD as an extra synthetic source with auto-labels from keypoints. Effort: 1-2 days for RHD crops + labelling rule (download 7.1 GB, no login, verified).
3. **Real pre-training data (optional):** COCO-WholeBody hand crops with 2D keypoints (real, small, blurry, no login): derive open/fist from keypoint geometry (fingertip-to-wrist distance vs palm length: a rule you must validate by eye on a few hundred crops). HaGRID (no login; use the 512 px version, 119.4 GB, or only the "fist", "palm" archives) as a clean-image pre-training for the fist/palm/point/like classes. Effort: 2-3 days; benefit uncertain.
4. **Use a pretrained backbone and fine-tune** a small CNN/ViT (e.g. a small timm model) with heavy blur/downsample augmentation. Evaluate on a held-out *real* set from *different dances* (not different frames of the same dance: frames of one clip are near-duplicates, so a random split will overstate accuracy).
5. **Do not** expect to predict individual finger bends at 40 px: keep the label set to a few coarse classes. A fist is mostly a compact blob; classes like "point" vs "relaxed" are the hard pair (inference, not verified).

First download: **RHD (7.1 GB)** and your own crops; then COCO-WholeBody hand annotations. Risks: synthetic-to-real gap; label noise at transitions; class imbalance (open hands dominate).

### Goal B: close-up estimator (hands 150-250 px)

1. **WiLoR first, HaMeR as fallback**, or run them offline for close-ups only and, per-frame, feed their output as *finger pose suggestions* you accept or edit in the timeline. WiLoR has the lighter dependency list (verified); HaMeR is MIT and the better-documented, but needs `mmcv==1.3.9` and detectron2 to be removed. Both need MANO registration (free, research). Effort: 0.5-1 day to run on frames with your own boxes; 1-2 days to make the finger output robust and smooth. Risks: unverified ROCm behaviour, licence limits (NC / ND), per-frame jitter (smooth with a filter), left/right confusion, wrong flexion when the palm faces away.
2. **MediaPipe Hand Landmarker** as a cheap alternative that needs no GPU and no MANO. Apache-2.0 repo (verified). Gives 21 landmarks, not MANO angles, so you must convert to joint angles yourself (inverse kinematics); fine for open/fist/point, weak for pinch/grip with occlusion. Effort: 1-2 days.
3. **RTMPose hand / whole-body via rtmlib** (ONNX, no PyTorch needed): the third option for 2D keypoints; hand models are alpha (verified).
4. **SAM 3D Body** only if you want a second opinion: gated, heavier, MHR conversion required.
5. Skip training your own estimator: the data (MANO-labelled) is gated or non-commercial and the gain over HaMeR/WiLoR would be small for you.

First download: MANO (sign up on mano.is.tue.mpg.de), then WiLoR weights. Benchmark on **your own close-ups**, not on FreiHAND: a few dozen hand-checked frames tell you more than published numbers.

### Goal C: finger-motion priors for dance

1. **FineDance (already local):** compute a library of *real* dance hand poses and transitions (the 30 hand joints x 52-joint format). Use it to (a) pick the pose vocabulary (cluster hand poses; see which of your 7 named poses actually occur and with what intermediate poses), (b) sample plausible in-between motion instead of a linear ease, (c) add small natural variation ("micro-motion") to held poses. Effort: 1-2 days. Risks: licence is non-commercial/no-redistribution (verified); only 7.7 h of 14.6 h is public (verified); fingers' provenance unverified; hands in FineDance have the *choreographer's* style, not necessarily yours.
2. **Motion-X / BEAT2** for gesture-style fingers (non-dance): BEAT2 is the easiest (no gate shown, Apache-2.0 on HF card, verified; SMPL-X). Motion-X needs a form. Use for pose diversity only.
3. **GRAB / ARCTIC / HO-3D / DexYCB** for grip shapes: only if you need object-holding. Registration on some.
4. **A learned prior** (small VAE or diffusion over hand-pose sequences) is a research project, not a first step; do it only after the simple clustering/transition library from (1) proves useful.

First download: nothing new for step 1; BEAT2 next (`git clone` from Hugging Face, 20.3 GB).

### Overall order of work (my recommendation)

1. Hand crops saved with the labels (days, high value).
2. Synthetic + degraded crops from your rig and RHD; train the first classifier; evaluate on a held-out real dance.
3. Run WiLoR on close-ups with boxes from the wrist keypoint; check ROCm (day).
4. FineDance hand-pose library for priors and in-betweens.
5. Everything else only if these hit a ceiling.

---

## 5. What I could not verify (so you know)

- The exact HaGRIDv2 licence text (PDF not readable).
- Image resolution of InterHand2.6M, HInt, ObMan, DexYCB, ARCTIC, HO-3D (pages do not state).
- Whether FineDance fingers are mocap or fitted; whether the finger channels in your local files really vary (one check suggested above).
- Any report of HaMeR or WiLoR running on ROCm; GPU memory figures for any estimator.
- Any benchmark of any hand estimator at ~40 px.
- MANO's commercial terms (page links a separate licence page).
- BEAT2 hours and whether its fingers are captured or estimated.
- Whether MMPose and RTMPose hand weights are Apache-2.0.

---

## 6. Sources

- HaMeR repo (MIT, MANO, setup): https://github.com/geopavlakos/hamer ; setup.py https://raw.githubusercontent.com/geopavlakos/hamer/main/setup.py ; LICENSE https://raw.githubusercontent.com/geopavlakos/hamer/main/LICENSE.md ; config https://raw.githubusercontent.com/geopavlakos/hamer/main/hamer/configs/__init__.py
- HaMeR paper: https://arxiv.org/abs/2312.05251 (PDF https://arxiv.org/pdf/2312.05251)
- HInt: https://github.com/ddshan/hint
- WiLoR: https://github.com/rolpotamias/WiLoR ; paper https://arxiv.org/abs/2409.12259 ; requirements https://raw.githubusercontent.com/rolpotamias/WiLoR/main/requirements.txt ; WiLoR-mini https://github.com/warmshao/WiLoR-mini
- SAM 3D Body: https://github.com/facebookresearch/sam-3d-body ; INSTALL https://raw.githubusercontent.com/facebookresearch/sam-3d-body/main/INSTALL.md ; MHR https://github.com/facebookresearch/MHR
- MANO: https://mano.is.tue.mpg.de/
- MediaPipe Hand Landmarker guide: https://developers.google.com/edge/mediapipe/solutions/vision/hand_landmarker ; licence https://github.com/google-ai-edge/mediapipe/blob/master/LICENSE
- RTMPose / RTMW: https://github.com/open-mmlab/mmpose/blob/main/projects/rtmpose/README.md
- Hand4Whole: https://github.com/mks0601/Hand4Whole_RELEASE
- HaGRID: https://github.com/hukenovs/hagrid
- RHD: https://lmb.informatik.uni-freiburg.de/resources/datasets/RenderedHandposeDataset.en.html ; paper https://arxiv.org/abs/1705.01389
- FreiHAND: https://lmb.informatik.uni-freiburg.de/resources/datasets/FreihandDataset.en.html
- InterHand2.6M: https://mks0601.github.io/InterHand2.6M/ ; https://github.com/facebookresearch/InterHand2.6M ; https://arxiv.org/abs/2008.09309
- COCO-WholeBody: https://github.com/jin-s13/COCO-WholeBody
- GANerated Hands: https://handtracker.mpi-inf.mpg.de/projects/GANeratedHands/GANeratedDataset.htm
- ObMan: https://www.di.ens.fr/willow/research/obman/data/
- HO-3D: https://github.com/shreyashampali/ho3d ; page https://www.tugraz.at/institute/icg/research/team-lepetit/research-projects/hand-object-3d-pose-annotation/
- DexYCB: https://dex-ycb.github.io/
- GRAB: https://grab.is.tue.mpg.de/
- ARCTIC: https://github.com/zc-alexfan/arctic
- BEAT2: https://huggingface.co/datasets/H-Liu1997/BEAT2 ; https://github.com/PantoMatrix/PantoMatrix
- Motion-X: https://github.com/IDEA-Research/Motion-X
- FineDance: https://github.com/li-ronghui/FineDance ; LICENSE https://raw.githubusercontent.com/li-ronghui/FineDance/main/LICENSE ; paper https://arxiv.org/abs/2212.03741
- SoulDance: https://github.com/xjli360/SoulDance-Official (secondary)
- InterDance: https://arxiv.org/abs/2412.16982 (secondary)
- SignAvatars: https://arxiv.org/abs/2310.20436 (secondary)
- DanceHMR: https://arxiv.org/abs/2605.18102 (secondary)
- Long-range gesture recognition: https://arxiv.org/abs/2311.15361 (secondary)
- xformers on ROCm forum thread: https://discuss.pytorch.org/t/rocm-torch-xformers/217566 (secondary)
