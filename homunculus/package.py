"""One download per character: the rigged model, the textures, every animation clip and the notes, in one zip.
exports/<run>_package.zip:
  character/  <run>_final.fbx / .glb (rigged, textured), the textured mesh before rigging, the base-colour texture
  animations/ every clip as GLB and FBX (the textured copy when there is one), named after its prompt
  docs/       contact sheet, report, README.txt (what is where, how it was made, licence notes)"""
import json, os, re, time, zipfile
from pathlib import Path
from . import config as C

LICENCE_NOTES = """Licence notes for what is in this package
- The character was generated from your input. You decide what to do with it, subject to the terms of the tools below.
- Animation clips come from UniMate (code MIT, weights CC BY-NC 4.0: NON-COMMERCIAL). Do not use the clips commercially without checking that licence.
- The shape comes from Pixal3D (MIT); rigging from Make-It-Animatable (weights Apache-2.0); the 4x-UltraSharp upscaler, if it was used, is CC BY-NC-SA 4.0.
- Full list with links: THIRD_PARTY.md in the project repository."""


def _slug(t): return re.sub(r"[^a-z0-9]+", "_", str(t).lower()).strip("_")[:48] or "clip"


def plan(run):
    """(archive name, source path) pairs for a run."""
    rd = C.RUNS / run; S = json.load(open(rd / "state.json")); A = S.get("artifacts") or {}; out = []
    add = lambda arc, p: out.append((arc, Path(p))) if p and Path(p).exists() else None
    add(f"character/{run}_final.fbx", A.get("final_fbx")); add(f"character/{run}_final.glb", A.get("final_glb"))
    if not A.get("final_fbx"): add(f"character/{run}_rigged.fbx", A.get("rig_fbx")); add(f"character/{run}_rigged.glb", A.get("rig_glb"))
    tg = A.get("textured_glb") or A.get("colored_glb") or A.get("mesh_glb")
    if tg: add(f"character/{run}_mesh_before_rigging.glb", tg); add(f"character/{run}_basecolor.png", tg[:-4] + "_basecolor.png")
    try: M = json.load(open(rd / "09_animate" / "animations.json"))
    except Exception: M = {"clips": []}
    seen = {}
    for c in M.get("clips", []):
        base = f"animations/{_slug(c.get('prompt', ''))}_take{int(c.get('rep', 0)) + 1}"; seen[base] = seen.get(base, 0) + 1; base += (f"_{seen[base]}" if seen[base] > 1 else "")
        add(base + ".glb", rd / (c.get("textured") or c.get("glb") or "")); add(base + ".fbx", rd / (c.get("textured_fbx") or c.get("fbx") or ""))
    add("docs/contact_sheet.png", rd / "contact_sheet.png"); add("docs/report.md", rd / "report.md")
    return out, S, M


def readme(run, files, S, M):
    prompts = sorted({c.get("prompt", "") for c in M.get("clips", [])})
    lines = [f"{run}: character package", f"made {time.strftime('%Y-%m-%d %H:%M')} with Homunculus (https://github.com/So-bonkers/Homunculus)", "",
             "character/   the rigged, textured model (52-bone Mixamo skeleton with fingers) as FBX and GLB, the mesh before rigging, the base-colour texture",
             "animations/  one GLB and one FBX per clip, 30 fps, named after the prompt; clips use the same skeleton, so any clip plays on the character",
             "docs/       contact sheet and the pipeline report", ""]
    if prompts: lines += ["Animation prompts:"] + [f"  - {p}" for p in prompts] + [""]
    lines += [LICENCE_NOTES, "", f"{len(files)} files"]
    return "\n".join(lines)


def build(run):
    files, S, M = plan(run)
    if not files: raise RuntimeError("nothing to package yet")
    z = C.ROOT / "exports" / f"{run}_package.zip"; z.parent.mkdir(exist_ok=True)
    with zipfile.ZipFile(z, "w", zipfile.ZIP_DEFLATED, compresslevel=3) as zf:
        for arc, p in files: zf.write(p, f"{run}/{arc}")
        zf.writestr(f"{run}/README.txt", readme(run, files, S, M)); zf.writestr(f"{run}/docs/LICENCES.txt", LICENCE_NOTES)
    return z
