import * as React from "react";
import { Box, Bone, Camera, Expand, Grid3x3, Orbit, RotateCcw, Shrink, Sparkles } from "lucide-react";
import { Viewer, type LoadResult, type ViewerSettings } from "@/viewer/Viewer";
import { Tip } from "@/components/ui";
import { cn } from "@/lib/utils";

export interface ModelViewerHandle { viewer: Viewer | null }

interface Props {
  url: string | null | undefined;
  hero?: boolean;
  className?: string;
  /** show the floating toolbar (clay, wireframe, bones, turntable, grid, views, screenshot, fullscreen) */
  toolbar?: boolean;
  settings?: ViewerSettings;
  onLoaded?: (r: LoadResult | undefined, v: Viewer) => void;
  onViewer?: (v: Viewer | null) => void;
  children?: React.ReactNode;          // overlays drawn over the canvas (hints, tool panels)
  toolbarExtra?: React.ReactNode;
  emptyText?: string;
}

export const ModelViewer = React.forwardRef<ModelViewerHandle, Props>(function ModelViewer(
  { url, hero, className, toolbar = true, settings, onLoaded, onViewer, children, toolbarExtra, emptyText }, ref,
) {
  const host = React.useRef<HTMLDivElement>(null);
  const wrap = React.useRef<HTMLDivElement>(null);
  const vRef = React.useRef<Viewer | null>(null);
  const [progress, setProgress] = React.useState<number | null>(null);
  const [error, setError] = React.useState<string | null>(null);
  const [info, setInfo] = React.useState<{ tris: number; skinned: boolean; bones: number } | null>(null);
  const [opt, setOpt] = React.useState({ clay: false, wire: false, bones: false, rotate: settings?.rotate ?? true, grid: settings?.grid ?? true });
  const [full, setFull] = React.useState(false);

  React.useImperativeHandle(ref, () => ({ get viewer() { return vRef.current; } }), []);

  React.useEffect(() => {
    if (!host.current) return;
    const v = new Viewer(host.current, { hero, onProgress: (p) => setProgress(p), onInfo: setInfo });
    vRef.current = v; onViewer?.(v);
    return () => { v.dispose(); vRef.current = null; onViewer?.(null); };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [hero]);

  React.useEffect(() => {
    const v = vRef.current; if (!v || !url) return;
    let alive = true; setError(null); setProgress(0);
    v.load(url).then((r) => {
      if (!alive) return; setProgress(null);
      v.set({ ...opt, ...settings, rotate: r && r.clips.length ? false : (settings?.rotate ?? opt.rotate) });
      onLoaded?.(r, v);
    }).catch(() => { if (alive) { setError("Could not load this model."); setProgress(null); } });
    return () => { alive = false; };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [url]);

  React.useEffect(() => { if (settings) vRef.current?.set(settings); }, [settings]);

  const toggle = (k: keyof typeof opt) => setOpt((o) => { const n = { ...o, [k]: !o[k] }; vRef.current?.set({ [k]: n[k] }); return n; });

  React.useEffect(() => {
    const on = () => setFull(document.fullscreenElement === wrap.current);
    document.addEventListener("fullscreenchange", on); return () => document.removeEventListener("fullscreenchange", on);
  }, []);

  const shot = () => {
    const v = vRef.current; if (!v) return;
    const a = document.createElement("a"); a.href = v.screenshot(); a.download = "homunculus.png"; a.click();
  };

  const btn = (on: boolean) => cn("grid size-8 place-items-center rounded-lg text-ink-2 transition hover:bg-white/8 hover:text-ink [&_svg]:size-4", on && "bg-accent/20 text-[#d4c9ff]");

  return (
    <div ref={wrap} className={cn("relative overflow-hidden rounded-xl2 bg-[radial-gradient(ellipse_at_50%_35%,#1a1830_0%,#0d0e14_55%,#08090b_100%)]", full && "rounded-none", className)}>
      <div ref={host} className="absolute inset-0" />
      {!url && (
        <div className="absolute inset-0 grid place-items-center text-center text-[13px] text-ink-3">
          <div className="flex flex-col items-center gap-3"><Box className="size-8 opacity-50" /><span className="max-w-xs">{emptyText ?? "No 3D model yet."}</span></div>
        </div>
      )}
      {progress !== null && url && (
        <div className="absolute inset-0 grid place-items-center bg-canvas/40 backdrop-blur-[2px]">
          <div className="flex w-48 flex-col items-center gap-3">
            <div className="relative size-12"><div className="absolute inset-0 animate-spin rounded-full border-2 border-white/10 border-t-accent" /><Sparkles className="absolute inset-0 m-auto size-5 text-accent" /></div>
            <div className="h-1 w-full overflow-hidden rounded-full bg-white/10"><div className="h-full rounded-full bg-gradient-to-r from-accent to-accent-2 transition-all" style={{ width: `${Math.round(progress * 100)}%` }} /></div>
            <span className="font-mono text-[11px] text-ink-3">loading model · {Math.round(progress * 100)}%</span>
          </div>
        </div>
      )}
      {error && <div className="absolute inset-0 grid place-items-center text-[13px] text-bad">{error}</div>}
      {info && !hero && (
        <div className="pointer-events-none absolute top-3 left-3 rounded-lg bg-black/40 px-2 py-1 font-mono text-[10.5px] text-ink-3 backdrop-blur">
          {info.tris.toLocaleString()} tris{info.skinned ? ` · ${info.bones} bones` : ""}
        </div>
      )}
      {children}
      {toolbar && !hero && url && (
        <div className="glass absolute bottom-3 left-1/2 flex max-w-[calc(100%-16px)] -translate-x-1/2 items-center gap-0.5 overflow-x-auto rounded-xl p-1 shadow-2xl [scrollbar-width:none]">
          {toolbarExtra}
          {toolbarExtra && <span className="mx-1 h-5 w-px bg-white/10" />}
          <Tip content="Clay: the shape without its texture"><button className={btn(opt.clay)} onClick={() => toggle("clay")}><Sparkles /></button></Tip>
          <Tip content="Wireframe"><button className={btn(opt.wire)} onClick={() => toggle("wire")}><Box /></button></Tip>
          {info?.skinned && <Tip content="Bones"><button className={btn(opt.bones)} onClick={() => toggle("bones")}><Bone /></button></Tip>}
          <Tip content="Turntable"><button className={btn(opt.rotate)} onClick={() => toggle("rotate")}><Orbit /></button></Tip>
          <Tip content="Floor grid"><button className={btn(opt.grid)} onClick={() => toggle("grid")}><Grid3x3 /></button></Tip>
          <span className="mx-1 h-5 w-px bg-white/10" />
          {[["F", 0, "Front"], ["R", 90, "Right side"], ["B", 180, "Back"], ["L", 270, "Left side"]].map(([l, az, t]) => (
            <Tip key={l as string} content={t as string}><button className={cn(btn(false), "font-mono text-[11px]")} onClick={() => { vRef.current?.set({ rotate: false }); setOpt((o) => ({ ...o, rotate: false })); vRef.current?.view(az as number); }}>{l}</button></Tip>
          ))}
          <span className="mx-1 h-5 w-px bg-white/10" />
          <Tip content="Reframe"><button className={btn(false)} onClick={() => vRef.current?.reset()}><RotateCcw /></button></Tip>
          <Tip content="Save a picture"><button className={btn(false)} onClick={shot}><Camera /></button></Tip>
          <Tip content={full ? "Exit full screen" : "Full screen"}><button className={btn(full)} onClick={() => (full ? document.exitFullscreen() : wrap.current?.requestFullscreen())}>{full ? <Shrink /> : <Expand />}</button></Tip>
        </div>
      )}
    </div>
  );
});
