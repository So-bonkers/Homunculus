import * as React from "react";
import { motion } from "motion/react";
import { toast } from "sonner";
import { Box, Check, Hand, Maximize2, RefreshCw, ThumbsDown, ThumbsUp } from "lucide-react";
import { api, useInvalidate } from "@/lib/api";
import type { Review } from "@/lib/types";
import { Badge, Button, Textarea } from "@/components/ui";
import { useLightbox } from "@/components/common";
import { GATE_NAME } from "@/lib/stages";
import { cn, duration } from "@/lib/utils";

function Countdown({ left, total }: { left: number; total: number }) {
  const r = 26, c = 2 * Math.PI * r, f = Math.max(0, Math.min(1, left / Math.max(total, 1)));
  return (
    <div className="relative size-16">
      <svg viewBox="0 0 64 64" className="size-16 -rotate-90"><circle cx="32" cy="32" r={r} fill="none" stroke="rgba(255,255,255,.08)" strokeWidth="5" />
        <circle cx="32" cy="32" r={r} fill="none" stroke={f > 0.25 ? "var(--color-warn)" : "var(--color-bad)"} strokeWidth="5" strokeLinecap="round" strokeDasharray={c} strokeDashoffset={c * (1 - f)} className="transition-[stroke-dashoffset] duration-1000 ease-linear" /></svg>
      <span className="absolute inset-0 grid place-items-center font-mono text-xs">{left > 0 ? duration(left) : "…"}</span>
    </div>
  );
}

