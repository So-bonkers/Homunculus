import * as React from "react";
import { toast } from "sonner";
import { Clapperboard, Download, Film, GitFork, Hand, Image as ImageIcon, Loader2, Pause, Play, Sparkles, Upload, Wand2, X } from "lucide-react";
import { api, q, upload, useInvalidate, useVideoJobs } from "@/lib/api";
import { Link } from "react-router-dom";
import { SyncPlayer } from "@/features/animate/SyncPlayer";
import { HandTimeline } from "@/features/animate/HandTimeline";
import { VideoJobCard } from "@/features/animate/VideoJob";
import type { Clip, RunDetail } from "@/lib/types";
import { Badge, Button, Empty, Field, Input, Panel, Progress, Segmented, Select, Spinner, Textarea } from "@/components/ui";
import { Img, useLightbox } from "@/components/common";
import { ModelViewer } from "@/components/ModelViewer";
import type { Viewer } from "@/viewer/Viewer";
import { PresetPicker } from "@/features/PresetPicker";
import { cn } from "@/lib/utils";

/* ---------------------------------------------------------------- Activity */
export function ActivityTab({ d, sel, clearSel }: { d: RunDetail; sel: string | null; clearSel: () => void }) {
  const lb = useLightbox();
  const snaps = [...d.snapshots].reverse().filter((x) => !sel || x.stage === sel || (sel === "pick" && x.stage === "edit"));
  const all = snaps.flatMap((x) => (x.images?.length ? x.images.map((im) => ({ url: im.url, title: `${x.label} · ${im.caption || x.title}` })) : x.url ? [{ url: x.url, title: `${x.label} · ${x.title}` }] : []));
  const open = (url: string) => lb(all, Math.max(0, all.findIndex((a) => a.url === url)));
  return (
    <div className="grid gap-4">
      {sel && <div><button onClick={clearSel} className="inline-flex items-center gap-2 rounded-full border border-line-strong px-3 py-1 text-xs text-ink-2 hover:text-ink">Showing {d.stages.find((s) => s.key === sel)?.label} <X className="size-3" /></button></div>}
      {!snaps.length ? <Empty icon={<ImageIcon />} title="Nothing here yet.">Snapshots appear here at every important moment of the run.</Empty> : (
        <ol className="relative grid gap-4 border-l border-line pl-6">
          {snaps.map((x) => {
            const failed = /FAILED/.test(x.title);
            return (
              <li key={x.n} className="relative">
                <span className={cn("absolute top-1.5 -left-[29px] size-2.5 rounded-full border-2 border-canvas", failed ? "bg-bad" : "bg-accent")} />
                <div className="mb-2 flex flex-wrap items-center gap-2 text-xs"><span className="font-mono text-ink-3">{x.time}</span><Badge>{x.label}</Badge><b className="text-[13px] text-ink">{x.title}</b></div>
                {x.images?.length ? (
                  <div className={cn("grid gap-2", x.images.length === 1 ? "max-w-xl grid-cols-1" : "grid-cols-2 md:grid-cols-3 xl:grid-cols-4")}>
                    {x.images.map((im) => (
                      <figure key={im.url} className="overflow-hidden rounded-lg border border-line bg-black/30">
                        <Img src={im.url} className="aspect-[4/3]" onClick={() => open(im.url)} />
                        {im.caption && <figcaption className="truncate px-2 py-1.5 text-[11px] text-ink-3">{im.caption}</figcaption>}
                      </figure>
                    ))}
                  </div>
                ) : x.url ? <Img src={x.url} className="aspect-[16/7] max-w-3xl rounded-lg border border-line" onClick={() => open(x.url!)} /> : null}
                {x.text && <pre className="mt-2 max-w-3xl overflow-x-auto rounded-lg border border-line bg-black/30 p-3 font-mono text-[11.5px] leading-relaxed whitespace-pre-wrap text-ink-2">{x.text}</pre>}
              </li>
            );
          })}
        </ol>
      )}
    </div>
  );
}

