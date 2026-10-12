"""Trial: a four-view turnaround sheet generated locally from SEVERAL pictures of one character (Qwen-Image 2.1 edit with reference_images), then composed into one picture for `--sheet lfrb`.
    .venv/bin/python tools/sheet_from_refs.py <out_dir> <front_tpose.png> <ref1> [ref2 ...] [--seed N] [--only back,left]
The front view is a T-pose redraw you already have (tools/multiref_trial.py); the other three are drawn from it with the pictures as references. Views already in out_dir are kept (re-run with --only to redo one)."""
import io, os, sys, threading, time
from pathlib import Path
ROOT = Path(__file__).resolve().parent.parent
sys.path[:0] = [str(ROOT)]
import requests
from PIL import Image
import qwen_edit as q
from homunculus import gpu

SIZE = 768
KEEP = ("Keep the exact same character and costume as in the first image: the same hood, mask, jacket, suit pattern, shorts, gloves and shoes, the same T-pose, the same scale and the same framing, "
        "the whole body from head to feet in view. Orthographic camera at chest height, plain light grey background, soft even studio lighting, no motion blur, no scenery, no text. "
        "The other pictures show the same character from other angles: use them for the details that the first picture cannot show.")
VIEWS = {
    "back": "Draw this same character seen exactly from BEHIND, a 180 degree turn of the camera around the character. We see the back of the hood, the back of the jacket and the back of the legs; "
            "the chest emblem is on the FRONT only and must not appear here. ",
    "left": "Draw this same character in a strict 90 degree SIDE PROFILE, the camera at the character's LEFT side: the whole body, hood, mask and both feet in profile, the character faces toward the LEFT edge "
            "of the picture. The arms are stretched out sideways, so from this angle they point straight toward and away from the camera and are foreshortened. ",
    "right": "Draw this same character in a strict 90 degree SIDE PROFILE, the camera at the character's RIGHT side: the whole body, hood, mask and both feet in profile, the character faces toward the RIGHT "
             "edge of the picture. The arms are stretched out sideways, so from this angle they point straight toward and away from the camera and are foreshortened. ",
    "top": "Draw this same character seen from DIRECTLY ABOVE, a top-down view looking straight down at it: we see the top of the hood, both shoulders, the tops of the arms stretched out to the sides, the tops of both hands "
           "and the toes of the shoes just peeking out. The character's FRONT faces the BOTTOM of the picture and its LEFT side is on the right of the picture. Keep the T-pose, centred. ",
    "bottom": "Draw this same character seen from DIRECTLY BELOW, looking straight up at it: we see the soles of both shoes, the underside of the jacket and of the shorts and the undersides of the arms stretched out to the sides. "
              "The character's FRONT faces the TOP of the picture and its LEFT side is on the right of the picture. Keep the T-pose, centred. ",
}


def fit(path, long_side):
    im = Image.open(path).convert("RGB"); k = long_side / max(im.size); return im.resize((max(32, round(im.width * k / 32) * 32), max(32, round(im.height * k / 32) * 32)), Image.LANCZOS)


def main():
    a = sys.argv[1:]; seed = int(a[a.index("--seed") + 1]) if "--seed" in a else 5; only = a[a.index("--only") + 1].split(",") if "--only" in a else ["back", "left", "right"]      # top and bottom: --only top,bottom
    for flag in ("--seed", "--only"):
        if flag in a: i = a.index(flag); del a[i:i + 2]
    out, front, refs = a[0], a[1], a[2:]; os.makedirs(out, exist_ok=True); log = print
    Image.open(front).convert("RGB").save(f"{out}/front.png")
    q.SOFT_LIMIT_GB, q.HARD_LIMIT_GB = 21.8, 22.4             # several references need more room than one picture; the pipeline's own cap is 22.5
    gpu.free_all(log, keep="studio"); q.ensure_loaded()
    stop, st = threading.Event(), {"peak": 0.0}; th = threading.Thread(target=q.watchdog, args=(stop, st), daemon=True); th.start()
    try:
        init = q.to_b64(Image.open(front).convert("RGB").resize((SIZE, SIZE), Image.LANCZOS) if Image.open(front).size[0] == Image.open(front).size[1] else fit(front, SIZE))
        rb = [q.to_b64(fit(p, 640)) for p in refs]
        for name in only:
            t0 = time.time()
            r = q.post("/api/inference/images/generate", timeout=1800, json={"prompt": VIEWS[name] + KEEP, "init_image": init, "workflow": "edit", "reference_images": rb, "width": SIZE, "height": SIZE,
                                                                             "steps": 30, "seed": seed, "reference_resolution": 512})
            if r.status_code != 200: log(f"{name}: error {r.status_code} {r.text[:200]}"); continue
            iid = r.json()["images"][0]["id"]
            Image.open(io.BytesIO(requests.get(f"{q.API}/api/inference/images/gallery/{iid}/file", timeout=300).content)).convert("RGB").save(f"{out}/{name}.png")
            log(f"{name}: saved in {time.time() - t0:.0f}s, peak {st['peak']:.1f} GB")
    finally:
        stop.set(); th.join()
        try: q.post("/api/inference/images/unload")
        except Exception: pass


if __name__ == "__main__":
    main()
