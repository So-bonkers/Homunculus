import * as React from "react";
import { Link, useLocation, useNavigate } from "react-router-dom";
import { motion } from "motion/react";
import { toast } from "sonner";
import { ArrowRight, GitFork, Library, Plus, Search, Square, Trash2, Wand2 } from "lucide-react";
import { api, useInvalidate, useRuns } from "@/lib/api";
import type { RunSummary } from "@/lib/types";
import { Button, Empty, Input, Progress, Segmented, Tip } from "@/components/ui";
import { Img, Stat, StatusPill } from "@/components/common";
import { ModelViewer } from "@/components/ModelViewer";
import { ForkDialog } from "@/features/dialogs/ForkDialog";
import { DeleteDialog } from "@/features/dialogs/DeleteDialog";
import { TIPS } from "@/lib/options";
import { ago, cn } from "@/lib/utils";

function Hero({ runs }: { runs: RunSummary[] | undefined }) {
  const withModel = runs?.filter((r) => r.model) ?? [];
  const hero = withModel.find((r) => r.status === "finished") ?? withModel[0];
  return (
    <section className="relative overflow-hidden border-b border-line">
      <div className="pointer-events-none absolute inset-0 bg-[radial-gradient(800px_400px_at_75%_40%,rgba(139,108,255,0.16),transparent_70%)]" />
      <div className="relative mx-auto grid max-w-7xl items-center gap-10 px-4 py-14 lg:grid-cols-[1.05fr_1fr] lg:px-6 lg:py-20">
        <motion.div initial={{ opacity: 0, y: 14 }} animate={{ opacity: 1, y: 0 }} transition={{ duration: 0.6, ease: [0.2, 0.8, 0.2, 1] }}>
          <div className="mb-5 inline-flex items-center gap-2 rounded-full border border-line-strong bg-white/4 px-3 py-1 text-xs text-ink-2">
            <span className="size-1.5 rounded-full bg-ok" /> Fully local · one 24 GB GPU · v1.6
          </div>
          <h1 className="text-5xl leading-[1.02] font-semibold tracking-[-0.035em] sm:text-6xl lg:text-7xl">
            Picture in.<br /><span className="text-gradient">Character out.</span>
          </h1>
          <p className="mt-6 max-w-xl text-[15px] leading-relaxed text-ink-2">
            One picture becomes a textured, rigged 3D character with a 52-bone skeleton, then dances whatever you film. Every stage runs on this machine; you, the judges, or nobody decides at each gate.
          </p>
          <div className="mt-8 flex flex-wrap gap-3">
            <Link to="/new"><Button variant="primary" size="lg"><Plus /> Start a run</Button></Link>
            <Link to="/library"><Button variant="outline" size="lg"><Library /> Animation library</Button></Link>
          </div>
          <div className="mt-10 flex gap-10">
            <Stat value="15" label="stages" /><Stat value="3" label="local judges" /><Stat value="52" label="bones" /><Stat value={runs?.length ?? "–"} label="runs" />
          </div>
        </motion.div>
        <motion.div initial={{ opacity: 0, scale: 0.97 }} animate={{ opacity: 1, scale: 1 }} transition={{ duration: 0.8, delay: 0.1 }} className="relative">
          <div className="absolute -inset-6 rounded-[2rem] bg-gradient-to-tr from-accent/25 via-transparent to-cyan/10 blur-2xl" />
          <ModelViewer url={hero?.model} hero toolbar={false} className="relative aspect-[4/5] w-full border border-line shadow-[0_30px_80px_-20px_rgba(0,0,0,0.8)] sm:aspect-square lg:aspect-[4/5]"
            emptyText="Your first character will appear here." />
          {hero && (
            <Link to={`/run/${encodeURIComponent(hero.name)}`} className="glass absolute bottom-4 left-4 flex items-center gap-2 rounded-full px-3 py-1.5 text-xs text-ink-2 hover:text-ink">
              <span className="font-medium text-ink">{hero.name}</span> · drag to turn <ArrowRight className="size-3" />
            </Link>
          )}
        </motion.div>
      </div>
    </section>
  );
}