/* ---------------------------------------------------------------- 3D model */
export function ModelTab({ d }: { d: RunDetail }) {
  const [key, setKey] = React.useState<string | null>(null);
  const m = d.models.find((x) => x.key === key) ?? d.models[0];
  if (!d.models.length) return (
    <Empty icon={<Wand2 />} title="No 3D model yet.">
      {d.models_pending ? "A light preview of the shape is being prepared (about a minute). This panel updates by itself." : "The shape candidates appear here while you judge them, and the textured model as soon as it is built."}
    </Empty>
  );
  return (
    <div className="grid gap-3">
      <div className="flex flex-wrap gap-1.5">
        {d.models.map((x) => (
          <button key={x.key} onClick={() => setKey(x.key)} className={cn("rounded-lg border px-3 py-1.5 text-xs transition", m?.key === x.key ? "border-accent/60 bg-accent/15 text-ink" : "border-line-strong text-ink-2 hover:text-ink")}>{x.label}</button>
        ))}
      </div>
      <ModelViewer url={m?.url} className="h-[min(72vh,760px)] border border-line" />
    </div>
  );
}

/* ---------------------------------------------------------------- Animate */
function ClipPlayer({ clips, run }: { clips: Clip[]; run: string }) {
  const [id, setId] = React.useState<string | null>(null);
  const c = clips.find((x) => x.id === id) ?? clips[clips.length - 1];
  const [v, setV] = React.useState<Viewer | null>(null);
  const [play, setPlay] = React.useState(true);
  const [speed, setSpeed] = React.useState("1");
  const [t, setT] = React.useState(0);
  React.useEffect(() => { if (!v) return; const i = setInterval(() => setT(v.clipTime()), 50); return () => clearInterval(i); }, [v]);
  const list = (
    <div className="grid max-h-[min(64vh,640px)] min-w-0 content-start gap-1.5 overflow-y-auto pr-1">
      {[...clips].reverse().map((x) => (
        <button key={x.id} onClick={() => setId(x.id)} className={cn("flex w-full min-w-0 items-center gap-3 rounded-xl border p-2 text-left transition", c?.id === x.id ? "border-accent/60 bg-accent/10" : "border-line hover:border-white/15")}>
          <Img src={x.thumb} className="size-12 shrink-0 rounded-lg" />
          <div className="min-w-0">
            <div className="line-clamp-3 break-words text-[13px] font-medium" title={x.prompt}>{x.prompt}</div>
            <div className="flex items-center gap-1.5 text-[11px] text-ink-3">{x.source === "video" ? <><Film className="size-3 text-cyan" /> from a video</> : `take ${x.rep + 1}`}{x.textured && " · textured"}</div>
          </div>
        </button>
      ))}
    </div>
  );
  if (c?.ref) return (        // a dance from a video: the video and the character play together
    <div className="grid gap-3 xl:grid-cols-[1fr_260px]">
      <SyncPlayer key={c.id} model={c.url} reference={c.ref} compare={c.compare} preview={c.video} fbx={c.fbx}>
        {(p) => <HandTimeline run={run} clip={c.id} name={c.prompt} t={p.t} len={p.len} seek={p.seek} wave={p.wave} />}
      </SyncPlayer>
      {list}
    </div>
  );
  return (
    <div className="grid gap-3 lg:grid-cols-[1fr_280px]">
      <div className="grid gap-2">
        <ModelViewer url={c?.url} onViewer={setV} onLoaded={(_, vv) => { vv.set({ play, speed: +speed }); }} className="h-[min(64vh,640px)] border border-line"
          toolbarExtra={<>
            <button className="grid size-8 place-items-center rounded-lg text-ink-2 hover:bg-white/8 hover:text-ink" onClick={() => { setPlay(!play); v?.set({ play: !play }); }}>{play ? <Pause className="size-4" /> : <Play className="size-4" />}</button>
            <Segmented value={speed} onValueChange={(s) => { setSpeed(s); v?.set({ speed: +s }); }} options={[{ value: "0.5", label: "0.5×" }, { value: "1", label: "1×" }]} className="border-0 bg-transparent" />
          </>} />
        <input type="range" min={0} max={1000} value={Math.round(t * 1000)} onChange={(e) => { setPlay(false); v?.set({ play: false }); v?.seek(+e.target.value / 1000); }} className="w-full accent-[var(--color-accent)]" />
        {c && (
          <div className="flex flex-wrap items-center gap-2">
            <a href={c.url} download><Button size="sm"><Download /> GLB</Button></a>
            {c.fbx && <a href={c.fbx} download><Button size="sm"><Download /> FBX</Button></a>}
            {c.video && <a href={c.video} download><Button size="sm"><Film /> Preview video</Button></a>}
          </div>
        )}
        {c?.compare && (
          <div className="overflow-hidden rounded-xl border border-line"><div className="border-b border-line px-3 py-2 text-xs text-ink-3">Side by side with the video</div><video src={c.compare} controls preload="metadata" className="w-full" /></div>
        )}
      </div>
      {list}
    </div>
  );
}

