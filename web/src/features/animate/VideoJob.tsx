import * as React from "react";
import { AnimatePresence, motion } from "motion/react";
import { Check, ChevronDown, Clock, Hourglass, Loader2, Minus, X } from "lucide-react";
import type { VideoJob, VideoStage } from "@/lib/types";
import { Badge, Progress } from "@/components/ui";
import { Img, useLightbox } from "@/components/common";
import { SyncPlayer } from "./SyncPlayer";
import { cn, duration } from "@/lib/utils";

/** Seconds per stage for a clip of s seconds, as stages/video_progress.py estimates them (shown before a job starts). */
export const VIDEO_ESTIMATE: [string, (s: number) => number][] = [
  ["cut", (s) => 2 + 0.1 * s], ["motion", (s) => 30 + 4.5 * s], ["camera", (s) => 2 + 0.7 * s], ["build", (s) => 6 + 0.6 * s],
  ["texture", () => 10], ["preview", (s) => 10 + 3.5 * s], ["compare", (s) => 3 + 0.5 * s],
];
export const estimateFor = (s: number) => VIDEO_ESTIMATE.reduce((a, [, f]) => a + f(s), 0);

/** Time left: the estimates of the stages still to run, scaled by how fast the finished ones went on this machine (0.5–2×). `now` is server time. */
export function eta(j: VideoJob, now: number) {
  const work = j.stages.filter((s) => s.key !== "queued");
  const done = work.filter((s) => s.status === "done" && s.started && s.ended && s.estimate > 0);
  const est = done.reduce((a, s) => a + s.estimate, 0), act = done.reduce((a, s) => a + (s.ended! - s.started!), 0);
  const pace = est > 5 ? Math.min(2, Math.max(0.5, act / est)) : 1;
  let left = 0;
  for (const s of work) {
    if (s.status === "pending") left += s.estimate * pace;
    if (s.status === "running") left += Math.max(s.estimate * pace - (now - (s.started ?? now)), 2);
  }
  return { left, pace };
}

const icon = (s: VideoStage["status"]) =>
  s === "done" ? <Check className="size-3.5" /> : s === "failed" ? <X className="size-3.5" /> : s === "running" ? <Loader2 className="size-3.5 animate-spin" /> : <Minus className="size-3.5" />;
const ring: Record<string, string> = { done: "border-ok/50 bg-ok/12 text-ok", running: "border-accent bg-accent/20 text-[#d9ceff] shadow-glow", failed: "border-bad/60 bg-bad/15 text-bad", pending: "border-white/10 text-ink-3" };