function RunCard({ r, onFork, onDelete, i }: { r: RunSummary; onFork: () => void; onDelete: () => void; i: number }) {
  const inv = useInvalidate();
  const stop = async (e: React.MouseEvent) => {
    e.preventDefault();
    if (!confirm(`Stop "${r.name}"?\nIt can be resumed later by starting the same name again.`)) return;
    try { await api.stop(r.name); toast(`Stopping ${r.name}…`); inv(["runs"], ["live"]); } catch (er: any) { toast.error(er.message); }
  };
  const sub = r.live ? (r.current ? `Now: ${r.current}` : "starting…") : r.status === "finished" ? `Finished · ${r.done} of ${r.total || 15} stages` : r.current ? `Stopped at ${r.current}` : r.last || r.file;
  return (
    <motion.div initial={{ opacity: 0, y: 10 }} animate={{ opacity: 1, y: 0 }} transition={{ duration: 0.35, delay: Math.min(i, 12) * 0.03 }}>
      <Link to={`/run/${encodeURIComponent(r.name)}`} className={cn("group relative block overflow-hidden rounded-xl2 border border-line bg-surface transition duration-300 hover:-translate-y-0.5 hover:border-line-strong hover:shadow-[0_20px_50px_-20px_rgba(0,0,0,0.9)]", r.live && "border-accent/40 shadow-glow")}>
        <Img src={r.thumb} className="aspect-[4/5] w-full transition duration-500 group-hover:scale-[1.03]" />
        <div className="absolute inset-0 bg-gradient-to-t from-black/90 via-black/20 to-transparent" />
        <div className="absolute top-3 left-3"><StatusPill status={r.status} className="bg-black/60 backdrop-blur" /></div>
        <div className="absolute top-3 right-3 flex gap-1 opacity-0 transition group-hover:opacity-100">
          {r.live ? (
            <Tip content="Stop the run"><button onClick={stop} className="glass grid size-8 place-items-center rounded-lg text-bad hover:bg-bad/20"><Square className="size-3.5" /></button></Tip>
          ) : (
            <>
              <Tip content="Fork: restart from any stage"><button onClick={(e) => { e.preventDefault(); onFork(); }} className="glass grid size-8 place-items-center rounded-lg text-ink-2 hover:text-ink"><GitFork className="size-3.5" /></button></Tip>
              <Tip content="Delete"><button onClick={(e) => { e.preventDefault(); onDelete(); }} className="glass grid size-8 place-items-center rounded-lg text-ink-2 hover:text-bad"><Trash2 className="size-3.5" /></button></Tip>
            </>
          )}
        </div>
        <div className="absolute inset-x-0 bottom-0 p-4">
          <div className="flex items-baseline justify-between gap-2">
            <h3 className="truncate text-[15px] font-semibold tracking-tight">{r.name}</h3>
            <span className="shrink-0 font-mono text-[10px] text-ink-3">{ago(r.updated)}</span>
          </div>
          <p className="mt-0.5 truncate text-xs text-ink-2">{sub}</p>
          <Progress value={(r.done / (r.total || 15)) * 100} tone={r.status === "failed" ? "bad" : r.status === "finished" ? "ok" : "accent"} className="mt-3 h-1" />
        </div>
      </Link>
    </motion.div>
  );
}

