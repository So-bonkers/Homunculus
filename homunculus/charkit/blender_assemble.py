"""Run tools/ren_graft/assemble_kit.py for any character: that script names Ren's garments in a constant (GARMENTS = {"hoodie": ..., "joggers": ...}); this wrapper reads its source,
swaps that one line for the character's garments (from the CHARKIT_GARMENTS environment variable, JSON {"item": ["bottom", "top"], ...}) and runs it unchanged otherwise.
    CHARKIT_GARMENTS='{"hoodie": ["bottom"]}' blender -b --factory-startup --python homunculus/charkit/blender_assemble.py -- KIT_DIR OUT.blend [--gap 0.004]
KIT_DIR as assemble_kit.py expects it (charkit stages.assemble builds it): <item>/s42/textured.glb (a link to the picked seed's mesh) and place_<item>.json; the base body is item "body".
If assemble_kit.py no longer has a single 'GARMENTS = {...}' line, this stops with an error rather than guess."""
import json, os, re, sys
SRC = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))), "tools", "ren_graft", "assemble_kit.py")
garments = json.loads(os.environ.get("CHARKIT_GARMENTS", "{}"))
src = open(SRC).read(); pat = re.compile(r"^GARMENTS = \{.*\}\s*$", re.M)
if len(pat.findall(src)) != 1: raise SystemExit(f"charkit: {SRC} has no single 'GARMENTS = {{...}}' line any more; update blender_assemble.py")
src = pat.sub("GARMENTS = " + repr({k: tuple(v) for k, v in garments.items()}), src)
print("charkit: assembling with garments", garments, flush=True)
exec(compile(src, SRC, "exec"), {"__name__": "__main__", "__file__": SRC})
