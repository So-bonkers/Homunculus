import * as React from "react";
import { toast } from "sonner";
import { ArrowLeftRight, Bot, Check, Hand, Loader2, RotateCcw, Search, Sparkles, Square, Star, Trash2, TriangleAlert } from "lucide-react";
import { api, useHandPoses, useHands, useInvalidate } from "@/lib/api";
import type { HandCurve, HandKey, HandKeyOpts, HandLane, HandPose, HandTracks } from "@/lib/types";
import { Badge, Button, Popover, PopoverContent, PopoverTrigger, Segmented, Tip } from "@/components/ui";
import { cn, duration } from "@/lib/utils";
import { GESTURES, WRIST_GESTURES, type Gesture } from "./handGestures";
import type { Wave } from "./SyncPlayer";

/** The hand timeline of a dance: one lane per hand, a block per pose, under the video and the character on their shared clock. Press 1-9 to give the chosen hand(s) a pinned pose from the playhead on
 *  (the first pose of a lane holds from the start), pick any of the 48 library poses from the picker, or drop a quick gesture (snap, flick, pulse ...) at the playhead. Drag a block's left edge to move
 *  the change; each change has its own transition (smooth, quick, snap, linear, cut). Apply bakes the poses into a copy of the clip (the fingers of the 3D model then follow). */
const CAT_COLOR: Record<string, string> = {
  Neutral: "#5b8cff", Curved: "#2dd4f2", Closed: "#f87171", Pointing: "#34d399", Signs: "#a78bfa", "Pinch & snap": "#fbbf24", "Finger wave": "#f472b6",     // fingers
  Straight: "#94a3b8", "Bent in": "#fb7185", "Bent back": "#38bdf8", Sideways: "#facc15", Combined: "#c084fc",                                              // wrist
  Palm: "#2dd4bf",                                                                                                                                         // palm direction
};
/** Three kinds of label, each with a lane per hand: the fingers, the wrist (how the hand bends on the forearm) and the palm direction (the forearm's roll: which way the palm faces). */
type Mode = "fingers" | "wrist" | "palm";
const MODES: { key: Mode; label: string; kind: "pose" | "wrist" | "palm"; hint: string }[] = [
  { key: "fingers", label: "Fingers", kind: "pose", hint: "The shape of the hand" }, { key: "wrist", label: "Wrist", kind: "wrist", hint: "The hand bending in, back or sideways on the forearm" },
  { key: "palm", label: "Palm", kind: "palm", hint: "Which way the palm faces (the forearm's roll); as the clip when off" },
];
const DEFAULTS: Record<Mode, string[]> = {
  fingers: ["open", "relaxed", "fist", "point", "grip", "thumbs_up", "pinch", "claw", "spread"],
  wrist: ["neutral", "flex_20", "flex_40", "ext_20", "ext_40", "radial_20", "ulnar_30", "flex_ulnar", "ext_radial"],
  palm: ["as_clip", "palm_down", "palm_up", "palm_forward", "palm_back", "palm_in", "palm_out"],
};
const PALM_GLYPH: Record<string, string> = { as_clip: "↺", palm_down: "⤓", palm_up: "⤒", palm_forward: "⊙", palm_back: "⊗", palm_in: "⇥", palm_out: "⇤" };
/** Where a lane starts when its first change comes later: the fingers rest, the wrist is level, the palm is whatever the clip has. */
const START: Record<Mode, string> = { fingers: "relaxed", wrist: "neutral", palm: "as_clip" };
const laneOf = (side: Side, mode: Mode): HandLane => (mode === "fingers" ? side : (`${side}_${mode}` as HandLane));
const EMPTY: HandTracks = { left: [], right: [], left_wrist: [], right_wrist: [], left_palm: [], right_palm: [] };
const CURVES: { key: HandCurve | ""; label: string; hint: string }[] = [
  { key: "", label: "Auto", hint: "smooth, shortened after a short pose" }, { key: "smooth", label: "Smooth", hint: "about 0.13 s, gentle at both ends" }, { key: "quick", label: "Quick", hint: "about 0.07 s, fast start" },
  { key: "snap", label: "Snap", hint: "about 0.05 s with a little overshoot" }, { key: "linear", label: "Linear", hint: "even speed" }, { key: "hold", label: "Cut", hint: "no transition" },
];
type Side = "left" | "right"; type Active = Side | "both";
const r3 = (x: number) => Math.round(x * 1000) / 1000;
const optsOf = (k: HandKey): HandKeyOpts => (k.length > 2 ? (k[2] as HandKeyOpts) : {});
const mk = (t: number, pose: string, o?: HandKeyOpts): HandKey => (o && (o.curve || o.d) ? [t, pose, o] : [t, pose]);

function dedupe(ks: HandKey[]): HandKey[] { return ks.filter((k, i) => i === 0 || k[1] !== ks[i - 1][1] || k.length > 2 || ks[i - 1].length > 2); }
const sorted = (keys: HandKey[]) => keys.map((k) => [...k] as HandKey).sort((a, b) => a[0] - b[0]);

