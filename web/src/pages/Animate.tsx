import * as React from "react";
import { Link, useNavigate, useParams } from "react-router-dom";
import { toast } from "sonner";
import { motion } from "motion/react";
import { ArrowRight, Check, Clock, Film, Flag, FlagTriangleRight, PersonStanding, Repeat, Upload } from "lucide-react";
import { q, upload, useInvalidate, useLive, useRuns, useVideoJobs } from "@/lib/api";
import type { RunSummary } from "@/lib/types";
import { Badge, Button, Empty, Input, Panel, Progress, Spinner } from "@/components/ui";
import { Img, StatusPill } from "@/components/common";
import { ModelViewer } from "@/components/ModelViewer";
import { VideoJobList, estimateFor } from "@/features/animate/VideoJob";
import { cn, duration } from "@/lib/utils";

const MAX = 180;

function Step({ n, title, done, children, tour }: { n: number; title: string; done?: boolean; children: React.ReactNode; tour?: string }) {
  return (
    <Panel className="p-5" data-tour={tour}>
      <div className="mb-4 flex items-center gap-3">
        <span className={cn("grid size-7 place-items-center rounded-full border text-[12px] font-semibold", done ? "border-ok/50 bg-ok/12 text-ok" : "border-accent/50 bg-accent/15 text-[#d4c9ff]")}>{done ? <Check className="size-3.5" /> : n}</span>
        <h2 className="text-[15px] font-semibold">{title}</h2>
      </div>
      {children}
    </Panel>
  );
}

/** Pick a finished character. Only rigged runs can dance; finished ones first. */
function CharacterPicker({ runs, value, onChange }: { runs: RunSummary[]; value: string | null; onChange: (n: string) => void }) {
  if (!runs.length) return <Empty icon={<PersonStanding />} title="No rigged character yet.">A run needs to get past the Auto-rig stage first. <Link to="/new" className="text-accent">Start a run</Link></Empty>;
  return (
    <div className="grid grid-cols-3 gap-2 sm:grid-cols-4 xl:grid-cols-5">
      {runs.map((r) => (
        <button key={r.name} onClick={() => onChange(r.name)} className={cn("group overflow-hidden rounded-xl border text-left transition", value === r.name ? "border-accent/70 ring-2 ring-accent/30" : "border-line hover:border-white/20")}>
          <Img src={r.thumb} className="aspect-[3/4] transition group-hover:scale-[1.02]" />
          <div className="flex items-center gap-1.5 px-2 py-1.5"><span className="flex-1 truncate text-[12px] font-medium">{r.name}</span>{value === r.name && <Check className="size-3.5 text-accent" />}</div>
        </button>
      ))}
    </div>
  );
}

