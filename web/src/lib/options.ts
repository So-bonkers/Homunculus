// Every run option the launcher and the Fork dialog offer, with the server's values and the hint shown for each.
export interface Opt { value: string; label: string; hint: string }

export const LOOKS: Opt[] = [
  { value: "choose", label: "All · I pick", hint: "First redraw: one image per look (As is + 5 styles). You pick the look and the image; the rest of the run uses it." },
  { value: "asis", label: "As is", hint: "Keeps the picture's own style." },
  { value: "stylized", label: "3D film", hint: "Pixar/Disney-like 3D animated film character." },
  { value: "game", label: "Game", hint: "Realistic game character, clean Unreal-style render." },
  { value: "anime3d", label: "Anime 3D", hint: "Cel-shaded anime 3D (Genshin-like)." },
  { value: "clay", label: "Clay", hint: "Matte claymation / vinyl toy figure." },
  { value: "chibi", label: "Chibi", hint: "Big head, short limbs. Risky for the auto-rigger." },
];
export const OUTFITS: Opt[] = [
  { value: "keep", label: "Keep", hint: "Redraws the outfit from the picture." },
  { value: "shirtless", label: "Shirtless", hint: "Bare torso and arms; avoids sleeve cuffs tearing at the wrists." },
  { value: "nude", label: "Nude", hint: "Unclothed, anatomy kept. Only for generated or fictional adult characters." },
];
export const TEXTURES: Opt[] = [
  { value: "simple", label: "Simple", hint: "The texture comes from your upscaled picture (or the chosen redraw) alone: projected onto the model, face fitted. No extra generated images." },
  { value: "full", label: "Full", hint: "Also redraws the face as a reference and has the image model clean the side and back views. More detail guessed, but it can make the model look worse than the picture." },
];
export const FACES: Opt[] = [
  { value: "auto", label: "Auto", hint: "The planner checks whether a full-face helmet or mask hides the face." },
  { value: "off", label: "No face", hint: "Helmets, masks, visors: skip every face step (close-up redraw, reshape, face fit), so no face gets carved into them." },
  { value: "on", label: "Always", hint: "Always fit a face, even if the planner thinks it is hidden." },
];
export const AUTO_REPAIR: Opt[] = [
  { value: "auto", label: "Repair automatically", hint: "When the hands come out torn or cut off, the repair runs before rigging (Turbo redraws, a Pixal3D donor, a clean graft; about 12 extra minutes) and the run continues with the repaired mesh. In manual review you choose the redraw." },
  { value: "alert", label: "Warn me", hint: "The hands are checked after the 3D shape; if they look broken you get a warning pointing to the Repair tab." },
  { value: "off", label: "Off", hint: "No check." },
];
export const FACE_SOURCES: Opt[] = [
  { value: "original", label: "Your picture", hint: "The face is taken from your own picture (upscaled): the face as it really is. Falls back to the redraw if its landmarks cannot be matched." },
  { value: "redraw", label: "The redraw", hint: "The face is taken from the redrawn T-pose picture (the image model may have changed it)." },
];
export const REVIEWS: Opt[] = [
  { value: "override", label: "Override", hint: "The judges decide; you can overrule them within the review window." },
  { value: "manual", label: "Manual", hint: "You are the judge: one redraw, one 3D shape at a time; use it or try another. No AI judges, no time limit." },
  { value: "off", label: "Automatic", hint: "Fully automatic, no questions asked." },
];
export const RIGGERS: Opt[] = [
  { value: "mia", label: "Make-It-Animatable", hint: "Default skin weights: a good all-round rig (52 Mixamo bones with fingers)." },
  { value: "mia_normal", label: "MIA · normal weights", hint: "Binds the skin using the surface normals; try it if the default tears at thick armour, cloth or the shoulders." },
];
export const SHEET_ORDERS: Opt[] = [
  { value: "lfrb", label: "Left · Front · Right · Back", hint: 'Left to right, as the figures are drawn. "Left" means the character\'s left side: that figure faces the left edge of the picture.' },
  { value: "flbr", label: "Front · Left · Back · Right", hint: 'Left to right, as the figures are drawn. "Left" means the character\'s left side: that figure faces the left edge of the picture.' },
];
export const STYLES: Opt[] = [
  { value: "", label: "Auto-detect", hint: "Chosen from the picture (flat colours = anime)." },
  { value: "photo", label: "Photo", hint: "RealESRGAN x4plus." },
  { value: "anime", label: "Anime", hint: "RealESRGAN anime 6B." },
  { value: "3d_render", label: "3D render", hint: "4x-UltraSharp." },
];

export const hintOf = (list: Opt[], v: string) => list.find((o) => o.value === v)?.hint ?? "";

export const NAME_RE = /^[A-Za-z0-9_-]{1,40}$/;
export const nameFromFile = (f: string) => f.replace(/\.[^.]+$/, "").replace(/[^A-Za-z0-9_-]+/g, "_").slice(0, 40);
export const MESH_RE = /\.(stl|obj|ply|glb|gltf|fbx)$/i;
export const ACCEPT_INPUT = "image/png,image/jpeg,image/webp,.stl,.obj,.ply,.glb,.gltf,.fbx";

export const TIPS: { icon: string; title: string; text: string }[] = [
  { icon: "🧍", title: "One character, full body, facing the camera", text: "The whole figure from head to feet, nothing cropped. A plain background helps, but busy ones are cleaned away." },
  { icon: "🙌", title: "Arms away from the body, hands open", text: "Everything is redrawn into a T-pose anyway, but a close start keeps the face and outfit more faithful, and open hands give cleaner fingers." },
  { icon: "🔎", title: "Small or blurry pictures are fine", text: "The input is upscaled 4× with the model that fits its style before anything else." },
  { icon: "⚡", title: "Already have a clean reference?", text: "Turn on Use my picture as is: the redraw is skipped and the texture comes from your picture itself. A turnaround sheet (four views) gives real backs and sides." },
  { icon: "💃", title: "Copy a dance from a video", text: "Once the rig is built, the Animate tab copies the dance of one person in a video onto your character: one continuous shot, whole body in view." },
  { icon: "🎭", title: "Describe the motion, not the character", text: "Text prompts like \"walks forward\" or \"waves with the right hand\". The preset library has 190 ready-made ones." },
  { icon: "⚖️", title: "Pick how much you want to decide", text: "Override gives you a window to overrule the judges, Manual makes you the judge, Automatic lets them decide. Runs can also go without any language model (--no-llm)." },
  { icon: "🗿", title: "Have a 3D model instead?", text: "Drop an STL, OBJ, PLY, GLB or FBX: it is oriented, painted from its own renders and rigged; a posed model is put into a T-pose first." },
  { icon: "🩹", title: "Something came out wrong?", text: "Paint over it in the Repair tab and it is rebuilt and grafted in. Torn hands are repaired automatically. Or Fork the run from any stage with new instructions." },
  { icon: "🖥️", title: "Give it the whole GPU", text: "It runs one heavy model at a time within 22.5 GB; close games and other GPU apps during a run." },
];
