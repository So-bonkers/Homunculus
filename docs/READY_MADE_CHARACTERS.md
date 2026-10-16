# Ready-made rigged characters (game models)

Community models of the Valorant agents (GLB or FBX with the game's own humanoid skeleton, textures inside the file or in a folder) can be put on any of the dance clips.

    python tools/import_rigged.py --name yoru --model Yoru.glb [--textures <folder>[|m0=file,m1=file]] [--skeleton valorant|mixamo]
    python tools/register_group.py --dir <group dir> --run yoru --rig runs/yoru/07_rig/yoru_rigged.glb --video ... --prefix yoru --only 1

- `tools/convert_rigged.py` (Blender) rebuilds the game rig as the 52-bone Mixamo skeleton: the bones sit at the same joints, the weights of the twist, cloth, face and fourth spine bones go to the nearest of the 52, the model is turned to face -Y (from the hips: the way left hip minus right hip crosses up), scaled to metres if it was made in centimetres (Tejo) and moved so its hips are at the origin. Every tool that expects Mixamo names (hand layer, retargeting, library pictures) then works unchanged. Pictures a material lacks are attached from the textures folder by name (`_DF` is the colour map; hair and eyes by their material names).
- A model with no rig: `tools/skin_from_donor.py` copies the weights of a converted agent's rig onto its mesh (nearest surface point, with a reach check so loose pieces are not dragged by a hand). It gave Raze her textures but her right arm flew away when she danced; not solved, she was swapped for Viper. The Make-It-Animatable route (the app's own rigging) re-bakes the mesh flat-shaded with one merged atlas and loses texture quality.
- **A-pose rigs** (arms about 66 degrees from the source's T-pose): `tools/retarget_bvh.py` applies the arm's correction to the hand as well (otherwise the wrist is bent by the whole swing) and turns the arm about its length so the rest palm faces down. Mixamo and Make-It-Animatable rigs (within about 15 degrees) are left exactly as they were. `--target valorant` retargets onto the unconverted game skeleton.
- The hand layer reads the game rig's names too (`canon()` in `homunculus/blender_handpose.py`).
- A run made this way records its `skeleton` in state.json; copying a dance onto it from the web app passes it to the retargeter.