/** The timeline with `pose` from time t on: a key within 60 ms is changed, an empty lane gets a relaxed start first, and a key that repeats the pose before it is not added. */
/** The model's labels for the stretch [t0, t1) of one lane put into the lane: your keys before t0 stay, the model's keys inside the stretch come in (starting with its pose at t0), and what was after t1 stays (with the pose the lane had at t1). */
function splice(mine: HandKey[], llm: HandKey[], t0: number, t1: number): HandKey[] {
  const at = (ks: HandKey[], t: number) => { let p: HandKey | null = null; for (const k of ks) if (k[0] <= t + 1e-6) p = k; return p; };
  const head = mine.filter((k) => k[0] < t0 - 1e-6); const mid: HandKey[] = []; const p0 = at(llm, t0); if (p0) mid.push([r3(t0), p0[1]] as HandKey);
  for (const k of llm) if (k[0] > t0 + 1e-6 && k[0] < t1 - 1e-6) mid.push(k);
  let tail = Number.isFinite(t1) ? mine.filter((k) => k[0] >= t1 - 1e-6) : [];
  if (tail.length && tail[0][0] > t1 + 1e-6) { const s = at(mine, t1); if (s) tail = [[r3(t1), s[1]] as HandKey, ...tail]; }
  return dedupe([...head, ...mid, ...tail]);
}
function setAt(keys: HandKey[], t: number, pose: string, o?: HandKeyOpts, start = "relaxed"): HandKey[] {
  const ks = sorted(keys); t = r3(Math.max(0, t));
  const near = ks.findIndex((k) => Math.abs(k[0] - t) < 0.06);
  if (near >= 0) { ks[near] = mk(ks[near][0], pose, o ?? optsOf(ks[near])); return dedupe(ks); }
  if (!ks.length && t > 0.15) ks.push([0, start]);
  ks.push(mk(t, pose, o)); return dedupe(ks.sort((a, b) => a[0] - b[0]));
}
/** A run of keys (a gesture) dropped in: whatever the hand had over its span is replaced. */
function insertRun(keys: HandKey[], run: HandKey[], start = "relaxed"): HandKey[] {
  const lo = Math.min(...run.map((k) => k[0])) - 0.02, hi = Math.max(...run.map((k) => k[0])) + 0.02; let ks = sorted(keys).filter((k) => k[0] < lo || k[0] > hi);
  if (!ks.length && lo > 0.15) ks.push([0, start]);
  return dedupe([...ks, ...run].sort((a, b) => a[0] - b[0]));
}

function PoseCard({ p, onPick, pinned, onPin }: { p: HandPose; onPick: () => void; pinned: boolean; onPin: () => void }) {
  return (
    <div className="group relative overflow-hidden rounded-lg border border-line bg-black/25 transition hover:border-white/25" title={p.description}>
      <button onClick={onPick} className="block w-full text-left">
        {p.image ? <img src={p.image} loading="lazy" className="aspect-[2/1] w-full bg-[#b0b0b4] object-cover" /> : <div className="grid aspect-[2/1] w-full place-items-center bg-white/5 text-[26px]" style={{ color: CAT_COLOR[p.category] }}>{PALM_GLYPH[p.key] ?? "•"}</div>}
        <div className="flex items-center gap-1.5 px-2 py-1.5 text-[11.5px]"><span className="size-2 shrink-0 rounded-sm" style={{ background: CAT_COLOR[p.category] }} /><span className="truncate font-medium text-ink">{p.label}</span></div>
      </button>
      <button onClick={onPin} className={cn("absolute top-1 right-1 grid size-6 place-items-center rounded-md bg-black/50 backdrop-blur transition", pinned ? "text-warn" : "text-ink-3 opacity-0 group-hover:opacity-100")} title={pinned ? "Unpin" : "Pin to keys 1-9"}><Star className={cn("size-3.5", pinned && "fill-current")} /></button>
    </div>
  );
}

/** The sound of the clip as a strip aligned with the lanes: the envelope, and a tick where the sound jumps (a hit). Click it to jump there. */
function WaveStrip({ wave, len, t, seek }: { wave: Wave | null | "none"; len: number; t: number; seek: (s: number) => void }) {
  const cv = React.useRef<HTMLCanvasElement>(null); const box = React.useRef<HTMLDivElement>(null);
  React.useEffect(() => {
    const c = cv.current, b = box.current; if (!c || !b) return;
    const draw = () => {
      const w = b.clientWidth, h = b.clientHeight, dpr = devicePixelRatio || 1; c.width = w * dpr; c.height = h * dpr; const g = c.getContext("2d")!; g.scale(dpr, dpr); g.clearRect(0, 0, w, h);
      if (!wave || wave === "none" || !len) return;
      const P = wave.peaks; g.fillStyle = "rgba(139,108,255,0.55)";
      for (let x = 0; x < w; x++) { const i = Math.min(P.length - 1, Math.floor((x / w) * P.length)); const a = Math.max(1, P[i] * (h - 4)); g.fillRect(x, (h - a) / 2, 1, a); }
      g.fillStyle = "rgba(251,191,36,0.9)"; for (const o of wave.onsets) g.fillRect(Math.round((o / len) * w), 0, 1.5, 5);
    };
    draw(); const ro = new ResizeObserver(draw); ro.observe(b); return () => ro.disconnect();
  }, [wave, len]);
  return (
    <div ref={box} className="relative h-9 cursor-pointer overflow-hidden rounded-lg border border-line bg-black/30" onPointerDown={(e) => { const r = e.currentTarget.getBoundingClientRect(); seek(((e.clientX - r.left) / r.width) * len); }}>
      <canvas ref={cv} className="absolute inset-0 size-full" />
      {wave === "none" && <div className="absolute inset-0 grid place-items-center text-[11px] text-warn">no sound in this reference file</div>}
      {wave === null && <div className="absolute inset-0 grid place-items-center text-[11px] text-ink-3">reading the sound…</div>}
      <div className="pointer-events-none absolute inset-y-0 w-0.5 bg-white" style={{ left: `${len ? Math.min(100, (t / len) * 100) : 0}%` }} />
    </div>
  );
}

