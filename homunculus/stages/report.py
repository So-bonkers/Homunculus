"""Contact sheet + report.md for the final (Claude) check."""
import json, os
from PIL import Image, ImageDraw

def sheet(rows, out, cell=360):
    """rows: list of (title, [image paths])"""
    W = cell * max(len(r[1]) for r in rows); H = (cell + 24) * len(rows)
    s = Image.new("RGB", (W, H), (245, 245, 245)); d = ImageDraw.Draw(s)
    for ri, (title, paths) in enumerate(rows):
        y = ri * (cell + 24); d.text((6, y + 4), title, fill=(20, 20, 20))
        for ci, p in enumerate(paths):
            if not p or not os.path.exists(p): continue
            im = Image.open(p).convert("RGB"); im.thumbnail((cell, cell))
            s.paste(im, (ci * cell + (cell - im.width) // 2, y + 24 + (cell - im.height) // 2))
    s.save(out); return out

def write(run_dir, state):
    S = state["stages"]; A = state["artifacts"]
    rows = [("input / upscaled / chosen redraw / upscaled redraw", [A.get("input"), A.get("upscaled"), A.get("chosen_edit"), A.get("edit_upscaled")]),
            ("redraw candidates (last round)", A.get("edit_candidates", [])[-4:]),
            ("3D shape (grey): front / side / face / hands", [A.get("mesh_views", {}).get(k) for k in ("front", "side", "face", "handR", "handL")]),
            ("final textured: front / side / face", [A.get("final_views", {}).get(k) for k in ("front", "side", "face")]),
            ("rig test poses: rest / walk / wave / open hand / fists", [A.get("pose_views", {}).get(k) for k in ("rest_front", "walk_34", "wave_front", "wave_hand", "fist_Left_a", "fist_Right_a")])]
    sh = sheet(rows, os.path.join(run_dir, "contact_sheet.png"))
    L = [f"# homunculus report: {state['name']}", "", f"Input: `{state['input']}`", f"Contact sheet: `{sh}`", "",
         "| stage | status | time (s) | peak VRAM (GB) | notes |", "|---|---|---|---|---|"]
    for k, v in S.items():
        L.append(f"| {k} | {v.get('status')} | {v.get('seconds', '')} | {v.get('peak_vram', '')} | {str(v.get('note', ''))[:120]} |")
    L += ["", "## VLM decisions", "```json", json.dumps(state.get("vlm", {}), indent=1)[:6000], "```", "", "## Final files"]
    for k in ("final_fbx", "final_glb", "chosen_edit", "mesh_glb", "mesh_hi_glb", "rig_fbx", "rig_glb"):
        if A.get(k): L.append(f"- {k}: `{A[k]}`")
    L += ["", "## For the final reviewer (Claude)", "Check the contact sheet and the pose renders: identity and outfit kept, five separated fingers per hand,",
          "no fused limbs, no tearing in the posed renders. Record the verdict below.", "", "Verdict: _pending_"]
    p = os.path.join(run_dir, "report.md"); open(p, "w").write("\n".join(L)); return p
