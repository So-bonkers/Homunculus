"""Every person in a clip, tracked once and kept as raw boxes: the first step of following a group of dancers through a long shot.  Run with the GVHMR environment:

    gvhmr/.venv/bin/python tools/track_raw.py --video shot.mp4 --out tracks_raw.json

Writes {"video", "frames", "width", "height", "tracks": {id: {frame: [x0, y0, x1, y1], ...}}} using GVHMR's own tracker (YOLO + a tracker that gives each person an id; the id can change when a person is lost and found again,
which tools/group_tracks.py repairs). Adapted from GVHMR's tracker (ZJU licence: research use)."""
import os, sys, json, argparse
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__))); GV = os.path.join(ROOT, "gvhmr")
sys.path[:0] = [os.path.join(GV, "shim"), os.path.join(GV, "repo")]
ap = argparse.ArgumentParser(); ap.add_argument("--video", required=True); ap.add_argument("--out", required=True); a = ap.parse_args()
a.video, a.out = os.path.abspath(a.video), os.path.abspath(a.out); os.chdir(os.path.join(GV, "repo"))
import cv2
from hmr4d.utils.preproc import Tracker
cap = cv2.VideoCapture(a.video); W, H, N = int(cap.get(3)), int(cap.get(4)), int(cap.get(7)); cap.release()
hist = Tracker().track(a.video); tracks = {}
for f, dets in enumerate(hist):
    for d in dets: tracks.setdefault(int(d["id"]), {})[f] = [round(float(v), 1) for v in d["bbx_xyxy"]]
json.dump({"video": a.video, "frames": N, "width": W, "height": H, "tracks": tracks}, open(a.out, "w"))
print(f"{len(tracks)} ids over {N} frames -> {a.out}")
