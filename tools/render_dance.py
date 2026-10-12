"""Render an animated rigged character to PNG frames with a moving camera (run inside Blender; tools/make_mp4.py drives it and encodes the video).

blender -b --python tools/render_dance.py -- <character.fbx> <frames_dir> [--fps 30] [--size 1280x720] [--range a b] [--seed 7] [--cuts f1,f2,..] [--fixed] [--samples 12] [--engine eevee|workbench] [--probe]
  --range a b   render output frames a..b-1 only (so several Blender processes can share one clip); the camera plan is deterministic, every process computes the same one
  --cuts        output frames at which a new shot must start (the seams of a joined clip)
  --probe       print the plan and the time of one frame, render nothing else
Use an FBX (60 fps animation, exact frame numbers). The character is scaled to 1.75 m whatever its file units (a Mixamo export of the Thriller character is 9 mm tall in glTF units).

The camera director: shots of 3 to 6 s cut between a slow orbit, a push-in, a low hero angle, a close-up and a side track, always following the dancer (hips and head, smoothed over 0.5 s) with a little handheld drift.
Every clip (and every seam) starts and ends on the same neutral medium front shot, so separate clips and the joined one cut together cleanly. No sound."""
import bpy, sys, os, math, time, random
import numpy as np
from mathutils import Vector, Matrix

argv = sys.argv[sys.argv.index("--") + 1:]
def opt(flag, default=None, n=1, cast=str):
    if flag in argv:
        i = argv.index(flag); v = [cast(x) for x in argv[i + 1:i + 1 + n]]; del argv[i:i + 1 + n]; return v[0] if n == 1 else v
    return default
OUT_FPS = opt("--fps", 30, cast=int); W, H_PX = [int(x) for x in opt("--size", "1280x720").split("x")]; RANGE = opt("--range", None, n=2, cast=int)
SEED = opt("--seed", 7, cast=int); CUTS = [int(x) for x in (opt("--cuts", "") or "").split(",") if x]; SAMPLES = opt("--samples", 12, cast=int); ENGINE = opt("--engine", "eevee")
FIXED = "--fixed" in argv                                    # one steady front camera for the whole clip (to compare with a video)
if FIXED: argv.remove("--fixed")
PROBE = "--probe" in argv
if PROBE: argv.remove("--probe")
model, frames_dir = argv[0], argv[1]; os.makedirs(frames_dir, exist_ok=True)

# ---------------------------------------------------------------- the character
bpy.ops.wm.read_factory_settings(use_empty=True)
bpy.ops.import_scene.fbx(filepath=model)
A = next(o for o in bpy.data.objects if o.type == "ARMATURE"); sc = bpy.context.scene; act = A.animation_data.action
SRC_FPS = sc.render.fps; f0, f1 = int(round(act.frame_range[0])), int(round(act.frame_range[1]))
N = int((f1 - f0 + 1) * OUT_FPS / SRC_FPS); STEP = SRC_FPS / OUT_FPS
meshes = [o for o in bpy.data.objects if o.type == "MESH"]
def world_bbox():
    dg = bpy.context.evaluated_depsgraph_get(); P = []
    for o in meshes:
        e = o.evaluated_get(dg); me = e.to_mesh(); V = np.empty(len(me.vertices) * 3, np.float32); me.vertices.foreach_get("co", V); M = np.array(e.matrix_world); P.append(V.reshape(-1, 3) @ M[:3, :3].T + M[:3, 3]); e.to_mesh_clear()
    P = np.concatenate(P); return P.min(0), P.max(0)
sc.frame_set(f0); lo, hi = world_bbox(); F = 1.75 / max(hi[2] - lo[2], 1e-9)
ROOT = bpy.data.objects.new("stage_scale", None); sc.collection.objects.link(ROOT); ROOT.scale = (F, F, F); A.parent = ROOT      # the action animates the armature's own location, rotation AND scale: scaling the armature is undone at every frame, so a parent holds the scale
bpy.context.view_layer.update(); sc.frame_set(f0); lo, hi = world_bbox(); FLOOR = float(lo[2]); HH = float(hi[2] - lo[2])
hips, head = A.pose.bones["mixamorig:Hips"], A.pose.bones["mixamorig:Head"]
print(f"[render] {os.path.basename(model)}: {SRC_FPS} fps source, {f1 - f0 + 1} frames -> {N} frames at {OUT_FPS} fps = {N / OUT_FPS:.1f} s; character scaled x{F:.1f} to {HH:.2f} m; floor z {FLOOR:.3f}", flush=True)

