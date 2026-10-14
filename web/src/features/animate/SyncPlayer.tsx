import * as React from "react";
import { Columns2, Download, Film, Pause, Play, Repeat, Repeat1, Rows2, Volume2, VolumeX } from "lucide-react";
import { ModelViewer } from "@/components/ModelViewer";
import type { Viewer } from "@/viewer/Viewer";
import { Button, Segmented, Tip } from "@/components/ui";
import { cn, duration } from "@/lib/utils";

const STILL = { rotate: false };

/** The reference video and the character dancing it, played together. The video is the clock: every frame the 3D clip is posed at the video's time, so play, pause,
 *  scrubbing and the speed move both, and the 3D view can still be orbited while it plays. The reference is the same range of the video the motion was read from. */
export interface Wave { peaks: Float32Array; onsets: number[]; duration: number }
export interface PlayerCtx { t: number; len: number; seek: (s: number) => void; playing: boolean; toggle: () => void; wave: Wave | null | "none" }

/** The reference file's sound, decoded in the browser: a peak envelope for drawing and the moments where the sound jumps (hits). "none" if the file has no sound track (or it cannot be decoded). */
export function useAudioPeaks(url: string): Wave | null | "none" {
  const [d, setD] = React.useState<Wave | null | "none">(null);
  React.useEffect(() => {
    let alive = true; setD(null);
    (async () => {
      try {
        const buf = await (await fetch(url)).arrayBuffer(); const ctx = new AudioContext(); const a = await ctx.decodeAudioData(buf); void ctx.close();
        const ch = a.getChannelData(0); const N = 1400, per = Math.max(1, Math.floor(ch.length / N)); const peaks = new Float32Array(N);
        for (let i = 0; i < N; i++) { let m = 0; for (let j = i * per; j < Math.min(ch.length, (i + 1) * per); j++) { const x = Math.abs(ch[j]); if (x > m) m = x; } peaks[i] = m; }
        const mx = peaks.reduce((x, y) => Math.max(x, y), 0) || 1; for (let i = 0; i < N; i++) peaks[i] /= mx;
        const win = Math.max(1, Math.floor(a.sampleRate * 0.01)); const env: number[] = [];
        for (let i = 0; i + win < ch.length; i += win) { let s = 0; for (let j = i; j < i + win; j++) s += ch[j] * ch[j]; env.push(Math.sqrt(s / win)); }
        const flux = env.map((x, i) => Math.max(0, x - (env[i - 1] ?? x))); const m = flux.reduce((x, y) => x + y, 0) / flux.length; const sd = Math.sqrt(flux.reduce((x, y) => x + (y - m) ** 2, 0) / flux.length);
        const onsets: number[] = []; let last = -1;
        for (let i = 1; i < flux.length - 1; i++) if (flux[i] > m + 2 * sd && flux[i] >= flux[i - 1] && flux[i] >= flux[i + 1] && (i - last) * 0.01 > 0.12) { onsets.push(i * 0.01); last = i; }
        if (alive) setD({ peaks, onsets, duration: a.duration });
      } catch { if (alive) setD("none"); }
    })();
    return () => { alive = false; };
  }, [url]);
  return d;
}

