import * as React from "react";
import { toast } from "sonner";
import { Check, Hand, Loader2, RotateCcw, Search, Sparkles, Star, Trash2, TriangleAlert } from "lucide-react";
import { api, useHandPoses, useHands, useInvalidate } from "@/lib/api";
import type { HandCurve, HandKey, HandKeyOpts, HandPose, HandTracks } from "@/lib/types";
import { Badge, Button, Popover, PopoverContent, PopoverTrigger, Tip } from "@/components/ui";
import { cn, duration } from "@/lib/utils";
import { GESTURES, type Gesture } from "./handGestures";

/** The hand timeline of a dance: one lane per hand, a block per pose, under the video and the character on their shared clock. Press 1-9 to give the chosen hand(s) a pinned pose from the playhead on
 *  (the first pose of a lane holds from the start), pick any of the 48 library poses from the picker, or drop a quick gesture (snap, flick, pulse ...) at the playhead. Drag a block's left edge to move
 *  the change; each change has its own transition (smooth, quick, snap, linear, cut). Apply bakes the poses into a copy of the clip (the fingers of the 3D model then follow). */
const CAT_COLOR: Record<string, string> = { Neutral: "#5b8cff", Curved: "#2dd4f2", Closed: "#f87171", Pointing: "#34d399", Signs: "#a78bfa", "Pinch & snap": "#fbbf24", "Finger wave": "#f472b6" };
const CATS = Object.keys(CAT_COLOR);
const DEFAULT_PINS = ["open", "relaxed", "fist", "point", "grip", "thumbs_up", "pinch", "claw", "spread"];
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
function setAt(keys: HandKey[], t: number, pose: string, o?: HandKeyOpts): HandKey[] {
  const ks = sorted(keys); t = r3(Math.max(0, t));
  const near = ks.findIndex((k) => Math.abs(k[0] - t) < 0.06);
  if (near >= 0) { ks[near] = mk(ks[near][0], pose, o ?? optsOf(ks[near])); return dedupe(ks); }
  if (!ks.length && t > 0.15) ks.push([0, "relaxed"]);
  ks.push(mk(t, pose, o)); return dedupe(ks.sort((a, b) => a[0] - b[0]));
}
/** A run of keys (a gesture) dropped in: whatever the hand had over its span is replaced. */
function insertRun(keys: HandKey[], run: HandKey[]): HandKey[] {
  const lo = Math.min(...run.map((k) => k[0])) - 0.02, hi = Math.max(...run.map((k) => k[0])) + 0.02; let ks = sorted(keys).filter((k) => k[0] < lo || k[0] > hi);
  if (!ks.length && lo > 0.15) ks.push([0, "relaxed"]);
  return dedupe([...ks, ...run].sort((a, b) => a[0] - b[0]));
}

function PoseCard({ p, onPick, pinned, onPin }: { p: HandPose; onPick: () => void; pinned: boolean; onPin: () => void }) {
  return (
    <div className="group relative overflow-hidden rounded-lg border border-line bg-black/25 transition hover:border-white/25" title={p.description}>
      <button onClick={onPick} className="block w-full text-left">
        <img src={p.image} loading="lazy" className="aspect-[2/1] w-full bg-[#b0b0b4] object-cover" />
        <div className="flex items-center gap-1.5 px-2 py-1.5 text-[11.5px]"><span className="size-2 shrink-0 rounded-sm" style={{ background: CAT_COLOR[p.category] }} /><span className="truncate font-medium text-ink">{p.label}</span></div>
      </button>
      <button onClick={onPin} className={cn("absolute top-1 right-1 grid size-6 place-items-center rounded-md bg-black/50 backdrop-blur transition", pinned ? "text-warn" : "text-ink-3 opacity-0 group-hover:opacity-100")} title={pinned ? "Unpin" : "Pin to keys 1-9"}><Star className={cn("size-3.5", pinned && "fill-current")} /></button>
    </div>
  );
}

