"""Progress of one dance-from-video job, as stages with estimates and reports, for the web app (09_animate/video_jobs/<job>.json).

Estimates come from measurements on the Radeon (seconds, for a clip of s seconds): a 10 s clip took 63 s of GVHMR, 8 s of camera tracking, 11 s to build the
animation, then about 50 s for the texture and the preview render. The web app scales the remaining estimates by how fast the finished stages actually went."""
import json, os, time

STAGES = [
    ("queued", "Waiting for the GPU", lambda s: 0),
    ("cut", "Cut the clip", lambda s: 2 + 0.1 * s),
    ("motion", "Body motion (GVHMR)", lambda s: 30 + 4.5 * s),
    ("camera", "Camera", lambda s: 2 + 0.7 * s),
    ("build", "Retarget onto the rig", lambda s: 6 + 0.6 * s),
    ("texture", "Final texture on the clip", lambda s: 10),
    ("preview", "Preview render", lambda s: 10 + 3.5 * s),
    ("compare", "Side by side with the video", lambda s: 3 + 0.5 * s),
]


class Progress:
    def __init__(self, path, job, run, title, video, start, end):
        self.path = str(path); os.makedirs(os.path.dirname(self.path), exist_ok=True); s = float(end) - float(start)
        self.d = {"job": job, "run": run, "title": title, "video": os.path.basename(str(video)), "start": float(start), "end": float(end), "seconds": s,
                  "status": "queued", "error": None, "created": time.time(), "finished": None, "clip": None,
                  "stages": [{"key": k, "label": l, "status": "pending", "estimate": round(f(s), 1), "started": None, "ended": None, "report": None} for k, l, f in STAGES]}
        self._save()

    @classmethod
    def load(cls, path):
        p = cls.__new__(cls); p.path = str(path); p.d = json.load(open(path)); return p

    def _save(self):
        tmp = self.path + ".tmp"; json.dump(self.d, open(tmp, "w"), indent=1); os.replace(tmp, self.path)

    def _st(self, key): return next(x for x in self.d["stages"] if x["key"] == key)

    def begin(self, key):
        now = time.time()
        for x in self.d["stages"]:          # everything before this stage is over (a skipped stage counts as done)
            if x["key"] == key: break
            if x["status"] in ("pending", "running"): x["status"] = "done"; x["ended"] = x["ended"] or now; x["started"] = x["started"] or now
        st = self._st(key); st["status"] = "running"; st["started"] = now; self.d["status"] = "running"; self._save()

    def end(self, key, text=None, images=None, video=None):
        st = self._st(key); st["status"] = "done"; st["ended"] = time.time(); st["started"] = st["started"] or st["ended"]
        if text or images or video: st["report"] = {"text": text, "images": images or [], "video": video}
        self._save()

    def report(self, key, text=None, images=None, video=None):
        st = self._st(key); st["report"] = {"text": text, "images": images or [], "video": video}; self._save()

    def fail(self, err):
        for x in self.d["stages"]:
            if x["status"] == "running": x["status"] = "failed"; x["ended"] = time.time()
        self.d["status"] = "failed"; self.d["error"] = str(err)[:400]; self.d["finished"] = time.time(); self._save()

    def finish(self, clip_id):
        for x in self.d["stages"]:
            if x["status"] in ("pending", "running"): x["status"] = "done"; x["ended"] = x["ended"] or time.time(); x["started"] = x["started"] or x["ended"]
        self.d["status"] = "done"; self.d["clip"] = clip_id; self.d["finished"] = time.time(); self._save()
