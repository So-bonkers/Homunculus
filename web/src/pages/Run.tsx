import * as React from "react";
import { Link, useNavigate, useParams, useSearchParams } from "react-router-dom";
import { toast } from "sonner";
import {
  AlertTriangle, ArrowLeft, Box, Clapperboard, Download, FileArchive, FileText, GitFork, Images, Package, PackageCheck, PaintBucket, Palette, ScrollText, Square, Trash2, Wrench,
} from "lucide-react";
import { api, useInvalidate, useRun } from "@/lib/api";
import type { RunDetail } from "@/lib/types";
import { Badge, Button, Panel, SectionTitle, Spinner, Tabs, TabsContent, TabsList, TabsTrigger, Tip } from "@/components/ui";
import { StatusPill } from "@/components/common";
import { Pipeline } from "@/features/run/Pipeline";
import { ReviewPanel } from "@/features/run/ReviewPanel";
import { ActivityTab, AnimateTab, LogTab, LooksTab, ModelTab } from "@/features/run/Tabs";
import { RepairTab } from "@/features/run/RepairTab";
import { RetexTab } from "@/features/run/RetexTab";
import { ForkDialog } from "@/features/dialogs/ForkDialog";
import { AcceptDialog } from "@/features/dialogs/AcceptDialog";
import { DeleteDialog } from "@/features/dialogs/DeleteDialog";
import { FORK_LABEL, FORK_OF, REPAIR_STEP, STAGE_META, effectiveStages } from "@/lib/stages";
import { cn, duration } from "@/lib/utils";

function useClock(d: RunDetail | undefined) {
  const [now, setNow] = React.useState(Date.now() / 1000);
  React.useEffect(() => { const t = setInterval(() => setNow(Date.now() / 1000), 1000); return () => clearInterval(t); }, []);
  const offset = React.useRef(0);
  React.useEffect(() => { if (d?.now) offset.current = d.now - Date.now() / 1000; }, [d?.now]);
  return now + offset.current;
}

function Inspector({ d, sel, onFork }: { d: RunDetail; sel: string | null; onFork: (stage: string) => void }) {
  const s = sel ? d.stages.find((x) => x.key === sel) : null;
  const plan = Object.entries(d.plan || {}).filter(([, v]) => v != null && v !== "");
  return (
    <div className="grid content-start gap-4" data-tour="inspector">
      {s && (
        <Panel className="p-5">
          <SectionTitle>Stage {d.stages.indexOf(s) + 1} · {s.label}</SectionTitle>
          <p className="mb-3 text-[13px] text-ink-3">{STAGE_META[s.key]?.blurb}</p>
          <dl className="grid grid-cols-[90px_1fr] gap-y-1.5 text-[13px]">
            <dt className="text-ink-3">Status</dt><dd><StatusPill status={s.status} /></dd>
            <dt className="text-ink-3">Model</dt><dd className="text-ink-2">{s.model}</dd>
            {s.seconds ? <><dt className="text-ink-3">Time</dt><dd className="font-mono text-ink-2">{duration(s.seconds)}</dd></> : null}
            {s.peak_vram ? <><dt className="text-ink-3">Peak VRAM</dt><dd className="font-mono text-ink-2">{s.peak_vram} GB</dd></> : null}
            {s.note && <><dt className="text-ink-3">Result</dt><dd className="text-ink-2">{s.note}</dd></>}
          </dl>
          {!d.live && FORK_OF[s.key] && <Button size="sm" variant="secondary" className="mt-4" onClick={() => onFork(FORK_OF[s.key]!)}><GitFork /> Fork from {FORK_LABEL[FORK_OF[s.key]!]}</Button>}
        </Panel>
      )}
      {d.human_notes && <Panel className="p-5"><SectionTitle>Instructions in effect</SectionTitle><p className="text-[13px] text-ink-2">{d.human_notes}</p></Panel>}
      <Panel className="p-5">
        <SectionTitle>Downloads</SectionTitle>
        <div className="grid gap-1.5">
          {d.zip && <a href={d.zip} download className="flex items-center gap-3 rounded-lg px-2 py-2 text-[13px] hover:bg-white/5"><FileArchive className="size-4 text-accent" /><span className="flex-1">Mixamo zip</span><span className="text-[11px] text-ink-3">OBJ + texture</span></a>}
          {d.files.map((f) => (
            <a key={f.url} href={f.url} download className="flex items-center gap-3 rounded-lg px-2 py-2 text-[13px] hover:bg-white/5">
              {/\.(md|txt)$/i.test(f.name) ? <FileText className="size-4 text-ink-3" /> : <Box className="size-4 text-ink-3" />}
              <span className="flex-1 truncate">{f.label}</span><Download className="size-3.5 text-ink-3" />
            </a>
          ))}
          {!d.zip && !d.files.length && <p className="text-[13px] text-ink-3">Nothing to download yet.</p>}
        </div>
      </Panel>
      {!!plan.length && (
        <Panel className="p-5">
          <SectionTitle>What the planner saw</SectionTitle>
          <dl className="grid gap-2 text-[13px]">
            {plan.map(([k, v]) => <div key={k}><dt className="text-[11px] tracking-wide text-ink-3 uppercase">{k}</dt><dd className="text-ink-2">{Array.isArray(v) ? v.join(", ") : typeof v === "object" ? JSON.stringify(v) : String(v)}</dd></div>)}
          </dl>
        </Panel>
      )}
      <Panel className="p-5">
        <SectionTitle>Options</SectionTitle>
        <div className="flex flex-wrap gap-1.5">
          {d.options.outfit && <Badge>outfit · {d.options.outfit}</Badge>}
          {d.options.review && <Badge>review · {d.options.review}{d.options.review === "override" ? ` · ${d.options.grace} s` : ""}</Badge>}
          <Badge>style · {d.options.style || "auto"}</Badge>
          {d.options.look && <Badge>look · {d.options.look}</Badge>}
          {d.options.rigger && <Badge>rigger · {d.options.rigger}</Badge>}
          {d.options.texture && <Badge>texture · {d.options.texture}</Badge>}
          {d.options.face && <Badge>face · {d.options.face}</Badge>}
          {d.options.auto_repair && <Badge>hands · {d.options.auto_repair}</Badge>}
        </div>
      </Panel>
      {!!d.human_reviews.length && (
        <Panel className="p-5">
          <SectionTitle>Your decisions</SectionTitle>
          <ul className="grid gap-2 text-[12px]">
            {d.human_reviews.slice(-10).reverse().map((h, i) => (
              <li key={i} className="text-ink-2"><span className="font-mono text-ink-3">{h.time}</span> · {h.gate}: <b className="text-ink">{h.action}</b>{h.choice > 0 ? ` #${h.choice}` : ""}{h.notes ? ` · "${h.notes}"` : ""}</li>
            ))}
          </ul>
        </Panel>
      )}
    </div>
  );
}