function StageRow({ s, now, pace, open, onToggle, last }: { s: VideoStage; now: number; pace: number; open: boolean; onToggle: () => void; last: boolean }) {
  const lb = useLightbox();
  const took = s.started && s.ended ? s.ended - s.started : s.started && s.status === "running" ? now - s.started : null;
  const frac = s.status === "running" && s.estimate > 0 ? Math.min(0.95, (took ?? 0) / (s.estimate * pace)) : s.status === "done" ? 1 : 0;
  const r = s.report; const has = !!(r && (r.text || r.images.length || r.video));
  return (
    <li className="relative pl-10">
      {!last && <span className={cn("absolute top-8 bottom-0 left-[13px] w-px", s.status === "done" ? "bg-ok/40" : "bg-white/8")} />}
      <span className={cn("absolute top-1 left-0 grid size-7 place-items-center rounded-lg border transition", ring[s.status] ?? ring.pending)}>{icon(s.status)}</span>
      <button onClick={has ? onToggle : undefined} className={cn("flex w-full items-center gap-3 rounded-lg py-1.5 pr-1 text-left", has && "hover:bg-white/[0.03]")}>
        <span className={cn("flex-1 text-[13px]", s.status === "pending" ? "text-ink-3" : "text-ink")}>{s.label}</span>
        <span className="font-mono text-[11px] text-ink-3 tabular-nums">
          {s.key === "queued" ? (s.status === "running" ? "waiting…" : took ? duration(took) : "") :
            s.status === "pending" ? `~${duration(s.estimate * pace)}` : s.status === "running" ? `${duration(took)} / ~${duration(s.estimate * pace)}` : took != null ? duration(took) : ""}
        </span>
        {has ? <ChevronDown className={cn("size-3.5 text-ink-3 transition", open && "rotate-180")} /> : <span className="w-3.5" />}
      </button>
      {s.status === "running" && s.key !== "queued" && <Progress value={frac * 100} className="mt-1 mb-2 h-1" />}
      <AnimatePresence initial={false}>
        {open && has && (
          <motion.div initial={{ height: 0, opacity: 0 }} animate={{ height: "auto", opacity: 1 }} exit={{ height: 0, opacity: 0 }} className="overflow-hidden">
            <div className="mb-3 grid gap-2 rounded-xl border border-line bg-black/25 p-3">
              {r!.text && <pre className="font-mono text-[11.5px] leading-relaxed whitespace-pre-wrap text-ink-2">{r!.text}</pre>}
              {!!r!.images.length && (
                <div className="flex flex-wrap gap-2">
                  {r!.images.map((u, i) => <Img key={u} src={u} className="aspect-[4/3] h-36 rounded-lg border border-line bg-black [&_img]:object-contain" onClick={() => lb(r!.images.map((x) => ({ url: x, title: s.label })), i)} />)}
                </div>
              )}
              {r!.video && <video src={r!.video} controls preload="metadata" className="max-h-64 w-full rounded-lg bg-black" />}
            </div>
          </motion.div>
        )}
      </AnimatePresence>
    </li>
  );
}

