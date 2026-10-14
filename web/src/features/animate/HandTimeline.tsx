import * as React from "react";
import { toast } from "sonner";
import { Check, Hand, Loader2, RotateCcw, Trash2, TriangleAlert } from "lucide-react";
import { api, useHands, useInvalidate } from "@/lib/api";
import type { HandKey, HandTracks } from "@/lib/types";
import { Badge, Button, Tip } from "@/components/ui";
import { cn, duration } from "@/lib/utils";

/** The hand timeline of a dance: one lane per hand, a block per pose, under the video and the character on their shared clock. Press a number to give the chosen hand(s) that pose from the
 *  playhead on (the first pose of a lane holds from the start); drag a block's left edge to move the change; Apply bakes the poses into a copy of the clip (the fingers of the 3D model then follow). */
const POSES: { key: string; label: string; color: string }[] = [
  { key: "open", label: "Open", color: "#5b8cff" }, { key: "relaxed", label: "Relaxed", color: "#7b8494" }, { key: "fist", label: "Fist", color: "#f87171" },
  { key: "grip", label: "Grip", color: "#fbbf24" }, { key: "point", label: "Point", color: "#34d399" }, { key: "thumbs_up", label: "Thumbs up", color: "#a78bfa" },
  { key: "pinch", label: "Pinch", color: "#2dd4f2" },
];
const COLOR = Object.fromEntries(POSES.map((p) => [p.key, p.color])); const LABEL = Object.fromEntries(POSES.map((p) => [p.key, p.label]));
type Side = "left" | "right"; type Active = Side | "both";
const r3 = (x: number) => Math.round(x * 1000) / 1000;

/** The timeline with `pose` from time t on: a key within 60 ms is changed, an empty lane gets a relaxed start first, and a key that repeats the pose before it is not added. */
function setAt(keys: HandKey[], t: number, pose: string): HandKey[] {
  const ks = keys.map((k) => [...k] as HandKey).sort((a, b) => a[0] - b[0]); t = r3(Math.max(0, t));
  const near = ks.findIndex((k) => Math.abs(k[0] - t) < 0.06);
  if (near >= 0) { ks[near][1] = pose; return dedupe(ks); }
  if (!ks.length && t > 0.15) ks.push([0, "relaxed"]);
  ks.push([t, pose]); ks.sort((a, b) => a[0] - b[0]); return dedupe(ks);
}
function dedupe(ks: HandKey[]): HandKey[] { return ks.filter((k, i) => i === 0 || k[1] !== ks[i - 1][1]); }

