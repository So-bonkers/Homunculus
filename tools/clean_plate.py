"""The room without the people: every frame of a shot with the people painted out, to put rendered characters on top of the real place.

    gvhmr/.venv/bin/python tools/clean_plate.py --video shot.mp4 --out plate.mp4 [--size 1280x720] [--grow 17]

People are found with a segmentation model (YOLOv8-seg, class person), their masks grown by --grow pixels (shadows and blur at the edges) and painted over from the surrounding picture (OpenCV inpainting).  What a person hid
for a long time is only guessed (smeared from the surroundings), so the plate is for a dark, busy room and characters about the people's size; it is not a clean photograph.  Writes the video (no sound)."""
import os, sys, argparse, subprocess
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__))); GV = os.path.join(ROOT, "gvhmr"); sys.path[:0] = [os.path.join(GV, "shim"), os.path.join(GV, "repo")]
ap = argparse.ArgumentParser(); ap.add_argument("--video", required=True); ap.add_argument("--out", required=True); ap.add_argument("--size", default="1280x720"); ap.add_argument("--grow", type=int, default=21); ap.add_argument("--conf", type=float, default=0.15); ap.add_argument("--feet", type=float, default=0.13, help="the lowest this fraction of every person's box is painted out whole (shoes and their motion blur are missed by the person masks)")
ap.add_argument("--box", action="append", default=[], help="x0,y0,x1,y1 (pixels of --size): a fixed overlay (a channel logo) painted out in every frame; may be repeated")
ap.add_argument("--gold-text-frames", type=int, default=0, help="in the first N frames the gold title text (hue 12-38, saturated and bright) is painted out as well"); a = ap.parse_args()
BOXES = [tuple(int(v) for v in b.split(",")) for b in a.box]
import cv2, numpy as np
from ultralytics import YOLO
W, H = (int(x) for x in a.size.split("x")); model = YOLO(os.path.join(GV, "yolov8m-seg.pt"))               # downloaded on first use into gvhmr/ (not in git); cap = cv2.VideoCapture(a.video); fps = cap.get(cv2.CAP_PROP_FPS) or 30
enc = subprocess.Popen(["ffmpeg", "-v", "error", "-y", "-f", "rawvideo", "-pix_fmt", "bgr24", "-s", f"{W}x{H}", "-r", f"{fps:.3f}", "-i", "-", "-c:v", "libx264", "-crf", "16", "-pix_fmt", "yuv420p", a.out], stdin=subprocess.PIPE)
k = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (a.grow, a.grow)); n = 0
while True:
    ok, im = cap.read()
    if not ok: break
    im = cv2.resize(im, (W, H), interpolation=cv2.INTER_AREA); r = model.predict(im, classes=[0], conf=a.conf, verbose=False, imgsz=960)[0]; m = np.zeros((H, W), np.uint8)
    if r.boxes is not None:
        for bx in r.boxes.xyxy.cpu().numpy():
            x0, y0, x1, y1 = bx; bw = x1 - x0; fy = y1 - a.feet * (y1 - y0)
            m[int(max(0, fy)):int(min(H, y1 + 0.05 * (y1 - y0))), int(max(0, x0 - 0.04 * bw)):int(min(W, x1 + 0.04 * bw))] = 1
    if r.masks is not None:
        for mk in r.masks.data.cpu().numpy(): m |= (cv2.resize(mk, (W, H), interpolation=cv2.INTER_LINEAR) > 0.4).astype(np.uint8)
    m = cv2.dilate(m, k)
    for x0, y0, x1, y1 in BOXES: m[y0:y1, x0:x1] = 1
    if n < a.gold_text_frames:
        hsv = cv2.cvtColor(im, cv2.COLOR_BGR2HSV); g = ((hsv[..., 0] >= 12) & (hsv[..., 0] <= 38) & (hsv[..., 1] > 90) & (hsv[..., 2] > 150)).astype(np.uint8); m |= cv2.dilate(g, cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (9, 9)))
    out = cv2.inpaint(im, m * 255, 6, cv2.INPAINT_TELEA) if m.any() else im
    enc.stdin.write(out.tobytes()); n += 1
    if n % 200 == 0: print(f"  {n} frames", flush=True)
enc.stdin.close(); enc.wait(); print(f"{n} frames -> {a.out}")
