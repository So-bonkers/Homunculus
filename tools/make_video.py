"""The 30-second demo video (1080x1350, silent, captioned) on the female preview character:
python tools/make_video.py <preset-clips-dir> [out.mp4]      e.g. homunculus/static/presets/clips/female
Renders transparent frames with Blender (tools/render_frames.py), composes them with PIL and encodes with ffmpeg."""
import subprocess, sys, os, shutil, glob, hashlib
from pathlib import Path
from PIL import Image, ImageDraw, ImageFont
ROOT = Path(__file__).resolve().parent.parent; CLIPDIR = Path(sys.argv[1]); OUT = Path(sys.argv[2] if len(sys.argv) > 2 and not sys.argv[2].startswith("--") else "homunculus_demo.mp4")
MODEL = ROOT / "presets" / "female" / "gwen.glb"
TMP = Path(os.environ.get("TMPDIR", "/tmp")) / "homunculus_video"; W, H, FPS = 1080, 1350, 30
FB = "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"; FR = "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"
font = lambda p, s: ImageFont.truetype(p, s)
pid = lambda p: hashlib.sha1(p.encode()).hexdigest()[:10]
CLIPS = ["walks forward", "does a spinning kick", "dances hip hop, bouncing and swinging the arms", "dances salsa, stepping side to side and swaying the hips", "slashes forward with a sword"]

def render():
    shutil.rmtree(TMP, ignore_errors=True); TMP.mkdir(parents=True)
    bl = os.environ.get("BLENDER") or shutil.which("blender") or "/snap/bin/blender"
    def r(glb, name, mode, n=90): subprocess.run([bl, "-b", "--python", str(ROOT / "tools" / "render_frames.py"), "--", str(glb), str(TMP / name), "720", "900", mode, str(n)], capture_output=True, check=True)
    r(MODEL, "turn", "turn", 120)
    for i, p in enumerate(CLIPS): r(CLIPDIR / f"{pid(p)}_1.glb", f"clip{i}", "clip")

def bg():
    im = Image.new("RGB", (W, H)); px = ImageDraw.Draw(im)
    for y in range(H):
        t = y / H; px.line([(0, y), (W, y)], fill=(int(236 - 34 * t), int(239 - 36 * t), int(248 - 30 * t)))
    return im
BG = bg()

def text(d, xy, s, f, fill, anchor="mm"): d.text(xy, s, font=f, fill=fill, anchor=anchor)
def wrap(d, s, f, width):
    out, cur = [], ""
    for w in s.split():
        t = (cur + " " + w).strip()
        if d.textlength(t, font=f) > width and cur: out.append(cur); cur = w
        else: cur = t
    return out + [cur]

def frame(step, title, sub=None, art=None, art_box=(80, 250, 920, 900), alpha=1.0):
    im = BG.copy(); d = ImageDraw.Draw(im)
    text(d, (W // 2, 92), step, font(FB, 28), (60, 90, 200)); lines = wrap(d, title, font(FB, 54), 900)
    for i, l in enumerate(lines): text(d, (W // 2, 160 + i * 66), l, font(FB, 54), (18, 22, 44))
    if sub: text(d, (W // 2, 160 + len(lines) * 66 + 14), sub, font(FR, 30), (84, 92, 120))
    if art is not None:
        a = art.copy(); a.thumbnail((art_box[2], art_box[3]), Image.LANCZOS) if max(a.size) > max(art_box[2:]) else None; x = (W - a.width) // 2; y = art_box[1] + (art_box[3] - a.height) // 2
        if a.mode == "RGBA": im.paste(a, (x, y), a)
        else: im.paste(a, (x, y))
    text(d, (W // 2, H - 52), "github.com/So-bonkers/Homunculus   ·   fully local   ·   one 24 GB GPU", font(FR, 25), (96, 104, 134))
    return im

def crop_char(frames):
    """Common crop box over all frames so the character stays steady, scaled up to fill the slot."""
    box = None
    for f in frames[::4]:
        b = f.getchannel("A").getbbox()
        if b: box = b if box is None else (min(box[0], b[0]), min(box[1], b[1]), max(box[2], b[2]), max(box[3], b[3]))
    m = 20; box = (max(0, box[0] - m), max(0, box[1] - m), min(frames[0].width, box[2] + m), min(frames[0].height, box[3] + m))
    return [f.crop(box) for f in frames]
def lift(f):    # the knight's texture is very dark: lift it so it reads on the light background
    rgb = f.convert("RGB").point(lambda v: int(255 * (v / 255) ** 0.9)); rgb.putalpha(f.getchannel("A")); return rgb
def load(name): return crop_char([lift(Image.open(p).convert("RGBA")) for p in sorted(glob.glob(str(TMP / name / "f*.png")))])

def frames():
    shot = Image.open(ROOT / "docs" / "media" / "screens" / "04b-preset-preview-female.jpg").convert("RGB").crop((680, 235, 1335, 790))
    turn = load("turn"); clips = [load(f"clip{i}") for i in range(len(CLIPS))]
    n = lambda s: int(s * FPS)
    for k in range(n(2.6)): yield frame("1 · START WITH A 3D MODEL", "A character with no skeleton", "Just a mesh and a texture", art=turn[(k * 2) % len(turn)], art_box=(80, 300, 1000, 960))
    for k in range(n(3.0)): yield frame("2 · AUTO-RIG", "Rigged automatically", "A 52-bone skeleton with fingers", art=turn[(k * 2 + 60) % len(turn)], art_box=(80, 300, 1000, 960))
    for k in range(n(3.4)): yield frame("3 · PICK A MOTION", "190 ready-made prompts", "Preview each one, or type your own", art=shot, art_box=(80, 380, 920, 780))
    for i, prompt in enumerate(CLIPS):
        for k in range(n(3.2)): yield frame("4 · ANIMATE FROM TEXT", f"“{prompt}”", art=clips[i][k % len(clips[i])], art_box=(80, 340, 1000, 940))
    for k in range(n(3.6)):
        im = BG.copy(); d = ImageDraw.Draw(im)
        text(d, (W // 2, 480), "Homunculus", font(FB, 110), (18, 22, 44)); text(d, (W // 2, 600), "picture or 3D model  →  rigged, animated character", font(FR, 34), (60, 90, 200))
        text(d, (W // 2, 700), "Open source (GPL-3.0)  ·  runs fully local", font(FR, 32), (84, 92, 120)); text(d, (W // 2, 810), "github.com/So-bonkers/Homunculus", font(FB, 40), (18, 22, 44))
        text(d, (W // 2, 1000), "Model: “Spider Gwen Low Poly” by So7ion", font(FR, 24), (96, 104, 134)); text(d, (W // 2, 1036), "CC BY 4.0 · skfb.ly/oxwZX · animated with UniMate", font(FR, 24), (96, 104, 134)); yield im

if __name__ == "__main__":
    if "--no-render" not in sys.argv: render()
    p = subprocess.Popen(["ffmpeg", "-loglevel", "error", "-y", "-f", "rawvideo", "-pix_fmt", "rgb24", "-s", f"{W}x{H}", "-r", str(FPS), "-i", "-", "-c:v", "libx264", "-pix_fmt", "yuv420p",
                          "-crf", "20", "-preset", "medium", "-movflags", "+faststart", str(OUT)], stdin=subprocess.PIPE)
    c = 0
    for im in frames(): p.stdin.write(im.tobytes()); c += 1
    p.stdin.close(); p.wait(); print(f"{c} frames, {c / FPS:.1f}s -> {OUT}")