/** The video with a range on it: drag the handles, or play and press "start here" / "end here". The preview loops the range. */
function RangePicker({ url, len, from, to, setFrom, setTo }: { url: string; len: number; from: number; to: number; setFrom: (v: number) => void; setTo: (v: number) => void }) {
  const vid = React.useRef<HTMLVideoElement>(null);
  const bar = React.useRef<HTMLDivElement>(null);
  const [t, setT] = React.useState(0);
  const [loop, setLoop] = React.useState(true);
  const drag = React.useRef<"from" | "to" | "head" | null>(null);
  const at = (x: number) => { const b = bar.current!.getBoundingClientRect(); return Math.max(0, Math.min(1, (x - b.left) / b.width)) * len; };
  const r1 = (v: number) => Math.round(v * 10) / 10;

  const move = (e: PointerEvent | React.PointerEvent) => {
    if (!drag.current || !len) return; const s = at(e.clientX);
    if (drag.current === "from") setFrom(r1(Math.max(0, Math.min(s, to - 1, len))));
    else if (drag.current === "to") setTo(r1(Math.min(len, Math.max(s, from + 1))));
    else if (vid.current) vid.current.currentTime = s;
  };
  React.useEffect(() => {
    const up = () => (drag.current = null); const mv = (e: PointerEvent) => move(e);
    addEventListener("pointermove", mv); addEventListener("pointerup", up); return () => { removeEventListener("pointermove", mv); removeEventListener("pointerup", up); };
  });
  const onTime = () => { const e = vid.current; if (!e) return; setT(e.currentTime); if (loop && !e.paused && (e.currentTime >= to || e.currentTime < from - 0.25)) e.currentTime = from; };
  const pct = (v: number) => `${len ? (v / len) * 100 : 0}%`;
  const too = to - from > MAX;

  return (
    <div className="grid gap-3">
      <video ref={vid} src={url} controls playsInline className="max-h-[44vh] w-full rounded-xl bg-black" onTimeUpdate={onTime} />
      <div ref={bar} className="relative h-10 cursor-pointer touch-none select-none" onPointerDown={(e) => { drag.current = "head"; move(e); }}>
        <div className="absolute inset-x-0 top-1/2 h-2 -translate-y-1/2 rounded-full bg-white/8" />
        <div className={cn("absolute top-1/2 h-2 -translate-y-1/2 rounded-full", too ? "bg-bad/60" : "bg-gradient-to-r from-accent to-accent-2")} style={{ left: pct(from), width: pct(to - from) }} />
        <div className="absolute top-1 bottom-1 w-0.5 bg-white/70" style={{ left: pct(t) }} />
        {(["from", "to"] as const).map((k) => (
          <div key={k} onPointerDown={(e) => { e.stopPropagation(); drag.current = k; }} style={{ left: pct(k === "from" ? from : to) }}
            className="absolute top-1/2 grid h-8 w-4 -translate-x-1/2 -translate-y-1/2 cursor-ew-resize place-items-center rounded-md border border-white/30 bg-raised shadow-lg hover:border-accent">
            <span className="h-3 w-px bg-white/50" />
          </div>
        ))}
      </div>
      <div className="flex flex-wrap items-center gap-2">
        <Button size="sm" onClick={() => vid.current && setFrom(r1(Math.min(vid.current.currentTime, to - 1)))}><Flag /> Start here</Button>
        <Button size="sm" onClick={() => vid.current && setTo(r1(Math.max(vid.current.currentTime, from + 1)))}><FlagTriangleRight /> End here</Button>
        <Button size="sm" variant="ghost" className={cn(loop && "text-accent")} onClick={() => setLoop(!loop)}><Repeat /> Loop the range</Button>
        <div className="ml-auto flex items-center gap-1.5">
          <Input type="number" min={0} step={0.1} value={from} onChange={(e) => setFrom(+e.target.value)} className="h-8 w-20 font-mono text-xs" aria-label="Start (seconds)" />
          <span className="text-ink-3">–</span>
          <Input type="number" min={0} step={0.1} value={to} onChange={(e) => setTo(+e.target.value)} className="h-8 w-20 font-mono text-xs" aria-label="End (seconds)" />
          <span className="text-[12px] text-ink-3">s</span>
        </div>
      </div>
      <div className={cn("text-[12px]", too ? "text-bad" : "text-ink-3")}>{duration(from)} to {duration(to)} · {(to - from).toFixed(1)} s selected{too ? ` · at most ${MAX} s per clip` : ""}</div>
    </div>
  );
}

