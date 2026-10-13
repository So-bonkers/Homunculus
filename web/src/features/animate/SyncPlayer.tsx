import * as React from "react";
import { Columns2, Download, Film, Pause, Play, Repeat, Rows2, Volume2, VolumeX } from "lucide-react";
import { ModelViewer } from "@/components/ModelViewer";
import type { Viewer } from "@/viewer/Viewer";
import { Button, Segmented, Tip } from "@/components/ui";
import { cn, duration } from "@/lib/utils";

const STILL = { rotate: false };

/** The reference video and the character dancing it, played together. The video is the clock: every frame the 3D clip is posed at the video's time, so play, pause,
 *  scrubbing and the speed move both, and the 3D view can still be orbited while it plays. The reference is the same range of the video the motion was read from. */
export function SyncPlayer({ model, reference, compare, preview, fbx, className }: {
  model: string | null | undefined; reference: string; compare?: string | null; preview?: string | null; fbx?: string | null; className?: string;
}) {
  const vid = React.useRef<HTMLVideoElement>(null);
  const [v, setV] = React.useState<Viewer | null>(null);
  const [ready, setReady] = React.useState(false);
  const [playing, setPlaying] = React.useState(false);
  const [t, setT] = React.useState(0);
  const [len, setLen] = React.useState(0);
  const [muted, setMuted] = React.useState(false);
  const [loop, setLoop] = React.useState(true);
  const [speed, setSpeed] = React.useState("1");
  const [stack, setStack] = React.useState(false);
  const [ar, setAr] = React.useState(16 / 9);        // the video's width / height: the panes take its shape

  // the video drives the clip (one rAF loop, also while paused so a scrub poses the character)
  React.useEffect(() => {
    if (!v) return;
    let raf = 0;
    const tick = () => { raf = requestAnimationFrame(tick); const e = vid.current; if (e && e.readyState >= 1) { v.setTime(e.currentTime); setT(e.currentTime); } };
    raf = requestAnimationFrame(tick); return () => cancelAnimationFrame(raf);
  }, [v]);

  React.useEffect(() => { if (vid.current) vid.current.playbackRate = +speed; }, [speed]);

  const toggle = () => { const e = vid.current; if (!e) return; if (e.paused) { if (e.ended || e.currentTime >= len - 0.05) e.currentTime = 0; void e.play(); } else e.pause(); };
  const seek = (s: number) => { const e = vid.current; if (e) e.currentTime = Math.max(0, Math.min(s, len)); };

  React.useEffect(() => {
    const k = (ev: KeyboardEvent) => {
      if ((ev.target as HTMLElement)?.closest("input,textarea,select,[contenteditable]")) return;
      if (ev.key === " " && vid.current) { ev.preventDefault(); toggle(); }
      if (ev.key === "ArrowLeft") seek((vid.current?.currentTime ?? 0) - 1 / 30);
      if (ev.key === "ArrowRight") seek((vid.current?.currentTime ?? 0) + 1 / 30);
    };
    addEventListener("keydown", k); return () => removeEventListener("keydown", k);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [len]);

  // the viewer is built once per model (the time readout re-renders this component every frame)
  const viewer = React.useMemo(() => (
    <ModelViewer url={model} onViewer={setV} onLoaded={(_, vv) => { vv.set({ play: false, rotate: false }); if (vid.current) vv.setTime(vid.current.currentTime); }}
      className="h-full rounded-none" settings={STILL} />
  ), [model]);

  const pane = "relative overflow-hidden rounded-xl border border-line bg-black";
  const label = (s: string) => <span className="pointer-events-none absolute top-3 left-3 z-10 rounded-md bg-black/55 px-2 py-0.5 text-[11px] font-medium text-ink-2 backdrop-blur">{s}</span>;

  return (
    <div className={cn("grid gap-3", className)} data-tour="sync">
      <div className={cn("grid gap-3", stack ? "grid-cols-1" : ar > 1.2 ? "md:grid-cols-[1.35fr_1fr]" : "md:grid-cols-2")}>
        <div className={cn(pane, "grid max-h-[64vh] w-full place-items-center md:min-h-[300px]")} style={{ aspectRatio: ar }}>
          {label("Reference")}
          <video ref={vid} src={reference} playsInline preload="auto" muted={muted} loop={loop} className="h-full w-full object-contain"
            onLoadedMetadata={(e) => { const el = e.currentTarget; setLen(el.duration); if (el.videoWidth && el.videoHeight) setAr(el.videoWidth / el.videoHeight); setReady(true); }} onPlay={() => setPlaying(true)} onPause={() => setPlaying(false)} onEnded={() => setPlaying(false)} onClick={toggle} />
        </div>
        <div className={cn(pane, "h-[min(60vh,440px)] md:h-auto md:min-h-[300px]", stack && "md:h-[min(56vh,560px)]")}>
          {label("Your character")}
          {viewer}
        </div>
      </div>

      <div className="panel flex flex-wrap items-center gap-3 px-3 py-2">
        <Button variant="primary" size="icon" onClick={toggle} disabled={!ready} aria-label={playing ? "Pause" : "Play"}>{playing ? <Pause /> : <Play />}</Button>
        <span className="w-24 shrink-0 font-mono text-[11.5px] text-ink-2 tabular-nums">{duration(t)} / {duration(len)}</span>
        <input type="range" min={0} max={Math.max(len, 0.01)} step={1 / 30} value={t} onChange={(e) => seek(+e.target.value)} className="min-w-40 flex-1 accent-[var(--color-accent)]" aria-label="Time" />
        <Segmented value={speed} onValueChange={setSpeed} options={[{ value: "0.25", label: "¼×" }, { value: "0.5", label: "½×" }, { value: "1", label: "1×" }]} />
        <Tip content={loop ? "Looping" : "Play once"}><Button variant="ghost" size="icon" onClick={() => setLoop(!loop)} className={cn(loop && "text-accent")}><Repeat /></Button></Tip>
        <Tip content={muted ? "Sound off" : "Sound on"}><Button variant="ghost" size="icon" onClick={() => setMuted(!muted)}>{muted ? <VolumeX /> : <Volume2 />}</Button></Tip>
        <Tip content={stack ? "Side by side" : "One above the other"}><Button variant="ghost" size="icon" onClick={() => setStack(!stack)} className="hidden md:inline-flex">{stack ? <Columns2 /> : <Rows2 />}</Button></Tip>
      </div>

      {(model || fbx || preview || compare) && (
        <div className="flex flex-wrap items-center gap-2">
          {model && <a href={model} download><Button size="sm"><Download /> GLB</Button></a>}
          {fbx && <a href={fbx} download><Button size="sm"><Download /> FBX</Button></a>}
          {preview && <a href={preview} download><Button size="sm"><Film /> Rendered preview</Button></a>}
          {compare && <a href={compare} download><Button size="sm"><Columns2 /> Side-by-side MP4</Button></a>}
          <span className="ml-auto text-[11px] text-ink-3">Space plays and pauses · ← → step one frame</span>
        </div>
      )}
    </div>
  );
}