export function HandTimeline({ run, clip, t, len, seek }: { run: string; clip: string; t: number; len: number; seek: (s: number) => void }) {
  const q = useHands(run, clip); const inv = useInvalidate();
  const [tracks, setTracks] = React.useState<HandTracks>({ left: [], right: [] });
  const [saved, setSaved] = React.useState(JSON.stringify({ left: [], right: [] }));
  const [active, setActive] = React.useState<Active>("both");
  const [sel, setSel] = React.useState<{ side: Side; i: number } | null>(null);
  const tRef = React.useRef(t); tRef.current = t;
  const was = React.useRef<string | undefined>(undefined);

  // the saved timeline arrives (or the clip changes): start from it; later refetches while baking must not overwrite what is being edited
  React.useEffect(() => { if (q.data) { setTracks(q.data.tracks); setSaved(JSON.stringify(q.data.tracks)); setSel(null); } }, [clip, q.data?.updated]);   // eslint-disable-line react-hooks/exhaustive-deps
  React.useEffect(() => {   // a bake that has just finished: the run's clip now points at the file with the fingers
    const s = q.data?.status; if (was.current === "running" && s && s !== "running") { inv(["run", run]); s === "done" ? toast.success("The fingers are set on the model") : toast.error("Could not set the fingers: " + (q.data?.error ?? "")); }
    was.current = s;
  }, [q.data?.status]);   // eslint-disable-line react-hooks/exhaustive-deps

  const dirty = JSON.stringify(tracks) !== saved; const baking = q.data?.status === "running";
  const sides = (a: Active): Side[] => (a === "both" ? ["left", "right"] : [a]);
  const put = React.useCallback((pose: string) => setTracks((T) => { const n = { ...T }; for (const s of sides(active)) n[s] = setAt(T[s], tRef.current, pose); return n; }), [active]);   // eslint-disable-line react-hooks/exhaustive-deps

  React.useEffect(() => {
    const k = (e: KeyboardEvent) => {
      if ((e.target as HTMLElement)?.closest("input,textarea,select,[contenteditable]") || e.ctrlKey || e.metaKey) return;
      const n = +e.key; if (n >= 1 && n <= POSES.length) { e.preventDefault(); put(POSES[n - 1].key); return; }
      if (e.key === "l" || e.key === "L") setActive("left"); else if (e.key === "r" || e.key === "R") setActive("right"); else if (e.key === "b" || e.key === "B") setActive("both");
      else if ((e.key === "Delete" || e.key === "Backspace") && sel) { e.preventDefault(); remove(sel.side, sel.i); }
    };
    addEventListener("keydown", k); return () => removeEventListener("keydown", k);
  });   // re-bound every render: it reads the selection and the active hand

  const remove = (side: Side, i: number) => { setTracks((T) => ({ ...T, [side]: T[side].filter((_, j) => j !== i) })); setSel(null); };
  const move = (side: Side, i: number, nt: number) => setTracks((T) => {
    const ks = T[side].map((k) => [...k] as HandKey); const lo = i > 0 ? ks[i - 1][0] + 0.05 : 0, hi = i < ks.length - 1 ? ks[i + 1][0] - 0.05 : len; ks[i][0] = r3(Math.min(Math.max(nt, lo), hi)); return { ...T, [side]: ks };
  });
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
  const keyOf = (s: Side) => tracks[s];
  const selKey = sel ? tracks[sel.side][sel.i] : null;
  const current = (s: Side) => { const ks = tracks[s]; let p: string | null = ks.length ? ks[0][1] : null; for (const k of ks) if (k[0] <= t + 1e-6) p = k[1]; return p; };

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

      <div className="mb-3 flex flex-wrap gap-1.5">
        {POSES.map((p, i) => (
          <button key={p.key} onClick={() => put(p.key)} className="group flex items-center gap-1.5 rounded-lg border border-line-strong px-2.5 py-1.5 text-[12px] text-ink-2 transition hover:text-ink" style={{ borderColor: `${p.color}55` }}>
            <span className="size-2.5 rounded-sm" style={{ background: p.color }} />{p.label}<kbd className="rounded bg-white/8 px-1 font-mono text-[10px] text-ink-3">{i + 1}</kbd>
          </button>
        ))}
      </div>

      <div className="grid grid-cols-[64px_1fr] gap-x-2 gap-y-1.5">
        <div />
        <div ref={lane} className="relative h-5 cursor-pointer select-none" onPointerDown={(e) => seek(at(e.clientX))}>
          {ticks.map((s) => <span key={s} className="absolute top-0 -translate-x-1/2 font-mono text-[10px] text-ink-3" style={{ left: pct(s) }}>{duration(s)}</span>)}
        </div>
        {(["left", "right"] as Side[]).map((side) => {
          const ks = keyOf(side);
          return (
            <React.Fragment key={side}>
              <button onClick={() => setActive(side)} className={cn("flex h-11 flex-col items-start justify-center rounded-lg px-2 text-left text-[12px] capitalize transition", sides(active).includes(side) ? "bg-accent/12 text-ink" : "text-ink-3 hover:text-ink")}>
                {side}<span className="text-[10px] normal-case" style={{ color: COLOR[current(side) ?? ""] ?? "inherit" }}>{current(side) ? LABEL[current(side)!] : "rest"}</span>
              </button>
              <div className="relative h-11 select-none overflow-hidden rounded-lg border border-line bg-black/30" onPointerDown={(e) => { if (e.target === e.currentTarget) { seek(at(e.clientX)); setActive(side); setSel(null); } }}>
                {!ks.length && <div className="pointer-events-none absolute inset-0 grid place-items-center text-[11px] text-ink-3">no poses: press a number to set one at the playhead</div>}
                {ks.map((k, i) => {
                  const from = i === 0 ? 0 : k[0], to = i < ks.length - 1 ? ks[i + 1][0] : len; const on = sel?.side === side && sel.i === i;
                  return (
                    <div key={i} onPointerDown={(e) => { e.stopPropagation(); setSel({ side, i }); setActive(side); seek(Math.max(0, k[0])); }} title={`${LABEL[k[1]]} from ${duration(k[0])}`}
                      className={cn("absolute inset-y-0 flex cursor-pointer items-center overflow-hidden border-l px-1.5 text-[11px] font-medium text-black/80", on && "ring-2 ring-white/70 ring-inset")}
                      style={{ left: pct(from), width: `calc(${pct(to)} - ${pct(from)})`, background: `${COLOR[k[1]]}cc`, borderColor: "rgba(0,0,0,.35)" }}>
                      <span className="truncate">{LABEL[k[1]]}</span>
                      {i > 0 && <span onPointerDown={(e) => { e.stopPropagation(); drag.current = { side, i }; setSel({ side, i }); }} className="absolute inset-y-0 left-0 w-2 cursor-ew-resize" />}
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
            <select value={selKey[1]} onChange={(e) => setTracks((T) => ({ ...T, [sel.side]: dedupe(T[sel.side].map((k, i) => (i === sel.i ? [k[0], e.target.value] as HandKey : k))) }))}
              className="h-7 rounded-md border border-line-strong bg-raised px-2 text-ink">{POSES.map((p) => <option key={p.key} value={p.key}>{p.label}</option>)}</select>
            <Button size="sm" variant="ghost" onClick={() => remove(sel.side, sel.i)}><Trash2 /> Remove this change</Button>
          </>
        ) : <span>Play the video, press <kbd className="rounded bg-white/8 px-1 font-mono text-[10px]">1</kbd>–<kbd className="rounded bg-white/8 px-1 font-mono text-[10px]">7</kbd> at the moment a hand changes. Click a block to change or remove it; drag its left edge to move it.</span>}
      </div>
    </div>
  );
}