/** One job: the stages as a vertical timeline with a report each, the time left and when it will be done; the synced player when it is finished. */
export function VideoJobCard({ j, defaultOpen = true }: { j: VideoJob; defaultOpen?: boolean }) {
  const [skew] = React.useState(() => j.now - Date.now() / 1000);     // server clock minus browser clock
  const [tick, setTick] = React.useState(0);
  const active = j.status === "queued" || j.status === "running";
  React.useEffect(() => { if (!active) return; const i = setInterval(() => setTick((x) => x + 1), 1000); return () => clearInterval(i); }, [active]);
  const now = Date.now() / 1000 + skew; void tick;
  const { left, pace } = eta(j, now);
  const [open, setOpen] = React.useState<Record<string, boolean>>({});
  const [expanded, setExpanded] = React.useState(defaultOpen);
  const queued = j.stages[0]?.status === "running";
  const elapsed = (j.finished ?? now) - j.created;
  const doneAt = new Date((Date.now() / 1000 + left) * 1000);
  const total = j.stages.filter((s) => s.key !== "queued").reduce((a, s) => a + s.estimate, 0);
  const spent = j.stages.filter((s) => s.key !== "queued" && s.status === "done").reduce((a, s) => a + s.estimate, 0);
  const runningStage = j.stages.find((s) => s.status === "running");
  const runFrac = runningStage && runningStage.key !== "queued" && runningStage.started ? Math.min(0.95, (now - runningStage.started) / (runningStage.estimate * pace)) * runningStage.estimate : 0;
  const pct = j.status === "done" ? 100 : Math.min(99, ((spent + runFrac) / Math.max(total, 1)) * 100);
  const R = j.result;

  return (
    <div className="panel overflow-hidden" data-tour="job">
      <button onClick={() => setExpanded(!expanded)} className="flex w-full flex-wrap items-center gap-x-4 gap-y-2 px-5 py-4 text-left">
        {R?.thumb ? <img src={R.thumb} className="size-11 rounded-lg border border-line object-cover" /> : <div className="grid size-11 place-items-center rounded-lg border border-line bg-white/[0.03]"><Hourglass className="size-4 text-ink-3" /></div>}
        <div className="min-w-0 flex-1">
          <div className="truncate text-[14px] font-semibold">{j.title}</div>
          <div className="text-[12px] text-ink-3">{duration(j.start)}–{duration(j.end)} of {j.video.replace(/^.*?_motion_/, "")} · {j.seconds.toFixed(1)} s · started {new Date(j.created * 1000).toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" })}</div>
        </div>
        {active ? (
          <div className="text-right">
            <div className="flex items-center justify-end gap-1.5 text-[13px] font-medium text-[#d4c9ff]"><Clock className="size-3.5" />{queued ? "waiting for the GPU" : `about ${duration(left)} left`}</div>
            <div className="font-mono text-[11px] text-ink-3">{queued ? `then about ${duration(left)}` : `done by ${doneAt.toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" })}`} · {duration(elapsed)} so far</div>
          </div>
        ) : j.status === "done" ? <Badge tone="ok">done in {duration(elapsed)}</Badge> : <Badge tone="bad">failed</Badge>}
        <ChevronDown className={cn("size-4 text-ink-3 transition", expanded && "rotate-180")} />
      </button>
      {active && <Progress value={pct} className="h-0.5 rounded-none" />}
      {expanded && (
        <div className="grid gap-5 border-t border-line p-5 xl:grid-cols-[minmax(260px,340px)_1fr]">
          <ol className="grid content-start gap-0.5">
            {j.stages.map((s, i) => <StageRow key={s.key} s={s} now={now} pace={pace} last={i === j.stages.length - 1} open={open[s.key] ?? (s.status === "failed")} onToggle={() => setOpen((o) => ({ ...o, [s.key]: !(o[s.key] ?? false) }))} />)}
            {j.error && <li className="mt-2 rounded-lg border border-bad/30 bg-bad/8 px-3 py-2 text-[12px] text-bad">{j.error}</li>}
            {active && pace !== 1 && <li className="mt-2 text-[11px] text-ink-3">This machine is running at {pace < 1 ? `${(1 / pace).toFixed(1)}× faster` : `${pace.toFixed(1)}× slower`} than the estimates; the times above are adjusted.</li>}
          </ol>
          <div className="min-w-0">
            {R?.ref && R.url ? <SyncPlayer model={R.url} reference={R.ref} compare={R.compare} preview={R.video} fbx={R.fbx} /> : <LiveReport j={j} />}
          </div>
        </div>
      )}
    </div>
  );
}

/** While a job runs: the latest report (the frame it cut, the retargeted pose, the preview) so there is something to look at. */
function LiveReport({ j }: { j: VideoJob }) {
  const lb = useLightbox();
  const last = [...j.stages].reverse().find((s) => s.report && (s.report.images.length || s.report.video));
  const cut = j.stages.find((s) => s.key === "cut")?.report;
  if (!last) return <div className="grid h-full min-h-48 place-items-center rounded-xl border border-dashed border-line text-[13px] text-ink-3">{j.status === "failed" ? "No clip: see the stage that failed." : "The first report appears in a few seconds."}</div>;
  return (
    <div className="grid gap-3">
      <div className="text-xs text-ink-3">Latest: <b className="text-ink-2">{last.label}</b></div>
      {last.report!.video && last.key !== "cut" ? <video src={last.report!.video} controls autoPlay muted loop className="max-h-[50vh] w-full rounded-xl bg-black" />
        : cut?.video ? <video src={cut.video} controls autoPlay muted loop className="max-h-[50vh] w-full rounded-xl bg-black" />
        : <Img src={last.report!.images[0]} className="max-h-[50vh] rounded-xl border border-line [&_img]:object-contain" onClick={() => lb([{ url: last.report!.images[0], title: last.label }], 0)} />}
    </div>
  );
}

export function VideoJobList({ jobs, limit = 6 }: { jobs: VideoJob[]; limit?: number }) {
  return <div className="grid gap-3">{jobs.slice(0, limit).map((j, i) => <VideoJobCard key={j.job} j={j} defaultOpen={i === 0} />)}</div>;
}