export function ReviewPanel({ run, r, now, onInspect }: { run: string; r: Review; now: number; onInspect?: () => void }) {
  const lb = useLightbox(); const inv = useInvalidate();
  const sig = JSON.stringify([r.gate, r.opened, r.images]);
  const [sel, setSel] = React.useState<number>(0);
  const [notes, setNotes] = React.useState("");
  const [sent, setSent] = React.useState<string | null>(null);
  React.useEffect(() => { setSel(0); }, [sig]);
  const done = sent === sig;
  const isLook = r.kind === "look";
  const send = async (action: string, choice: number) => {
    setSent(sig);
    try { await api.review(run, r.gate, action, choice, notes.trim()); setNotes(""); toast.success("Sent. The run continues in a moment."); inv(["run", run]); }
    catch (e: any) { setSent(null); toast.error(e.message || "Could not reach the server."); }
  };
  const left = r.opened ? r.grace - (now - r.opened) : r.grace;
  const items = r.images.map((u, i) => ({ url: u, title: r.captions[i] || `#${i + 1}` }));
  const many = r.images.length >= 5;

  return (
    <motion.section initial={{ opacity: 0, y: -8 }} animate={{ opacity: 1, y: 0 }} data-tour="review"
      className="relative overflow-hidden rounded-xl2 border border-warn/40 bg-[linear-gradient(180deg,rgba(251,191,36,0.07),rgba(251,191,36,0.01))] p-5 shadow-[0_0_0_1px_rgba(251,191,36,0.1),0_20px_60px_-30px_rgba(251,191,36,0.5)]">
      <div className="mb-4 flex flex-wrap items-start justify-between gap-4">
        <div className="min-w-0">
          <div className="mb-1 flex items-center gap-2 text-[11px] font-semibold tracking-[0.14em] text-warn uppercase"><Hand className="size-3.5" /> Your call · {GATE_NAME[r.kind] ?? GATE_NAME[r.gate] ?? r.gate}</div>
          <h2 className="text-xl font-semibold tracking-tight">{r.title}</h2>
          {r.verdict && <p className="mt-1 text-[13px] text-ink-2"><b className="text-ink">Judges:</b> {r.verdict}</p>}
        </div>
        {r.manual || !r.grace ? (
          <Badge tone="warn">{isLook ? "pick a look · no time limit" : r.you_judge ? "you are the judge" : /voting/.test(r.verdict) ? "judges voting · you can choose now" : "waiting for you"}</Badge>
        ) : <Countdown left={left} total={r.grace} />}
      </div>
      <div className={cn("grid gap-3", many ? "grid-cols-2 md:grid-cols-3 xl:grid-cols-5" : "grid-cols-1 md:grid-cols-2 xl:grid-cols-3")}>
        {r.images.map((u, i) => {
          const k = i + 1; const on = r.choose && sel === k;
          return (
            <div key={u} onClick={() => (r.choose ? setSel(k) : lb(items, i))}
              className={cn("group relative cursor-pointer overflow-hidden rounded-xl border bg-black/30 transition", on ? "border-accent shadow-glow" : "border-line hover:border-white/20")}>
              <img src={u} className="aspect-[4/3] w-full object-contain" loading="lazy" />
              <span className="absolute top-2 left-2 grid size-6 place-items-center rounded-md bg-black/60 font-mono text-[11px]">{k}</span>
              {r.choose && r.judge_best === k && <span className="absolute top-2 left-10"><Badge tone="accent">Judges' pick</Badge></span>}
              {on && <span className="absolute top-2 right-11 grid size-6 place-items-center rounded-full bg-accent text-white"><Check className="size-3.5" /></span>}
              <button onClick={(e) => { e.stopPropagation(); lb(items, i); }} className="absolute top-2 right-2 grid size-7 place-items-center rounded-md bg-black/60 opacity-0 transition group-hover:opacity-100"><Maximize2 className="size-3.5" /></button>
              {r.captions[i] && <div className="border-t border-line px-3 py-2 text-xs text-ink-2">{r.captions[i]}</div>}
            </div>
          );
        })}
      </div>
      <Textarea value={notes} onChange={(e) => setNotes(e.target.value)} disabled={done} className="mt-4 min-h-14" placeholder="Your observations (optional): added to the next redraw prompt and shown to the judges" />
      <div className="mt-3 flex flex-wrap items-center gap-2">
        {isLook ? (
          <>
            <Button variant="primary" disabled={!sel || done} onClick={() => send("choose", sel)}><Check /> {sel ? `Use ${r.captions[sel - 1] || "this look"}` : "Use this look"}</Button>
            <Button variant="secondary" disabled={done} onClick={() => send("redo", 0)}><RefreshCw /> Redraw all looks</Button>
          </>
        ) : r.choose && r.images.length === 1 ? (
          <>
            <Button variant="primary" disabled={done} onClick={() => send("choose", 1)}><Check /> Use this</Button>
            <Button variant="secondary" disabled={done} onClick={() => send("redo", 0)}><RefreshCw /> {r.gate === "pick" ? "Try another redraw" : "Try another shape"}</Button>
            {!r.you_judge && <Button variant="ghost" disabled={done} onClick={() => send("none", 0)}>Keep judges' decision</Button>}
          </>
        ) : r.choose ? (
          <>
            <Button variant="primary" disabled={!sel || done} onClick={() => send("choose", sel)}><Check /> {sel ? `Use #${sel}` : "Use selected"}</Button>
            <Button variant="secondary" disabled={!r.judge_best || done} onClick={() => send("choose", r.judge_best)}>Keep judges' pick{r.judge_best ? ` (#${r.judge_best})` : ""}</Button>
            <Button variant="danger" disabled={done} onClick={() => send("redo", 0)}><RefreshCw /> {r.gate === "pick" ? "Redraw again" : "Make new candidates"}</Button>
          </>
        ) : (
          <>
            <Button variant="success" disabled={done} onClick={() => send("accept", 0)}><ThumbsUp /> Accept & continue</Button>
            <Button variant="danger" disabled={done} onClick={() => send("reject", 0)}><ThumbsDown /> Reject & retry</Button>
            {!r.you_judge && <Button variant="ghost" disabled={done} onClick={() => send("none", 0)}>Keep judges' decision</Button>}
          </>
        )}
        {r.gate === "mesh_check" && onInspect && <Button variant="ghost" onClick={onInspect}><Box /> Inspect in 3D</Button>}
        {done && <span className="ml-1 text-[13px] text-ok">Sent. The run continues in a moment.</span>}
      </div>
    </motion.section>
  );
}
