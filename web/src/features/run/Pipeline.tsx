import * as React from "react";
import { motion } from "motion/react";
import { Check, Loader2, Minus, X, Hand } from "lucide-react";
import type { Stage } from "@/lib/types";
import { STAGE_META } from "@/lib/stages";
import { cn, duration } from "@/lib/utils";

const ring: Record<string, string> = {
  done: "border-ok/50 bg-ok/12 text-ok", running: "border-accent bg-accent/20 text-[#d9ceff]", waiting: "border-warn bg-warn/15 text-warn",
  failed: "border-bad/60 bg-bad/15 text-bad", stopped: "border-dashed border-white/20 text-ink-3", skipped: "border-dashed border-white/10 text-ink-3/50", pending: "border-white/10 text-ink-3",
};

/** The 15 stages as a horizontal rail: status, time, and the selected stage. Retry gates (pick, shape check, rig check) carry a small loop mark. */
export function Pipeline({ stages, selected, onSelect }: { stages: Stage[]; selected: string | null; onSelect: (k: string | null) => void }) {
  const scroller = React.useRef<HTMLDivElement>(null);
  const active = stages.find((s) => s.status === "running" || s.status === "waiting")?.key;
  React.useEffect(() => {
    if (!active || !scroller.current) return;
    const el = scroller.current.querySelector<HTMLElement>(`[data-stage="${active}"]`);
    el?.scrollIntoView({ behavior: "smooth", inline: "center", block: "nearest" });
  }, [active]);
  return (
    <div ref={scroller} className="relative overflow-x-auto [scrollbar-width:none]" data-tour="pipeline">
      <div className="flex min-w-[1040px] items-start px-1 pt-1">
        {stages.map((s, i) => {
          const M = STAGE_META[s.key]; const Icon = M?.icon ?? Minus; const st = s.status;
          const next = stages[i + 1];
          const flowDone = (st === "done" || st === "skipped") && next && (next.status === "done" || next.status === "skipped");
          const flowLive = (st === "done" || st === "skipped") && next && (next.status === "running" || next.status === "waiting");
          return (
            <React.Fragment key={s.key}>
              <button data-stage={s.key} onClick={() => onSelect(selected === s.key ? null : s.key)} title={M?.blurb}
                className={cn("group flex w-[70px] shrink-0 flex-col items-center gap-1.5 rounded-xl px-1 py-2 transition", selected === s.key ? "bg-white/6" : "hover:bg-white/[0.03]")}>
                <div className={cn("relative grid size-10 place-items-center rounded-xl border transition", ring[st] ?? ring.pending, st === "running" && "shadow-glow")}>
                  {st === "running" && <span className="absolute inset-0 animate-ping rounded-xl border border-accent/40" />}
                  {st === "done" ? <Check className="size-4" /> : st === "failed" ? <X className="size-4" /> : st === "waiting" ? <Hand className="size-4" /> : st === "running" ? <Loader2 className="size-4 animate-spin" /> : <Icon className="size-4" />}
                  {["pick", "mesh_check", "rig_check"].includes(s.key) && <span className="absolute -top-1.5 -right-1.5 grid size-4 place-items-center rounded-full border border-line-strong bg-raised text-[8px] text-ink-3">↺</span>}
                </div>
                <div className={cn("text-center text-[11px] leading-tight", st === "pending" || st === "skipped" ? "text-ink-3" : "text-ink")}>{s.label}</div>
                <div className="h-3 font-mono text-[9.5px] text-ink-3">{st === "waiting" ? <span className="text-warn">your call</span> : s.seconds ? duration(s.seconds) : st === "skipped" ? "skipped" : ""}</div>
              </button>
              {next && (
                <div className="relative mt-[26px] h-0.5 min-w-2 flex-1 overflow-hidden rounded-full bg-white/8">
                  {flowDone && <div className="absolute inset-0 bg-ok/50" />}
                  {flowLive && <motion.div className="absolute inset-y-0 w-3 rounded-full bg-accent" animate={{ x: [-12, 20] }} transition={{ repeat: Infinity, duration: 1.1, ease: "easeInOut" }} />}
                </div>
              )}
            </React.Fragment>
          );
        })}
      </div>
    </div>
  );
}
