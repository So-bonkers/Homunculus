"""Progress snapshots: a labelled composite image per important moment (shown on the run page and in desktop notifications).

runs/<name>/progress/NN_<stage>.png   one image per snapshot (also copied to progress/latest.png)
runs/<name>/progress.html             a shortcut that opens the run page in the web app
"""
import html, json, os, shutil, subprocess, textwrap, time
from PIL import Image, ImageDraw, ImageFont

def _font(size):
    for p in ("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf", "/usr/share/fonts/TTF/DejaVuSans.ttf"):
        if os.path.exists(p): return ImageFont.truetype(p, size)
    return ImageFont.load_default()

def _tile(path, cell, caption=None, border=None):
    t = Image.new("RGB", (cell, cell + (46 if caption else 0)), (250, 250, 250))
    if path and os.path.exists(path):
        im = Image.open(path).convert("RGB"); im.thumbnail((cell - 8, cell - 8))
        t.paste(im, ((cell - im.width) // 2, (cell - im.height) // 2))
    if border:
        d = ImageDraw.Draw(t); d.rectangle([1, 1, cell - 2, cell - 2], outline=border, width=6)
    if caption:
        d = ImageDraw.Draw(t); f = _font(14)
        for i, line in enumerate(textwrap.wrap(caption, 48)[:2]): d.text((6, cell + 4 + 18 * i), line, fill=(30, 30, 30), font=f)
    return t

def _text_tile(text, cell):
    t = Image.new("RGB", (cell * 2, cell), (252, 252, 246)); d = ImageDraw.Draw(t); f = _font(15); y = 8
    for para in text.split("\n"):
        for line in textwrap.wrap(para, 95) or [""]:
            if y > cell - 20: break
            d.text((10, y), line, fill=(25, 25, 25), font=f); y += 19
    return t

def snap(R, stage, title, images=(), captions=None, borders=None, text=None, cell=320):
    """Make a labelled grid of `images` (+ optional text panel), store it and refresh the live page."""
    tiles = [_tile(p, cell, (captions or [None] * len(images))[i], (borders or [None] * len(images))[i]) for i, p in enumerate(images)]
    if text: tiles.append(_text_tile(text, cell))
    W = max(1, sum(t.width for t in tiles)) if tiles else cell; H = max([t.height for t in tiles] or [cell])
    head = 44; sheet = Image.new("RGB", (max(W, 900), H + head), (255, 255, 255)); d = ImageDraw.Draw(sheet)
    d.rectangle([0, 0, sheet.width, head], fill=(35, 45, 60))
    d.text((12, 10), f"{R.state['name']} · {stage} · {title}", fill=(255, 255, 255), font=_font(20))
    x = 0
    for t in tiles: sheet.paste(t, (x, head)); x += t.width
    pdir = R.dir / "progress"; os.makedirs(pdir, exist_ok=True)
    n = len(R.state.setdefault("snapshots", [])) + 1
    out = pdir / f"{n:02d}_{stage}.png"; sheet.save(out); shutil.copy(out, pdir / "latest.png")
    R.state["snapshots"].append({"n": n, "stage": stage, "title": title, "file": f"progress/{out.name}", "time": time.strftime("%H:%M:%S"),
                                 # the web app shows the source images as a gallery (the sheet stays for notifications and old pages)
                                 "images": [os.path.relpath(str(i), R.dir) for i in images], "captions": list(captions or []), "text": text or ""})
    R.save(); write_html(R)
    try: subprocess.run(["notify-send", "-a", "homunculus", "-i", str(out), f"homunculus · {R.state['name']}", f"{stage}: {title}"], timeout=5, capture_output=True)
    except Exception: pass
    R.log(f"[snapshot] {out.name}: {title}")
    return str(out)


def write_html(R, final=False):
    """runs/<name>/progress.html is kept as a shortcut into the web app (http://127.0.0.1:8765/#/run/<name>)."""
    from . import server
    u = server.url(R.state["name"])
    page = (f"<!doctype html><meta charset='utf-8'><title>homunculus · {html.escape(R.state['name'])}</title>"
            f"<meta http-equiv='refresh' content='0; url={u}'><script>location.replace({json.dumps(u)})</script>"
            f"<p style='font:15px system-ui;padding:30px'>Opening <a href='{u}'>{u}</a> …</p>")
    open(R.dir / "progress.html", "w").write(page)