export function HandTimeline({ run, clip, name, t, len, seek, wave }: { run: string; clip: string; name?: string; t: number; len: number; seek: (s: number) => void; wave?: Wave | null | "none" }) {
  const q = useHands(run, clip); const inv = useInvalidate(); const cat = useHandPoses();
  const all = cat.data ?? []; const byKey = React.useMemo(() => Object.fromEntries(all.map((p) => [p.key, p])), [all]);
  const [mode, setMode] = React.useState<Mode>("fingers"); const kind = MODES.find((m) => m.key === mode)!.kind;
  const poses = React.useMemo(() => all.filter((p) => (p.kind ?? "pose") === kind), [all, kind]); const CATS = React.useMemo(() => [...new Set(poses.map((p) => p.category))], [poses]);
  const colorOf = (k: string) => CAT_COLOR[byKey[k]?.category] ?? "#7b8494"; const labelOf = (k: string) => byKey[k]?.label ?? k;
  const [tracks, setTracks] = React.useState<HandTracks>(EMPTY);
  const [saved, setSaved] = React.useState(JSON.stringify(EMPTY));
  const [active, setActive] = React.useState<Active>("both");
  const [sel, setSel] = React.useState<{ lane: HandLane; i: number } | null>(null);
  const [allPins, setAllPins] = React.useState<Record<Mode, string[]>>(() => {
    try { const v = JSON.parse(localStorage.getItem("homunculus_hand_pins2") || "null"); return { ...DEFAULTS, ...(v ?? {}) }; } catch { return DEFAULTS; }
  });
  const pins = allPins[mode];
  const [find, setFind] = React.useState(""); const [catF, setCatF] = React.useState<string | null>(null);
  const tRef = React.useRef(t); tRef.current = t;
  const was = React.useRef<string | undefined>(undefined);
  const savePins = (p: string[]) => { const n = { ...allPins, [mode]: p }; setAllPins(n); try { localStorage.setItem("homunculus_hand_pins2", JSON.stringify(n)); } catch { /* private mode */ } };
  const togglePin = (k: string) => savePins(pins.includes(k) ? pins.filter((x) => x !== k) : pins.length >= 9 ? [...pins.slice(0, 8), k] : [...pins, k]);

  // the saved timeline arrives (or the clip changes): start from it; later refetches while baking must not overwrite what is being edited
  React.useEffect(() => { if (q.data) { const tr = { ...EMPTY, ...q.data.tracks }; setTracks(tr); setSaved(JSON.stringify(tr)); setSel(null); } }, [clip, q.data?.updated]);   // eslint-disable-line react-hooks/exhaustive-deps
  // the vision-language model's labels land in the editor (unsaved) as it finishes each 5 s of the clip: the part just finished replaces that stretch of the timeline, everything you edited
  // before it stays, and what was there after it stays too. A result that was already there when the clip was opened is not loaded again.
  const llm = q.data?.llm; const llmRunning = llm?.status === "running"; const [fromLlm, setFromLlm] = React.useState(false);
  const llmSeen = React.useRef<{ clip: string; started: number | null; chunk: number; upto: number; done: boolean; busy: boolean } | null>(null);
  React.useEffect(() => {
    if (!q.data) return; const st = llm?.status; const started = (llm as any)?.started ?? null; const chunk = llm?.chunk ?? 0;
    let h = llmSeen.current;
    if (!h || h.clip !== clip) { h = llmSeen.current = { clip, started, chunk: st === "running" ? 0 : chunk, upto: 0, done: st !== "running", busy: false }; setFromLlm(false); }
    else if (h.started !== started && st === "running") h = llmSeen.current = { clip, started, chunk: 0, upto: 0, done: false, busy: false };      // a new job
    if (h.done) return;
    if (st === "failed") { h.done = true; toast.error("The LLM annotation failed: " + (llm?.error ?? "")); return; }
    if (st === "stopped") { h.done = true; return; }
    if (h.busy || !(st === "running" || st === "done")) return;
    if (!(chunk > h.chunk || st === "done")) return;
    h.busy = true;
    api.handsLlmResult(run, clip).then((r) => {
      const t0 = h!.upto, t1 = r.final === false ? (r.upto ?? t0) : Infinity; h!.upto = r.final === false ? (r.upto ?? t0) : t0; h!.chunk = r.chunk ?? chunk; h!.done = r.final !== false && st === "done"; h!.busy = false;
      setTracks((T) => { const n = { ...T }; for (const l of Object.keys(EMPTY) as HandLane[]) n[l] = splice(T[l] ?? [], r.tracks[l] ?? [], t0, t1); return n; }); setSel(null); setFromLlm(true);
      if (r.final === false) toast.message(`The LLM has labelled the first ${Math.round(r.upto ?? 0)} s; they are in the editor.`);
      else toast.success("The LLM has labelled the whole clip. Nothing is saved yet: edit anything, then Apply to the model.");
    }).catch((e) => { h!.busy = false; toast.error(e.message); });
  }, [clip, llm?.status, llm?.chunk]);   // eslint-disable-line react-hooks/exhaustive-deps
  // what is sent to the model: how many frames per second of the reference video (never more than it has) and whether it thinks first; the time it will take is estimated from the jobs that ran before
  const video = q.data?.video; const native = video?.fps ?? 30; const chunkFrames = q.data?.chunk_frames ?? 125;
  const [llmOpt, setLlmOpt] = React.useState<{ fps: number | null; thinking: boolean; model: string }>(() => { try { const v = JSON.parse(localStorage.getItem("homunculus_llm_opts") || "null"); return { fps: v?.fps ?? null, thinking: v?.thinking ?? true, model: v?.model ?? "qwen38" }; } catch { return { fps: null, thinking: true, model: "qwen38" }; } });
  const setOpt = (o: Partial<{ fps: number | null; thinking: boolean; model: string }>) => setLlmOpt((x) => { const n = { ...x, ...o }; try { localStorage.setItem("homunculus_llm_opts", JSON.stringify(n)); } catch { /* private mode */ } return n; });
  const fpsChoices = React.useMemo(() => [...new Set([5, 10, 12.5, 15, 25, native].filter((f) => f <= native + 0.01))].sort((a, b) => a - b), [native]);
  const sendFps = Math.min(llmOpt.fps ?? 25, native); const sendFpsShown = fpsChoices.reduce((b, f) => (Math.abs(f - sendFps) < Math.abs(b - sendFps) ? f : b), fpsChoices[0]);
  const models = q.data?.llm_models ?? []; const modelKey = models.some((m) => m.key === llmOpt.model) ? llmOpt.model : "qwen38"; const tm = q.data?.llm_timing?.[`${modelKey}:${llmOpt.thinking ? "on" : "off"}`]; const requests = video ? Math.max(1, Math.ceil((video.duration * sendFpsShown) / chunkFrames)) : 0; const estSec = tm ? requests * tm.s + 30 : 0;
  const estText = (s: number) => (s < 90 ? `${Math.round(s)} s` : `${Math.round(s / 60)} min`);
  const [llmOpen, setLlmOpen] = React.useState(false);
  const annotate = async (stop = false) => {
    try {
      if (stop) await api.handsLlm(run, clip, true);
      else { await api.handsLlm(run, clip, false, { fps: sendFpsShown, thinking: llmOpt.thinking, model: modelKey }); setLlmOpen(false); toast.message("The LLM is watching the clip. Each part lands in the editor as it is labelled; you can keep editing."); }
      inv(["hands", run, clip]);
    } catch (e: any) { toast.error(e.message); }
  };
  React.useEffect(() => {   // a bake that has just finished: the run's clip now points at the file with the fingers
    const s = q.data?.status; if (was.current === "running" && s && s !== "running") { inv(["run", run]); s === "done" ? toast.success("The fingers are set on the model") : toast.error("Could not set the fingers: " + (q.data?.error ?? "")); }
    was.current = s;
  }, [q.data?.status]);   // eslint-disable-line react-hooks/exhaustive-deps

  const dirty = JSON.stringify(tracks) !== saved; const baking = q.data?.status === "running";
  const sides = (a: Active): Side[] => (a === "both" ? ["left", "right"] : [a]);
  const put = React.useCallback((pose: string) => setTracks((T) => { const n = { ...T }; for (const s of sides(active)) { const l = laneOf(s, mode); n[l] = setAt(T[l], tRef.current, pose, undefined, START[mode]); } return n; }), [active, mode]);   // eslint-disable-line react-hooks/exhaustive-deps
  const drop = (g: Gesture) => setTracks((T) => {
    const n = { ...T }; const t0 = tRef.current; const gm: Mode = g.wrist ? "wrist" : "fingers";
    for (const s of sides(active)) { const l = laneOf(s, gm); n[l] = insertRun(T[l], g.keys.map((k) => mk(r3(Math.max(0, t0 + k.dt)), k.pose, { curve: k.curve, d: k.d })), START[gm]); }
    return n;
  });

  React.useEffect(() => {
    const k = (e: KeyboardEvent) => {
      if ((e.target as HTMLElement)?.closest("input,textarea,select,[contenteditable]") || e.ctrlKey || e.metaKey) return;
      const n = +e.key; if (n >= 1 && n <= pins.length) { e.preventDefault(); put(pins[n - 1]); return; }
      if (e.key === "l" || e.key === "L") setActive("left"); else if (e.key === "r" || e.key === "R") setActive("right"); else if (e.key === "b" || e.key === "B") setActive("both");
      else if (e.key === "f" || e.key === "F") setMode("fingers"); else if (e.key === "w" || e.key === "W") setMode("wrist"); else if (e.key === "p" || e.key === "P") setMode("palm");
      else if ((e.key === "Delete" || e.key === "Backspace") && sel) { e.preventDefault(); remove(sel.lane, sel.i); }
    };
    addEventListener("keydown", k); return () => removeEventListener("keydown", k);
  });   // re-bound every render: it reads the selection, the pins and the active hand

  const remove = (lane: HandLane, i: number) => { setTracks((T) => ({ ...T, [lane]: T[lane].filter((_, j) => j !== i) })); setSel(null); };
  const move = (lane: HandLane, i: number, nt: number) => setTracks((T) => {
    const ks = T[lane].map((k) => [...k] as HandKey); const lo = i > 0 ? ks[i - 1][0] + 0.02 : 0, hi = i < ks.length - 1 ? ks[i + 1][0] - 0.02 : len; ks[i][0] = r3(Math.min(Math.max(nt, lo), hi)); return { ...T, [lane]: ks };
  });
  const change = (lane: HandLane, i: number, f: (k: HandKey) => HandKey) => setTracks((T) => ({ ...T, [lane]: dedupe(T[lane].map((k, j) => (j === i ? f(k) : k))) }));
  const apply = async () => {
    try { await api.hands(run, clip, tracks); setSaved(JSON.stringify(tracks)); inv(["hands", run, clip]); } catch (e: any) { toast.error(e.message); }
  };
  const swap = () => {      // the left and right hands were labelled the wrong way round: exchange the two lanes of what is shown (fingers, wrist or palm); Apply keeps it
    const a = laneOf("left", mode), b = laneOf("right", mode); setTracks((T) => ({ ...T, [a]: T[b], [b]: T[a] })); setSel(null); toast.message(`${MODES.find((m) => m.key === mode)!.label}: left and right swapped. Apply to keep it.`);
  };
  const reset = () => { if (q.data) { setTracks({ ...EMPTY, ...q.data.tracks }); setSel(null); } };

  const lane = React.useRef<HTMLDivElement>(null); const drag = React.useRef<{ lane: HandLane; i: number } | null>(null);
  const at = (x: number) => { const b = lane.current!.getBoundingClientRect(); return Math.max(0, Math.min(1, (x - b.left) / b.width)) * len; };
  React.useEffect(() => {
    const mv = (e: PointerEvent) => { if (drag.current) move(drag.current.lane, drag.current.i, at(e.clientX)); }; const up = () => { drag.current = null; };
    addEventListener("pointermove", mv); addEventListener("pointerup", up); return () => { removeEventListener("pointermove", mv); removeEventListener("pointerup", up); };
  });
  const pct = (s: number) => `${len ? Math.max(0, Math.min(100, (s / len) * 100)) : 0}%`;
  const ticks = React.useMemo(() => { const step = len > 40 ? 5 : 2; return Array.from({ length: Math.floor(len / step) + 1 }, (_, i) => i * step); }, [len]);
  const selKey = sel ? tracks[sel.lane][sel.i] : null;
  const current = (l: HandLane) => { const ks = tracks[l]; let p: string | null = ks.length ? ks[0][1] : null; for (const k of ks) if (k[0] <= t + 1e-6) p = k[1]; return p; };
  const gestures = mode === "wrist" ? WRIST_GESTURES : mode === "fingers" ? GESTURES : [];
  const shown = poses.filter((p) => (!catF || p.category === catF) && (!find.trim() || `${p.label} ${p.key} ${p.search} ${p.description}`.toLowerCase().includes(find.trim().toLowerCase())));

  return (
    <div className="panel p-4" data-tour="hands">
      <div className="mb-3 flex flex-wrap items-center gap-2">
        <Hand className="size-4 text-accent" /><h3 className="text-[14px] font-semibold">Hands</h3>
        {name && <span className="min-w-0 break-words text-[13px] font-medium text-ink-2" title={clip}>· {name}</span>}
        {video && <Tip content="The reference video you see here: its own frame rate and length (what the LLM can be shown)."><Badge>video {+video.fps.toFixed(2)} fps · {video.duration.toFixed(1)} s</Badge></Tip>}
        {q.data?.agreement && Object.entries(q.data.agreement).map(([ln, a]) => (
          <Tip key={ln} content={`${a.model ?? "The model"} proposed this lane; your labels keep its choice on ${a.agree} % of the clip. Always guessing your own most common label would score ${a.majority} %.${a.agree > a.majority ? " The model is ahead of that guess." : " The model is not ahead of that guess."}`}>
            <Badge tone={a.agree > a.majority ? "ok" : "warn"}>model vs you · {ln.replace("_", " ")} {a.agree} % <span className="opacity-70">(guess {a.majority} %)</span></Badge>
          </Tip>
        ))}
        {fromLlm && dirty && <Badge tone="accent"><Bot className="size-3" /> LLM labels loaded: check them, edit, then Apply</Badge>}
        {q.data?.meta?.source === "draft" && !dirty && !baking && <Tip content={q.data.meta.how ?? ""}><Badge tone="accent"><Sparkles className="size-3" /> auto draft: check it</Badge></Tip>}
        {baking ? <Badge tone="accent"><Loader2 className="size-3 animate-spin" /> setting the fingers…</Badge>
          : q.data?.status === "failed" ? <Tip content={q.data.error ?? ""}><Badge tone="bad"><TriangleAlert className="size-3" /> failed</Badge></Tip>
          : dirty ? <Badge tone="warn">not applied</Badge> : q.data?.applied ? <Badge tone="ok"><Check className="size-3" /> on the model</Badge> : <Badge>fingers at rest</Badge>}
        <div className="ml-auto flex flex-wrap items-center gap-1.5">
          <div className="flex rounded-lg border border-line-strong p-0.5 text-[12px]">
            {MODES.map((m) => <Tip key={m.key} content={`${m.hint} (${m.key === "fingers" ? "F" : m.key === "wrist" ? "W" : "P"})`}><button onClick={() => setMode(m.key)} className={cn("rounded-md px-2.5 py-1 transition", mode === m.key ? "bg-accent/25 text-ink" : "text-ink-3 hover:text-ink")}>{m.label}</button></Tip>)}
          </div>
          <div className="flex rounded-lg border border-line-strong p-0.5 text-[12px]">
            {(["left", "right", "both"] as Active[]).map((a) => (
              <button key={a} onClick={() => setActive(a)} className={cn("rounded-md px-2.5 py-1 capitalize transition", active === a ? "bg-accent/25 text-ink" : "text-ink-3 hover:text-ink")}>{a === "both" ? "Both (B)" : a === "left" ? "Left (L)" : "Right (R)"}</button>
            ))}
          </div>
          <Tip content={`Swap the left and right hand lanes (${MODES.find((m) => m.key === mode)!.label.toLowerCase()}), if they were labelled the wrong way round`}><Button size="icon" variant="ghost" onClick={swap} disabled={!tracks[laneOf("left", mode)].length && !tracks[laneOf("right", mode)].length} aria-label="Swap left and right"><ArrowLeftRight /></Button></Tip>
          <Tip content="Back to what is saved"><Button size="icon" variant="ghost" onClick={reset} disabled={!dirty}><RotateCcw /></Button></Tip>
          {llmRunning
            ? <Tip content="Stop after the request it is working on"><Button size="sm" variant="ghost" onClick={() => annotate(true)} className="text-accent"><Loader2 className="animate-spin" /> LLM {llm?.chunks ? `${llm.chunk ?? 0}/${llm.chunks}` : "starting"} <Square className="size-3" /></Button></Tip>
            : (
              <Popover open={llmOpen} onOpenChange={setLlmOpen}>
                <PopoverTrigger asChild><Button size="sm" variant="ghost" disabled={baking || len <= 0}><Bot /> Annotate with LLM</Button></PopoverTrigger>
                <PopoverContent align="end" className="w-[340px] p-4">
                  <div className="mb-2 text-[13px] font-medium">Annotate this clip with the LLM</div>
                  <p className="mb-3 text-[11.5px] text-ink-3">A vision-language model watches the clip and proposes every lane (all poses, wrists and palms). Each part lands in the editor unsaved; edit anything, then Apply.</p>
                  <div className="mb-3 rounded-lg bg-white/5 px-3 py-2 text-[12px]">Reference video: <b>{video ? `${+video.fps.toFixed(2)} fps` : "unknown"}</b>{video && <> · {video.duration.toFixed(1)} s · {Math.round(video.duration * video.fps)} frames</>}</div>
                  {models.length > 1 && <><div className="mb-1 text-[11.5px] text-ink-3">Model</div><Segmented value={modelKey} onValueChange={(v) => setOpt({ model: v })} options={models.map((m) => ({ value: m.key, label: m.label }))} /><div className="mb-3" /></>}
                  <div className="mb-1 text-[11.5px] text-ink-3">Frames per second sent to the model</div>
                  <Segmented value={String(sendFpsShown)} onValueChange={(v) => setOpt({ fps: +v })} options={fpsChoices.map((f) => ({ value: String(f), label: f === native ? `${+f.toFixed(1)} (all)` : String(f) }))} />
                  <div className="mt-3 mb-1 text-[11.5px] text-ink-3">Thinking before it answers</div>
                  <Segmented value={llmOpt.thinking ? "on" : "off"} onValueChange={(v) => setOpt({ thinking: v === "on" })} options={[{ value: "on", label: "On" }, { value: "off", label: "Off" }]} />
                  <div className="mt-3 rounded-lg border border-line-strong px-3 py-2 text-[12px]">
                    {video && tm ? <>About <b>{estText(estSec)}</b> · {requests} request{requests > 1 ? "s" : ""} of up to {chunkFrames} frames ({+(chunkFrames / sendFpsShown).toFixed(1)} s of video each)
                      <div className="mt-0.5 text-[11px] text-ink-3">{tm.n ? `from ${tm.n} earlier run${tm.n > 1 ? "s" : ""} (${Math.round(tm.s)} s per request)` : `a guess (${Math.round(tm.s)} s per request) until one has run`}</div></> : "No reference video to look at."}
                  </div>
                  <Button variant="primary" size="sm" className="mt-3 w-full" onClick={() => annotate(false)} disabled={!video}><Bot /> Start</Button>
                </PopoverContent>
              </Popover>
            )}
          <Button variant="primary" size="sm" onClick={apply} disabled={!dirty || baking || len <= 0}>{baking ? <Loader2 className="animate-spin" /> : <Check />} Apply to the model</Button>
        </div>
      </div>

      <div className="mb-3 flex flex-wrap items-stretch gap-1.5">
        {pins.map((k, i) => (
          <button key={k} onClick={() => put(k)} title={byKey[k]?.description} className="group flex w-[88px] flex-col overflow-hidden rounded-lg border bg-black/20 text-left transition hover:bg-white/5" style={{ borderColor: `${colorOf(k)}66` }}>
            {byKey[k]?.image ? <img src={byKey[k].image!} className="aspect-[2/1] w-full bg-[#b0b0b4] object-cover" /> : <div className="grid aspect-[2/1] w-full place-items-center bg-white/5 text-[18px]" style={{ color: colorOf(k) }}>{PALM_GLYPH[k] ?? "•"}</div>}
            <span className="flex items-center gap-1 px-1.5 py-1 text-[11px] text-ink-2"><span className="truncate">{labelOf(k)}</span><kbd className="ml-auto rounded bg-white/8 px-1 font-mono text-[9.5px] text-ink-3">{i + 1}</kbd></span>
          </button>
        ))}
        <Popover>
          <PopoverTrigger asChild><button className="flex w-[88px] flex-col items-center justify-center gap-1 rounded-lg border border-dashed border-line-strong text-[11.5px] text-ink-2 transition hover:border-accent/50 hover:text-ink"><Search className="size-4" />All {poses.length || 48} {mode === "fingers" ? "poses" : mode === "wrist" ? "bends" : "directions"}</button></PopoverTrigger>
          <PopoverContent className="w-[min(720px,92vw)] p-3" align="start">
            <div className="mb-2 flex items-center gap-2">
              <div className="relative flex-1"><Search className="absolute top-2 left-2.5 size-4 text-ink-3" /><input autoFocus value={find} onChange={(e) => setFind(e.target.value)} placeholder={mode === "fingers" ? "Search: fist, claw, snap, peace, rock…" : mode === "wrist" ? "Search: down, up, push, ulnar…" : "Search: down, up, forward, in, out…"} className="h-8 w-full rounded-lg border border-line-strong bg-black/30 pr-2 pl-8 text-[13px] outline-none focus:border-accent/60" /></div>
              <span className="text-[11px] whitespace-nowrap text-ink-3">sets the {mode} of {active === "both" ? "both hands" : `the ${active} hand`} at the playhead · ★ pins to keys 1-9</span>
            </div>
            <div className="mb-2 flex flex-wrap gap-1">
              <button onClick={() => setCatF(null)} className={cn("rounded-md px-2 py-1 text-[11.5px]", !catF ? "bg-white/12 text-ink" : "text-ink-3 hover:text-ink")}>All</button>
              {CATS.map((c) => <button key={c} onClick={() => setCatF(catF === c ? null : c)} className={cn("flex items-center gap-1 rounded-md px-2 py-1 text-[11.5px]", catF === c ? "bg-white/12 text-ink" : "text-ink-3 hover:text-ink")}><span className="size-2 rounded-sm" style={{ background: CAT_COLOR[c] }} />{c}</button>)}
            </div>
            <div className="grid max-h-[52vh] grid-cols-2 gap-2 overflow-y-auto pr-1 sm:grid-cols-3 md:grid-cols-4">
              {shown.map((p) => <PoseCard key={p.key} p={p} onPick={() => put(p.key)} pinned={pins.includes(p.key)} onPin={() => togglePin(p.key)} />)}
              {!shown.length && <div className="col-span-full py-8 text-center text-[13px] text-ink-3">Nothing matches.</div>}
            </div>
          </PopoverContent>
        </Popover>
        <Popover>
          <PopoverTrigger asChild><button className="flex w-[88px] flex-col items-center justify-center gap-1 rounded-lg border border-dashed border-line-strong text-[11.5px] text-ink-2 transition hover:border-accent/50 hover:text-ink"><Sparkles className="size-4" />Gestures</button></PopoverTrigger>
          <PopoverContent className="w-[min(420px,92vw)] p-2" align="start">
            <div className="mb-1 px-1 text-[11px] text-ink-3">Dropped at the playhead for {active === "both" ? "both hands" : active}; the playhead is the moment of the hit.</div>
            {!gestures.length && <div className="px-2 py-3 text-[12px] text-ink-3">No gestures for the palm direction: set a direction at the moment it should turn.</div>}
            {gestures.map((g) => (
              <button key={g.key} onClick={() => drop(g)} className="flex w-full items-start gap-2 rounded-lg px-2 py-2 text-left transition hover:bg-white/6"><Sparkles className="mt-0.5 size-3.5 shrink-0 text-accent" /><span><b className="block text-[13px] font-medium">{g.label}</b><span className="text-[11.5px] text-ink-3">{g.text}</span></span></button>
            ))}
          </PopoverContent>
        </Popover>
      </div>

      <div className="grid grid-cols-[64px_1fr] gap-x-2 gap-y-1.5">
        <div className="flex h-9 flex-col items-start justify-center px-2 text-[11px] text-ink-3"><span>Sound</span><span className="text-[9px] opacity-70">{wave && wave !== "none" ? `${wave.onsets.length} hits` : ""}</span></div>
        <WaveStrip wave={wave ?? null} len={len} t={t} seek={seek} />
        <div />
        <div ref={lane} className="relative h-5 cursor-pointer select-none" onPointerDown={(e) => seek(at(e.clientX))}>
          {ticks.map((s) => <span key={s} className="absolute top-0 -translate-x-1/2 font-mono text-[10px] text-ink-3" style={{ left: pct(s) }}>{duration(s)}</span>)}
        </div>
        {(["fingers", "wrist", "palm"] as Mode[]).flatMap((m) => (["left", "right"] as Side[]).map((side) => {
          const ln = laneOf(side, m), ks = tracks[ln]; const tall = m === "fingers"; const on0 = mode === m && sides(active).includes(side);
          return (
            <React.Fragment key={ln}>
              <button onClick={() => { setActive(side); setMode(m); }} className={cn("flex flex-col items-start justify-center rounded-lg px-2 text-left text-[12px] capitalize transition", tall ? "h-11" : "h-8", on0 ? "bg-accent/12 text-ink" : "text-ink-3 hover:text-ink")}>
                <span className="leading-none">{side}{m !== "fingers" && <span className="ml-1 text-[10px] normal-case opacity-70">{m}</span>}</span>
                {tall && <span className="max-w-full truncate text-[10px] normal-case" style={{ color: colorOf(current(ln) ?? "") }}>{current(ln) ? labelOf(current(ln)!) : "rest"}</span>}
              </button>
              <div className={cn("relative select-none overflow-hidden rounded-lg border bg-black/30", tall ? "h-11" : "h-8", on0 ? "border-accent/40" : "border-line")} onPointerDown={(e) => { if (e.target === e.currentTarget) { seek(at(e.clientX)); setActive(side); setMode(m); setSel(null); } }}>
                {!ks.length && <div className="pointer-events-none absolute inset-0 grid place-items-center text-[11px] text-ink-3">{m === "fingers" ? "no poses: press a number or open the picker to set one at the playhead" : m === "wrist" ? "wrist as the clip has it" : "palm direction as the clip has it"}</div>}
                {ks.map((k, i) => {
                  const from = i === 0 ? 0 : k[0], to = i < ks.length - 1 ? ks[i + 1][0] : len; const on = sel?.lane === ln && sel.i === i; const o = optsOf(k);
                  return (
                    <div key={i} onPointerDown={(e) => { e.stopPropagation(); setSel({ lane: ln, i }); setActive(side); setMode(m); seek(Math.max(0, k[0])); }} title={`${labelOf(k[1])} from ${duration(k[0])}${o.curve ? ` · ${o.curve}` : ""}`}
                      className={cn("absolute inset-y-0 flex cursor-pointer items-center overflow-hidden border-l px-1 text-[10.5px] font-medium text-black/80", on && "ring-2 ring-white/70 ring-inset")}
                      style={{ left: pct(from), width: `calc(${pct(to)} - ${pct(from)})`, background: `${colorOf(k[1])}cc`, borderColor: "rgba(0,0,0,.35)" }}>
                      <span className="truncate">{labelOf(k[1])}</span>
                      {o.curve && o.curve !== "smooth" && <span className="absolute right-0.5 bottom-0 text-[8px] uppercase opacity-70">{o.curve === "hold" ? "cut" : o.curve}</span>}
                      {i > 0 && <span onPointerDown={(e) => { e.stopPropagation(); drag.current = { lane: ln, i }; setSel({ lane: ln, i }); }} className="absolute inset-y-0 left-0 w-1.5 cursor-ew-resize" />}
                    </div>
                  );
                })}
                <div className="pointer-events-none absolute inset-y-0 w-0.5 bg-white" style={{ left: pct(t) }} />
              </div>
            </React.Fragment>
          );
        }))}
      </div>

      <div className="mt-3 flex min-h-8 flex-wrap items-center gap-2 text-[12px] text-ink-3">
        {sel && selKey ? (
          <>
            <span className="text-ink-2 capitalize">{sel.lane.replace("_", " ")}</span> from <span className="font-mono text-ink-2">{duration(selKey[0])}</span>:
            <select value={selKey[1]} onChange={(e) => change(sel.lane, sel.i, (k) => mk(k[0], e.target.value, optsOf(k)))} className="h-7 max-w-44 rounded-md border border-line-strong bg-raised px-2 text-ink">
              {[...new Set(all.filter((p) => (p.kind ?? "pose") === (sel.lane.endsWith("_wrist") ? "wrist" : sel.lane.endsWith("_palm") ? "palm" : "pose")).map((p) => p.category))].map((c) => <optgroup key={c} label={c}>{all.filter((p) => p.category === c).map((p) => <option key={p.key} value={p.key}>{p.label}</option>)}</optgroup>)}
            </select>
            <span className="ml-1">arrives</span>
            <select value={optsOf(selKey).curve ?? ""} onChange={(e) => change(sel.lane, sel.i, (k) => mk(k[0], k[1], { ...optsOf(k), curve: (e.target.value || undefined) as HandCurve | undefined }))} className="h-7 rounded-md border border-line-strong bg-raised px-2 text-ink" title={CURVES.find((c) => c.key === (optsOf(selKey).curve ?? ""))?.hint}>
              {CURVES.map((c) => <option key={c.key} value={c.key}>{c.label} · {c.hint}</option>)}
            </select>
            <input type="number" min={5} max={3000} step={5} placeholder="ms" value={optsOf(selKey).d ? Math.round(optsOf(selKey).d! * 1000) : ""} onChange={(e) => change(sel.lane, sel.i, (k) => mk(k[0], k[1], { ...optsOf(k), d: e.target.value ? Math.max(0.005, +e.target.value / 1000) : undefined }))} className="h-7 w-16 rounded-md border border-line-strong bg-raised px-2 text-ink" title="Length of the change in milliseconds (empty = automatic)" />
            <Button size="sm" variant="ghost" onClick={() => remove(sel.lane, sel.i)}><Trash2 /> Remove</Button>
          </>
        ) : <span>Play the video and press <kbd className="rounded bg-white/8 px-1 font-mono text-[10px]">1</kbd>–<kbd className="rounded bg-white/8 px-1 font-mono text-[10px]">9</kbd> at the moment a hand changes; <kbd className="rounded bg-white/8 px-1 font-mono text-[10px]">F</kbd> fingers, <kbd className="rounded bg-white/8 px-1 font-mono text-[10px]">W</kbd> wrist, <kbd className="rounded bg-white/8 px-1 font-mono text-[10px]">P</kbd> palm direction. Click a block to change its pose or transition, or remove it; drag its left edge to move it.</span>}
      </div>
    </div>
  );
}
