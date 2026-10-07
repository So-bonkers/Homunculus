"""Local web server for the homunculus app: http://127.0.0.1:8765/ (runs, launcher, live run pages at /#/run/<name>)
POST /api/review {"run", "gate", "action": accept|reject|choose|redo, "choice": k, "notes": "..."} -> runs/<run>/review.json"""
import json, os, threading, time
from http.server import ThreadingHTTPServer, SimpleHTTPRequestHandler
from functools import partial
from . import config as C
PORT = int(os.environ.get("HOMUNCULUS_PORT", "8765"))

def _live_pids():
    out = {}
    for pid in os.listdir("/proc"):
        if not pid.isdigit(): continue
        try: cmd = open(f"/proc/{pid}/cmdline", "rb").read().decode(errors="ignore").split("\0")
        except Exception: continue
        if any(c.endswith("homunculus.orchestrate") for c in cmd) and "--name" in cmd:
            i = cmd.index("--name")
            if i + 1 < len(cmd): out[cmd[i + 1]] = int(pid)
    return out

def live_runs():
    """Names of runs whose orchestrator process is alive right now (a run that was stopped or crashed is not 'in progress')."""
    return set(_live_pids())

class H(SimpleHTTPRequestHandler):
    def do_GET(self):
        path = self.path.split("?")[0]
        if path == "/api/live":
            self.send_response(200); self.send_header("Content-Type", "application/json"); self.send_header("Cache-Control", "no-store"); self.end_headers()
            self.wfile.write(json.dumps(sorted(live_runs())).encode()); return
        if path == "/api/version":      # the open app reloads itself when its files change
            base = os.path.join(os.path.dirname(__file__), "static")
            v = max(os.path.getmtime(os.path.join(base, f)) for f in ("app.html", "app.js", "app.css", "viewer.js", "repair.js", "tour.js"))
            return self._json(200, {"v": v})
        if path == "/api/runs":
            from . import api; return self._json(200, api.runs(live_runs()))
        if path.startswith("/api/repair/"):
            from . import api; return self._json(200, api.repairs(os.path.basename(path)))
        if path.startswith("/api/run/"):
            from . import api
            r = api.run(os.path.basename(path), live_runs())
            return self._json(200, r) if r else self._json(404, {"error": "no such run"})
        if path in ("/", "/index.html", "/app", "/app/"): return self._static("app.html")
        if path.startswith("/static/"): return self._static(path[len("/static/"):])
        if self.path.startswith("/api/zip/"):
            self.send_zip(os.path.basename(self.path.split("?")[0])[:-4]); return
        super().do_GET()
    def send_zip(self, run):
        """Build (once) and serve the Mixamo upload zip for a run."""
        try:
            from . import export_zip
            z = C.ROOT / "exports" / f"mixamo_{run}.zip"
            if not z.exists():
                S = json.load(open(C.RUNS / run / "state.json"))
                export_zip.make(C.RUNS / run, run, S["artifacts"]["mesh_glb"], lambda m: None)
            data = z.read_bytes()
            self.send_response(200); self.send_header("Content-Type", "application/zip"); self.send_header("Content-Length", str(len(data)))
            self.send_header("Content-Disposition", f'attachment; filename="mixamo_{run}.zip"'); self.end_headers(); self.wfile.write(data)
        except Exception as e:
            self.send_response(500); self.end_headers(); self.wfile.write(f"zip failed: {e}".encode())
    def log_message(self, fmt, *a):
        try: open("/tmp/homunculus_web_requests.log", "a").write(time.strftime("%H:%M:%S ") + (fmt % a) + "\n")
        except Exception: pass
    def _json(self, code, obj):
        b = json.dumps(obj).encode(); self.send_response(code); self.send_header("Content-Type", "application/json"); self.send_header("Cache-Control", "no-store")
        self.send_header("Content-Length", str(len(b))); self.end_headers(); self.wfile.write(b)
    def _static(self, rel):
        """Files of the web app (homunculus/static), never outside it."""
        base = os.path.realpath(os.path.join(os.path.dirname(__file__), "static")); p = os.path.realpath(os.path.join(base, rel))
        if not p.startswith(base + os.sep) or not os.path.isfile(p): self.send_error(404); return
        ctype = {".html": "text/html; charset=utf-8", ".js": "text/javascript; charset=utf-8", ".css": "text/css; charset=utf-8",
                 ".woff2": "font/woff2", ".svg": "image/svg+xml", ".png": "image/png", ".json": "application/json", ".glb": "model/gltf-binary"}.get(os.path.splitext(p)[1], "application/octet-stream")
        data = open(p, "rb").read(); self.send_response(200); self.send_header("Content-Type", ctype); self.send_header("Content-Length", str(len(data)))
        self.send_header("Cache-Control", "no-cache" if "/vendor/" not in p else "max-age=86400"); self.end_headers(); self.wfile.write(data)
    def guess_type(self, path):
        return "model/gltf-binary" if str(path).endswith(".glb") else super().guess_type(path)
    def do_POST(self):
        path = self.path.split("?")[0]
        if path == "/api/upload": return self.start_run()
        if path == "/api/stop": return self.stop_run()
        if path == "/api/fork": return self.fork_run()
        if path == "/api/looks": return self.look_previews()
        if path == "/api/animate": return self.animate_job()
        if path == "/api/repair": return self.repair_job()
        if path == "/api/repair_use": return self.repair_use()
        if self.path not in ("/api/pick", "/api/review"): self.send_error(404); return
        try:
            d = json.loads(self.rfile.read(int(self.headers.get("Content-Length", 0))) or b"{}")
            run = os.path.basename(str(d["run"]))
            rec = {"action": str(d.get("action", "choose")), "choice": int(d.get("choice", -1)), "notes": str(d.get("notes", ""))[:2000],
                   "gate": str(d.get("gate", ""))}
            json.dump(rec, open(C.RUNS / run / "review.json", "w"))
            self.send_response(200); self.send_header("Content-Type", "application/json"); self.end_headers(); self.wfile.write(b'{"ok":true}')
        except Exception as e:
            self.send_response(400); self.end_headers(); self.wfile.write(str(e).encode())

    def start_run(self):
        """Upload an image + options (query string) and launch the orchestrator as its own systemd unit (survives a page-server restart)."""
        import re, subprocess, sys
        from urllib.parse import urlparse, parse_qs
        try:
            q = {k: v[0] for k, v in parse_qs(urlparse(self.path).query).items()}
            name = q.get("name", "")
            if not re.fullmatch(r"[A-Za-z0-9_-]{1,40}", name): return self._json(400, {"error": "Run name: letters, digits, - and _ only (max 40)."})
            fname = re.sub(r"[^A-Za-z0-9._-]", "_", os.path.basename(q.get("fname", "image.jpg")))
            if os.path.splitext(fname)[1].lower() not in (".jpg", ".jpeg", ".png", ".webp", ".stl", ".obj", ".ply", ".glb", ".gltf", ".fbx"):
                return self._json(400, {"error": "Use an image (.jpg, .png, .webp) or a 3D model (.stl, .obj, .ply, .glb, .fbx)."})
            if name in _live_pids(): return self._json(409, {"error": f"'{name}' is already running."})
            n = int(self.headers.get("Content-Length", 0))
            if n > 400 * 1024 * 1024: return self._json(400, {"error": "File larger than 400 MB."})
            up = C.ROOT / "uploads"; up.mkdir(exist_ok=True); img = up / f"{name}_{fname}"
            data = self.rfile.read(n)
            if data: img.write_bytes(data)
            elif not img.exists():
                prev = C.RUNS / name / "00_input"; cand = sorted(prev.glob("input.*")) if prev.exists() else []
                if not cand: return self._json(400, {"error": "No image uploaded."})
                img = cand[0]
            err = _launch(name, img, q)
            if err: return self._json(500, {"error": err})
            self._json(200, {"ok": True, "run": name})
        except Exception as e:
            self._json(500, {"error": f"{type(e).__name__}: {e}"})

    def fork_run(self):
        """Fork (or restart in place) a run that is not running: {run, name, stage, notes, outfit, review, grace, style, zip}."""
        import re
        from . import fork
        try:
            d = json.loads(self.rfile.read(int(self.headers.get("Content-Length", 0))) or b"{}")
            src = os.path.basename(str(d.get("run", ""))); name = str(d.get("name", "")).strip() or src
            if not (C.RUNS / src / "state.json").exists(): return self._json(404, {"error": "No such run."})
            if not re.fullmatch(r"[A-Za-z0-9_-]{1,40}", name): return self._json(400, {"error": "Run name: letters, digits, - and _ only (max 40)."})
            live = _live_pids()
            if src in live: return self._json(409, {"error": "Stop the run first; forking unlocks once it is stopped."})
            if name in live: return self._json(409, {"error": f"'{name}' is running."})
            stage = str(d.get("stage", ""))
            img = fork.prepare(src, name, stage, str(d.get("notes", ""))[:1500])
            q = {k: str(d[k]) for k in ("outfit", "face", "face_redraw", "review", "grace", "style", "look", "rigger", "anim", "anim_reps") if d.get(k) not in (None, "")}
            q["frm"] = stage; q["zip"] = "1" if d.get("zip") else "0"; q["direct"] = "1" if d.get("direct") else "0"
            err = _launch(name, img, q)
            if err: return self._json(500, {"error": err})
            self._json(200, {"ok": True, "run": name})
        except ValueError as e:
            self._json(400, {"error": str(e)})
        except Exception as e:
            self._json(500, {"error": f"{type(e).__name__}: {e}"})

    def look_previews(self):
        """Queue one redraw per look for a run (python -m homunculus.look_preview); it waits for the GPU lock by itself."""
        import subprocess, sys
        try:
            run = os.path.basename(str(json.loads(self.rfile.read(int(self.headers.get("Content-Length", 0))) or b"{}")["run"]))
            if not (C.RUNS / run / "state.json").exists(): return self._json(404, {"error": "No such run."})
            if not (json.load(open(C.RUNS / run / "state.json")).get("vlm") or {}).get("plan"): return self._json(400, {"error": "This run has no plan yet."})
            unit = f"homunculus-looks-{run}"
            subprocess.run(["systemctl", "--user", "reset-failed", f"{unit}.service"], capture_output=True)
            r = subprocess.run(["systemd-run", "--user", f"--unit={unit}", "--collect", f"--working-directory={C.ROOT}", "-p", "KillSignal=SIGINT",
                                *[f"--setenv={k}={os.environ[k]}" for k in ("DISPLAY", "WAYLAND_DISPLAY", "DBUS_SESSION_BUS_ADDRESS", "XDG_RUNTIME_DIR") if os.environ.get(k)],
                                sys.executable, "-m", "homunculus.look_preview", run], capture_output=True, text=True)
            if r.returncode: return self._json(409 if "already" in (r.stderr or "") else 500, {"error": "Previews are already queued for this run." if "already" in (r.stderr or "") else (r.stderr or r.stdout)[-300:]})
            self._json(200, {"ok": True})
        except Exception as e:
            self._json(500, {"error": f"{type(e).__name__}: {e}"})

    def repair_use(self):
        """Continue a run with a repaired mesh: {run, job, mode: "new" | "same", name}. The textured single mesh of the repair job replaces the run's 3D model and the run restarts
        from the Colour stage (colour, rig, rig check, animation, texture); mode "new" forks a new run and leaves this one untouched."""
        import re, shutil
        from . import fork
        try:
            d = json.loads(self.rfile.read(int(self.headers.get("Content-Length", 0))) or b"{}")
            src = os.path.basename(str(d.get("run", ""))); job = os.path.basename(str(d.get("job", ""))); mode = "same" if d.get("mode") == "same" else "new"
            rg = C.RUNS / src / "10_repair" / job / "repaired_textured.glb"
            if not rg.exists(): return self._json(404, {"error": "That repair has no textured mesh yet."})
            dst = src if mode == "same" else str(d.get("name", "")).strip() or f"{src}_repaired"
            if not re.fullmatch(r"[A-Za-z0-9_-]{1,40}", dst): return self._json(400, {"error": "Run name: letters, digits, - and _ only (max 40)."})
            live = _live_pids()
            if src in live or dst in live: return self._json(409, {"error": "Stop the run first."})
            import subprocess
            if subprocess.run(["systemctl", "--user", "is-active", "--quiet", f"homunculus-repair-{src}.service"]).returncode == 0: return self._json(409, {"error": "A repair is still running for this run."})
            S0 = json.load(open(C.RUNS / src / "state.json"))
            img = fork.prepare(src, dst, "color", f"continued with the repaired mesh from {job}")
            S = json.load(open(C.RUNS / dst / "state.json")); A = S.setdefault("artifacts", {})
            old = A.get("mesh_glb") or ""; mdir = os.path.dirname(old) if old else str(C.RUNS / dst / "05_mesh" / "try1")
            os.makedirs(mdir, exist_ok=True); new = os.path.join(mdir, "mesh_repaired.glb"); shutil.copy(rg, new)
            if not A.get("mesh_before_repair"): A["mesh_before_repair"] = old          # keep the ORIGINAL mesh path through repeated repairs
            A["mesh_glb"] = new; A["mesh_hi_glb"] = new
            for k in ("colored_glb", "textured_glb", "rig_fbx", "rig_glb", "final_fbx", "final_glb", "anim_asset"): A.pop(k, None)
            S["repaired_from"] = {"run": src, "job": job}; json.dump(S, open(C.RUNS / dst / "state.json", "w"), indent=1)
            q = {"frm": "color", "zip": "1" if S0.get("zip") else "0", "direct": "1" if S0.get("direct") else "0", "face_redraw": "1" if S0.get("face_redraw") is not False else "0"}
            for k, sk in (("outfit", "outfit"), ("face", "face"), ("review", "review_mode"), ("grace", "review_grace"), ("look", "look"), ("rigger", "rigger"), ("anim_reps", "anim_reps")):
                if S0.get(sk) not in (None, ""): q[k] = str(S0[sk])
            q["anim"] = "\n".join(S0.get("anim_prompts") or [])
            err = _launch(dst, img, q)
            if err: return self._json(500, {"error": err})
            self._json(200, {"ok": True, "run": dst})
        except ValueError as e:
            self._json(400, {"error": str(e)})
        except Exception as e:
            self._json(500, {"error": f"{type(e).__name__}: {e}"})

    def repair_job(self):
        """Start a repair of the painted region of a run's 3D model: {run, strokes: [[x, y, z, r], ...] (glTF coordinates), notes}. The job waits for the GPU
        lock; its progress is runs/<run>/10_repair/<id>/status.json (GET /api/repair/<run>)."""
        import re, subprocess, sys, time
        try:
            d = json.loads(self.rfile.read(int(self.headers.get("Content-Length", 0))) or b"{}")
            run = os.path.basename(str(d.get("run", "")))
            if not (C.RUNS / run / "state.json").exists(): return self._json(404, {"error": "No such run."})
            S = json.load(open(C.RUNS / run / "state.json"))
            if not (S.get("artifacts") or {}).get("mesh_glb"): return self._json(400, {"error": "This run has no 3D model yet."})
            st = d.get("strokes") or []
            if not (isinstance(st, list) and 1 <= len(st) <= 1500 and all(isinstance(s, list) and len(s) == 4 and all(isinstance(x, (int, float)) for x in s) for s in st)):
                return self._json(400, {"error": "Paint the broken region on the model first."})
            job = time.strftime("%Y%m%d_%H%M%S"); jd = C.RUNS / run / "10_repair" / job; jd.mkdir(parents=True, exist_ok=True)
            json.dump({"strokes": st, "notes": str(d.get("notes", ""))[:400]}, open(jd / "request.json", "w"))
            unit = f"homunculus-repair-{run}"
            subprocess.run(["systemctl", "--user", "reset-failed", f"{unit}.service"], capture_output=True)
            r = subprocess.run(["systemd-run", "--user", f"--unit={unit}", "--collect", f"--working-directory={C.ROOT}", "-p", "KillSignal=SIGINT",
                                *[f"--setenv={k}={os.environ[k]}" for k in ("DISPLAY", "WAYLAND_DISPLAY", "DBUS_SESSION_BUS_ADDRESS", "XDG_RUNTIME_DIR") if os.environ.get(k)],
                                sys.executable, "-m", "homunculus.repair", run, "--job", job], capture_output=True, text=True)
            if r.returncode:
                busy = "already" in (r.stderr or "")
                return self._json(409 if busy else 500, {"error": "A repair is already running for this run." if busy else (r.stderr or r.stdout)[-300:]})
            self._json(200, {"ok": True, "job": job})
        except Exception as e:
            self._json(500, {"error": f"{type(e).__name__}: {e}"})

    def animate_job(self):
        """Queue animation clips for a rigged run: {run, prompts: [...], reps}. The job waits for the GPU lock, appends clips to
        runs/<run>/09_animate/animations.json and puts the run's finished texture on them."""
        import re, subprocess, sys
        try:
            d = json.loads(self.rfile.read(int(self.headers.get("Content-Length", 0))) or b"{}")
            run = os.path.basename(str(d.get("run", ""))); ps = [str(p).strip()[:200] for p in d.get("prompts", []) if str(p).strip()][:8]
            if not (C.RUNS / run / "state.json").exists(): return self._json(404, {"error": "No such run."})
            S = json.load(open(C.RUNS / run / "state.json"))
            if not (S.get("artifacts") or {}).get("rig_fbx"): return self._json(400, {"error": "This run has no rig yet; animate after the Auto-rig stage."})
            if not ps: return self._json(400, {"error": "Type at least one animation prompt."})
            reps = max(1, min(6, int(d.get("reps") or 2)))
            unit = f"homunculus-anim-{run}"
            subprocess.run(["systemctl", "--user", "reset-failed", f"{unit}.service"], capture_output=True)
            cmd = [sys.executable, "-m", "homunculus.animate", run, "--reps", str(reps)]
            for p in ps: cmd += ["--prompt", p]
            r = subprocess.run(["systemd-run", "--user", f"--unit={unit}", "--collect", f"--working-directory={C.ROOT}", "-p", "KillSignal=SIGINT",
                                *[f"--setenv={k}={os.environ[k]}" for k in ("DISPLAY", "WAYLAND_DISPLAY", "DBUS_SESSION_BUS_ADDRESS", "XDG_RUNTIME_DIR") if os.environ.get(k)],
                                *cmd], capture_output=True, text=True)
            if r.returncode:
                busy = "already" in (r.stderr or "")
                return self._json(409 if busy else 500, {"error": "Animation clips are already being generated for this run." if busy else (r.stderr or r.stdout)[-300:]})
            self._json(200, {"ok": True})
        except Exception as e:
            self._json(500, {"error": f"{type(e).__name__}: {e}"})

    def stop_run(self):
        import subprocess, signal
        try:
            run = os.path.basename(str(json.loads(self.rfile.read(int(self.headers.get("Content-Length", 0))) or b"{}")["run"]))
            pid = _live_pids().get(run)
            if not pid: return self._json(404, {"error": "That run is not running."})
            u = subprocess.run(["systemctl", "--user", "stop", "--no-block", f"homunculus-run-{run}.service"], capture_output=True)
            if u.returncode: os.kill(pid, signal.SIGINT)          # started from a terminal: Ctrl+C equivalent
            self._json(200, {"ok": True})
        except Exception as e:
            self._json(500, {"error": str(e)})