export default function RunPage() {
  const { name = "" } = useParams(); const nav = useNavigate(); const inv = useInvalidate();
  const { data: d, error, isLoading } = useRun(name);
  const now = useClock(d);
  const [sel, setSel] = React.useState<string | null>(null);
  const [sp] = useSearchParams();
  const [tab, setTab] = React.useState(sp.get("tab") || "activity");
  React.useEffect(() => { const t = sp.get("tab"); if (t) setTab(t); }, [sp]);        // ?tab=animate opens a tab (the tour uses it)
  const [fork, setFork] = React.useState<{ stage?: string | null; look?: string } | null>(null);
  const [accept, setAccept] = React.useState(false);
  const [del, setDel] = React.useState(false);
  React.useEffect(() => { document.title = `${name} · Homunculus`; return () => { document.title = "Homunculus"; }; }, [name]);

  if (!d) return (
    <div className="mx-auto grid max-w-7xl place-items-center px-4 py-32 text-center">
      {isLoading || (error as any)?.status === 404 ? <div className="flex flex-col items-center gap-3 text-ink-3"><Spinner className="size-6" /><span className="text-[13px]">{(error as any)?.status === 404 ? "Waiting for the run to begin…" : "Loading…"}</span></div> : <span className="text-bad">{String(error)}</span>}
    </div>
  );

  const stages = effectiveStages(d.stages, d.review);
  const stop = async () => {
    if (!confirm(`Stop "${d.name}"?\nIt can be resumed later by starting the same name again.`)) return;
    try { await api.stop(d.name); toast(`Stopping ${d.name}…`); inv(["run", d.name], ["live"]); } catch (e: any) { toast.error(e.message); }
  };
  const compute = d.stages.reduce((n, s) => n + (s.seconds || 0), 0);
  const clock = d.t_total ? `took ${duration(Math.max(d.t_total, compute))}` : d.live && d.t_start ? `${duration(now - d.t_start)} elapsed` : "stopped";
  const mode = d.mode === "mesh" ? "3D model input" : d.options.direct ? "picture as is" : d.options.outfit;

  return (
    <div className="mx-auto max-w-[1600px] px-4 py-6 lg:px-6">
      <Link to="/" className="mb-4 inline-flex items-center gap-1.5 text-xs text-ink-3 hover:text-ink"><ArrowLeft className="size-3.5" /> All runs</Link>
      <header className="mb-5 flex flex-wrap items-center gap-4" data-tour="header">
        {d.input && <img src={d.input} className="size-14 rounded-xl border border-line object-cover" />}
        <div className="min-w-0 flex-1">
          <h1 className="truncate text-2xl font-semibold tracking-tight">{d.name}</h1>
          <div className="mt-1 flex flex-wrap items-center gap-x-3 gap-y-1 text-xs text-ink-3">
            <StatusPill status={d.status} />
            {d.repair && <Badge tone="accent">Repairing · {REPAIR_STEP[d.repair.step] ?? "working"}</Badge>}
            <span className="truncate">{d.file}</span><span>·</span><span>{mode}</span><span>·</span><span>review {d.options.review}</span><span>·</span><span className="font-mono">{clock}</span>
            {d.forked_from && <><span>·</span><span>forked from <Link className="text-ink-2 underline-offset-2 hover:underline" to={`/run/${encodeURIComponent(d.forked_from.run)}`}>{d.forked_from.run}</Link> at {d.forked_from.stage}</span></>}
          </div>
        </div>
        <div className="flex flex-wrap items-center gap-2">
          {d.live ? <Button variant="danger" onClick={stop}><Square /> Stop run</Button> : <Tip content="Restart from any stage with new instructions or options"><Button onClick={() => setFork({ stage: sel })}><GitFork /> Fork</Button></Tip>}
          {!d.live && d.package && <Button variant={d.accepted ? "secondary" : "success"} onClick={() => setAccept(true)}><PackageCheck /> {d.accepted ? `Accepted · ${d.accepted.formats.join(", ").toUpperCase()}` : "Accept"}</Button>}
          {d.package && <Tip content="The rigged model, textures and every animation clip in one zip"><a href={d.package} download><Button variant="ghost"><Package /> Package</Button></a></Tip>}
          {!d.live && <Tip content="Delete the run and everything made for it"><Button variant="ghost" size="icon" onClick={() => setDel(true)}><Trash2 /></Button></Tip>}
          {!!d.models.length && <Button variant="primary" onClick={() => setTab("model")}><Box /> View in 3D</Button>}
        </div>
      </header>

      {d.alert && (
        <div className="mb-4 flex items-start gap-3 rounded-xl border border-warn/35 bg-warn/8 px-4 py-3 text-[13px]">
          <AlertTriangle className="mt-0.5 size-4 shrink-0 text-warn" />
          <div><b className="text-warn">{d.live ? "Needs your attention" : "Why it stopped"}</b> <span className="text-ink-2">{d.alert.msg}</span> <span className="font-mono text-[11px] text-ink-3">{d.alert.time}</span></div>
        </div>
      )}

      <Panel className="mb-5 p-3"><Pipeline stages={stages} selected={sel} onSelect={(k) => { setSel(k); if (k) setTab("activity"); }} /></Panel>

      {d.review && <div className="mb-5"><ReviewPanel run={d.name} r={d.review} now={now} onInspect={() => setTab("model")} /></div>}

      <div className={cn("grid gap-5", tab === "repair" || tab === "retex" ? "" : "xl:grid-cols-[1fr_360px]")}>
        <Tabs value={tab} onValueChange={setTab} className="min-w-0">
          <TabsList className="mb-5 overflow-x-auto" data-tour="tabs">
            <TabsTrigger value="activity"><Images /> Activity</TabsTrigger>
            <TabsTrigger value="model"><Box /> 3D model</TabsTrigger>
            <TabsTrigger value="animate"><Clapperboard /> Animate{d.animations?.clips?.length ? <span className="ml-1 rounded-full bg-white/10 px-1.5 text-[10px]">{d.animations.clips.length}</span> : null}</TabsTrigger>
            <TabsTrigger value="looks"><Palette /> Looks</TabsTrigger>
            <TabsTrigger value="repair"><Wrench /> Repair</TabsTrigger>
            <TabsTrigger value="retex"><PaintBucket /> Retexture</TabsTrigger>
            <TabsTrigger value="log"><ScrollText /> Log</TabsTrigger>
          </TabsList>
          <TabsContent value="activity"><ActivityTab d={d} sel={sel} clearSel={() => setSel(null)} /></TabsContent>
          <TabsContent value="model"><ModelTab d={d} /></TabsContent>
          <TabsContent value="animate"><AnimateTab d={d} /></TabsContent>
          <TabsContent value="looks"><LooksTab d={d} onForkLook={(look) => setFork({ stage: "edit", look })} /></TabsContent>
          <TabsContent value="repair">{tab === "repair" && <RepairTab d={d} />}</TabsContent>
          <TabsContent value="retex">{tab === "retex" && <RetexTab d={d} />}</TabsContent>
          <TabsContent value="log"><LogTab lines={d.log} /></TabsContent>
        </Tabs>
        {!(tab === "repair" || tab === "retex") && <Inspector d={d} sel={sel} onFork={(stage) => setFork({ stage })} />}
      </div>

      {fork && <ForkDialog run={d.name} open onOpenChange={(v) => !v && setFork(null)} stage={fork.stage} look={fork.look} />}
      <AcceptDialog run={d.name} open={accept} onOpenChange={setAccept} />
      {del && <DeleteDialog run={d.name} open onOpenChange={(v) => !v && setDel(false)} onDone={() => nav("/")} />}
    </div>
  );
}
