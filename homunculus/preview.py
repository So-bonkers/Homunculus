"""Browser-sized previews of heavy models. ensure(glb) returns the path the viewer should load: the file itself when it is small, a decimated <name>_preview.glb when that exists,
else None while one is being made in the background (CPU, about a minute). One decimation runs at a time (a lock): a raw shape of 30 million vertices needs about 22 GB of RAM to load, and
the orchestrator and the web app ask for all the candidates at once; three together filled 60 GB, used all the swap and got a Blender killed by the kernel."""
import os, subprocess, time
from . import config as C

LIMIT = 60e6        # a GLB above this is too heavy to open in the browser
LOCK = C.RUNS / ".preview.lock"   # held by the one Blender decimation that is running


def ensure(glb):
    if not glb or not os.path.exists(glb): return None
    if os.path.getsize(glb) <= LIMIT: return glb
    prev = glb[:-4] + "_preview.glb"; marker = prev + ".working"
    if os.path.exists(prev) and os.path.getsize(prev) > 1000: return prev
    if os.path.exists(marker) and time.time() - os.path.getmtime(marker) < 2400: return None      # already being made, or waiting its turn (up to a few in a queue)
    try:
        open(marker, "w").write(str(time.time()))
        subprocess.Popen(f'flock "{LOCK}" "{C.BLENDER}" -b --python "{C.ROOT / "homunculus" / "blender_preview.py"}" -- "{glb}" "{prev}" 150000 >/dev/null 2>&1; rm -f "{marker}"', shell=True, start_new_session=True,
                         stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    except Exception: pass
    return None