export default function AnimatePage() {
  const { name } = useParams();
  const nav = useNavigate(); const inv = useInvalidate();
  const { data: all, isLoading } = useRuns();
  const { data: live } = useLive();
  const rigged = React.useMemo(() => (all ?? []).filter((r) => r.rigged).sort((a, b) => +(b.status === "finished") - +(a.status === "finished")), [all]);
  const sel = name ?? null; const run = rigged.find((r) => r.name === sel);
  const { data: jobs } = useVideoJobs(sel);
  const busy = jobs?.some((j) => j.status === "queued" || j.status === "running");

  const [file, setFile] = React.useState<File | null>(null);
  const [url, setUrl] = React.useState<string | null>(null);
  const [len, setLen] = React.useState(0);
  const [from, setFrom] = React.useState(0);
  const [to, setTo] = React.useState(10);
  const [pct, setPct] = React.useState<number | null>(null);
  const [over, setOver] = React.useState(false);
  React.useEffect(() => () => { if (url) URL.revokeObjectURL(url); }, [url]);

  const pick = (f: File | null | undefined) => {
    if (!f) return; if (!f.type.startsWith("video/") && !/\.(mp4|mov|mkv|webm|avi|m4v)$/i.test(f.name)) return toast.error("That is not a video file.");
    setFile(f); setUrl((u) => { if (u) URL.revokeObjectURL(u); return URL.createObjectURL(f); }); setLen(0);
    const probe = document.createElement("video"); probe.preload = "metadata"; probe.src = URL.createObjectURL(f);
    probe.onloadedmetadata = () => { const d = probe.duration; setLen(d); setFrom(0); setTo(Math.round(Math.min(d, 15) * 10) / 10); URL.revokeObjectURL(probe.src); };
  };

  const secs = Math.max(0, to - from); const ok = !!sel && !!file && secs >= 1 && secs <= MAX && !busy;
  const est = estimateFor(secs) * 1.0;
  const start = async () => {
    if (!ok || !file || !sel) return;
    setPct(0);
    try {
      await upload(`/api/animate_video?${q({ run: sel, fname: file.name, start: from.toFixed(2), end: to.toFixed(2), title: file.name.replace(/\.[^.]+$/, "") })}`, file, setPct);
      toast.success("Started: follow the stages below"); inv(["video", sel], ["run", sel]);
      setTimeout(() => document.getElementById("jobs")?.scrollIntoView({ behavior: "smooth" }), 400);
    } catch (e: any) { toast.error(e.message); } finally { setPct(null); }
  };

  return (
    <div className="mx-auto max-w-7xl px-4 py-10 lg:px-6">
      <div className="mb-8">
        <div className="mb-2 flex items-center gap-2 text-[11px] font-semibold tracking-[0.14em] text-ink-3 uppercase"><Film className="size-3.5" /> Animate</div>
        <h1 className="text-3xl font-semibold tracking-tight">Make a character <span className="text-gradient">dance a video</span></h1>
        <p className="mt-2 max-w-2xl text-[14px] text-ink-3">Pick a character you have already built, drop in a video of one person dancing, choose the part to copy. No new run: the motion is read from the video and put on the rig, stage by stage, with a report at each step and the time it will take.</p>
      </div>

      <div className="grid gap-5 lg:grid-cols-[minmax(0,1.15fr)_minmax(0,1fr)]">
        <div className="grid content-start gap-5">
          <Step n={1} title="Choose a character" done={!!run} tour="anim-character">
            {isLoading ? <Spinner /> : <CharacterPicker runs={rigged} value={sel} onChange={(n) => nav(`/animate/${encodeURIComponent(n)}`, { replace: true })} />}
          </Step>
          <Step n={2} title="Choose a video and the part to copy" done={!!file && secs >= 1 && secs <= MAX} tour="anim-video">
            <label onDragOver={(e) => { e.preventDefault(); setOver(true); }} onDragLeave={() => setOver(false)} onDrop={(e) => { e.preventDefault(); setOver(false); pick(e.dataTransfer.files[0]); }}
              className={cn("mb-3 flex cursor-pointer items-center gap-3 rounded-xl border-2 border-dashed px-4 py-4 transition", over ? "border-accent bg-accent/8" : file ? "border-cyan/40 bg-cyan/5" : "border-line-strong hover:border-cyan/40")}>
              <input type="file" accept="video/*" className="hidden" onChange={(e) => pick(e.target.files?.[0])} />
              <Upload className="size-5 text-cyan" />
              <span className="min-w-0 text-[13px]">{file ? <><b className="block truncate">{file.name}</b><span className="text-ink-3">{(file.size / 1048576).toFixed(1)} MB{len ? ` · ${duration(len)}` : ""} · click or drop to change</span></>
                : <><b>Drop a video here, or click to choose</b><span className="block text-ink-3">One person, whole body in view, one continuous shot. MP4, MOV, MKV, WebM.</span></>}</span>
            </label>
            {url && len > 0 && <RangePicker url={url} len={len} from={from} to={to} setFrom={setFrom} setTo={setTo} />}
          </Step>
        </div>

        <div className="grid content-start gap-5">
          <Panel className="overflow-hidden">
            <ModelViewer url={run?.model} className="h-[min(42vh,420px)] rounded-none" emptyText="Choose a character to see it here." />
            {run && <div className="flex items-center gap-2 border-t border-line px-4 py-2.5 text-[13px]"><b className="flex-1 truncate">{run.name}</b><StatusPill status={run.status} /><Link to={`/run/${encodeURIComponent(run.name)}`} className="text-[12px] text-ink-3 hover:text-ink">open run <ArrowRight className="inline size-3" /></Link></div>}
          </Panel>
          <Step n={3} title="Start" tour="anim-start">
            <div className="mb-4 grid grid-cols-3 gap-3 text-center">
              <div className="rounded-xl border border-line bg-white/[0.02] p-3"><div className="font-mono text-lg">{secs ? `${secs.toFixed(1)} s` : "–"}</div><div className="text-[11px] text-ink-3">of video</div></div>
              <div className="rounded-xl border border-line bg-white/[0.02] p-3"><div className="font-mono text-lg">{secs ? `~${duration(est)}` : "–"}</div><div className="text-[11px] text-ink-3">estimated</div></div>
              <div className="rounded-xl border border-line bg-white/[0.02] p-3"><div className="font-mono text-lg">{secs ? new Date(Date.now() + est * 1000).toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" }) : "–"}</div><div className="text-[11px] text-ink-3">done by</div></div>
            </div>
            {!!live?.length && <div className="mb-3 flex items-center gap-2 rounded-lg border border-warn/30 bg-warn/8 px-3 py-2 text-[12px] text-warn"><Clock className="size-3.5" /> {live.length === 1 ? `${live[0]} is using the GPU` : `${live.length} runs are using the GPU`}: this waits its turn, and the estimate starts then.</div>}
            {busy && <div className="mb-3 text-[12px] text-ink-3">This character already has a dance being made; start the next one when it is done.</div>}
            {pct !== null && <div className="mb-3"><Progress value={pct * 100} /><p className="mt-1 text-[11px] text-ink-3">Uploading · {Math.round(pct * 100)}%</p></div>}
            <Button variant="primary" size="lg" className="w-full" disabled={!ok} loading={pct !== null} onClick={start}><Film /> {!sel ? "Choose a character" : !file ? "Choose a video" : busy ? "A dance is being made" : "Copy the dance"}</Button>
            <p className="mt-3 text-[11.5px] text-ink-3">Stages: cut → body motion (GVHMR) → camera → retarget onto the rig → final texture → preview → side by side. Body only, no fingers.</p>
          </Step>
        </div>
      </div>

      {sel && (
        <section id="jobs" className="mt-10 scroll-mt-20">
          <div className="mb-4 flex items-center gap-3"><h2 className="text-lg font-semibold">Dances for {sel}</h2>{!!jobs?.length && <Badge>{jobs.length}</Badge>}</div>
          {jobs?.length ? <motion.div initial={{ opacity: 0 }} animate={{ opacity: 1 }}><VideoJobList jobs={jobs} /></motion.div>
            : <Empty icon={<Film />} title="No dances from a video yet.">Each one appears here with its stages, the time left, and the result played next to the video.</Empty>}
        </section>
      )}
    </div>
  );
}