def _launch(name, img, q):
    """Start the orchestrator for `name` as its own systemd user unit (survives a page-server restart; Stop sends Ctrl+C).
    q: outfit, style, review, grace, frm, zip (strings). Returns an error text or None."""
    import re, subprocess, sys
    cmd = [sys.executable, "-m", "homunculus.orchestrate", str(img), "--name", name, "--no-open"]
    if q.get("outfit") in ("keep", "shirtless", "nude"): cmd += ["--outfit", q["outfit"]]
    if q.get("face") in ("auto", "on", "off"): cmd += ["--face", q["face"]]
    if q.get("face_redraw") in ("1", "0", "on", "off"): cmd += ["--face-redraw", "on" if q["face_redraw"] in ("1", "on") else "off"]
    if q.get("style") in C.UPSCALERS: cmd += ["--style", q["style"]]
    if q.get("review") in ("off", "override", "manual"): cmd += ["--review", q["review"]]
    if str(q.get("grace", "")).isdigit(): cmd += ["--review-grace", str(q["grace"])]
    if q.get("frm"): cmd += ["--from", re.sub(r"[^a-z_]", "", q["frm"])]
    if q.get("zip") == "1": cmd += ["--zip"]
    if q.get("direct") == "1": cmd += ["--direct"]
    if q.get("rigger") in C.RIGGERS: cmd += ["--rigger", q["rigger"]]
    for line in str(q.get("anim", "")).splitlines():
        if line.strip(): cmd += ["--anim", line.strip()[:200]]
    if str(q.get("anim_reps", "")).isdigit(): cmd += ["--anim-reps", str(max(1, min(6, int(q["anim_reps"]))))]
    if q.get("look") in ("choose", "asis", "stylized", "game", "anime3d", "clay", "chibi"): cmd += ["--look", q["look"]]
    env = [f"--setenv={k}={os.environ[k]}" for k in ("DISPLAY", "WAYLAND_DISPLAY", "DBUS_SESSION_BUS_ADDRESS", "XDG_RUNTIME_DIR") if os.environ.get(k)]
    subprocess.run(["systemctl", "--user", "reset-failed", f"homunculus-run-{name}.service"], capture_output=True)
    r = subprocess.run(["systemd-run", "--user", f"--unit=homunculus-run-{name}", "--collect", f"--working-directory={C.ROOT}", "-p", "KillSignal=SIGINT",
                        "-p", "TimeoutStopSec=90", *env, *cmd], capture_output=True, text=True)
    return (r.stderr or r.stdout)[-300:] if r.returncode else None

def ensure_service():
    """Make sure the page server is up for this session: start the homunculus-web user service if nothing serves the port.
    It is NOT started at login; it runs from the first pipeline run (or ./web.sh start) until ./web.sh stop or logout."""
    import socket, subprocess, time
    def up():
        with socket.socket() as s_:
            s_.settimeout(0.5); return s_.connect_ex(("127.0.0.1", PORT)) == 0
    if up(): return True
    subprocess.run(["systemctl", "--user", "start", "homunculus-web.service"], capture_output=True)
    for _ in range(20):
        if up(): return True
        time.sleep(0.5)
    return start()          # fallback: serve from this process

_started = False
def start():
    """Start once per process; if the port is already served by another run, reuse it."""
    global _started
    if _started: return True
    try:
        srv = ThreadingHTTPServer(("127.0.0.1", PORT), partial(H, directory=str(C.RUNS)))
    except OSError:
        return True      # another homunculus process already serves the runs folder
    threading.Thread(target=srv.serve_forever, daemon=True).start(); _started = True; return True

def url(run): return f"http://127.0.0.1:{PORT}/#/run/{run}"