export function HandTimeline({ run, clip, t, len, seek }: { run: string; clip: string; t: number; len: number; seek: (s: number) => void }) {
  const q = useHands(run, clip); const inv = useInvalidate(); const cat = useHandPoses();
  const poses = cat.data ?? []; const byKey = React.useMemo(() => Object.fromEntries(poses.map((p) => [p.key, p])), [poses]);
  const colorOf = (k: string) => CAT_COLOR[byKey[k]?.category] ?? "#7b8494"; const labelOf = (k: string) => byKey[k]?.label ?? k;
  const [tracks, setTracks] = React.useState<HandTracks>({ left: [], right: [] });
  const [saved, setSaved] = React.useState(JSON.stringify({ left: [], right: [] }));
  const [active, setActive] = React.useState<Active>("both");
  const [sel, setSel] = React.useState<{ side: Side; i: number } | null>(null);
  const [pins, setPins] = React.useState<string[]>(() => { try { const v = JSON.parse(localStorage.getItem("homunculus_hand_pins") || "null"); return Array.isArray(v) && v.length ? v.slice(0, 9) : DEFAULT_PINS; } catch { return DEFAULT_PINS; } });
  const [find, setFind] = React.useState(""); const [catF, setCatF] = React.useState<string | null>(null);
  const tRef = React.useRef(t); tRef.current = t;
  const was = React.useRef<string | undefined>(undefined);
  const savePins = (p: string[]) => { setPins(p); try { localStorage.setItem("homunculus_hand_pins", JSON.stringify(p)); } catch { /* private mode */ } };
  const togglePin = (k: string) => savePins(pins.includes(k) ? pins.filter((x) => x !== k) : pins.length >= 9 ? [...pins.slice(0, 8), k] : [...pins, k]);

  // the saved timeline arrives (or the clip changes): start from it; later refetches while baking must not overwrite what is being edited
  React.useEffect(() => { if (q.data) { setTracks(q.data.tracks); setSaved(JSON.stringify(q.data.tracks)); setSel(null); } }, [clip, q.data?.updated]);   // eslint-disable-line react-hooks/exhaustive-deps
  React.useEffect(() => {   // a bake that has just finished: the run's clip now points at the file with the fingers
    const s = q.data?.status; if (was.current === "running" && s && s !== "running") { inv(["run", run]); s === "done" ? toast.success("The fingers are set on the model") : toast.error("Could not set the fingers: " + (q.data?.error ?? "")); }
    was.current = s;
  }, [q.data?.status]);   // eslint-disable-line react-hooks/exhaustive-deps

  const dirty = JSON.stringify(tracks) !== saved; const baking = q.data?.status === "running";
  const sides = (a: Active): Side[] => (a === "both" ? ["left", "right"] : [a]);
  const put = React.useCallback((pose: string) => setTracks((T) => { const n = { ...T }; for (const s of sides(active)) n[s] = setAt(T[s], tRef.current, pose); return n; }), [active]);   // eslint-disable-line react-hooks/exhaustive-deps
  const drop = (g: Gesture) => setTracks((T) => {
    const n = { ...T }; const t0 = tRef.current;
    for (const s of sides(active)) n[s] = insertRun(T[s], g.keys.map((k) => mk(r3(Math.max(0, t0 + k.dt)), k.pose, { curve: k.curve, d: k.d })));
    return n;
  });

  React.useEffect(() => {
    const k = (e: KeyboardEvent) => {
      if ((e.target as HTMLElement)?.closest("input,textarea,select,[contenteditable]") || e.ctrlKey || e.metaKey) return;
      const n = +e.key; if (n >= 1 && n <= pins.length) { e.preventDefault(); put(pins[n - 1]); return; }
      if (e.key === "l" || e.key === "L") setActive("left"); else if (e.key === "r" || e.key === "R") setActive("right"); else if (e.key === "b" || e.key === "B") setActive("both");
      else if ((e.key === "Delete" || e.key === "Backspace") && sel) { e.preventDefault(); remove(sel.side, sel.i); }
    };
    addEventListener("keydown", k); return () => removeEventListener("keydown", k);
  });   // re-bound every render: it reads the selection, the pins and the active hand

  const remove = (side: Side, i: number) => { setTracks((T) => ({ ...T, [side]: T[side].filter((_, j) => j !== i) })); setSel(null); };
  const move = (side: Side, i: number, nt: number) => setTracks((T) => {
    const ks = T[side].map((k) => [...k] as HandKey); const lo = i > 0 ? ks[i - 1][0] + 0.02 : 0, hi = i < ks.length - 1 ? ks[i + 1][0] - 0.02 : len; ks[i][0] = r3(Math.min(Math.max(nt, lo), hi)); return { ...T, [side]: ks };
  });
  const change = (side: Side, i: number, f: (k: HandKey) => HandKey) => setTracks((T) => ({ ...T, [side]: dedupe(T[side].map((k, j) => (j === i ? f(k) : k))) }));
  const apply = async () => {
    try { await api.hands(run, clip, tracks); setSaved(JSON.stringify(tracks)); inv(["hands", run, clip]); } catch (e: any) { toast.error(e.message); }
  };
  const reset = () => { if (q.data) { setTracks(q.data.tracks); setSel(null); } };

  const lane = React.useRef<HTMLDivElement>(null); const drag = React.useRef<{ side: Side; i: number } | null>(null);
  const at = (x: number) => { const b = lane.current!.getBoundingClientRect(); return Math.max(0, Math.min(1, (x - b.left) / b.width)) * len; };
  React.useEffect(() => {
    const mv = (e: PointerEvent) => { if (drag.current) move(drag.current.side, drag.current.i, at(e.clientX)); }; const up = () => { drag.current = null; };
    addEventListener("pointermove", mv); addEventListener("pointerup", up); return () => { removeEventListener("pointermove", mv); removeEventListener("pointerup", up); };
  });
  const pct = (s: number) => `${len ? Math.max(0, Math.min(100, (s / len) * 100)) : 0}%`;
  const ticks = React.useMemo(() => { const step = len > 40 ? 5 : 2; return Array.from({ length: Math.floor(len / step) + 1 }, (_, i) => i * step); }, [len]);
  const selKey = sel ? tracks[sel.side][sel.i] : null;
  const current = (s: Side) => { const ks = tracks[s]; let p: string | null = ks.length ? ks[0][1] : null; for (const k of ks) if (k[0] <= t + 1e-6) p = k[1]; return p; };
  const shown = poses.filter((p) => (!catF || p.category === catF) && (!find.trim() || `${p.label} ${p.key} ${p.search} ${p.description}`.toLowerCase().includes(find.trim().toLowerCase())));

  return (
    <div className="panel p-4" data-tour="hands">
      <div className="mb-3 flex flex-wrap items-center gap-2">
        <Hand className="size-4 text-accent" /><h3 className="text-[14px] font-semibold">Hands</h3>
        {baking ? <Badge tone="accent"><Loader2 className="size-3 animate-spin" /> setting the fingers…</Badge>
          : q.data?.status === "failed" ? <Tip content={q.data.error ?? ""}><Badge tone="bad"><TriangleAlert className="size-3" /> failed</Badge></Tip>
          : dirty ? <Badge tone="warn">not applied</Badge> : q.data?.applied ? <Badge tone="ok"><Check className="size-3" /> on the model</Badge> : <Badge>fingers at rest</Badge>}
        <div className="ml-auto flex items-center gap-1.5">
          <div className="flex rounded-lg border border-line-strong p-0.5 text-[12px]">
            {(["left", "right", "both"] as Active[]).map((a) => (
              <button key={a} onClick={() => setActive(a)} className={cn("rounded-md px-2.5 py-1 capitalize transition", active === a ? "bg-accent/25 text-ink" : "text-ink-3 hover:text-ink")}>{a === "both" ? "Both (B)" : a === "left" ? "Left (L)" : "Right (R)"}</button>
            ))}
          </div>
          <Tip content="Back to what is saved"><Button size="icon" variant="ghost" onClick={reset} disabled={!dirty}><RotateCcw /></Button></Tip>
          <Button variant="primary" size="sm" onClick={apply} disabled={!dirty || baking || len <= 0}>{baking ? <Loader2 className="animate-spin" /> : <Check />} Apply to the model</Button>
        </div>
      </div>

      <div className="mb-3 flex flex-wrap items-stretch gap-1.5">
        {pins.map((k, i) => (
          <button key={k} onClick={() => put(k)} title={byKey[k]?.description} className="group flex w-[88px] flex-col overflow-hidden rounded-lg border bg-black/20 text-left transition hover:bg-white/5" style={{ borderColor: `${colorOf(k)}66` }}>
            {byKey[k] ? <img src={byKey[k].image} className="aspect-[2/1] w-full bg-[#b0b0b4] object-cover" /> : <div className="aspect-[2/1] w-full bg-white/5" />}
            <span className="flex items-center gap-1 px-1.5 py-1 text-[11px] text-ink-2"><span className="truncate">{labelOf(k)}</span><kbd className="ml-auto rounded bg-white/8 px-1 font-mono text-[9.5px] text-ink-3">{i + 1}</kbd></span>
          </button>
        ))}
        <Popover>
          <PopoverTrigger asChild><button className="flex w-[88px] flex-col items-center justify-center gap-1 rounded-lg border border-dashed border-line-strong text-[11.5px] text-ink-2 transition hover:border-accent/50 hover:text-ink"><Search className="size-4" />All {poses.length || 48} poses</button></PopoverTrigger>
          <PopoverContent className="w-[min(720px,92vw)] p-3" align="start">
            <div className="mb-2 flex items-center gap-2">
              <div className="relative flex-1"><Search className="absolute top-2 left-2.5 size-4 text-ink-3" /><input autoFocus value={find} onChange={(e) => setFind(e.target.value)} placeholder="Search: fist, claw, snap, peace, rock…" className="h-8 w-full rounded-lg border border-line-strong bg-black/30 pr-2 pl-8 text-[13px] outline-none focus:border-accent/60" /></div>
              <span className="text-[11px] whitespace-nowrap text-ink-3">sets {active === "both" ? "both hands" : active} at the playhead · ★ pins to keys 1-9</span>
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
            {GESTURES.map((g) => (
              <button key={g.key} onClick={() => drop(g)} className="flex w-full items-start gap-2 rounded-lg px-2 py-2 text-left transition hover:bg-white/6"><Sparkles className="mt-0.5 size-3.5 shrink-0 text-accent" /><span><b className="block text-[13px] font-medium">{g.label}</b><span className="text-[11.5px] text-ink-3">{g.text}</span></span></button>
            ))}
          </PopoverContent>
        </Popover>
      </div>

      <div className="grid grid-cols-[64px_1fr] gap-x-2 gap-y-1.5">
        <div />
        <div ref={lane} className="relative h-5 cursor-pointer select-none" onPointerDown={(e) => seek(at(e.clientX))}>
          {ticks.map((s) => <span key={s} className="absolute top-0 -translate-x-1/2 font-mono text-[10px] text-ink-3" style={{ left: pct(s) }}>{duration(s)}</span>)}
        </div>
        {(["left", "right"] as Side[]).map((side) => {
          const ks = tracks[side];
          return (
            <React.Fragment key={side}>
              <button onClick={() => setActive(side)} className={cn("flex h-11 flex-col items-start justify-center rounded-lg px-2 text-left text-[12px] capitalize transition", sides(active).includes(side) ? "bg-accent/12 text-ink" : "text-ink-3 hover:text-ink")}>
                {side}<span className="max-w-full truncate text-[10px] normal-case" style={{ color: colorOf(current(side) ?? "") }}>{current(side) ? labelOf(current(side)!) : "rest"}</span>
              </button>
              <div className="relative h-11 select-none overflow-hidden rounded-lg border border-line bg-black/30" onPointerDown={(e) => { if (e.target === e.currentTarget) { seek(at(e.clientX)); setActive(side); setSel(null); } }}>
                {!ks.length && <div className="pointer-events-none absolute inset-0 grid place-items-center text-[11px] text-ink-3">no poses: press a number or open the picker to set one at the playhead</div>}
                {ks.map((k, i) => {
                  const from = i === 0 ? 0 : k[0], to = i < ks.length - 1 ? ks[i + 1][0] : len; const on = sel?.side === side && sel.i === i; const o = optsOf(k);
                  return (
                    <div key={i} onPointerDown={(e) => { e.stopPropagation(); setSel({ side, i }); setActive(side); seek(Math.max(0, k[0])); }} title={`${labelOf(k[1])} from ${duration(k[0])}${o.curve ? ` · ${o.curve}` : ""}`}
                      className={cn("absolute inset-y-0 flex cursor-pointer items-center overflow-hidden border-l px-1 text-[10.5px] font-medium text-black/80", on && "ring-2 ring-white/70 ring-inset")}
                      style={{ left: pct(from), width: `calc(${pct(to)} - ${pct(from)})`, background: `${colorOf(k[1])}cc`, borderColor: "rgba(0,0,0,.35)" }}>
                      <span className="truncate">{labelOf(k[1])}</span>
                      {o.curve && o.curve !== "smooth" && <span className="absolute right-0.5 bottom-0 text-[8px] uppercase opacity-70">{o.curve === "hold" ? "cut" : o.curve}</span>}
                      {i > 0 && <span onPointerDown={(e) => { e.stopPropagation(); drag.current = { side, i }; setSel({ side, i }); }} className="absolute inset-y-0 left-0 w-1.5 cursor-ew-resize" />}
                    </div>
                  );
                })}
                <div className="pointer-events-none absolute inset-y-0 w-0.5 bg-white" style={{ left: pct(t) }} />
              </div>
            </React.Fragment>
          );
        })}
      </div>

      <div className="mt-3 flex min-h-8 flex-wrap items-center gap-2 text-[12px] text-ink-3">
        {sel && selKey ? (
          <>
            <span className="capitalize text-ink-2">{sel.side}</span> from <span className="font-mono text-ink-2">{duration(selKey[0])}</span>:
            <select value={selKey[1]} onChange={(e) => change(sel.side, sel.i, (k) => mk(k[0], e.target.value, optsOf(k)))} className="h-7 max-w-44 rounded-md border border-line-strong bg-raised px-2 text-ink">
              {CATS.map((c) => <optgroup key={c} label={c}>{poses.filter((p) => p.category === c).map((p) => <option key={p.key} value={p.key}>{p.label}</option>)}</optgroup>)}
            </select>
            <span className="ml-1">arrives</span>
            <select value={optsOf(selKey).curve ?? ""} onChange={(e) => change(sel.side, sel.i, (k) => mk(k[0], k[1], { ...optsOf(k), curve: (e.target.value || undefined) as HandCurve | undefined }))} className="h-7 rounded-md border border-line-strong bg-raised px-2 text-ink" title={CURVES.find((c) => c.key === (optsOf(selKey).curve ?? ""))?.hint}>
              {CURVES.map((c) => <option key={c.key} value={c.key}>{c.label} · {c.hint}</option>)}
            </select>
            <input type="number" min={5} max={3000} step={5} placeholder="ms" value={optsOf(selKey).d ? Math.round(optsOf(selKey).d! * 1000) : ""} onChange={(e) => change(sel.side, sel.i, (k) => mk(k[0], k[1], { ...optsOf(k), d: e.target.value ? Math.max(0.005, +e.target.value / 1000) : undefined }))} className="h-7 w-16 rounded-md border border-line-strong bg-raised px-2 text-ink" title="Length of the change in milliseconds (empty = automatic)" />
            <Button size="sm" variant="ghost" onClick={() => remove(sel.side, sel.i)}><Trash2 /> Remove</Button>
          </>
        ) : <span>Play the video and press <kbd className="rounded bg-white/8 px-1 font-mono text-[10px]">1</kbd>–<kbd className="rounded bg-white/8 px-1 font-mono text-[10px]">9</kbd> at the moment a hand changes. Click a block to change its pose or transition, or remove it; drag its left edge to move it.</span>}
      </div>
    </div>
  );
}
