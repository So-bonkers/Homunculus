import * as React from "react";
import { createPortal } from "react-dom";
import { ChevronLeft, ChevronRight, X } from "lucide-react";
import { Badge, Dot } from "@/components/ui";
import { RUN_STATUS_LABEL } from "@/lib/stages";
import { cn } from "@/lib/utils";

export function StatusPill({ status, className }: { status: string; className?: string }) {
  const tone = { running: "accent", waiting: "warn", finished: "ok", failed: "bad", stopped: "neutral", queued: "neutral", done: "ok" }[status] as any || "neutral";
  const dot = { running: "run", waiting: "warn", finished: "ok", failed: "bad", stopped: "neutral", done: "ok" }[status] as any || "neutral";
  return (
    <Badge tone={tone} className={className}>
      <Dot tone={dot} pulse={status === "running" || status === "waiting"} />
      {RUN_STATUS_LABEL[status] ?? status}
    </Badge>
  );
}

/* ---------------------------------------------------------------- Lightbox (global) */
type LBItem = { url: string; title?: string };
const LBCtx = React.createContext<(items: LBItem[], index: number) => void>(() => {});
export const useLightbox = () => React.useContext(LBCtx);

export function LightboxProvider({ children }: { children: React.ReactNode }) {
  const [state, setState] = React.useState<{ items: LBItem[]; i: number } | null>(null);
  const open = React.useCallback((items: LBItem[], i: number) => setState({ items, i }), []);
  React.useEffect(() => {
    if (!state) return;
    const k = (e: KeyboardEvent) => {
      if (e.key === "Escape") setState(null);
      if (e.key === "ArrowRight") setState((s) => s && { ...s, i: (s.i + 1) % s.items.length });
      if (e.key === "ArrowLeft") setState((s) => s && { ...s, i: (s.i - 1 + s.items.length) % s.items.length });
    };
    addEventListener("keydown", k); return () => removeEventListener("keydown", k);
  }, [state]);
  const cur = state ? state.items[state.i] : null;
  return (
    <LBCtx.Provider value={open}>
      {children}
      {state && cur && createPortal(
        <div className="fixed inset-0 z-[60] flex flex-col bg-black/90 backdrop-blur-md" onClick={() => setState(null)}>
          <div className="flex items-center justify-between px-5 py-3 text-[13px] text-ink-2" onClick={(e) => e.stopPropagation()}>
            <span className="truncate">{cur.title}</span>
            <div className="flex items-center gap-3">
              {state.items.length > 1 && <span className="font-mono text-[11px] text-ink-3">{state.i + 1} / {state.items.length}</span>}
              <button className="rounded-md p-1.5 hover:bg-white/10" onClick={() => setState(null)}><X className="size-5" /></button>
            </div>
          </div>
          <div className="relative flex min-h-0 flex-1 items-center justify-center px-16 pb-8">
            <img src={cur.url} alt="" className="max-h-full max-w-full rounded-lg object-contain shadow-2xl" onClick={(e) => e.stopPropagation()} />
            {state.items.length > 1 && (
              <>
                <button className="absolute left-4 rounded-full bg-white/8 p-2 hover:bg-white/15" onClick={(e) => { e.stopPropagation(); setState((s) => s && { ...s, i: (s.i - 1 + s.items.length) % s.items.length }); }}><ChevronLeft /></button>
                <button className="absolute right-4 rounded-full bg-white/8 p-2 hover:bg-white/15" onClick={(e) => { e.stopPropagation(); setState((s) => s && { ...s, i: (s.i + 1) % s.items.length }); }}><ChevronRight /></button>
              </>
            )}
          </div>
        </div>, document.body)}
    </LBCtx.Provider>
  );
}

export function Img({ src, className, alt = "", onClick }: { src?: string | null; className?: string; alt?: string; onClick?: () => void }) {
  const [ok, setOk] = React.useState(false);
  if (!src) return <div className={cn("bg-white/4", className)} />;
  return (
    <div className={cn("relative overflow-hidden bg-white/4", className, onClick && "cursor-zoom-in")} onClick={onClick}>
      {!ok && <div className="absolute inset-0 skeleton" />}
      <img src={src} alt={alt} loading="lazy" onLoad={() => setOk(true)} className={cn("h-full w-full object-cover transition-opacity duration-300", ok ? "opacity-100" : "opacity-0")} />
    </div>
  );
}

/** A big number with a caption, for the hero stats strip. */
export function Stat({ value, label }: { value: React.ReactNode; label: string }) {
  return (
    <div className="flex flex-col">
      <span className="font-mono text-2xl font-semibold tracking-tight text-ink">{value}</span>
      <span className="text-[11px] tracking-wide text-ink-3 uppercase">{label}</span>
    </div>
  );
}
