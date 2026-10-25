"""4x upscale of one picture with a spandrel model (4x-UltraSharp by default), tiled so the VRAM stays small. Standalone: runs in the ComfyUI venv (it has spandrel and ROCm torch).
    comfy/.venv/bin/python homunculus/charkit/upscale_x4.py IN.png OUT.png [--model comfy/ComfyUI/models/upscale_models/4x-UltraSharp.pth] [--tile 512] [--cpu]"""
import argparse, numpy as np, torch
from PIL import Image
from spandrel import ModelLoader
ap = argparse.ArgumentParser(); ap.add_argument("inp"); ap.add_argument("out"); ap.add_argument("--model", default="comfy/ComfyUI/models/upscale_models/4x-UltraSharp.pth"); ap.add_argument("--tile", type=int, default=512); ap.add_argument("--pad", type=int, default=32); ap.add_argument("--cpu", action="store_true"); a = ap.parse_args()
dev = "cuda" if torch.cuda.is_available() and not a.cpu else "cpu"; half = dev == "cuda"
m = ModelLoader().load_from_file(a.model).eval().to(dev); net = m.model.half() if half else m.model; S = m.scale
im = torch.from_numpy(np.asarray(Image.open(a.inp).convert("RGB")).astype(np.float32) / 255).permute(2, 0, 1)[None]; _, _, H, W = im.shape
out = torch.zeros(1, 3, H * S, W * S); T, P = a.tile, a.pad
with torch.no_grad():
    for y in range(0, H, T):
        for x in range(0, W, T):
            y0, x0, y1, x1 = max(0, y - P), max(0, x - P), min(H, y + T + P), min(W, x + T + P)          # the tile with a margin, cut back after (no seams)
            t = im[:, :, y0:y1, x0:x1].to(dev); t = t.half() if half else t; r = net(t).float().cpu()
            out[:, :, y * S:min(H, y + T) * S, x * S:min(W, x + T) * S] = r[:, :, (y - y0) * S:(y - y0 + min(T, H - y)) * S, (x - x0) * S:(x - x0 + min(T, W - x)) * S]
Image.fromarray((out[0].clamp(0, 1).permute(1, 2, 0).numpy() * 255).round().astype(np.uint8)).save(a.out); print(f"upscaled {W}x{H} -> {W * S}x{H * S} on {dev}: {a.out}")