export default function Home() {
  const { data: runs, isLoading } = useRuns();
  const [filter, setFilter] = React.useState("all");
  const [qs, setQs] = React.useState("");
  const [fork, setFork] = React.useState<string | null>(null);
  const [del, setDel] = React.useState<string | null>(null);
  const loc = useLocation(); const nav = useNavigate();
  const tipsRef = React.useRef<HTMLDivElement>(null);
  React.useEffect(() => { if (loc.pathname === "/tips" || loc.search.includes("tips")) setTimeout(() => tipsRef.current?.scrollIntoView({ behavior: "smooth" }), 100); }, [loc]);

  const list = (runs ?? []).filter((r) =>
    (filter === "all" || (filter === "active" && r.live) || (filter === "finished" && r.status === "finished") || (filter === "failed" && r.status === "failed")) &&
    (!qs || r.name.toLowerCase().includes(qs.toLowerCase())));
  const live = runs?.filter((r) => r.live) ?? [];

  return (
    <div>
      <Hero runs={runs} />
      <div className="mx-auto max-w-7xl px-4 py-12 lg:px-6">
        {live.length > 0 && (
          <section className="mb-12">
            <h2 className="mb-4 text-[11px] font-semibold tracking-[0.14em] text-ink-3 uppercase">Working now</h2>
            <div className="grid gap-3 md:grid-cols-2">
              {live.map((r) => (
                <button key={r.name} onClick={() => nav(`/run/${encodeURIComponent(r.name)}`)} className="panel flex items-center gap-4 p-3 text-left transition hover:border-accent/40">
                  <Img src={r.thumb} className="size-16 shrink-0 rounded-lg" />
                  <div className="min-w-0 flex-1">
                    <div className="flex items-center gap-2"><span className="truncate font-semibold">{r.name}</span><StatusPill status={r.status} /></div>
                    <div className="mt-1 truncate text-xs text-ink-2">{r.current ?? "starting…"}</div>
                    <Progress value={(r.done / (r.total || 15)) * 100} className="mt-2" />
                  </div>
                  <ArrowRight className="size-4 text-ink-3" />
                </button>
              ))}
            </div>
          </section>
        )}
        <section>
          <div className="mb-5 flex flex-wrap items-end justify-between gap-4">
            <div><h2 className="text-2xl font-semibold tracking-tight">Runs</h2><p className="mt-1 text-[13px] text-ink-3">Every character you have made on this machine.</p></div>
            <div className="flex items-center gap-2">
              <div className="relative"><Search className="absolute top-2.5 left-3 size-4 text-ink-3" /><Input value={qs} onChange={(e) => setQs(e.target.value)} placeholder="Find a run" className="w-48 pl-9" /></div>
              <Segmented value={filter} onValueChange={setFilter} options={[{ value: "all", label: "All" }, { value: "active", label: "Active" }, { value: "finished", label: "Finished" }, { value: "failed", label: "Failed" }]} />
            </div>
          </div>
          {isLoading ? (
            <div className="grid grid-cols-2 gap-4 md:grid-cols-3 xl:grid-cols-4">{Array.from({ length: 4 }).map((_, i) => <div key={i} className="aspect-[4/5] rounded-xl2 skeleton" />)}</div>
          ) : list.length ? (
            <div className="grid grid-cols-2 gap-4 md:grid-cols-3 xl:grid-cols-4">
              {list.map((r, i) => <RunCard key={r.name} r={r} i={i} onFork={() => setFork(r.name)} onDelete={() => setDel(r.name)} />)}
            </div>
          ) : (
            <Empty icon={<Wand2 />} title={runs?.length ? "Nothing here." : "No runs yet."} action={!runs?.length && <Link to="/new"><Button variant="primary"><Plus /> Start your first run</Button></Link>}>
              {!runs?.length && "Drop a picture of a character and watch it become a rigged, animated 3D model."}
            </Empty>
          )}
        </section>
        <section ref={tipsRef} className="mt-20 scroll-mt-20">
          <h2 className="text-2xl font-semibold tracking-tight">Get better results</h2>
          <p className="mt-1 mb-6 text-[13px] text-ink-3">What helps the pipeline most.</p>
          <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-5">
            {TIPS.map((t) => (
              <div key={t.title} className="panel p-4">
                <div className="mb-2 text-xl">{t.icon}</div>
                <h3 className="text-[14px] font-semibold">{t.title}</h3>
                <p className="mt-1.5 text-[13px] leading-relaxed text-ink-3">{t.text}</p>
              </div>
            ))}
          </div>
        </section>
        <footer className="mt-16 border-t border-line pt-6 text-xs text-ink-3">Homunculus · everything runs on this machine · <a className="hover:text-ink-2" href="https://github.com/So-bonkers/Homunculus" target="_blank" rel="noreferrer">GitHub</a></footer>
      </div>
      {fork && <ForkDialog run={fork} open onOpenChange={(v) => !v && setFork(null)} />}
      {del && <DeleteDialog run={del} open onOpenChange={(v) => !v && setDel(null)} />}
    </div>
  );
}