# ---------------------------------------------------------------- where the dancer is, frame by frame (smoothed 0.5 s)
def src_frame(k): return f0 + k * STEP
track_h, track_hd = [], []
for k in range(N):
    sc.frame_set(int(round(src_frame(k)))); track_h.append(np.array((A.matrix_world @ hips.matrix).translation)); track_hd.append(np.array((A.matrix_world @ head.matrix).translation))
def smooth(a, w):
    a = np.array(a); out = np.empty_like(a); r = w // 2
    for i in range(len(a)): out[i] = a[max(0, i - r):i + r + 1].mean(0)
    return out
SUBJ = smooth(track_h, int(OUT_FPS * 0.5)); HEAD = smooth(track_hd, int(OUT_FPS * 0.4))

# ---------------------------------------------------------------- the camera director
rng = random.Random(SEED)
def ease(u): return u * u * (3 - 2 * u)
SHOTS = {      # name: (distance from, to; camera height from, to (x character height); look-at height from, to; orbit sweep degrees; focal mm)
    "medium": ((2.9, 2.6), (0.62, 0.62), (0.55, 0.55), 0, 40), "orbit": ((3.6, 3.4), (0.35, 0.5), (0.5, 0.5), 40, 28), "push_in": ((4.0, 1.9), (0.5, 0.7), (0.5, 0.62), 0, 38),
    "low_hero": ((2.7, 2.2), (0.08, 0.14), (0.6, 0.6), 22, 26), "close_up": ((1.7, 1.35), (0.78, 0.84), (0.8, 0.82), 15, 70), "fixed": ((3.4, 3.4), (0.5, 0.5), (0.5, 0.5), 0, 40), "side_track": ((3.0, 3.1), (0.45, 0.5), (0.5, 0.5), 8, 40)}
def plan(n, cuts):
    if FIXED: return [dict(name="fixed", a=0, b=n, ang=0, sweep=0)]
    segs = [0] + [c for c in cuts if 0 < c < n] + [n]; shots = []; last = None; last_ang = 0.0
    for a, b in zip(segs[:-1], segs[1:]):
        t = a; first = True
        while t < b:
            rem = b - t
            if first: name, dur = "medium", int(OUT_FPS * 2.5)
            elif rem <= int(OUT_FPS * 7.5): name, dur = "medium", rem         # the last shot of a segment: neutral again
            else:
                name = rng.choice([s for s in ("orbit", "push_in", "low_hero", "close_up", "side_track") if s != last]); dur = int(OUT_FPS * rng.uniform(3.0, 5.5))
                if rem - dur < int(OUT_FPS * 2.5): dur = rem - int(OUT_FPS * 2.5)
            dur = min(dur, rem)
            ang = rng.choice([-1, 1]) * rng.uniform(25, 55) if name not in ("medium", "side_track") else (rng.uniform(-8, 8) if name == "medium" else rng.choice([-90, 90]))
            if abs(ang - last_ang) < 20 and name not in ("medium",): ang = -ang if ang != 0 else 40
            sweep = rng.choice([-1, 1]) * SHOTS[name][3]
            shots.append(dict(name=name, a=t, b=t + dur, ang=ang, sweep=sweep)); last, last_ang, t, first = name, ang, t + dur, False
    return shots
SHOT_LIST = plan(N, CUTS)
print("[render] shots: " + ", ".join(f"{s['name']}@{s['a'] / OUT_FPS:.1f}s" for s in SHOT_LIST), flush=True)
nrng = random.Random(SEED + 1); PH = [(nrng.uniform(0, 6.28), nrng.uniform(0.4, 1.3)) for _ in range(6)]
def cam_for(k):
    s = next(x for x in SHOT_LIST if x["a"] <= k < x["b"]); u = ease((k - s["a"]) / max(1, s["b"] - s["a"] - 1)); d0, h0, l0, _, focal = SHOTS[s["name"]]
    lerp = lambda p: p[0] + (p[1] - p[0]) * u
    ang = math.radians(s["ang"] + s["sweep"] * u); dist = lerp(d0) * HH; subj = SUBJ[k]
    tgt = Vector((subj[0], subj[1], FLOOR + lerp(l0) * HH)) if s["name"] != "close_up" else Vector((HEAD[k][0], HEAD[k][1], HEAD[k][2] - 0.08 * HH))
    pos = Vector((subj[0] + dist * math.sin(ang), subj[1] - dist * math.cos(ang), FLOOR + lerp(h0) * HH))
    t = k / OUT_FPS; j = Vector(sum(0.006 * HH * math.sin(w * t * 2.1 + p + i) for i, (p, w) in enumerate(PH[a:a + 2])) for a in (0, 2, 4)) if False else Vector((sum(0.005 * HH * math.sin(w * t * 2.3 + p) for p, w in PH[0:2]), sum(0.005 * HH * math.sin(w * t * 1.9 + p) for p, w in PH[2:4]), sum(0.004 * HH * math.sin(w * t * 2.7 + p) for p, w in PH[4:6])))
    return pos + j, tgt + j * 0.5, focal