export function AnimateTab({ d }: { d: RunDetail }) {
  const inv = useInvalidate();
  const rigged = d.stages.find((s) => s.key === "rig")?.status === "done" || d.files.some((f) => /rig/i.test(f.label));
  const A = d.animations; const busy = A?.status === "queued" || A?.status === "running";
  const { data: vjobs } = useVideoJobs(d.name);
  const vjob = vjobs?.find((j) => j.status === "queued" || j.status === "running" || (j.finished && d.now - j.finished < 600));
  const [prompts, setPrompts] = React.useState("");
  const [reps, setReps] = React.useState("2");
  const [vfile, setVfile] = React.useState<File | null>(null);
  const [from, setFrom] = React.useState(0);
  const [to, setTo] = React.useState(20);
  const [vpct, setVpct] = React.useState<number | null>(null);
  const [dur, setDur] = React.useState<number | null>(null);
  const [vurl, setVurl] = React.useState<string | null>(null);
  React.useEffect(() => () => { if (vurl) URL.revokeObjectURL(vurl); }, [vurl]);

  const gen = async () => {
    const ps = prompts.split("\n").map((s) => s.trim()).filter(Boolean);
    if (!ps.length) return toast.error("Type at least one prompt.");
    try { await api.animate(d.name, ps, +reps); setPrompts(""); toast.success("Generating clips…"); inv(["run", d.name]); } catch (e: any) { toast.error(e.message); }
  };
  const copyDance = async () => {
    if (!vfile) return toast.error("Choose a video file.");
    if (!(to > from)) return toast.error("The end must be after the start.");
    setVpct(0);
    try {
      await upload(`/api/animate_video?${q({ run: d.name, fname: vfile.name, start: from, end: to, title: vfile.name.replace(/\.[^.]+$/, "") })}`, vfile, setVpct);
      toast.success("Copying the dance… the clip appears here when it is ready"); inv(["run", d.name]);
    } catch (e: any) { toast.error(e.message); } finally { setVpct(null); }
  };

  return (
    <div className="grid gap-5">
      {!rigged && <div className="rounded-xl border border-line bg-white/[0.02] px-4 py-3 text-[13px] text-ink-3">Animation is available once the rig is built.</div>}
      {A?.status === "failed" && A.error && <div className="rounded-xl border border-bad/30 bg-bad/8 px-4 py-3 text-[13px] text-bad">Last attempt failed: {A.error}</div>}
      <div className={cn("grid gap-4 xl:grid-cols-2", !rigged && "pointer-events-none opacity-50")}>
        <Panel className="p-5" data-tour="video">
          <div className="mb-1 flex items-center gap-2"><Film className="size-4 text-cyan" /><h3 className="text-[15px] font-semibold">Copy a dance from a video</h3><Badge tone="cyan">default</Badge><Link to={`/animate/${encodeURIComponent(d.name)}`} className="ml-auto text-[12px] text-ink-3 hover:text-ink">Animate studio →</Link></div>
          <p className="mb-4 text-[13px] text-ink-3">One person dancing, one continuous shot, whole body in view. The motion is read on the GPU (the camera's own motion taken out) and put on this rig, with a side-by-side preview. About 4 minutes for 20 seconds; body only, no fingers.</p>
          <label className={cn("flex cursor-pointer items-center gap-3 rounded-xl border-2 border-dashed px-4 py-4 transition", vfile ? "border-cyan/40 bg-cyan/5" : "border-line-strong hover:border-cyan/40")}>
            <input type="file" accept="video/*" className="hidden" onChange={(e) => { const f = e.target.files?.[0] ?? null; setVfile(f); setVurl((u) => { if (u) URL.revokeObjectURL(u); return f ? URL.createObjectURL(f) : null; }); }} />
            <Upload className="size-5 text-cyan" />
            <span className="min-w-0 text-[13px]">{vfile ? <><b className="block truncate">{vfile.name}</b><span className="text-ink-3">{(vfile.size / 1048576).toFixed(1)} MB{dur ? ` · ${dur.toFixed(1)} s` : ""} · click to change</span></> : <><b>Choose a video</b><span className="block text-ink-3">MP4, MOV, MKV, WebM</span></>}</span>
          </label>
          {vurl && <video src={vurl} className="mt-3 max-h-56 w-full rounded-lg bg-black" controls muted onLoadedMetadata={(e) => { const dd = (e.target as HTMLVideoElement).duration; setDur(dd); setTo((t) => Math.min(t, Math.floor(dd))); }} />}
          <div className="mt-3 grid grid-cols-2 gap-3">
            <Field label="From (seconds)"><Input type="number" min={0} step={0.5} value={from} onChange={(e) => setFrom(+e.target.value)} /></Field>
            <Field label="To (seconds)" hint="At most 180 s per clip."><Input type="number" min={1} step={0.5} value={to} onChange={(e) => setTo(+e.target.value)} /></Field>
          </div>
          {vpct !== null && <div className="mt-3"><Progress value={vpct * 100} /><p className="mt-1 text-[11px] text-ink-3">Uploading · {Math.round(vpct * 100)}%</p></div>}
          <Button variant="primary" className="mt-4" onClick={copyDance} loading={vpct !== null} disabled={busy}><Film /> {busy ? (A?.status === "queued" ? "Queued: waits for the GPU" : "Making a clip…") : "Copy the dance"}</Button>
        </Panel>
        <Panel className="p-5">
          <div className="mb-1 flex items-center gap-2"><Clapperboard className="size-4 text-accent" /><h3 className="text-[15px] font-semibold">Text to animation</h3></div>
          <p className="mb-4 text-[13px] text-ink-3">One motion per line, in plain words ("walks forward", "raises both arms and cheers"). UniMate animates this rig locally; clips take under a minute.</p>
          <Textarea value={prompts} onChange={(e) => setPrompts(e.target.value)} placeholder={"walks forward\nraises both arms and cheers"} />
          <div className="mt-3"><PresetPicker value={prompts} onChange={setPrompts} /></div>
          <div className="mt-4 flex flex-wrap items-center gap-2">
            <Select value={reps} onValueChange={setReps} options={["1", "2", "3", "4"].map((v) => ({ value: v, label: `${v} clip${v === "1" ? "" : "s"} per prompt` }))} className="w-44" />
            <Button variant="primary" onClick={gen} disabled={busy}>{busy ? <><Loader2 className="animate-spin" /> {A?.status === "queued" ? "Queued" : "Generating…"}</> : <><Sparkles /> Generate clips</>}</Button>
            {!!A?.clips?.length && <Button variant="ghost" onClick={async () => { try { await api.handPoses(d.name); toast("Setting hand poses on the clips…"); } catch (e: any) { toast.error(e.message); } }} title="Fists for a punch, an open hand for a wave, a grip for a sword. No GPU needed."><Hand /> Set hand poses</Button>}
          </div>
        </Panel>
      </div>
      {vjob && <VideoJobCard key={vjob.job} j={vjob} />}
      {busy && !(vjob && (vjob.status === "queued" || vjob.status === "running")) && <div className="flex items-center gap-3 rounded-xl border border-accent/30 bg-accent/8 px-4 py-3 text-[13px]"><Spinner className="text-accent" /> A clip is being made; the Log tab has the details.</div>}
      {A?.clips?.length ? <ClipPlayer clips={A.clips} run={d.name} /> : <Empty icon={<Clapperboard />} title={busy ? "Making the first clips…" : "No clips yet."}>Copy a dance from a video or type a prompt above.</Empty>}
    </div>
  );
}

/* ---------------------------------------------------------------- Looks */
export function LooksTab({ d, onForkLook }: { d: RunDetail; onForkLook: (look: string) => void }) {
  const lb = useLightbox(); const inv = useInvalidate();
  const L = d.looks; const busy = L?.status === "queued" || L?.status === "running";
  const tiles = L ? [{ label: "Raw input", url: L.raw, look: null }, ...(L.asis ? [{ label: "As is (this run's redraw)", url: L.asis, look: "asis" }] : []), ...L.items.map((x) => ({ label: x.label, url: x.url, look: x.look }))] : [];
  const gen = async () => { try { await api.looks(d.name); toast.success("Look previews queued"); inv(["run", d.name]); } catch (e: any) { toast.error(e.message); } };
  return (
    <div className="grid gap-4">
      <div className="flex flex-wrap items-end justify-between gap-3">
        <div><h3 className="text-[15px] font-semibold">Target looks</h3><p className="text-[13px] text-ink-3">One redraw per look from this run's input, to choose a style before forking.</p></div>
        <Button variant={L?.items.length ? "secondary" : "primary"} onClick={gen} disabled={busy}>{busy ? (L?.status === "queued" ? "Queued: waits for the GPU" : <><Loader2 className="animate-spin" /> Generating…</>) : L?.items.length ? "Regenerate" : <><Sparkles /> Generate look previews</>}</Button>
      </div>
      {!L ? <Empty icon={<Sparkles />} title="No previews yet.">They take about a minute per look and wait for the GPU if a run is busy.</Empty> : (
        <div className="grid grid-cols-2 gap-3 md:grid-cols-3 xl:grid-cols-4">
          {tiles.map((t, i) => (
            <figure key={t.label} className="overflow-hidden rounded-xl border border-line bg-surface">
              <Img src={t.url} className="aspect-[3/4]" onClick={() => lb(tiles.map((x) => ({ url: x.url, title: x.label })), i)} />
              <figcaption className="flex items-center justify-between gap-2 px-3 py-2 text-xs">
                <span className="truncate text-ink-2">{t.label}</span>
                {t.look && <Button size="sm" variant="ghost" disabled={d.live} title={d.live ? "Available when the run is not running" : ""} onClick={() => onForkLook(t.look!)}><GitFork /> Fork</Button>}
              </figcaption>
            </figure>
          ))}
          {busy && ["stylized", "game", "anime3d", "clay", "chibi"].filter((k) => !L.items.some((x) => x.look === k)).map((k) => (
            <div key={k} className="grid aspect-[3/4] place-items-center rounded-xl border border-dashed border-line-strong text-xs text-ink-3"><span className="flex items-center gap-2"><Spinner /> waiting</span></div>
          ))}
        </div>
      )}
    </div>
  );
}

/* ---------------------------------------------------------------- Log */
export function LogTab({ lines }: { lines: string[] }) {
  const box = React.useRef<HTMLDivElement>(null);
  const stick = React.useRef(true);
  React.useEffect(() => { const b = box.current; if (b && stick.current) b.scrollTop = b.scrollHeight; }, [lines]);
  const cls = (l: string) => /\[review\] .*(YOU CHOSE|\buser (choose|accept|reject|redo)\b|\byou (accept|reject|redo|choose))/i.test(l) ? "-mx-2 rounded-md border-l-2 border-accent bg-accent/12 px-2 font-semibold text-[#e4dcff]" : /Traceback|Error|FAILED|failed/.test(l) ? "text-bad" : /^\S+ !!|Waiting/.test(l) ? "text-warn" : /--- stage|=== /.test(l) ? "font-semibold text-[#b8a9ff]" : /done in|picked|PASS|accept/i.test(l) ? "text-ok" : "text-ink-2";
  return (
    <div ref={box} onScroll={(e) => { const b = e.currentTarget; stick.current = b.scrollHeight - b.scrollTop - b.clientHeight < 30; }}
      className="h-[min(70vh,720px)] overflow-y-auto rounded-xl border border-line bg-black/40 p-4 font-mono text-[11.5px] leading-[1.65]">
      {lines.map((l, i) => { const m = l.match(/^(\d\d:\d\d:\d\d )(.*)$/); return <div key={i} className={cls(l)}>{m ? <><span className="text-ink-3/70">{m[1]}</span>{m[2]}</> : l}</div>; })}
    </div>
  );
}