export function SyncPlayer({ model, reference, compare, preview, fbx, className, children }: {
  model: string | null | undefined; reference: string; compare?: string | null; preview?: string | null; fbx?: string | null; className?: string;
  /** drawn under the transport bar with the player's clock (the hand timeline) */ children?: (c: PlayerCtx) => React.ReactNode;
}) {
  const vid = React.useRef<HTMLVideoElement>(null);
  const [v, setV] = React.useState<Viewer | null>(null);
  const [ready, setReady] = React.useState(false);
  const [playing, setPlaying] = React.useState(false);
  const [t, setT] = React.useState(0);
  const [len, setLen] = React.useState(0);
  const [muted, setMuted] = React.useState(false);
  const [vol, setVol] = React.useState(() => { try { const x = parseFloat(localStorage.getItem("homunculus_volume") || ""); return isFinite(x) ? Math.min(1, Math.max(0, x)) : 1; } catch { return 1; } });
  const [win, setWin] = React.useState<number | null>(null);        // a 2 s stretch looped at full speed, with sound
  const wave = useAudioPeaks(reference);
  const [loop, setLoop] = React.useState(true);
  const [speed, setSpeed] = React.useState("1");
  const [stack, setStack] = React.useState(false);
  const [ar, setAr] = React.useState(16 / 9);        // the video's width / height: the panes take its shape

  // the video drives the clip (one rAF loop, also while paused so a scrub poses the character)
  React.useEffect(() => {
    if (!v) return;
    let raf = 0;
    const tick = () => {
      raf = requestAnimationFrame(tick); const e = vid.current;
      if (e && e.readyState >= 1) { if (winRef.current !== null && (e.currentTime >= winRef.current + 2 || e.currentTime < winRef.current - 0.1)) e.currentTime = winRef.current; v.setTime(e.currentTime); setT(e.currentTime); }
    };
    raf = requestAnimationFrame(tick); return () => cancelAnimationFrame(raf);
  }, [v]);

  const winRef = React.useRef<number | null>(null); winRef.current = win;
  React.useEffect(() => { if (vid.current) vid.current.playbackRate = +speed; }, [speed]);
  React.useEffect(() => { const e = vid.current; if (e) { e.muted = muted; e.volume = vol; } try { localStorage.setItem("homunculus_volume", String(vol)); } catch { /* private mode */ } }, [muted, vol]);     // set on the element, not as a React prop (React only reads `muted` at mount)
  const toggleWin = () => { const e = vid.current; if (!e) return; if (win === null) { setWin(Math.max(0, Math.min(e.currentTime - 0.3, Math.max(0, len - 2)))); setSpeed("1"); if (e.paused) void e.play(); } else setWin(null); };

  const toggle = () => { const e = vid.current; if (!e) return; if (e.paused) { if (e.ended || e.currentTime >= len - 0.05) e.currentTime = 0; void e.play(); } else e.pause(); };
  const seek = (s: number) => { const e = vid.current; if (e) e.currentTime = Math.max(0, Math.min(s, len)); };

  React.useEffect(() => {
    const k = (ev: KeyboardEvent) => {
      if ((ev.target as HTMLElement)?.closest("input,textarea,select,[contenteditable]")) return;
      if (ev.key === " " && vid.current) { ev.preventDefault(); toggle(); }
      if (ev.key === "ArrowLeft") seek((vid.current?.currentTime ?? 0) - 1 / 30);
      if (ev.key === "ArrowRight") seek((vid.current?.currentTime ?? 0) + 1 / 30);
      if (ev.key === "o" || ev.key === "O") toggleWin(); else if (ev.key === "m" || ev.key === "M") setMuted((x) => !x);
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
          <video ref={vid} src={reference} playsInline preload="auto" loop={loop} className="h-full w-full object-contain"
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
        <Tip content={win === null ? "Loop 2 s from just before here, at full speed, with sound (O)" : "Stop looping (O)"}><Button variant="ghost" size="icon" onClick={toggleWin} className={cn(win !== null && "text-accent")}><Repeat1 /></Button></Tip>
        <div className="flex items-center gap-1.5">
          <Tip content={wave === "none" ? "This reference has no sound" : muted ? "Sound off (M)" : "Sound on (M)"}><Button variant="ghost" size="icon" onClick={() => setMuted(!muted)} className={cn(wave === "none" && "text-warn")}>{muted || vol === 0 || wave === "none" ? <VolumeX /> : <Volume2 />}</Button></Tip>
          <input type="range" min={0} max={1} step={0.05} value={muted ? 0 : vol} onChange={(e) => { const x = +e.target.value; setVol(x); setMuted(x === 0); }} className="w-20 accent-[var(--color-accent)]" aria-label="Volume" />
        </div>
        {wave === "none" && <span className="text-[11px] text-warn">no sound in this reference file</span>}
        <Tip content={stack ? "Side by side" : "One above the other"}><Button variant="ghost" size="icon" onClick={() => setStack(!stack)} className="hidden md:inline-flex">{stack ? <Columns2 /> : <Rows2 />}</Button></Tip>
      </div>

      {children?.({ t, len, seek, playing, toggle, wave })}

      {(model || fbx || preview || compare) && (
        <div className="flex flex-wrap items-center gap-2">
          {model && <a href={model} download><Button size="sm"><Download /> GLB</Button></a>}
          {fbx && <a href={fbx} download><Button size="sm"><Download /> FBX</Button></a>}
          {preview && <a href={preview} download><Button size="sm"><Film /> Rendered preview</Button></a>}
          {compare && <a href={compare} download><Button size="sm"><Columns2 /> Side-by-side MP4</Button></a>}
          <span className="ml-auto text-[11px] text-ink-3">Space plays and pauses · ← → step one frame · O loops 2 s with sound · M mutes</span>
        </div>
      )}
    </div>
  );
}