# ---------------------------------------------------------------- the stage: floor, lights, camera
def mat(name, col, rough=0.5):
    m = bpy.data.materials.new(name); m.use_nodes = True; b = m.node_tree.nodes["Principled BSDF"]; b.inputs["Base Color"].default_value = (*col, 1); b.inputs["Roughness"].default_value = rough; return m
bpy.ops.mesh.primitive_plane_add(size=60, location=(0, 0, FLOOR)); fl = bpy.context.object; fl.data.materials.append(mat("floor", (0.03, 0.035, 0.05), 0.35))
w = bpy.data.worlds.new("w"); w.use_nodes = True; w.node_tree.nodes["Background"].inputs["Color"].default_value = (0.01, 0.012, 0.02, 1); w.node_tree.nodes["Background"].inputs["Strength"].default_value = 1.0; sc.world = w
def light(kind, loc, energy, col, size=None, rot=None):
    L = bpy.data.lights.new(kind, kind); L.energy = energy; L.color = col
    if size and kind == "AREA": L.size = size
    o = bpy.data.objects.new(kind, L); sc.collection.objects.link(o); o.location = loc
    return o
def aim(o, target): o.rotation_euler = (Vector(target) - o.location).to_track_quat("-Z", "Y").to_euler()
c0 = Vector((0, 0, FLOOR + 0.9 * HH / 1.75))
key = light("AREA", (2.5, -4.0, FLOOR + 3.2), 900, (1.0, 0.93, 0.85), 3.0); aim(key, c0)
rim1 = light("AREA", (-3.2, 3.0, FLOOR + 2.4), 700, (0.35, 0.65, 1.0), 2.0); aim(rim1, c0)
rim2 = light("AREA", (3.2, 3.2, FLOOR + 2.4), 500, (1.0, 0.35, 0.7), 2.0); aim(rim2, c0)
fill = light("AREA", (-3.0, -3.5, FLOOR + 1.2), 160, (0.8, 0.85, 1.0), 4.0); aim(fill, c0)
cam = bpy.data.objects.new("cam", bpy.data.cameras.new("cam")); sc.collection.objects.link(cam); sc.camera = cam; cam.data.sensor_width = 36
sc.render.resolution_x, sc.render.resolution_y, sc.render.resolution_percentage = W, H_PX, 100; sc.render.image_settings.file_format = "PNG"; sc.render.image_settings.color_mode = "RGB"
if ENGINE == "eevee":
    sc.render.engine = "BLENDER_EEVEE"; sc.eevee.taa_render_samples = SAMPLES
    for attr, val in (("use_shadows", True), ("use_raytracing", False), ("use_gtao", True)):
        if hasattr(sc.eevee, attr): setattr(sc.eevee, attr, val)
else:
    sc.render.engine = "BLENDER_WORKBENCH"; sh = sc.display.shading; sh.light = "STUDIO"; sh.color_type = "TEXTURE"; sh.show_shadows = True; sc.world.color = (0.05, 0.05, 0.08)
try: sc.view_settings.look = "AgX - Medium High Contrast"
except Exception: pass
sc.view_settings.exposure = 0.3

# ---------------------------------------------------------------- render
a, b = (RANGE if RANGE else (0, N)); a, b = max(0, a), min(N, b)
if PROBE:
    t = time.time(); k = a
    pos, tgt, focal = cam_for(k); cam.location = pos; cam.rotation_euler = (tgt - pos).to_track_quat("-Z", "Y").to_euler(); cam.data.lens = focal; sc.frame_set(int(round(src_frame(k))))
    sc.render.filepath = os.path.join(frames_dir, f"probe_{k:05d}.png"); bpy.ops.render.render(write_still=True); print(f"[render] one frame in {time.time() - t:.1f} s", flush=True); sys.exit(0)
t0 = time.time()
for k in range(a, b):
    pos, tgt, focal = cam_for(k); cam.location = pos; cam.rotation_euler = (tgt - pos).to_track_quat("-Z", "Y").to_euler(); cam.data.lens = focal
    sc.frame_set(int(round(src_frame(k)))); sc.render.filepath = os.path.join(frames_dir, f"f{k:05d}.png"); bpy.ops.render.render(write_still=True)
    if (k - a) % 50 == 0: print(f"[render] frame {k} ({k - a + 1}/{b - a}), {(time.time() - t0) / (k - a + 1):.2f} s per frame", flush=True)
print(f"[render] frames {a}..{b - 1} done in {time.time() - t0:.0f} s", flush=True)
